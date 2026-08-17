from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Request
from pydantic import BaseModel, Field

from lit.storage.settings_store import load_settings, patch_settings

router = APIRouter(prefix="/api/settings", tags=["settings"])


class SettingsPatch(BaseModel):
    last_project_slug: str | None = None
    last_workspace_by_project: dict[str, str] | None = None
    theme: str | None = None
    transparent_panels: bool | None = None
    backup_retention_days: int | None = Field(default=None, ge=1, le=365)
    window: dict[str, Any] | None = None


@router.get("")
def get_settings() -> dict[str, Any]:
    return load_settings()


@router.patch("")
async def update_settings(request: Request) -> dict[str, Any]:
    """Accept known settings fields; merge last_workspace_by_project by project slug."""
    raw = await request.json()
    if not isinstance(raw, dict):
        return load_settings()
    # Only allow known keys (ignore junk)
    allowed = {
        "last_project_slug",
        "last_workspace_by_project",
        "theme",
        "transparent_panels",
        "backup_retention_days",
        "window",
        "seeded_sample",
    }
    updates = {k: v for k, v in raw.items() if k in allowed}
    return patch_settings(updates)
