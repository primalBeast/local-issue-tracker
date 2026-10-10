"""Security headers, local Host/Origin checks, and optional dev CORS."""

from __future__ import annotations

from urllib.parse import SplitResult, urlsplit

from starlette.datastructures import Headers, MutableHeaders
from starlette.responses import JSONResponse
from starlette.types import ASGIApp, Message, Receive, Scope, Send

from lit.config import DEFAULT_VITE_PORT
from lit.security import MAX_BODY_BYTES

# Binds that do not name one client-facing host. Adding them would not make
# Host: 0.0.0.0 useful, and must not widen the allowlist to every name.
_UNSPECIFIED_HOSTS = frozenset({"", "0.0.0.0", "::", "[::]", "*"})
_STATE_CHANGING = frozenset({"POST", "PUT", "PATCH", "DELETE"})


def trusted_hostnames(configured_host: str | None) -> list[str]:
    """Bare hostnames trusted for the Host and Origin checks.

    Always includes ``127.0.0.1``, ``localhost``, and ``::1``. A specific
    ``configured_host`` (``lit serve --host <ip>``) is added too. Unspecified
    binds (``0.0.0.0``, ``::``, empty) are not.

    IPv6 is bare here (``::1``). ``trusted_host_header_values`` adds brackets
    because Starlette compares the parsed Host host-part with brackets kept
    (``[::1]``). A bare ``::1`` Host header is not valid and is rejected.
    """
    hosts = ["127.0.0.1", "localhost", "::1"]
    raw = (configured_host or "").strip()
    if raw.lower() in _UNSPECIFIED_HOSTS or "*" in raw:
        return hosts
    bare = raw[1:-1] if raw.startswith("[") and raw.endswith("]") else raw
    if bare.lower() in _UNSPECIFIED_HOSTS or any(ch in bare for ch in " /\\@?#*"):
        return hosts
    for candidate in (bare, bare.lower()):
        if candidate not in hosts:
            hosts.append(candidate)
    return hosts


def trusted_host_header_values(hostnames: list[str]) -> list[str]:
    """Patterns for TrustedHostMiddleware. IPv6 keeps its brackets."""
    values: list[str] = []
    for name in hostnames:
        if ":" in name and not (name.startswith("[") and name.endswith("]")):
            value = f"[{name}]"
        else:
            value = name
        if value not in values:
            values.append(value)
    return values


def _http_origin_port(parts: SplitResult) -> int | None:
    """Explicit port, or 80 when an http Origin omits it.

    ``http://127.0.0.1`` is port 80, so it matches only an app bound to 80.
    An unparsable port is rejected.
    """
    try:
        explicit = parts.port
    except ValueError:
        return None
    if explicit is not None:
        return explicit
    if parts.scheme.lower() == "http":
        return 80
    return None


def _scope_server_port(scope: Scope) -> int:
    """Listening port from the ASGI server address, or 0 when it is unknown.

    uvicorn fills this after the socket binds, including when ``--port 0``
    asks the OS for a free port.
    """
    server = scope.get("server")
    if isinstance(server, (tuple, list)) and len(server) >= 2 and isinstance(server[1], int):
        port = int(server[1])
        if 0 < port <= 65535:
            return port
    return 0


def _is_trusted_origin(origin: str, allowed_hosts: set[str], allowed_ports: set[int]) -> bool:
    """True when Origin is http, the hostname is trusted, and the port is allowed.

    The app serves plain HTTP on its bound port. ``https`` is rejected: this
    process never terminates TLS, so an https Origin is not this app. A missing
    port is 80. When dev CORS is on, ``allowed_ports`` also contains the Vite
    port. ``Origin: null`` is not trusted. Userinfo, a path, a query, or a
    fragment is not a browser Origin and is rejected so
    ``http://evil@127.0.0.1`` cannot borrow the loopback name.
    """
    if not allowed_ports:
        return False
    if origin.strip().lower() == "null":
        return False
    parts = urlsplit(origin.strip())
    if parts.username is not None or parts.password is not None:
        return False
    if parts.scheme.lower() != "http":
        return False
    host = parts.hostname
    if host is None or host.lower() not in allowed_hosts:
        return False
    if parts.path not in {"", "/"} or parts.query or parts.fragment:
        return False
    port = _http_origin_port(parts)
    return port is not None and port in allowed_ports


