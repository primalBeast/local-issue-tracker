from __future__ import annotations

from typing import Any

from fastapi import APIRouter, HTTPException

from lit.api.deps import require_project
from lit.services.validation import ValidationError, validate_fields_schema
from lit.storage.project_fs import load_fields, save_fields

router = APIRouter(prefix="/api/projects/{slug}/fields", tags=["fields"])


@router.get("")
def get_fields(slug: str) -> dict[str, Any]:
    require_project(slug)
    return load_fields(slug)


@router.put("")
def put_fields(slug: str, body: dict[str, Any]) -> dict[str, Any]:
    require_project(slug)
    try:
        data = validate_fields_schema(body)
    except ValidationError as e:
        raise HTTPException(status_code=422, detail=e.errors) from e
    return save_fields(slug, data)
