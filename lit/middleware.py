"""Security headers, local Host/Origin checks, and optional dev CORS."""

from __future__ import annotations

from urllib.parse import urlsplit

from starlette.datastructures import Headers, MutableHeaders
from starlette.responses import JSONResponse
from starlette.types import ASGIApp, Message, Receive, Scope, Send

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


def _is_trusted_origin(origin: str, allowed_hosts: set[str]) -> bool:
    """True when Origin is http(s) and its hostname is in ``allowed_hosts``.

    The port is ignored, so the app (``127.0.0.1:8765``) and the Vite dev
    server (``localhost:5173``) are both accepted. ``Origin: null`` is not.
    Userinfo, a path, a query, or a fragment is not a browser Origin and is
    rejected so ``http://evil@127.0.0.1`` cannot borrow the loopback name.
    """
    if origin.strip().lower() == "null":
        return False
    parts = urlsplit(origin.strip())
    if parts.username is not None or parts.password is not None:
        return False
    if parts.scheme not in {"http", "https"}:
        return False
    host = parts.hostname
    if host is None or host.lower() not in allowed_hosts:
        return False
    if parts.path not in {"", "/"} or parts.query or parts.fragment:
        return False
    return True


# Pure ASGI, not BaseHTTPMiddleware. BaseHTTPMiddleware wraps the response
# body in a memory stream and hides client disconnects from SSE handlers.
_CSP = (
    "default-src 'self'; "
    "script-src 'self'; "
    "style-src 'self' 'unsafe-inline'; "
    "img-src 'self' data: blob:; "
    "font-src 'self' data:; "
    "connect-src 'self'; "
    "frame-ancestors 'none'; "
    "base-uri 'self'; "
    "form-action 'self'"
)


class OriginCheckMiddleware:
    """Block cross-site state changes against the local API.

    POST, PUT, PATCH, and DELETE are rejected with 403 when:

    - ``Origin`` is present and is not a trusted local origin, or
    - ``Sec-Fetch-Site: cross-site`` is set and there is no trusted Origin.

    A trusted origin is an http(s) URL whose hostname is in the trusted host
    set (``127.0.0.1``, ``localhost``, ``::1``, plus a specific ``cfg.host``).
    Any port on those hosts is accepted. ``Origin: null`` is foreign.

    A trusted Origin is still accepted when ``Sec-Fetch-Site`` is ``cross-site``.
    That is the Vite dev case: the page is ``http://localhost:5173`` and the
    API is ``http://127.0.0.1:8765``. Requests with no Origin header are
    allowed (pywebview, curl, local scripts) unless they are marked cross-site.

    GET, HEAD, and OPTIONS skip this check. The Host check still applies.
    """

    def __init__(self, app: ASGIApp, allowed_hosts: list[str]) -> None:
        self.app = app
        self.allowed_hosts = {host.lower() for host in allowed_hosts}

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return
        if scope.get("method", "GET").upper() not in _STATE_CHANGING:
            await self.app(scope, receive, send)
            return
        headers = Headers(scope=scope)
        origin = headers.get("origin")
        trusted = origin is not None and _is_trusted_origin(origin, self.allowed_hosts)
        if origin is not None and not trusted:
            response = JSONResponse({"detail": "Foreign origin blocked"}, status_code=403)
            await response(scope, receive, send)
            return
        sec_fetch = (headers.get("sec-fetch-site") or "").strip().lower()
        if sec_fetch == "cross-site" and not trusted:
            response = JSONResponse({"detail": "Cross-site request blocked"}, status_code=403)
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


def install_cors(app: ASGIApp, enabled: bool) -> None:
    if not enabled:
        return
    from fastapi.middleware.cors import CORSMiddleware

    # app is FastAPI
    app.add_middleware(  # type: ignore[attr-defined]
        CORSMiddleware,
        allow_origins=[
            "http://localhost:5173",
            "http://127.0.0.1:5173",
        ],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