# Pure ASGI, not BaseHTTPMiddleware. BaseHTTPMiddleware wraps the response
# body in a memory stream and hides client disconnects from SSE handlers.
_CSP = (
    "default-src 'self'; "
    "script-src 'self'; "
    "style-src 'self' 'unsafe-inline'; "
    "img-src 'self' data: blob:; "
    "media-src 'self' blob:; "
    "font-src 'self' data:; "
    "connect-src 'self'; "
    "object-src 'none'; "
    "frame-src 'none'; "
    "frame-ancestors 'none'; "
    "base-uri 'self'; "
    "form-action 'self'"
)


def _json_body_or_empty(headers: Headers) -> bool:
    """True when there is no body, or the body is declared as JSON."""
    raw_len = headers.get("content-length")
    if raw_len is None or raw_len.strip() in {"", "0"}:
        return True
    ctype = (headers.get("content-type") or "").split(";", 1)[0].strip().lower()
    return ctype == "application/json"


class BodyLimitMiddleware:
    """Reject a body larger than ``max_bytes`` before the route reads it.

    A declared ``Content-Length`` over the cap is refused immediately. A
    request that omits the length (chunked transfer) is counted as it arrives
    and refused the same way, so leaving the header off is not a bypass.
    """

    def __init__(self, app: ASGIApp, max_bytes: int = MAX_BODY_BYTES) -> None:
        self.app = app
        self.max_bytes = int(max_bytes)

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return
        raw_len = Headers(scope=scope).get("content-length")
        if raw_len is not None and raw_len.strip() != "":
            try:
                size = int(raw_len)
            except ValueError:
                response = JSONResponse({"detail": "Bad content length"}, status_code=400)
                await response(scope, receive, send)
                return
            if size < 0 or size > self.max_bytes:
                response = JSONResponse({"detail": "Request body is too large"}, status_code=413)
                await response(scope, receive, send)
                return
            await self.app(scope, receive, send)
            return

        chunks: list[bytes] = []
        total = 0
        pending: Message | None = None
        # A client can omit Content-Length and drip empty chunks. Cap the
        # number of messages so that cannot spin the process.
        for _ in range(10_000):
            message = await receive()
            if message["type"] != "http.request":
                pending = message
                break
            chunk = message.get("body") or b""
            total += len(chunk)
            if total > self.max_bytes:
                response = JSONResponse({"detail": "Request body is too large"}, status_code=413)
                await response(scope, receive, send)
                return
            if chunk:
                chunks.append(chunk)
            if not message.get("more_body", False):
                break
        else:
            response = JSONResponse({"detail": "Request body is too large"}, status_code=413)
            await response(scope, receive, send)
            return
        body = b"".join(chunks)
        sent_body = False

        async def replay() -> Message:
            nonlocal sent_body, pending
            if not sent_body:
                sent_body = True
                return {"type": "http.request", "body": body, "more_body": False}
            if pending is not None:
                message = pending
                pending = None
                return message
            return await receive()

        await self.app(scope, replay, send)


