from __future__ import annotations

from typing import Any

from fastapi import APIRouter

from lit.api.deps import require_project
from lit.storage.project_fs import load_notes, save_notes

router = APIRouter(prefix="/api/projects/{slug}/notes", tags=["notes"])


@router.get("")
def get_notes(slug: str) -> dict[str, Any]:
    require_project(slug)
    return load_notes(slug)


@router.put("")
def put_notes(slug: str, body: dict[str, Any]) -> dict[str, Any]:
    require_project(slug)
    data = {
        "schema_version": body.get("schema_version", 1),
        "content": body.get("content", {"type": "doc", "content": []}),
    }
    return save_notes(slug, data)
