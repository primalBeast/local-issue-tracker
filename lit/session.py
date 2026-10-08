"""In-memory client streams and per-project claims.

One server process owns the data directory. Every window is a client of that
server, so the claims live here and are pushed over the session event stream.
The OS lock in ``lit.locking`` only guarantees there is one such process.

``stream_opened`` / ``stream_closed`` stay reference-counted per client id.
``--exit-when-idle`` reads ``active_streams`` / ``idle_since`` and does not
care about claims.

A claim held by a client that never opened a stream (a curl claim, a script)
is not auto-released. The grace timer starts only when that client's last
event stream closes. Reconnecting with the same id before the timer fires
keeps the claims and does not broadcast, so other windows never see the
project as free across a reload.
"""

from __future__ import annotations

import asyncio
import os
import re
import threading
import time
from dataclasses import dataclass
from typing import Any

# SSE comment interval. ``LIT_SSE_HEARTBEAT_SECONDS`` overrides it in tests.
HEARTBEAT_SECONDS = 1.0
# How long a dropped stream keeps its claims. Reload reconnects inside this.
# ``LIT_CLAIM_GRACE_SECONDS`` overrides it in tests. A normal close releases
# explicitly and does not wait for this timer.
GRACE_SECONDS = 1.5

CLIENT_ID_RE = re.compile(r"^[A-Za-z0-9_-]{8,64}$")


def valid_client_id(value: str | None) -> bool:
    """True for ids the event stream and claim routes accept.

    A uuid (36 chars, hyphens) fits. Short or punctuated values do not.
    """
    return isinstance(value, str) and CLIENT_ID_RE.fullmatch(value) is not None


def _env_seconds(name: str, default: float) -> float:
    raw = os.environ.get(name)
    if raw is None or not str(raw).strip():
        return default
    try:
        value = float(raw)
    except ValueError:
        return default
    if value <= 0:
        return default
    return value


def heartbeat_seconds() -> float:
    return _env_seconds("LIT_SSE_HEARTBEAT_SECONDS", HEARTBEAT_SECONDS)


def grace_seconds() -> float:
    return _env_seconds("LIT_CLAIM_GRACE_SECONDS", GRACE_SECONDS)


@dataclass
class _Sub:
    client_id: str
    loop: asyncio.AbstractEventLoop
    queue: asyncio.Queue[dict[str, Any]]


