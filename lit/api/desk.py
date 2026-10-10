"""Read-only desk helpers: a JSON export and a plain-text standup."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Any

from fastapi import APIRouter, HTTPException
from fastapi.responses import Response

from lit.api.deps import db_path_for, require_project
from lit.services.standup import build_standup
from lit.storage import items_db
from lit.storage.project_fs import (
    load_deliverables,
    load_fields,
    load_notes,
    load_project,
    list_workspaces,
)

router = APIRouter(tags=["desk"])


def _project_without_path(slug: str) -> dict[str, Any]:
    data = dict(load_project(slug))
    data.pop("data_path", None)
    return data


@router.get("/api/projects/{slug}/export")
async def export_project(slug: str) -> Response:
    """Download this project's tickets and boards. No folder path is included."""
    require_project(slug)
    field_defs = load_fields(slug).get("fields", [])
    db = db_path_for(slug)

    def _items(conn):
        return items_db.list_items(conn, field_defs, lean=False)

    try:
        items = await items_db.run_db_async(db, _items)
    except FileNotFoundError:
        items = []
    payload = {
        "schema_version": 1,
        "exported_at": datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z"),
        "project": _project_without_path(slug),
        "fields": load_fields(slug),
        "items": items,
        "notes": load_notes(slug),
        "deliverables": load_deliverables(slug),
        "workspaces": list_workspaces(slug),
    }
    body = json.dumps(payload, indent=2, ensure_ascii=False).encode("utf-8")
    filename = f"{slug}-export.json"
    return Response(
        content=body,
        media_type="application/json",
        headers={
            "Content-Disposition": f'attachment; filename="{filename}"',
            "Cache-Control": "no-store",
        },
    )


@router.get("/api/projects/{slug}/standup")
async def project_standup(slug: str) -> dict[str, str]:
    """Plain text of open tickets, grouped by state, for a status update."""
    require_project(slug)
    project = _project_without_path(slug)
    field_defs = load_fields(slug).get("fields", [])
    db = db_path_for(slug)

    def _items(conn):
        return items_db.list_items(conn, field_defs, lean=False)

    try:
        items = await items_db.run_db_async(db, _items)
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail="Project not found") from exc
    text = build_standup(str(project.get("name") or slug), items)
    return {"text": text}
