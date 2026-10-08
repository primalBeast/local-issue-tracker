"""Shared FastAPI dependencies."""

from __future__ import annotations

from pathlib import Path

from fastapi import Header, HTTPException

from lit.paths import project_dir, validate_slug
from lit.session import registry
from lit.storage import items_db
from lit.storage.project_fs import load_fields, load_project


def require_writable(
    slug: str,
    x_lit_client: str | None = Header(default=None, alias="X-Lit-Client"),
) -> None:
    """423 when another window holds ``slug``. Memory only, no disk.

    An unclaimed project stays writable with no client header, so curl and
    scripts keep working. A claimed project requires the holder's header.
    Attach this on state-changing project routes so it runs before the handler.
    """
    holder = registry.holder(slug)
    if holder is None:
        return
    if x_lit_client != holder:
        raise HTTPException(status_code=423, detail="Project is open in another window")


def require_project(slug: str) -> Path:
    try:
        validate_slug(slug)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    path = project_dir(slug)
    if not path.exists() or not (path / "project.json").exists():
        raise HTTPException(status_code=404, detail=f"Project not found: {slug}")
    return path


def project_meta(slug: str) -> dict:
    require_project(slug)
    return load_project(slug)


def project_fields(slug: str) -> dict:
    require_project(slug)
    return load_fields(slug)


def db_path_for(slug: str) -> Path:
    return items_db.items_db_path(require_project(slug))
