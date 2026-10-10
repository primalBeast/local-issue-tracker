from __future__ import annotations

import json
import logging
import math
from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field, field_validator

from lit.api.deps import db_path_for, require_project, require_writable
from lit.services.validation import (
    ValidationError,
    apply_defaults,
    validate_item_fields,
)
from lit.services.waiting import (
    DONE_STATE,
    LEGACY_WAITING_STATE,
    WAITING_FALLBACK_STATE,
    apply_waiting_flag,
    is_waiting_flag,
    normalize_waiting_fields,
    set_open_started_at,
)


def _coerce_incoming_waiting(fields: dict[str, Any]) -> dict[str, Any]:
    """Rewrite a legacy Waiting For state so validation can accept the patch."""
    out = dict(fields)
    if out.get("state") == LEGACY_WAITING_STATE:
        out["state"] = WAITING_FALLBACK_STATE
        out["waiting"] = True
    if out.get("state") == DONE_STATE:
        out["waiting"] = False
    return out
from lit.storage import items_db
from lit.security import valid_item_id
from lit.services.standup import copy_ticket_key

from lit.storage.project_fs import load_fields, strip_item_from_workspaces

logger = logging.getLogger("lit.api.items")
router = APIRouter(prefix="/api/projects/{slug}/items", tags=["items"])


class ItemCreate(BaseModel):
    fields: dict[str, Any] = Field(default_factory=dict)
    sort_key: float = 0

    @field_validator("sort_key")
    @classmethod
    def _finite_sort_key(cls, value: float) -> float:
        if isinstance(value, bool) or not isinstance(value, (int, float)):
            raise ValueError("sort_key must be a finite number")
        if not math.isfinite(float(value)) or abs(float(value)) > 1_000_000_000_000:
            raise ValueError("sort_key is out of range")
        return float(value)


class ItemPatch(BaseModel):
    fields: dict[str, Any]
    version: int | None = None


def _require_item_id(item_id: str) -> None:
    if not valid_item_id(item_id):
        raise HTTPException(status_code=400, detail="Invalid item id")


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
    _require_item_id(item_id)
    require_project(slug)
    db = db_path_for(slug)

    def _get(conn):
        return items_db.get_item(conn, item_id)

    item = await items_db.run_db_async(db, _get)
    if not item:
        raise HTTPException(status_code=404, detail="Item not found")
    return item


@router.post("", status_code=201, dependencies=[Depends(require_writable)])
async def create_item(slug: str, body: ItemCreate) -> dict[str, Any]:
    require_project(slug)
    field_defs = load_fields(slug).get("fields", [])
    fields = normalize_waiting_fields(apply_defaults(field_defs, body.fields))
    try:
        fields = validate_item_fields(
            field_defs, fields, partial=False, require_required=True
        )
    except ValidationError as e:
        raise HTTPException(status_code=422, detail=e.errors) from e

    db = db_path_for(slug)

    def _create(conn):
        item = items_db.create_item(conn, fields, sort_key=body.sort_key)
        if is_waiting_flag(fields):
            apply_waiting_flag(
                conn,
                item["id"],
                was_waiting=False,
                is_waiting=True,
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


@router.patch("/{item_id}", dependencies=[Depends(require_writable)])
async def patch_item(slug: str, item_id: str, body: ItemPatch) -> dict[str, Any]:
    _require_item_id(item_id)
    require_project(slug)
    field_defs = load_fields(slug).get("fields", [])
    try:
        patch_fields = validate_item_fields(
            field_defs,
            _coerce_incoming_waiting(dict(body.fields)),
            partial=True,
            require_required=False,
        )
    except ValidationError as e:
        raise HTTPException(status_code=422, detail=e.errors) from e

    db = db_path_for(slug)

    def _patch(conn):
        current = items_db.get_item(conn, item_id)
        if not current:
            raise KeyError(item_id)
        old_fields = current["fields"]
        was_waiting = is_waiting_flag(old_fields)
        merged = normalize_waiting_fields({**old_fields, **patch_fields})
        try:
            item = items_db.update_item_fields(conn, item_id, merged, body.version)
        except items_db.ConflictError as e:
            raise e
        apply_waiting_flag(
            conn,
            item_id,
            was_waiting=was_waiting,
            is_waiting=is_waiting_flag(merged),
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


@router.delete("/{item_id}", dependencies=[Depends(require_writable)])
async def delete_item(slug: str, item_id: str) -> dict[str, str]:
    _require_item_id(item_id)
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


@router.post("/{item_id}/duplicate", status_code=201, dependencies=[Depends(require_writable)])
async def duplicate_item(slug: str, item_id: str) -> dict[str, Any]:
    """Copy a ticket. The new number ends in -copy. Pin is cleared. Waiting restarts."""
    _require_item_id(item_id)
    require_project(slug)
    field_defs = load_fields(slug).get("fields", [])
    db = db_path_for(slug)

    def _copy(conn):
        current = items_db.get_item(conn, item_id)
        if not current:
            raise KeyError(item_id)
        rows = conn.execute("SELECT fields_json FROM items").fetchall()
        existing: set[str] = set()
        for row in rows:
            try:
                stored = json.loads(row["fields_json"])
            except Exception:
                continue
            if isinstance(stored, dict):
                existing.add(str(stored.get("ticket_key") or ""))
        fields = dict(current["fields"])
        fields["ticket_key"] = copy_ticket_key(existing, str(fields.get("ticket_key") or ""))
        title = str(fields.get("title") or "").strip()
        if title and not title.endswith(" (copy)"):
            fields["title"] = f"{title} (copy)"
        fields["pinned"] = False
        fields = normalize_waiting_fields(fields)
        try:
            fields = validate_item_fields(field_defs, fields, partial=False, require_required=True)
        except ValidationError as exc:
            raise exc
        item = items_db.create_item(conn, fields, sort_key=float(current.get("sort_key") or 0))
        if is_waiting_flag(fields):
            apply_waiting_flag(
                conn,
                item["id"],
                was_waiting=False,
                is_waiting=True,
                waiting_for=fields.get("waiting_for"),
                reason=fields.get("waiting_for_reason"),
                started_on=fields.get("waiting_since"),
            )
            conn.commit()
            item = items_db.get_item(conn, item["id"])
        return item

    try:
        return await items_db.run_db_async(db, _copy)
    except KeyError:
        raise HTTPException(status_code=404, detail="Item not found") from None
    except ValidationError as exc:
        raise HTTPException(status_code=422, detail=exc.errors) from exc
