"""FastAPI application factory."""

from __future__ import annotations

import logging
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.responses import FileResponse, HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

from lit import __version__
from lit.api import backups, deliverables, fields, items, notes, projects, settings, templates, workspaces
from lit.config import get_config
from lit.middleware import SecurityHeadersMiddleware, install_cors

logger = logging.getLogger("lit.app")


def frontend_dist() -> Path:
    # package-relative: prefer repo frontend/dist when developing
    here = Path(__file__).resolve()
    # lit/app.py → parents[1] is repo root (package is at ./lit)
    candidates = [
        here.parents[1] / "frontend" / "dist",
        here.parent / "static",
    ]
    for c in candidates:
        if (c / "index.html").exists():
            return c
    return candidates[0]


def create_app() -> FastAPI:
    cfg = get_config()
    app = FastAPI(
        title="Local Issue Tracker",
        version=__version__,
        docs_url="/api/docs",
        redoc_url=None,
    )

    install_cors(app, enabled=cfg.dev_cors)
    app.add_middleware(SecurityHeadersMiddleware)

    @app.get("/health")
    def health() -> dict:
        return {"status": "ok", "version": __version__}

    app.include_router(settings.router)
    app.include_router(projects.router)
    app.include_router(fields.router)
    app.include_router(items.router)
    app.include_router(workspaces.router)
    app.include_router(notes.router)
    app.include_router(deliverables.router)
    app.include_router(templates.router)
    app.include_router(backups.router)

    dist = frontend_dist()
    assets = dist / "assets"
    if assets.is_dir():
        app.mount("/assets", StaticFiles(directory=str(assets)), name="assets")

    @app.get("/favicon.ico")
    def favicon():
        fav = dist / "favicon.ico"
        if fav.exists():
            return FileResponse(fav)
        return JSONResponse({"detail": "not found"}, status_code=404)

    @app.get("/{full_path:path}")
    def spa_fallback(full_path: str, request: Request):
        if full_path.startswith("api"):
            return JSONResponse({"detail": "Not Found"}, status_code=404)
        # known static root files
        candidate = dist / full_path
        if full_path and candidate.is_file() and dist in candidate.resolve().parents:
            return FileResponse(candidate)
        index = dist / "index.html"
        if not index.exists():
            return HTMLResponse(
                "<!doctype html><html><body style='font-family:system-ui;background:#0f1115;color:#e8eaed;padding:2rem'>"
                "<h1>Local Issue Tracker</h1>"
                "<p>Frontend build missing. Run <code>cd frontend && npm ci && npm run build</code> "
                "or restore committed <code>frontend/dist</code>.</p>"
                f"<p>API is up — try <a href='/health' style='color:#7dd3fc'>/health</a>.</p>"
                "</body></html>",
                status_code=503,
            )
        return FileResponse(index)

    return app
