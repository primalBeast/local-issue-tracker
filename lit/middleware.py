"""Security headers and optional dev CORS."""

from __future__ import annotations

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response
from starlette.types import ASGIApp


class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next) -> Response:
        response = await call_next(request)
        response.headers.setdefault("X-Content-Type-Options", "nosniff")
        response.headers.setdefault("X-Frame-Options", "DENY")
        response.headers.setdefault("Referrer-Policy", "no-referrer")
        # CSP: local app — allow self, inline styles for Svelte, data images
        response.headers.setdefault(
            "Content-Security-Policy",
            "default-src 'self'; "
            "script-src 'self'; "
            "style-src 'self' 'unsafe-inline'; "
            "img-src 'self' data: blob:; "
            "font-src 'self' data:; "
            "connect-src 'self'; "
            "frame-ancestors 'none'; "
            "base-uri 'self'; "
            "form-action 'self'",
        )
        path = request.url.path
        if path.startswith("/assets/"):
            # Hashed filenames — safe to cache forever once fetched
            response.headers.setdefault(
                "Cache-Control", "public, max-age=31536000, immutable"
            )
        elif path in ("/", "/index.html") or path.endswith(".html") or path == "":
            # Always revalidate the shell so clients pick up new asset hashes
            response.headers["Cache-Control"] = "no-store, no-cache, must-revalidate, max-age=0"
            response.headers["Pragma"] = "no-cache"
            response.headers["Expires"] = "0"
        return response


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
