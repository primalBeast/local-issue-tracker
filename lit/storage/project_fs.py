"""Project filesystem operations: create, seed, load metadata."""

from __future__ import annotations

import json
import shutil
import uuid
from copy import deepcopy
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from lit.paths import project_dir, projects_dir, templates_dir, validate_slug
from lit.storage import items_db
from lit.storage.json_io import read_json, write_json
from lit.storage.settings_store import load_settings, patch_settings


def _now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def ensure_data_layout() -> None:
    projects_dir().mkdir(parents=True, exist_ok=True)
    load_settings()


def list_project_slugs() -> list[str]:
    root = projects_dir()
    if not root.exists():
        return []
    return sorted(
        p.name
        for p in root.iterdir()
        if p.is_dir() and not p.name.startswith(".") and (p / "project.json").exists()
    )


def load_project(slug: str) -> dict[str, Any]:
    path = project_dir(slug) / "project.json"
    if not path.exists():
        raise FileNotFoundError(slug)
    data = read_json(path)
    data["slug"] = slug  # path is source of truth
    prefs = load_settings().get("ticket_prefix_by_project") or {}
    overlay = prefs.get(slug) if isinstance(prefs, dict) else None
    if overlay:
        data["ticket_prefix"] = overlay
    elif not data.get("ticket_prefix"):
        data["ticket_prefix"] = "NEW-"
    data["data_path"] = str(project_dir(slug))
    return data


def save_project(slug: str, data: dict[str, Any]) -> dict[str, Any]:
    data = deepcopy(data)
    data.pop("data_path", None)
    data["slug"] = slug
    data["updated_at"] = _now()
    dest = project_dir(slug)
    write_json(dest / "project.json", data)
    prefix = data.get("ticket_prefix")
    if prefix:
        patch_settings({"ticket_prefix_by_project": {slug: str(prefix)}})
    data["data_path"] = str(dest)
    return data


URGENCY_FIELD: dict[str, Any] = {
    "id": "urgency",
    "label": "Urgency",
    "type": "number",
    "required": False,
    "order": "30b",
    "default": 5,
    "validation": {"step": 1},
    "show_in_list": True,
    "filterable": True,
    "width_weight": 1,
}

_URGENCY_LABELS = {"Critical": 1, "High": 3, "Medium": 5, "Low": 8}


def coerce_urgency_int(value: Any) -> int:
    if isinstance(value, bool):
        return 5
    if isinstance(value, (int, float)):
        return int(value)
    if isinstance(value, str) and value in _URGENCY_LABELS:
        return _URGENCY_LABELS[value]
    try:
        return int(value)
    except (TypeError, ValueError):
        return 5


def ensure_urgency_field(data: dict[str, Any]) -> bool:
    """Insert or convert Urgency to an integer field between Priority and State."""
    fields = data.get("fields")
    if not isinstance(fields, list):
        return False
    existing = next((f for f in fields if isinstance(f, dict) and f.get("id") == "urgency"), None)
    if existing is not None:
        if existing.get("type") == "number":
            return False
        existing.clear()
        existing.update(URGENCY_FIELD)
        return True
    for f in fields:
        if isinstance(f, dict) and f.get("id") == "state" and str(f.get("order")) == "30b":
            f["order"] = "30c"
    insert_at = next(
        (i + 1 for i, f in enumerate(fields) if isinstance(f, dict) and f.get("id") == "priority"),
        len(fields),
    )
    fields.insert(insert_at, dict(URGENCY_FIELD))
    data["fields"] = fields
    return True


def _migrate_urgency_item_values(slug: str) -> None:
    db = items_db.items_db_path(project_dir(slug))
    if not db.exists():
        return

    def _walk(conn) -> None:
        rows = conn.execute("SELECT id, fields_json FROM items").fetchall()
        for row in rows:
            fields = json.loads(row["fields_json"])
            raw = fields.get("urgency")
            coerced = coerce_urgency_int(raw) if raw is not None else 5
            if raw == coerced:
                continue
            fields["urgency"] = coerced
            conn.execute(
                "UPDATE items SET fields_json=? WHERE id=?",
                (json.dumps(fields, ensure_ascii=False), row["id"]),
            )
        conn.commit()

    items_db.run_db(db, _walk)


