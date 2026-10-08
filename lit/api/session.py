"""Project claims and the session event stream.

Windows subscribe with ``GET /api/session/events?client=<id>``. Each claims
change is pushed as an SSE ``claims`` event carrying the full snapshot.
A comment heartbeat every ``HEARTBEAT_SECONDS`` keeps the socket writable so
a killed window is noticed quickly. The grace timer (see ``lit.session``)
covers a dropped stream; an explicit release does not wait for it.
"""

from __future__ import annotations

import asyncio
import json
import time
from collections.abc import AsyncIterator
from typing import Any

from fastapi import APIRouter, Header, HTTPException, Request
from fastapi.responses import JSONResponse, StreamingResponse

from lit.api.deps import require_project
from lit.session import (
    heartbeat_seconds,
    registry,
    valid_client_id,
)

router = APIRouter(tags=["session"])


def _require_client(value: str | None) -> str:
    if not valid_client_id(value):
        raise HTTPException(status_code=400, detail="Invalid client id")
    return value


def _resolve_client(query: str | None, header: str | None) -> str:
    if query and header and query != header:
        raise HTTPException(status_code=400, detail="Client id mismatch")
    return _require_client(query or header)


def _sse(event: str, data: dict[str, Any]) -> str:
    body = json.dumps(data, separators=(",", ":"))
    return f"event: {event}\ndata: {body}\n\n"


async def _watch_disconnect(request: Request) -> None:
    """Block until the ASGI server reports the client is gone.

    ``Request.is_disconnected`` only peeks, and uvicorn's ``send`` returns
    without error after the socket closes. Reading ``http.disconnect`` is
    what actually ends the stream so the grace timer can start.
    """
    while True:
        message = await request.receive()
        if message["type"] == "http.disconnect":
            return


async def _cancel_task(task: asyncio.Task[Any]) -> None:
    if not task.done():
        task.cancel()
    try:
        await task
    except (asyncio.CancelledError, Exception):
        return


async def _next_stream_item(
    request: Request,
    queue: asyncio.Queue[dict[str, Any]],
    timeout: float,
) -> tuple[str, dict[str, Any] | None]:
    """Return ``("claims", payload)``, ``("hb", None)``, or ``("gone", None)``."""
    if await request.is_disconnected():
        return "gone", None
    getter: asyncio.Task[dict[str, Any]] = asyncio.create_task(queue.get())
    watcher: asyncio.Task[None] = asyncio.create_task(_watch_disconnect(request))
    try:
        done, _pending = await asyncio.wait(
            {getter, watcher},
            timeout=timeout,
            return_when=asyncio.FIRST_COMPLETED,
        )
    except asyncio.CancelledError:
        await _cancel_task(getter)
        await _cancel_task(watcher)
        raise
    if watcher in done and getter not in done:
        await _cancel_task(getter)
        # A clean finish is the disconnect message. Anything else is a bug
        # in the receive loop and must not look like a dropped window.
        watcher.result()
        return "gone", None
    if getter in done:
        await _cancel_task(watcher)
        return "claims", getter.result()
    await _cancel_task(getter)
    await _cancel_task(watcher)
    if await request.is_disconnected():
        return "gone", None
    return "hb", None


async def _event_stream(request: Request, client_id: str) -> AsyncIterator[str]:
    loop = asyncio.get_running_loop()
    queue: asyncio.Queue[dict[str, Any]] = asyncio.Queue()
    connected = False
    try:
        snapshot = registry.connect_stream(client_id, loop, queue)
        connected = True
        # ``retry`` is its own SSE field so EventSource reconnects quickly
        # after a reload or a server restart. The hello and the snapshot
        # follow immediately, before the first heartbeat wait.
        yield "retry: 500\n\n"
        yield _sse("hello", {"client": client_id})
        yield _sse("claims", {"claims": snapshot})
        next_hb = time.monotonic() + heartbeat_seconds()
        while True:
            timeout = max(0.0, next_hb - time.monotonic())
            kind, payload = await _next_stream_item(request, queue, timeout)
            if kind == "gone":
                break
            if kind == "hb":
                next_hb = time.monotonic() + heartbeat_seconds()
                yield ": hb\n\n"
                continue
            if payload is not None:
                yield _sse("claims", payload)
    except asyncio.CancelledError:
        raise
    finally:
        if connected:
            registry.disconnect_stream(client_id, queue)


@router.get("/api/session/events", response_model=None)
async def session_events(request: Request, client: str | None = None) -> StreamingResponse:
    client_id = _require_client(client)
    return StreamingResponse(
        _event_stream(request, client_id),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
        },
    )


@router.get("/api/session/claims")
def session_claims() -> dict[str, Any]:
    return {"claims": registry.claims_snapshot()}


@router.post("/api/session/release-all")
def session_release_all(
    client: str | None = None,
    x_lit_client: str | None = Header(default=None, alias="X-Lit-Client"),
) -> dict[str, Any]:
    """Release every project this client holds.

    The window-close path calls this with ``?client=`` and no Origin header.
    The header is accepted too. A mismatch between the two is a 400.
    """
    client_id = _resolve_client(client, x_lit_client)
    released = sorted(registry.release_all(client_id))
    return {"released": released}


@router.post("/api/projects/{slug}/claim", response_model=None)
def claim_project(
    slug: str,
    x_lit_client: str | None = Header(default=None, alias="X-Lit-Client"),
) -> dict[str, Any] | JSONResponse:
    client_id = _require_client(x_lit_client)
    require_project(slug)
    if not registry.claim(slug, client_id):
        return JSONResponse(
            status_code=409,
            content={
                "held_by_other": True,
                "detail": "Already open in another window",
            },
        )
    return {"slug": slug, "holder": client_id, "claims": registry.claims_snapshot()}


@router.post("/api/projects/{slug}/release")
def release_project(
    slug: str,
    x_lit_client: str | None = Header(default=None, alias="X-Lit-Client"),
) -> dict[str, Any]:
    client_id = _require_client(x_lit_client)
    return {"released": registry.release(slug, client_id)}
