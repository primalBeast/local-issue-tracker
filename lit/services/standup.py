"""Plain-text standup built from the tickets already on disk."""

from __future__ import annotations

from collections import OrderedDict
from datetime import date, datetime
from typing import Any


def _ticket_key(fields: dict[str, Any]) -> str:
    key = str(fields.get("ticket_key") or "").strip()
    return key or "Untitled"


def _line(item: dict[str, Any], *, today: date) -> str:
    fields = item.get("fields") if isinstance(item.get("fields"), dict) else {}
    parts = [_ticket_key(fields)]
    title = str(fields.get("title") or "").strip()
    if title:
        parts.append(title)
    priority = fields.get("priority")
    if priority is not None and priority != "":
        parts.append(f"P{priority}")
    due = str(fields.get("due_on") or "").strip()
    if due:
        mark = "overdue" if _is_overdue(due, fields.get("state"), today) else "due"
        parts.append(f"{mark} {due}")
    if fields.get("pinned") is True:
        parts.append("pinned")
    waiting = item.get("waiting") if isinstance(item.get("waiting"), dict) else {}
    if waiting.get("is_waiting"):
        who = str(fields.get("waiting_for") or "").strip()
        parts.append(f"waiting{(' for ' + who) if who else ''}")
    return "- " + " — ".join(parts)


def _is_overdue(due: str, state: object, today: date) -> bool:
    if str(state or "") == "Done":
        return False
    try:
        return date.fromisoformat(due) < today
    except ValueError:
        return False


def build_standup(project_name: str, items: list[dict[str, Any]], *, today: date | None = None) -> str:
    """Open tickets grouped by state, overdue called out first. Done is omitted."""
    day = today or datetime.now().astimezone().date()
    name = (project_name or "Project").strip() or "Project"
    open_items = [
        item
        for item in items
        if str((item.get("fields") or {}).get("state") or "") != "Done"
    ]
    overdue = [
        item
        for item in open_items
        if _is_overdue(
            str((item.get("fields") or {}).get("due_on") or ""),
            (item.get("fields") or {}).get("state"),
            day,
        )
    ]
    lines = [f"{name} — {day.isoformat()}", ""]
    if not open_items:
        lines.append("No open tickets.")
        return "\n".join(lines).rstrip() + "\n"

    if overdue:
        lines.append(f"Overdue ({len(overdue)})")
        for item in overdue:
            lines.append(_line(item, today=day))
        lines.append("")

    grouped: OrderedDict[str, list[dict[str, Any]]] = OrderedDict()
    for item in open_items:
        state = str((item.get("fields") or {}).get("state") or "No state")
        grouped.setdefault(state, []).append(item)
    for state, group in grouped.items():
        lines.append(f"{state} ({len(group)})")
        for item in group:
            lines.append(_line(item, today=day))
        lines.append("")
    return "\n".join(lines).rstrip() + "\n"


def copy_ticket_key(existing: set[str], key: str) -> str:
    """A ticket number that is not already used, based on ``key``."""
    base = (key or "").strip() or "copy"
    if len(base) > 2000:
        base = base[:2000]
    candidate = f"{base}-copy"
    n = 2
    while candidate in existing:
        candidate = f"{base}-copy-{n}"
        n += 1
        if n > 500:
            break
    if len(candidate) > 2048:
        candidate = candidate[:2040].rstrip("-") + "-copy"
    return candidate
