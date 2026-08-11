"""Path helpers and sandboxing for project data."""

from __future__ import annotations

import re
from pathlib import Path

from lit.config import get_config

SLUG_RE = re.compile(r"^[a-z0-9][a-z0-9_-]{0,62}$")


def data_root() -> Path:
    return get_config().data_dir


def settings_path() -> Path:
    return data_root() / "settings.json"


def lock_path() -> Path:
    return data_root() / ".data.lock"


def projects_dir() -> Path:
    return data_root() / "projects"


def project_dir(slug: str) -> Path:
    validate_slug(slug)
    root = projects_dir().resolve()
    path = (root / slug).resolve()
    if path != root and root not in path.parents:
        raise ValueError(f"Path escapes data root: {slug}")
    if path.name != slug:
        raise ValueError(f"Invalid project path: {slug}")
    return path


def validate_slug(slug: str) -> str:
    if not slug or not SLUG_RE.match(slug):
        raise ValueError(
            "Invalid slug: use lowercase letters, digits, hyphens, underscores "
            "(start with alphanumeric, max 63 chars)"
        )
    if ".." in slug or "/" in slug or "\\" in slug:
        raise ValueError("Invalid slug: path separators not allowed")
    return slug


def templates_dir() -> Path:
    return Path(__file__).resolve().parent / "templates"
