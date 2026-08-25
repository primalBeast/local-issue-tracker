"""Project filesystem operations: create, seed, load metadata."""

from __future__ import annotations

import json
import shutil
import uuid
from copy import deepcopy
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from lit.paths import project_dir, projects_dir, validate_slug
from lit.services.waiting import (
    LEGACY_WAITING_STATE,
    apply_waiting_flag,
    get_open_period,
    is_waiting_flag,
    normalize_waiting_fields,
)
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
    if _migrate_project_waiting_meta(data):
        to_save = deepcopy(data)
        to_save.pop("data_path", None)
        write_json(path, to_save)
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
    "label": "Since",
    "type": "date",
    "required": False,
    "order": 51,
    "default": "",
    "visible_when": {"field": "waiting", "equals": True},
    "show_in_list": False,
}

WAITING_CHECKBOX_FIELD: dict[str, Any] = {
    "id": "waiting",
    "label": "Waiting for...",
    "type": "checkbox",
    "required": False,
    "order": "49",
    "default": False,
    "visible_when": {"field": "state", "not_equals": "Done"},
    "filterable": True,
    "show_in_list": False,
}

WAITING_VISIBLE_WHEN = {"field": "waiting", "equals": True}


def _set_visible_when(field: dict[str, Any], visible_when: dict[str, Any]) -> bool:
    if field.get("visible_when") != visible_when:
        field["visible_when"] = dict(visible_when)
        return True
    return False


def _insert_field_before(fields: list[Any], new_field: dict[str, Any], before_ids: tuple[str, ...]) -> None:
    idx = next(
        (i for i, f in enumerate(fields) if isinstance(f, dict) and f.get("id") in before_ids),
        None,
    )
    if idx is None:
        fields.append(dict(new_field))
    else:
        fields.insert(idx, dict(new_field))


def _waiting_for_names_from_items(slug: str) -> list[str]:
    """Unique waiting_for values already stored on tickets, for select options."""
    db = items_db.items_db_path(project_dir(slug))

    def _read(conn: Any) -> list[str]:
        rows = conn.execute("SELECT fields_json FROM items").fetchall()
        names: list[str] = []
        seen: set[str] = set()
        for row in rows:
            try:
                fields = json.loads(row["fields_json"])
            except Exception:
                continue
            if not isinstance(fields, dict):
                continue
            name = str(fields.get("waiting_for") or "").strip()
            if name and name not in seen:
                seen.add(name)
                names.append(name)
        return names

    try:
        return items_db.run_db(db, _read)
    except Exception:
        return []


def ensure_waiting_as_field(data: dict[str, Any], slug: str | None = None) -> bool:
    """Replace the Waiting For state with a Waiting checkbox + Name/Since fields."""
    fields = data.get("fields")
    if not isinstance(fields, list):
        return False
    changed = False
    for f in fields:
        if not isinstance(f, dict):
            continue
        fid = f.get("id")
        if fid == "state":
            opts = f.get("options")
            if isinstance(opts, list) and LEGACY_WAITING_STATE in opts:
                f["options"] = [o for o in opts if o != LEGACY_WAITING_STATE]
                changed = True
        elif fid == "ticket_key":
            if f.get("label") == "Ticket Key":
                f["label"] = "Ticket number"
                changed = True
        elif fid == "title":
            if f.get("label") == "Title":
                f["label"] = "Description"
                changed = True
        elif fid == "waiting":
            if _set_visible_when(f, {"field": "state", "not_equals": "Done"}):
                changed = True
            if f.get("label") == "Waiting":
                f["label"] = "Waiting for..."
                changed = True
        elif fid == "waiting_for":
            if _set_visible_when(f, WAITING_VISIBLE_WHEN):
                changed = True
            if f.get("label") == "Waiting For (person)":
                f["label"] = "Name"
                changed = True
            if not f.get("list_label"):
                f["list_label"] = "Waiting For"
                changed = True
            if f.get("type") != "select":
                f["type"] = "select"
                changed = True
            if not isinstance(f.get("options"), list):
                f["options"] = []
                changed = True
            if slug:
                for name in _waiting_for_names_from_items(slug):
                    if name not in f["options"]:
                        f["options"].append(name)
                        changed = True
        elif fid == "waiting_since":
            if _set_visible_when(f, WAITING_VISIBLE_WHEN):
                changed = True
            if f.get("label") == "Waiting Since":
                f["label"] = "Since"
                changed = True
        elif fid == "waiting_for_reason":
            if _set_visible_when(f, WAITING_VISIBLE_WHEN):
                changed = True
    if not any(isinstance(f, dict) and f.get("id") == "waiting_since" for f in fields):
        _insert_field_before(fields, WAITING_SINCE_FIELD, ("notes",))
        changed = True
    if not any(isinstance(f, dict) and f.get("id") == "waiting" for f in fields):
        _insert_field_before(fields, WAITING_CHECKBOX_FIELD, ("waiting_for", "waiting_since", "waiting_for_reason"))
        changed = True
    data["fields"] = fields
    return changed


