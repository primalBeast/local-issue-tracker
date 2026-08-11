"""Daily project backups."""

from __future__ import annotations

import logging
import shutil
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any

from lit.storage import items_db
from lit.storage.json_io import write_json
from lit.storage.project_fs import list_project_slugs, project_dir
from lit.storage.settings_store import load_settings

logger = logging.getLogger("lit.backup")

INCLUDE_FILES = (
    "project.json",
    "fields.json",
    "items.sqlite",
    "items.sqlite-wal",
    "items.sqlite-shm",
    "notes.json",
    "deliverables.json",
)


def local_today() -> str:
    return datetime.now().astimezone().date().isoformat()


def backup_project(slug: str, *, force: bool = False) -> dict[str, Any] | None:
    proj = project_dir(slug)
    if not proj.exists():
        raise FileNotFoundError(slug)

    day = local_today()
    backups_root = proj / "backups"
    dest = backups_root / day
    if dest.exists() and not force:
        logger.info("Backup for %s already exists at %s; skip", slug, dest)
        return None

    # Checkpoint SQLite
    db_path = items_db.items_db_path(proj)
    if db_path.exists():
        items_db.run_db(db_path, items_db.checkpoint)

    partial = backups_root / f"{day}.partial"
    if partial.exists():
        shutil.rmtree(partial)
    partial.mkdir(parents=True, exist_ok=True)

    for name in INCLUDE_FILES:
        src = proj / name
        if src.exists() and src.is_file():
            shutil.copy2(src, partial / name)

    ws_src = proj / "workspaces"
    if ws_src.is_dir():
        shutil.copytree(ws_src, partial / "workspaces")

    manifest = {
        "created_at": datetime.utcnow().replace(microsecond=0).isoformat() + "Z",
        "local_date": day,
        "project_slug": slug,
        "schema_version": 1,
    }
    write_json(partial / "backup_manifest.json", manifest)

    if dest.exists() and force:
        shutil.rmtree(dest)
    partial.rename(dest)
    logger.info("Created backup %s for project %s", dest, slug)

    _apply_retention(slug)
    return manifest


def _apply_retention(slug: str) -> None:
    settings = load_settings()
    days = int(settings.get("backup_retention_days") or 30)
    backups_root = project_dir(slug) / "backups"
    if not backups_root.exists():
        return
    cutoff = datetime.now().astimezone().date() - timedelta(days=days)
    for p in backups_root.iterdir():
        if not p.is_dir() or p.name.endswith(".partial"):
            continue
        try:
            d = datetime.strptime(p.name, "%Y-%m-%d").date()
        except ValueError:
            continue
        if d < cutoff:
            shutil.rmtree(p)
            logger.info("Pruned old backup %s", p)


def backup_all_projects(*, force: bool = False) -> list[dict[str, Any]]:
    results = []
    for slug in list_project_slugs():
        try:
            m = backup_project(slug, force=force)
            if m:
                results.append(m)
        except Exception:
            logger.exception("Backup failed for %s", slug)
    return results


def list_backups(slug: str) -> list[str]:
    root = project_dir(slug) / "backups"
    if not root.exists():
        return []
    return sorted(
        p.name
        for p in root.iterdir()
        if p.is_dir() and not p.name.endswith(".partial")
    )
