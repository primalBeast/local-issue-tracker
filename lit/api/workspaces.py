from __future__ import annotations

import json
import uuid
from typing import Any, NoReturn

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from lit.api.deps import require_project, require_writable
from lit.storage.project_fs import (
    delete_workspace,
    list_workspaces,
    load_workspace,
    save_workspace,
)

router = APIRouter(prefix="/api/projects/{slug}/workspaces", tags=["workspaces"])


class WorkspaceCreate(BaseModel):
    name: str = "New Workspace"
    order: int = 0


@router.get("")
def get_workspaces(slug: str) -> list[dict[str, Any]]:
    require_project(slug)
    return list_workspaces(slug)


@router.post("", status_code=201, dependencies=[Depends(require_writable)])
def create_workspace(slug: str, body: WorkspaceCreate) -> dict[str, Any]:
    require_project(slug)
    ws_id = f"ws-{uuid.uuid4().hex[:8]}"
    from datetime import datetime, timezone

    existing = list_workspaces(slug)
    order = body.order
    if order == 0 and existing:
        # Place new boards after existing non-main boards
        max_order = max(int(w.get("order") or 0) for w in existing)
        order = max_order + 1

    now = datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")
    data = {
        "id": ws_id,
        "name": body.name,
        "order": order,
        "tab_color": None,
        "created_at": now,
        "updated_at": now,
        "schema_version": 1,
        "ui": {"sidebar_visible": True, "zoom": 1.0, "viewport_scroll": {"x": 0, "y": 0}},
        "filters": {"active": {}, "presets": []},
        "sort": {"field": "priority", "direction": "asc"},
        "panels": [],
    }
    return save_workspace(slug, ws_id, data)


def _reject_bad_workspace_id(exc: ValueError) -> NoReturn:
    # json.JSONDecodeError is a ValueError; corrupt files stay a server error.
    if isinstance(exc, json.JSONDecodeError):
        raise exc
    raise HTTPException(status_code=400, detail="Invalid workspace id") from None


@router.get("/{workspace_id}")
def get_workspace(slug: str, workspace_id: str) -> dict[str, Any]:
    require_project(slug)
    try:
        return load_workspace(slug, workspace_id)
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail="Workspace not found") from None
    except ValueError as exc:
        _reject_bad_workspace_id(exc)


@router.put("/{workspace_id}", dependencies=[Depends(require_writable)])
def put_workspace(slug: str, workspace_id: str, body: dict[str, Any]) -> dict[str, Any]:
    require_project(slug)
    # LWW full replace
    body = dict(body)
    body["id"] = workspace_id
    try:
        return save_workspace(slug, workspace_id, body)
    except ValueError as exc:
        _reject_bad_workspace_id(exc)


@router.delete("/{workspace_id}", dependencies=[Depends(require_writable)])
def remove_workspace(slug: str, workspace_id: str) -> dict[str, str]:
    require_project(slug)
    try:
        deleted = delete_workspace(slug, workspace_id)
    except ValueError as exc:
        _reject_bad_workspace_id(exc)
    if not deleted:
        raise HTTPException(status_code=404, detail="Workspace not found")
    return {"status": "deleted", "id": workspace_id}
