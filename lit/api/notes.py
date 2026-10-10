from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, HTTPException

from lit.api.deps import require_project, require_writable
from lit.storage.project_fs import load_notes, save_notes

router = APIRouter(prefix="/api/projects/{slug}/notes", tags=["notes"])


@router.get("")
def get_notes(slug: str) -> dict[str, Any]:
    require_project(slug)
    return load_notes(slug)


@router.put("", dependencies=[Depends(require_writable)])
def put_notes(slug: str, body: dict[str, Any]) -> dict[str, Any]:
    require_project(slug)
    content = body.get("content", {"type": "doc", "content": []})
    if not isinstance(content, dict) or content.get("type") != "doc":
        raise HTTPException(status_code=422, detail="Notes must be a document")
    data = {
        "schema_version": 1,
        "content": content,
    }
    return save_notes(slug, data)