WAITING_SINCE_FIELD: dict[str, Any] = {
    "id": "waiting_since",
    "label": "Waiting Since",
    "type": "date",
    "required": False,
    "order": 51,
    "default": "",
    "visible_when": {"field": "state", "equals": "Waiting For"},
    "show_in_list": False,
}


def ensure_waiting_since_field(data: dict[str, Any]) -> bool:
    fields = data.get("fields")
    if not isinstance(fields, list):
        return False
    changed = False
    for f in fields:
        if isinstance(f, dict) and f.get("id") == "waiting_for" and not f.get("list_label"):
            f["list_label"] = "Waiting For"
            changed = True
    if any(isinstance(f, dict) and f.get("id") == "waiting_since" for f in fields):
        return changed
    last_waiting = max(
        (i for i, f in enumerate(fields) if isinstance(f, dict) and str(f.get("id", "")).startswith("waiting_for")),
        default=len(fields) - 1,
    )
    fields.insert(last_waiting + 1, dict(WAITING_SINCE_FIELD))
    data["fields"] = fields
    return True


def ensure_unbounded_int_fields(data: dict[str, Any]) -> bool:
    """Drop 1–10 clamps on priority/urgency so any integer is allowed."""
    fields = data.get("fields")
    if not isinstance(fields, list):
        return False
    changed = False
    for f in fields:
        if not isinstance(f, dict) or f.get("id") not in ("priority", "urgency"):
            continue
        val = f.get("validation")
        if not isinstance(val, dict):
            continue
        if "min" in val or "max" in val:
            val.pop("min", None)
            val.pop("max", None)
            if not val:
                f.pop("validation", None)
            else:
                f["validation"] = val
            changed = True
    return changed


def load_fields(slug: str) -> dict[str, Any]:
    path = project_dir(slug) / "fields.json"
    data = read_json(path)
    changed = False
    if ensure_urgency_field(data):
        changed = True
        try:
            _migrate_urgency_item_values(slug)
        except Exception:
            pass
    if ensure_waiting_since_field(data):
        changed = True
    if ensure_unbounded_int_fields(data):
        changed = True
    if changed:
        write_json(path, data)
    return data


def save_fields(slug: str, data: dict[str, Any]) -> dict[str, Any]:
    write_json(project_dir(slug) / "fields.json", data)
    return data


def load_notes(slug: str) -> dict[str, Any]:
    path = project_dir(slug) / "notes.json"
    if not path.exists():
        return {"schema_version": 1, "content": {"type": "doc", "content": []}}
    return read_json(path)


def save_notes(slug: str, data: dict[str, Any]) -> dict[str, Any]:
    write_json(project_dir(slug) / "notes.json", data)
    return data


def load_deliverables(slug: str) -> dict[str, Any]:
    path = project_dir(slug) / "deliverables.json"
    if not path.exists():
        return {"schema_version": 1, "items": []}
    return read_json(path)


def save_deliverables(slug: str, data: dict[str, Any]) -> dict[str, Any]:
    write_json(project_dir(slug) / "deliverables.json", data)
    return data


def list_workspaces(slug: str) -> list[dict[str, Any]]:
    ws_dir = project_dir(slug) / "workspaces"
    if not ws_dir.exists():
        return []
    result = []
    for p in sorted(ws_dir.glob("*.json")):
        data = read_json(p)
        result.append(data)
    result.sort(key=lambda w: (w.get("order", 0), w.get("name", "")))
    return result


def load_workspace(slug: str, workspace_id: str) -> dict[str, Any]:
    path = project_dir(slug) / "workspaces" / f"{workspace_id}.json"
    if not path.exists():
        raise FileNotFoundError(workspace_id)
    return read_json(path)


