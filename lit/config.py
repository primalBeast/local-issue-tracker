"""Application configuration and data-root resolution."""

from __future__ import annotations

import os
import platform
from dataclasses import dataclass, field
from pathlib import Path


DEFAULT_HOST = "127.0.0.1"
DEFAULT_PORT = 8765
APP_NAME = "LocalIssueTracker"


def default_data_dir() -> Path:
    env = os.environ.get("LIT_DATA_DIR")
    if env:
        return Path(env).expanduser().resolve()

    system = platform.system()
    home = Path.home()
    if system == "Darwin":
        return home / "Library" / "Application Support" / APP_NAME
    if system == "Windows":
        base = os.environ.get("APPDATA") or str(home / "AppData" / "Roaming")
        return Path(base) / APP_NAME
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
