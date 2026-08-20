from __future__ import annotations

import logging
import os
import platform
import subprocess
from pathlib import Path
from typing import Any

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from lit.paths import project_dir, validate_slug
from lit.storage.project_fs import (
    create_project,
    delete_project,
    list_project_slugs,
    load_project,
    save_project,
)
from lit.storage.settings_store import patch_settings

logger = logging.getLogger("lit.projects")
router = APIRouter(prefix="/api/projects", tags=["projects"])


class ProjectCreate(BaseModel):
    slug: str
    name: str | None = None
    template: str = "issue-tracker"
    ticket_prefix: str | None = None


class ProjectPatch(BaseModel):
    name: str | None = None
    waiting_state_value: str | None = None
    color_coding: dict[str, Any] | None = None
    primary_identifier_field: str | None = None
    compact_mode_zoom_threshold: float | None = None
    ticket_prefix: str | None = None


class ProjectDelete(BaseModel):
    confirm_slug: str


def reveal_folder(path: Path) -> None:
    """Open a folder in Explorer / Finder / the desktop file manager."""
    path = path.resolve()
    if not path.is_dir():
        raise FileNotFoundError(path)
    target = os.fsdecode(path)
    system = platform.system()
    logger.info("Opening project folder %s", target)
    if system == "Windows":
        # /n, always opens a new Explorer window. os.startfile() and the
        # "explore" verb often reuse a hidden/minimized window and look like a no-op.
        subprocess.Popen(["explorer.exe", "/n,", target], close_fds=False)
        return
    if system == "Darwin":
        subprocess.Popen(["open", target])
        return
    subprocess.Popen(["xdg-open", target])


@router.get("")
def list_projects() -> list[dict[str, Any]]:
    return [load_project(s) for s in list_project_slugs()]


@router.post("", status_code=201)
def create(body: ProjectCreate) -> dict[str, Any]:
    try:
        validate_slug(body.slug)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    try:
        proj = create_project(
            body.slug,
            name=body.name,
            template=body.template,
            ticket_prefix=body.ticket_prefix,
        )
    except FileExistsError:
        raise HTTPException(status_code=409, detail="Project already exists") from None
    except FileNotFoundError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    patch_settings({"last_project_slug": body.slug})
    return proj


@router.get("/{slug}")
def get_project(slug: str) -> dict[str, Any]:
    try:
        return load_project(slug)
    except (FileNotFoundError, ValueError):
        raise HTTPException(status_code=404, detail="Project not found") from None


@router.post("/{slug}/open-folder")
def open_project_folder(slug: str) -> dict[str, str]:
    try:
        load_project(slug)
        dest = project_dir(slug)
    except (FileNotFoundError, ValueError):
        raise HTTPException(status_code=404, detail="Project not found") from None
    if not dest.is_dir():
        raise HTTPException(status_code=404, detail="Project folder not found")
    try:
        reveal_folder(dest)
    except OSError as e:
        raise HTTPException(status_code=500, detail=f"Could not open folder: {e}") from e
    return {"status": "opened", "path": str(dest)}


@router.patch("/{slug}")
def patch_project(slug: str, body: ProjectPatch) -> dict[str, Any]:
    try:
        proj = load_project(slug)
    except (FileNotFoundError, ValueError):
        raise HTTPException(status_code=404, detail="Project not found") from None
    updates = body.model_dump(exclude_unset=True)
    proj.update(updates)
    return save_project(slug, proj)


@router.delete("/{slug}")
def remove_project(slug: str, body: ProjectDelete) -> dict[str, str]:
    try:
        delete_project(slug, body.confirm_slug)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail="Project not found") from None
    return {"status": "deleted", "slug": slug}