class OriginCheckMiddleware:
    """Block cross-site state changes against the local API.

    POST, PUT, PATCH, and DELETE are rejected with 403 when:

    - ``Origin`` is present and is not a trusted local origin, or
    - ``Sec-Fetch-Site: cross-site`` is set and there is no trusted Origin.

    A trusted origin is ``http`` (not ``https``), a hostname in the trusted
    host set (``127.0.0.1``, ``localhost``, ``::1``, plus a specific
    ``cfg.host``), and a port equal to the app's bound port. A missing port is
    80, so ``http://127.0.0.1`` is trusted only when the app listens on 80.
    ``https`` is not this server. ``Origin: null`` is foreign.

    The bound port is ``cfg.port``. ``lit serve`` and ``--port`` set it before
    ``create_app``, and the detached ``--webview`` server is spawned with that
    same ``--port``. Startup copies it to settings ``last_port``; this check
    does not read settings back. ``--port 0`` is resolved from the listening
    socket after the OS assigns one.

    When dev CORS is on, the Vite port (``cfg.vite_port``, default 5173,
    ``LIT_VITE_PORT``) is allowed on the same hosts. A trusted Origin is still
    accepted when ``Sec-Fetch-Site`` is ``cross-site`` (a page on
    ``localhost`` calling an API on ``127.0.0.1``, or Vite calling the API).
    Requests with no Origin header are allowed (pywebview, curl, local
    scripts) unless they are marked cross-site.

    GET, HEAD, and OPTIONS skip this check. The Host check stays
    hostname-only and still applies.
    """

    def __init__(
        self,
        app: ASGIApp,
        allowed_hosts: list[str],
        *,
        port: int,
        extra_ports: list[int] | None = None,
    ) -> None:
        self.app = app
        self.allowed_hosts = {host.lower() for host in allowed_hosts}
        self.configured_port = int(port)
        self.extra_ports = {int(item) for item in (extra_ports or []) if 0 < int(item) <= 65535}

    def _allowed_ports(self, scope: Scope) -> set[int]:
        ports = set(self.extra_ports)
        bound = self.configured_port
        if bound == 0:
            bound = _scope_server_port(scope)
        if 0 < bound <= 65535:
            ports.add(bound)
        return ports

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return
        if scope.get("method", "GET").upper() not in _STATE_CHANGING:
            await self.app(scope, receive, send)
            return
        headers = Headers(scope=scope)
        origin = headers.get("origin")
        trusted = origin is not None and _is_trusted_origin(
            origin, self.allowed_hosts, self._allowed_ports(scope)
        )
        if origin is not None and not trusted:
            response = JSONResponse({"detail": "Foreign origin blocked"}, status_code=403)
            await response(scope, receive, send)
            return
        sec_fetch = (headers.get("sec-fetch-site") or "").strip().lower()
        if sec_fetch == "cross-site" and not trusted:
            response = JSONResponse({"detail": "Cross-site request blocked"}, status_code=403)
            await response(scope, receive, send)
            return
        # HTML forms and "simple" fetches cannot set application/json. Requiring
        # it whenever a body is present blocks those without breaking curl,
        # the CLI, or the SPA, which already send JSON.
        if not _json_body_or_empty(headers):
            response = JSONResponse(
                {"detail": "State-changing requests must send application/json"},
                status_code=415,
            )
            await response(scope, receive, send)
            return
        await self.app(scope, receive, send)


class SecurityHeadersMiddleware:
    def __init__(self, app: ASGIApp) -> None:
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return
        path = scope.get("path") or ""

        async def send_with_headers(message: Message) -> None:
            if message["type"] == "http.response.start":
                message.setdefault("headers", [])
                headers = MutableHeaders(scope=message)
                headers.setdefault("X-Content-Type-Options", "nosniff")
                headers.setdefault("X-Frame-Options", "DENY")
                headers.setdefault("Referrer-Policy", "no-referrer")
                headers.setdefault("Cross-Origin-Opener-Policy", "same-origin")
                headers.setdefault("Cross-Origin-Resource-Policy", "same-origin")
                headers.setdefault("X-Permitted-Cross-Domain-Policies", "none")
                headers.setdefault(
                    "Permissions-Policy",
                    "camera=(), microphone=(), geolocation=(), payment=()",
                )
                # CSP: local app — allow self, inline styles for Svelte, data images
                headers.setdefault("Content-Security-Policy", _CSP)
                if path.startswith("/assets/"):
                    # Hashed filenames — safe to cache forever once fetched
                    headers.setdefault(
                        "Cache-Control", "public, max-age=31536000, immutable"
                    )
                elif path in ("/", "/index.html") or path.endswith(".html") or path == "":
                    # Always revalidate the shell so clients pick up new asset hashes
                    headers["Cache-Control"] = "no-store, no-cache, must-revalidate, max-age=0"
                    headers["Pragma"] = "no-cache"
                    headers["Expires"] = "0"
            await send(message)

        await self.app(scope, receive, send_with_headers)


def dev_cors_origins(vite_port: int) -> list[str]:
    """Browser origins for the Vite dev server. Same port the origin check allows."""
    port = int(vite_port)
    return [f"http://localhost:{port}", f"http://127.0.0.1:{port}"]


def install_cors(app: ASGIApp, enabled: bool, *, vite_port: int = DEFAULT_VITE_PORT) -> None:
    if not enabled:
        return
    from fastapi.middleware.cors import CORSMiddleware

    # app is FastAPI
    app.add_middleware(  # type: ignore[attr-defined]
        CORSMiddleware,
        allow_origins=dev_cors_origins(vite_port),
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