def ensure_waiting_since_field(data: dict[str, Any]) -> bool:
    """Back-compat alias used by older tests; now the full waiting-as-field migration."""
    return ensure_waiting_as_field(data)


def _migrate_project_waiting_meta(data: dict[str, Any]) -> bool:
    changed = False
    if "waiting_state_value" in data:
        data.pop("waiting_state_value", None)
        changed = True
    color = data.get("color_coding")
    if isinstance(color, dict):
        palette = color.get("palette")
        if isinstance(palette, dict) and LEGACY_WAITING_STATE in palette:
            palette.pop(LEGACY_WAITING_STATE, None)
            changed = True
    return changed


def _strip_legacy_waiting_filter(filt: dict[str, Any]) -> bool:
    states = filt.get("state")
    if not isinstance(states, list) or LEGACY_WAITING_STATE not in states:
        return False
    remaining = [s for s in states if s != LEGACY_WAITING_STATE]
    if remaining:
        filt["state"] = remaining
    else:
        filt.pop("state", None)
        if "waiting" not in filt:
            filt["waiting"] = [True]
    return True


def migrate_waiting_filters(data: dict[str, Any]) -> bool:
    filters = data.get("filters")
    if not isinstance(filters, dict):
        return False
    changed = False
    active = filters.get("active")
    if isinstance(active, dict) and _strip_legacy_waiting_filter(active):
        changed = True
    presets = filters.get("presets")
    if isinstance(presets, list):
        for preset in presets:
            if isinstance(preset, dict) and isinstance(preset.get("filter"), dict):
                if _strip_legacy_waiting_filter(preset["filter"]):
                    changed = True
    return changed


def _migrate_waiting_state_items(slug: str) -> None:
    db = items_db.items_db_path(project_dir(slug))
    if not db.exists():
        return

    def _walk(conn) -> None:
        rows = conn.execute(
            "SELECT id, fields_json FROM items WHERE fields_json LIKE ?",
            (f'%"{LEGACY_WAITING_STATE}"%',),
        ).fetchall()
        if not rows:
            return
        for row in rows:
            fields = json.loads(row["fields_json"])
            if fields.get("state") != LEGACY_WAITING_STATE:
                continue
            was_waiting = is_waiting_flag(fields) or get_open_period(conn, row["id"]) is not None
            fields = normalize_waiting_fields(fields)
            conn.execute(
                "UPDATE items SET fields_json=? WHERE id=?",
                (json.dumps(fields, ensure_ascii=False), row["id"]),
            )
            apply_waiting_flag(
                conn,
                row["id"],
                was_waiting=was_waiting,
                is_waiting=True,
                waiting_for=fields.get("waiting_for"),
                reason=fields.get("waiting_for_reason"),
                started_on=fields.get("waiting_since"),
            )
        conn.commit()

    items_db.run_db(db, _walk)


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
    if ensure_waiting_as_field(data, slug):
        changed = True
    if ensure_unbounded_int_fields(data):
        changed = True
    if changed:
        write_json(path, data)
    try:
        _migrate_waiting_state_items(slug)
    except Exception:
        pass
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
        if migrate_waiting_filters(data):
            write_json(p, data)
        result.append(data)
    result.sort(key=lambda w: (w.get("order", 0), w.get("name", "")))
    return result


def load_workspace(slug: str, workspace_id: str) -> dict[str, Any]:
    path = project_dir(slug) / "workspaces" / f"{workspace_id}.json"
    if not path.exists():
        raise FileNotFoundError(workspace_id)
    data = read_json(path)
    if migrate_waiting_filters(data):
        write_json(path, data)
    return data


def save_workspace(slug: str, workspace_id: str, data: dict[str, Any]) -> dict[str, Any]:
    data = deepcopy(data)
    data["id"] = workspace_id
    data["updated_at"] = _now()
    if "schema_version" not in data:
        data["schema_version"] = 1
    write_json(project_dir(slug) / "workspaces" / f"{workspace_id}.json", data)
    return data


def strip_item_from_workspaces(slug: str, item_id: str) -> None:
    """Drop item panels from every board after a ticket is deleted."""
    for ws in list_workspaces(slug):
        panels = ws.get("panels") or []
        kept = [
            p
            for p in panels
            if not (isinstance(p, dict) and p.get("kind") == "item" and p.get("item_id") == item_id)
        ]
        if len(kept) == len(panels):
            continue
        ws["panels"] = kept
        save_workspace(slug, str(ws.get("id") or ""), ws)


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
    from lit.storage.template_store import resolve_template

    src = resolve_template(template_name)
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
