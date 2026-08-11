from __future__ import annotations

from typing import Any

from fastapi import APIRouter

from lit.api.deps import require_project
from lit.storage.project_fs import load_deliverables, save_deliverables

router = APIRouter(prefix="/api/projects/{slug}/deliverables", tags=["deliverables"])


@router.get("")
def get_deliverables(slug: str) -> dict[str, Any]:
    require_project(slug)
    return load_deliverables(slug)


@router.put("")
def put_deliverables(slug: str, body: dict[str, Any]) -> dict[str, Any]:
    require_project(slug)
    data = {
        "schema_version": body.get("schema_version", 1),
        "items": body.get("items", []),
    }
    return save_deliverables(slug, data)