def save_workspace(slug: str, workspace_id: str, data: dict[str, Any]) -> dict[str, Any]:
    data = deepcopy(data)
    data["id"] = workspace_id
    data["updated_at"] = _now()
    if "schema_version" not in data:
        data["schema_version"] = 1
    write_json(project_dir(slug) / "workspaces" / f"{workspace_id}.json", data)
    return data


def delete_workspace(slug: str, workspace_id: str) -> bool:
    path = project_dir(slug) / "workspaces" / f"{workspace_id}.json"
    if not path.exists():
        return False
    path.unlink()
    return True


def _copy_template(
    template_name: str,
    slug: str,
    name: str | None = None,
    ticket_prefix: str | None = None,
) -> Path:
    src = templates_dir() / template_name
    if not src.is_dir():
        raise FileNotFoundError(f"Template not found: {template_name}")
    dest = project_dir(slug)
    if dest.exists():
        raise FileExistsError(slug)
    shutil.copytree(src, dest)

    # Fix project.json id/slug/name/timestamps
    proj_path = dest / "project.json"
    proj = read_json(proj_path)
    proj["id"] = str(uuid.uuid4())
    proj["slug"] = slug
    proj["name"] = name or proj.get("name") or slug
    if ticket_prefix:
        proj["ticket_prefix"] = ticket_prefix
    elif not proj.get("ticket_prefix"):
        proj["ticket_prefix"] = "NEW-"
    now = _now()
    proj["created_at"] = now
    proj["updated_at"] = now
    write_json(proj_path, proj)
    if proj.get("ticket_prefix"):
        patch_settings({"ticket_prefix_by_project": {slug: str(proj["ticket_prefix"])}})

    # Init empty sqlite
    db_path = items_db.items_db_path(dest)
    items_db.run_db(db_path, lambda c: None)  # applies migrations

    # Ensure notes/deliverables
    if not (dest / "notes.json").exists():
        write_json(dest / "notes.json", {"schema_version": 1, "content": {"type": "doc", "content": []}})
    if not (dest / "deliverables.json").exists():
        write_json(dest / "deliverables.json", {"schema_version": 1, "items": []})

    # Refresh workspace timestamps
    ws_dir = dest / "workspaces"
    if ws_dir.exists():
        for p in ws_dir.glob("*.json"):
            ws = read_json(p)
            ws["created_at"] = now
            ws["updated_at"] = now
            write_json(p, ws)

    return dest


def create_project(
    slug: str,
    *,
    name: str | None = None,
    template: str = "issue-tracker",
    ticket_prefix: str | None = None,
) -> dict[str, Any]:
    validate_slug(slug)
    ensure_data_layout()
    if (projects_dir() / slug).exists():
        raise FileExistsError(slug)
    _copy_template(template, slug, name=name, ticket_prefix=ticket_prefix)
    return load_project(slug)


def delete_project(slug: str, confirm_slug: str) -> None:
    if confirm_slug != slug:
        raise ValueError("confirm_slug does not match project slug")
    path = project_dir(slug)
    if not path.exists():
        raise FileNotFoundError(slug)
    # Close DB connections for this project
    db = items_db.items_db_path(path)
    key = str(db.resolve())
    with items_db._registry_guard:  # noqa: SLF001
        conn = items_db._connections.pop(key, None)  # noqa: SLF001
        if conn:
            try:
                conn.close()
            except Exception:
                pass
    shutil.rmtree(path)


def maybe_seed_sample() -> bool:
    """K16: auto-seed issue-tracker once when projects empty."""
    ensure_data_layout()
    settings = load_settings()
    if settings.get("seeded_sample"):
        return False
    if list_project_slugs():
        patch_settings({"seeded_sample": True})
        return False
    create_project("issue-tracker", name="Issue Tracker", template="issue-tracker")
    patch_settings({"seeded_sample": True, "last_project_slug": "issue-tracker"})
    return True
