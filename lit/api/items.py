from __future__ import annotations

import json
import logging
from typing import Any

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from lit.api.deps import db_path_for, project_meta, require_project
from lit.services.validation import (
    ValidationError,
    apply_defaults,
    validate_item_fields,
)
from lit.services.waiting import apply_state_transition, set_open_started_at
from lit.storage import items_db
from lit.storage.project_fs import load_fields, strip_item_from_workspaces

logger = logging.getLogger("lit.api.items")
router = APIRouter(prefix="/api/projects/{slug}/items", tags=["items"])


class ItemCreate(BaseModel):
    fields: dict[str, Any] = Field(default_factory=dict)
    sort_key: float = 0


class ItemPatch(BaseModel):
    fields: dict[str, Any]
    version: int | None = None


@router.get("")
async def list_items(slug: str) -> list[dict[str, Any]]:
    require_project(slug)
    field_defs = load_fields(slug).get("fields", [])
    db = db_path_for(slug)

    def _list(conn):
        return items_db.list_items(conn, field_defs, lean=True)

    items = await items_db.run_db_async(db, _list)
    try:
        size = len(json.dumps(items))
        if size > 5_000_000:
            logger.warning("Lean list for %s is large: %s bytes", slug, size)
    except Exception:
        pass
    return items


@router.get("/{item_id}")
async def get_item(slug: str, item_id: str) -> dict[str, Any]:
    require_project(slug)
    db = db_path_for(slug)

    def _get(conn):
        return items_db.get_item(conn, item_id)

    item = await items_db.run_db_async(db, _get)
    if not item:
        raise HTTPException(status_code=404, detail="Item not found")
    return item


@router.post("", status_code=201)
async def create_item(slug: str, body: ItemCreate) -> dict[str, Any]:
    require_project(slug)
    proj = project_meta(slug)
    field_defs = load_fields(slug).get("fields", [])
    fields = apply_defaults(field_defs, body.fields)
    try:
        fields = validate_item_fields(
            field_defs, fields, partial=False, require_required=True
        )
    except ValidationError as e:
        raise HTTPException(status_code=422, detail=e.errors) from e

    waiting_value = proj.get("waiting_state_value", "Waiting For")
    db = db_path_for(slug)

    def _create(conn):
        item = items_db.create_item(conn, fields, sort_key=body.sort_key)
        if fields.get("state") == waiting_value:
            apply_state_transition(
                conn,
                item["id"],
                old_state=None,
                new_state=fields.get("state"),
                waiting_state_value=waiting_value,
                waiting_for=fields.get("waiting_for"),
                reason=fields.get("waiting_for_reason"),
                started_on=fields.get("waiting_since"),
            )
            if fields.get("waiting_since"):
                set_open_started_at(conn, item["id"], str(fields.get("waiting_since")))
            conn.commit()
            item = items_db.get_item(conn, item["id"])
        return item

    return await items_db.run_db_async(db, _create)


@router.patch("/{item_id}")
async def patch_item(slug: str, item_id: str, body: ItemPatch) -> dict[str, Any]:
    require_project(slug)
    proj = project_meta(slug)
    field_defs = load_fields(slug).get("fields", [])
    try:
        patch_fields = validate_item_fields(
            field_defs, dict(body.fields), partial=True, require_required=False
        )
    except ValidationError as e:
        raise HTTPException(status_code=422, detail=e.errors) from e

    waiting_value = proj.get("waiting_state_value", "Waiting For")
    db = db_path_for(slug)

    def _patch(conn):
        current = items_db.get_item(conn, item_id)
        if not current:
            raise KeyError(item_id)
        old_fields = current["fields"]
        old_state = old_fields.get("state")
        merged = {**old_fields, **patch_fields}
        new_state = merged.get("state")
        try:
            item = items_db.update_item_fields(conn, item_id, merged, body.version)
        except items_db.ConflictError as e:
            raise e
        apply_state_transition(
            conn,
            item_id,
            old_state=old_state,
            new_state=new_state,
            waiting_state_value=waiting_value,
            waiting_for=merged.get("waiting_for"),
            reason=merged.get("waiting_for_reason"),
            started_on=merged.get("waiting_since"),
        )
        if "waiting_since" in patch_fields and patch_fields.get("waiting_since"):
            set_open_started_at(conn, item_id, str(patch_fields["waiting_since"]))
        conn.commit()
        return items_db.get_item(conn, item_id)

    try:
        return await items_db.run_db_async(db, _patch)
    except KeyError:
        raise HTTPException(status_code=404, detail="Item not found") from None
    except items_db.ConflictError as e:
        raise HTTPException(
            status_code=409,
            detail={"message": "version conflict", "current_version": e.current_version},
        ) from e


@router.delete("/{item_id}")
async def delete_item(slug: str, item_id: str) -> dict[str, str]:
    require_project(slug)
    db = db_path_for(slug)

    def _del(conn):
        return items_db.delete_item(conn, item_id)

    ok = await items_db.run_db_async(db, _del)
    if not ok:
        raise HTTPException(status_code=404, detail="Item not found")
    try:
        strip_item_from_workspaces(slug, item_id)
    except Exception:
        logger.exception("Failed to strip deleted item %s from workspaces", item_id)
    return {"status": "deleted", "id": item_id}
