from __future__ import annotations

from typing import Any

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from lit.api.deps import require_project
from lit.storage.backup import backup_all_projects, backup_project, list_backups

router = APIRouter(prefix="/api/projects/{slug}/backups", tags=["backups"])
now_router = APIRouter(prefix="/api/backups", tags=["backups"])


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


class BackupNowRequest(BaseModel):
    project: str | None = None
    force: bool = False


@now_router.post("/now")
def backup_now(body: BackupNowRequest | None = None) -> dict[str, Any]:
    """Run a backup while this server holds the data-root lock.

    CLI ``backup-now`` calls this when another process already holds the lock,
    so the command never writes project files itself.
    """
    body = body or BackupNowRequest()
    if body.project:
        try:
            manifest = backup_project(body.project, force=body.force)
        except FileNotFoundError:
            raise HTTPException(status_code=404, detail="Project not found") from None
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        if manifest is None:
            return {"status": "skipped", "count": 0, "reason": "already exists for today"}
        return {"status": "created", "count": 1, "manifest": manifest}
    results = backup_all_projects(force=body.force)
    return {"status": "ok", "count": len(results), "manifest": results}