class StreamRegistry:
    def __init__(self) -> None:
        self._guard = threading.Lock()
        self._counts: dict[str, int] = {}
        self._started = time.monotonic()
        self._idle_since: float | None = self._started
        self._ever = False
        self._claims: dict[str, str] = {}
        self._subs: list[_Sub] = []
        self._grace: dict[str, threading.Timer] = {}
        self._grace_token: dict[str, int] = {}
        self._epoch = 0

    def stream_opened(self, client_id: str) -> None:
        with self._guard:
            self._open_locked(client_id)

    def stream_closed(self, client_id: str) -> None:
        with self._guard:
            self._close_locked(client_id)

    def connect_stream(
        self,
        client_id: str,
        loop: asyncio.AbstractEventLoop,
        queue: asyncio.Queue[dict[str, Any]],
    ) -> dict[str, str]:
        """Register a stream and return the current claims snapshot.

        Opening a stream cancels a pending grace timer for this client, so a
        reload that reconnects in time keeps its projects. The snapshot is
        what the new stream sends first; later changes arrive on ``queue``.
        """
        with self._guard:
            self._open_locked(client_id)
            self._subs.append(_Sub(client_id, loop, queue))
            return dict(self._claims)

    def disconnect_stream(self, client_id: str, queue: asyncio.Queue[dict[str, Any]]) -> None:
        """Drop one stream. The last stream for a client starts the grace timer."""
        with self._guard:
            self._subs = [sub for sub in self._subs if sub.queue is not queue]
            self._close_locked(client_id)

    def active_streams(self) -> int:
        with self._guard:
            return sum(self._counts.values())

    def idle_since(self) -> float | None:
        """Monotonic time when the stream count last dropped to 0.

        Startup time if no stream has connected yet. None while a stream is open.
        """
        with self._guard:
            return self._idle_since

    def ever_connected(self) -> bool:
        with self._guard:
            return self._ever

    def reset(self) -> None:
        with self._guard:
            timers = list(self._grace.values())
            self._grace.clear()
            self._grace_token.clear()
            self._epoch += 1
            self._counts.clear()
            self._claims.clear()
            self._subs.clear()
            self._started = time.monotonic()
            self._idle_since = self._started
            self._ever = False
        for timer in timers:
            timer.cancel()

    def idle_exit_due(
        self,
        *,
        startup_seconds: float,
        idle_seconds: float,
        now: float | None = None,
    ) -> bool:
        """Whether the idle server should exit.

        No stream has ever connected: due ``startup_seconds`` after startup.
        The last stream disconnected: due ``idle_seconds`` after that moment.
        """
        with self._guard:
            if self._counts:
                return False
            since = self._idle_since if self._idle_since is not None else self._started
            limit = idle_seconds if self._ever else startup_seconds
        moment = time.monotonic() if now is None else now
        return (moment - since) >= limit

    def holder(self, slug: str) -> str | None:
        with self._guard:
            return self._claims.get(slug)

    def claims_snapshot(self) -> dict[str, str]:
        with self._guard:
            return dict(self._claims)

    def claim(self, slug: str, client_id: str) -> bool:
        """Claim ``slug`` for ``client_id``.

        True when it was free or already ours. False when another client holds
        it. A new claim is broadcast immediately. Re-claiming our own project
        is not a change and does not broadcast.
        """
        with self._guard:
            holder = self._claims.get(slug)
            if holder is not None and holder != client_id:
                return False
            changed = holder != client_id
            self._claims[slug] = client_id
            fanout = self._capture_locked() if changed else None
        self._fanout(fanout)
        return True

    def release(self, slug: str, client_id: str) -> bool:
        """Release ``slug`` if ``client_id`` holds it. Broadcasts on success.

        When that was the client's last claim, a pending grace timer is
        cancelled so it cannot broadcast again. Other claims of the same
        client stay under the existing timer.
        """
        with self._guard:
            if self._claims.get(slug) != client_id:
                return False
            del self._claims[slug]
            if not any(holder == client_id for holder in self._claims.values()):
                self._cancel_grace_locked(client_id)
            fanout = self._capture_locked()
        self._fanout(fanout)
        return True

    def release_all(self, client_id: str) -> list[str]:
        """Release every project ``client_id`` holds and cancel its grace timer.

        Returns the released slugs. Broadcasts once when anything changed.
        """
        with self._guard:
            self._cancel_grace_locked(client_id)
            released = [slug for slug, holder in self._claims.items() if holder == client_id]
            for slug in released:
                del self._claims[slug]
            fanout = self._capture_locked() if released else None
        self._fanout(fanout)
        return released

    def _open_locked(self, client_id: str) -> None:
        self._counts[client_id] = self._counts.get(client_id, 0) + 1
        self._ever = True
        self._idle_since = None
        self._cancel_grace_locked(client_id)

    def _close_locked(self, client_id: str) -> None:
        current = self._counts.get(client_id, 0)
        if current <= 1:
            self._counts.pop(client_id, None)
        else:
            self._counts[client_id] = current - 1
        if current > 0 and not self._counts:
            self._idle_since = time.monotonic()
        # Last stream for this client. A client that never connected is not
        # armed here, so a header-only claim stays until an explicit release.
        if current > 0 and self._counts.get(client_id, 0) == 0:
            self._arm_grace_locked(client_id)

    def _capture_locked(self) -> tuple[dict[str, Any], list[_Sub]]:
        return {"claims": dict(self._claims)}, list(self._subs)

    def _fanout(self, captured: tuple[dict[str, Any], list[_Sub]] | None) -> None:
        """Schedule a snapshot onto each stream. Never waits on the loop."""
        if not captured:
            return
        payload, subs = captured
        for sub in subs:
            self._enqueue(sub, payload)

    def _enqueue(self, sub: _Sub, payload: dict[str, Any]) -> None:
        loop = sub.loop
        queue = sub.queue

        def _put() -> None:
            try:
                queue.put_nowait(payload)
            except asyncio.QueueFull:
                return

        try:
            if not loop.is_running():
                return
            loop.call_soon_threadsafe(_put)
        except RuntimeError:
            # Loop is closed. The stream is going away with the process.
            return

    def _cancel_grace_locked(self, client_id: str) -> None:
        timer = self._grace.pop(client_id, None)
        self._grace_token[client_id] = self._grace_token.get(client_id, 0) + 1
        if timer is not None:
            timer.cancel()

    def _arm_grace_locked(self, client_id: str) -> None:
        self._cancel_grace_locked(client_id)
        token = self._grace_token.get(client_id, 0)
        epoch = self._epoch
        timer = threading.Timer(
            grace_seconds(),
            self._on_grace,
            args=(client_id, token, epoch),
        )
        timer.daemon = True
        self._grace[client_id] = timer
        timer.start()

    def _on_grace(self, client_id: str, token: int, epoch: int) -> None:
        with self._guard:
            if epoch != self._epoch or self._grace_token.get(client_id) != token:
                return
            if self._counts.get(client_id, 0) > 0:
                return
            self._grace.pop(client_id, None)
            released = [slug for slug, holder in self._claims.items() if holder == client_id]
            if not released:
                return
            for slug in released:
                del self._claims[slug]
            fanout = self._capture_locked()
        self._fanout(fanout)


registry = StreamRegistry()
