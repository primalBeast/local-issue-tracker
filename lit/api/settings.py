from __future__ import annotations

from typing import Any

from fastapi import APIRouter, HTTPException, Request

from lit.security import SettingsRejected, sanitize_settings_updates
from lit.storage.settings_store import load_settings, patch_settings

router = APIRouter(prefix="/api/settings", tags=["settings"])


@router.get("")
def get_settings() -> dict[str, Any]:
    return load_settings()


@router.patch("")
async def update_settings(request: Request) -> dict[str, Any]:
    """Accept known settings fields; merge last_workspace_by_project by project slug."""
    raw = await request.json()
    try:
        updates = sanitize_settings_updates(raw)
    except SettingsRejected as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    return patch_settings(updates)
