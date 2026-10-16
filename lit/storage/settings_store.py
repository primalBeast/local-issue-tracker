"""settings.json load/save."""

from __future__ import annotations

import re
from copy import deepcopy
from typing import Any

from lit.paths import settings_path
from lit.storage.json_io import read_json, write_json

DEFAULT_SETTINGS: dict[str, Any] = {
    "schema_version": 1,
    "last_project_slug": None,
    # project_slug -> workspace_id of last selected board
    "last_workspace_by_project": {},
    "theme": "dark",
    "transparent_panels": False,
    "transparency_by_theme": {},
    "favorite_themes": [],
    "ticket_prefix_by_project": {},
    "backup_retention_days": 30,
    "seeded_sample": False,
    "default_template": "issue-tracker",
    "window": {"last_host": "127.0.0.1", "last_port": 8765},
}


def load_settings() -> dict[str, Any]:
    path = settings_path()
    if not path.exists():
        data = deepcopy(DEFAULT_SETTINGS)
        write_json(path, data)
        return data
    data = read_json(path)
    # Tolerate additive keys; fill missing defaults
    out = deepcopy(DEFAULT_SETTINGS)
    out.update(data)
    return out


def save_settings(data: dict[str, Any]) -> dict[str, Any]:
    path = settings_path()
    write_json(path, data)
    return data


_THEME_ID_RE = re.compile(r"^[a-z0-9_-]{1,40}$")


def clean_favorite_themes(raw: Any) -> list[dict[str, Any]]:
    """Keep a short list of {id, pulse}. Pulse is the full glow cycle in seconds."""
    if not isinstance(raw, list):
        return []
    out: list[dict[str, Any]] = []
    seen: set[str] = set()
    for item in raw:
        if not isinstance(item, dict):
            continue
        theme_id = item.get("id")
        if not isinstance(theme_id, str) or _THEME_ID_RE.fullmatch(theme_id) is None:
            continue
        if theme_id in seen:
            continue
        try:
            pulse = float(item.get("pulse", 4))
        except (TypeError, ValueError):
            pulse = 4.0
        if pulse < 2 or pulse > 8:
            pulse = 4.0
        seen.add(theme_id)
        out.append({"id": theme_id, "pulse": pulse})
        if len(out) >= 80:
            break
    return out


def patch_settings(updates: dict[str, Any]) -> dict[str, Any]:
    data = load_settings()
    for k, v in updates.items():
        if k == "window" and isinstance(v, dict) and isinstance(data.get("window"), dict):
            data["window"] = {**data["window"], **v}
        elif k == "last_workspace_by_project" and isinstance(v, dict):
            existing = data.get("last_workspace_by_project")
            if not isinstance(existing, dict):
                existing = {}
            data["last_workspace_by_project"] = {**existing, **v}
        elif k == "ticket_prefix_by_project" and isinstance(v, dict):
            existing = data.get("ticket_prefix_by_project")
            if not isinstance(existing, dict):
                existing = {}
            data["ticket_prefix_by_project"] = {**existing, **{str(sk): str(sv) for sk, sv in v.items() if sv}}
        elif k == "transparency_by_theme" and isinstance(v, dict):
            existing = data.get("transparency_by_theme")
            if not isinstance(existing, dict):
                existing = {}
            merged = dict(existing)
            for theme_id, raw in v.items():
                try:
                    n = float(raw)
                except (TypeError, ValueError):
                    continue
                merged[str(theme_id)] = max(0.0, min(1.0, n))
            data["transparency_by_theme"] = merged
        elif k == "favorite_themes":
            data["favorite_themes"] = clean_favorite_themes(v)
        else:
            data[k] = v
    return save_settings(data)
