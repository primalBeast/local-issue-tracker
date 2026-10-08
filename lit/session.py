"""In-memory registry of connected client event streams.

The next slice adds project claims and the SSE endpoint on top of this.
This run only tracks how many streams are open so ``--exit-when-idle`` can
stop the shared server after the last window goes away.
``stream_opened`` / ``stream_closed`` are reference-counted per client id.
"""

from __future__ import annotations

import threading
import time


class StreamRegistry:
    def __init__(self) -> None:
        self._guard = threading.Lock()
        self._counts: dict[str, int] = {}
        self._started = time.monotonic()
        self._idle_since: float | None = self._started
        self._ever = False

    def stream_opened(self, client_id: str) -> None:
        with self._guard:
            self._counts[client_id] = self._counts.get(client_id, 0) + 1
            self._ever = True
            self._idle_since = None

    def stream_closed(self, client_id: str) -> None:
        with self._guard:
            current = self._counts.get(client_id, 0)
            if current <= 1:
                self._counts.pop(client_id, None)
            else:
                self._counts[client_id] = current - 1
            if current > 0 and not self._counts:
                self._idle_since = time.monotonic()

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
            self._counts.clear()
            self._started = time.monotonic()
            self._idle_since = self._started
            self._ever = False

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


registry = StreamRegistry()
