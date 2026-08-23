"""User-saved project templates (schema + empty board), stored under the data dir."""

from __future__ import annotations

import shutil
from copy import deepcopy
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from lit.paths import project_dir, templates_dir, user_templates_dir, validate_slug
from lit.storage.json_io import read_json, write_json
from lit.storage.settings_store import load_settings, patch_settings

SKIP_NAMES = frozenset(
    {
        "items.sqlite",
        "items.sqlite-wal",
        "items.sqlite-shm",
        "backups",
        "hourly-text",
    }
)


def _now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def default_template_id() -> str:
    raw = load_settings().get("default_template")
    if isinstance(raw, str) and raw.strip():
        return raw.strip()
    return "issue-tracker"


def resolve_template(name: str) -> Path:
    """Prefer a user-saved template, then the shipped seed."""
    validate_slug(name)
    user = user_templates_dir() / name
    if user.is_dir() and (user / "project.json").exists():
        return user
    shipped = templates_dir() / name
    if shipped.is_dir() and (shipped / "project.json").exists():
        return shipped
    raise FileNotFoundError(name)


def _display_name(path: Path, fallback: str) -> str:
    proj = path / "project.json"
    if proj.exists():
        try:
            data = read_json(proj)
            name = data.get("name")
            if isinstance(name, str) and name.strip():
                return name.strip()
        except Exception:
            pass
    return fallback


def list_templates() -> list[dict[str, Any]]:
    default = default_template_id()
    found: dict[str, dict[str, Any]] = {}
    shipped_root = templates_dir()
    if shipped_root.is_dir():
        for p in sorted(shipped_root.iterdir()):
            if p.is_dir() and (p / "project.json").exists():
                found[p.name] = {
                    "id": p.name,
                    "name": _display_name(p, p.name),
                    "origin": "shipped",
                    "editable": False,
                    "is_default": p.name == default,
                }
    user_root = user_templates_dir()
    if user_root.is_dir():
        for p in sorted(user_root.iterdir()):
            if p.is_dir() and (p / "project.json").exists():
                found[p.name] = {
                    "id": p.name,
                    "name": _display_name(p, p.name),
                    "origin": "user",
                    "editable": True,
                    "is_default": p.name == default,
                }
    if default not in found and found:
        first = next(iter(found.values()))
        first["is_default"] = True
    return sorted(found.values(), key=lambda t: (0 if t["is_default"] else 1, t["name"].lower(), t["id"]))


def load_template_fields(template_id: str) -> dict[str, Any]:
    path = resolve_template(template_id) / "fields.json"
    if not path.exists():
        raise FileNotFoundError(template_id)
    return read_json(path)


def save_template_fields(template_id: str, data: dict[str, Any]) -> dict[str, Any]:
    """Write fields.json for a user template only (never the shipped seed)."""
    validate_slug(template_id)
    dest = user_templates_dir() / template_id
    if not dest.is_dir() or not (dest / "project.json").exists():
        raise FileNotFoundError(template_id)
    write_json(dest / "fields.json", data)
    return data


def _strip_item_panels(ws: dict[str, Any]) -> dict[str, Any]:
    out = deepcopy(ws)
    panels = out.get("panels")
    if isinstance(panels, list):
        out["panels"] = [
            p
            for p in panels
            if not (isinstance(p, dict) and p.get("kind") == "item")
        ]
    return out


def save_project_as_template(
    slug: str,
    template_id: str,
    *,
    name: str | None = None,
    set_default: bool = False,
    include_layout: bool = True,
) -> dict[str, Any]:
    """Snapshot this project's schema (and optional board layout) as a reusable template."""
    validate_slug(template_id)
    src = project_dir(slug)
    if not src.is_dir() or not (src / "project.json").exists():
        raise FileNotFoundError(slug)
    dest = user_templates_dir() / template_id
    dest.mkdir(parents=True, exist_ok=True)

    fields_src = src / "fields.json"
    if fields_src.exists():
        write_json(dest / "fields.json", read_json(fields_src))

    proj = deepcopy(read_json(src / "project.json"))
    proj.pop("data_path", None)
    proj.pop("waiting_state_value", None)
    proj["id"] = f"template-{template_id}"
    proj["slug"] = template_id
    proj["name"] = (name or proj.get("name") or template_id).strip() or template_id
    now = _now()
    proj["created_at"] = now
    proj["updated_at"] = now
    write_json(dest / "project.json", proj)

    write_json(
        dest / "notes.json",
        {"schema_version": 1, "content": {"type": "doc", "content": []}},
    )
    write_json(dest / "deliverables.json", {"schema_version": 1, "items": []})

    ws_dest = dest / "workspaces"
    if ws_dest.exists():
        shutil.rmtree(ws_dest)
    ws_src = src / "workspaces"
    if include_layout and ws_src.is_dir():
        ws_dest.mkdir(parents=True, exist_ok=True)
        for p in ws_src.glob("*.json"):
            ws = _strip_item_panels(read_json(p))
            ws["created_at"] = now
            ws["updated_at"] = now
            write_json(ws_dest / p.name, ws)
    else:
        shipped_ws = templates_dir() / "issue-tracker" / "workspaces"
        if shipped_ws.is_dir():
            shutil.copytree(shipped_ws, ws_dest)

    if set_default:
        patch_settings({"default_template": template_id})

    return {
        "id": template_id,
        "name": proj["name"],
        "origin": "user",
        "editable": True,
        "is_default": default_template_id() == template_id,
    }


def delete_user_template(template_id: str) -> bool:
    validate_slug(template_id)
    dest = user_templates_dir() / template_id
    if not dest.is_dir():
        return False
    shutil.rmtree(dest)
    if default_template_id() == template_id:
        patch_settings({"default_template": "issue-tracker"})
    return True
