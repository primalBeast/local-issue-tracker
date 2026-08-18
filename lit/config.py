"""Application configuration and data-root resolution."""

from __future__ import annotations

import logging
import os
import platform
import shutil
from dataclasses import dataclass, field
from pathlib import Path


DEFAULT_HOST = "127.0.0.1"
DEFAULT_PORT = 8765
APP_NAME = "LocalIssueTracker"
# Explorer-friendly folder in OneDrive for every file this app writes.
WINDOWS_ONEDRIVE_FOLDER = "Local Issue Tracker"

logger = logging.getLogger("lit")


def onedrive_root() -> Path | None:
    """Return the signed-in OneDrive folder, if it exists."""
    for key in ("OneDrive", "OneDriveConsumer", "OneDriveCommercial"):
        raw = os.environ.get(key)
        if not raw:
            continue
        path = Path(raw).expanduser()
        if path.is_dir():
            return path
    fallback = Path.home() / "OneDrive"
    return fallback if fallback.is_dir() else None


def windows_legacy_data_dir() -> Path:
    home = Path.home()
    base = os.environ.get("APPDATA") or str(home / "AppData" / "Roaming")
    return Path(base) / APP_NAME


def windows_onedrive_data_dir() -> Path | None:
    root = onedrive_root()
    if root is None:
        return None
    return root / WINDOWS_ONEDRIVE_FOLDER


def _looks_populated(path: Path) -> bool:
    if (path / "settings.json").is_file():
        return True
    projects = path / "projects"
    if not projects.is_dir():
        return False
    return any(projects.iterdir())


def migrate_windows_appdata_to_onedrive(dest: Path) -> None:
    """Copy AppData\\LocalIssueTracker into OneDrive, then remove the old copy."""
    legacy = windows_legacy_data_dir()
    dest = dest.expanduser()
    if dest.resolve() == legacy.resolve():
        return
    if not _looks_populated(legacy):
        return
    if _looks_populated(dest):
        logger.info("Windows data already present at %s; leaving %s in place", dest, legacy)
        return

    dest.mkdir(parents=True, exist_ok=True)
    logger.info("Moving Local Issue Tracker data from %s to %s", legacy, dest)
    shutil.copytree(
        legacy,
        dest,
        dirs_exist_ok=True,
        ignore=shutil.ignore_patterns(".data.lock"),
    )
    if not _looks_populated(dest):
        raise RuntimeError(f"Migration to {dest} did not produce usable data")

    leftover_lock = dest / ".data.lock"
    leftover_lock.unlink(missing_ok=True)

    try:
        shutil.rmtree(legacy)
        logger.info("Removed legacy data directory %s", legacy)
    except OSError as exc:
        logger.warning("Could not fully remove %s after move (%s); leftover files are safe to delete", legacy, exc)
        for child in legacy.iterdir():
            if child.name == ".data.lock":
                continue
            try:
                if child.is_dir():
                    shutil.rmtree(child)
                else:
                    child.unlink()
            except OSError:
                logger.warning("Left behind %s", child)


def prepare_data_dir(dest: Path) -> None:
    """One-time Windows AppData → OneDrive move when using the default path."""
    if platform.system() != "Windows":
        return
    if os.environ.get("LIT_DATA_DIR"):
        return
    onedrive = windows_onedrive_data_dir()
    if onedrive is None:
        return
    if dest.expanduser().resolve() != onedrive.resolve():
        return
    migrate_windows_appdata_to_onedrive(dest)


def default_data_dir() -> Path:
    env = os.environ.get("LIT_DATA_DIR")
    if env:
        return Path(env).expanduser().resolve()

    system = platform.system()
    home = Path.home()
    if system == "Darwin":
        return home / "Library" / "Application Support" / APP_NAME
    if system == "Windows":
        onedrive = windows_onedrive_data_dir()
        if onedrive is not None:
            return onedrive
        return windows_legacy_data_dir()
    # Linux / other — XDG
    xdg = os.environ.get("XDG_DATA_HOME") or str(home / ".local" / "share")
    return Path(xdg) / "local-issue-tracker"


@dataclass
class AppConfig:
    data_dir: Path = field(default_factory=default_data_dir)
    host: str = DEFAULT_HOST
    port: int = DEFAULT_PORT
    open_browser: bool = False
    reload: bool = False
    dev_cors: bool = False

    def __post_init__(self) -> None:
        self.data_dir = Path(self.data_dir).expanduser().resolve()
        prepare_data_dir(self.data_dir)
        if os.environ.get("LIT_DEV_CORS") == "1":
            self.dev_cors = True
        if self.reload:
            self.dev_cors = True


# Process-wide config set at startup
_config: AppConfig | None = None


def set_config(cfg: AppConfig) -> None:
    global _config
    _config = cfg


def get_config() -> AppConfig:
    if _config is None:
        return AppConfig()
    return _config
