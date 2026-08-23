from __future__ import annotations

from typing import Any

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from lit.paths import validate_slug
from lit.services.validation import ValidationError, validate_fields_schema
from lit.storage.settings_store import patch_settings
from lit.storage.template_store import (
    default_template_id,
    delete_user_template,
    list_templates,
    load_template_fields,
    save_project_as_template,
    save_template_fields,
)

router = APIRouter(prefix="/api/templates", tags=["templates"])


class TemplateSave(BaseModel):
    from_project: str
    id: str
    name: str | None = None
    set_default: bool = False
    include_layout: bool = True


class TemplateDefault(BaseModel):
    id: str = Field(min_length=1)


@router.get("")
def get_templates() -> dict[str, Any]:
    return {"default": default_template_id(), "templates": list_templates()}


@router.post("", status_code=201)
def create_template(body: TemplateSave) -> dict[str, Any]:
    try:
        validate_slug(body.from_project)
        validate_slug(body.id)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    try:
        return save_project_as_template(
            body.from_project,
            body.id,
            name=body.name,
            set_default=body.set_default,
            include_layout=body.include_layout,
        )
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail="Project not found") from None


@router.get("/{template_id}/fields")
def get_template_fields(template_id: str) -> dict[str, Any]:
    try:
        validate_slug(template_id)
        return load_template_fields(template_id)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail="Template not found") from None


@router.put("/{template_id}/fields")
def put_template_fields(template_id: str, body: dict[str, Any]) -> dict[str, Any]:
    try:
        validate_slug(template_id)
        data = validate_fields_schema(body)
        return save_template_fields(template_id, data)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail="Template not found") from None
    except ValidationError as e:
        raise HTTPException(status_code=422, detail=e.errors) from e


@router.post("/default")
def set_default_template(body: TemplateDefault) -> dict[str, Any]:
    try:
        validate_slug(body.id)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    ids = {t["id"] for t in list_templates()}
    if body.id not in ids:
        raise HTTPException(status_code=404, detail="Template not found")
    patch_settings({"default_template": body.id})
    return {"default": default_template_id(), "templates": list_templates()}


@router.delete("/{template_id}")
def remove_template(template_id: str) -> dict[str, str]:
    try:
        validate_slug(template_id)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    if not delete_user_template(template_id):
        raise HTTPException(status_code=404, detail="Template not found")
    return {"status": "deleted", "id": template_id}
