from __future__ import annotations

from typing import Any

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from lit.api.deps import require_project
from lit.storage.backup import backup_project, list_backups

router = APIRouter(prefix="/api/projects/{slug}/backups", tags=["backups"])


class BackupRequest(BaseModel):
    force: bool = False


@router.get("")
def get_backups(slug: str) -> list[str]:
    require_project(slug)
    return list_backups(slug)


@router.post("")
def create_backup(slug: str, body: BackupRequest | None = None) -> dict[str, Any]:
    require_project(slug)
    force = body.force if body else False
    try:
        manifest = backup_project(slug, force=force)
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail="Project not found") from None
    if manifest is None:
        return {"status": "skipped", "reason": "already exists for today"}
    return {"status": "created", "manifest": manifest}
