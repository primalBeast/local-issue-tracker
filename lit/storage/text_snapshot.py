"""Hourly human-readable project snapshots (.txt + .md) for disaster recovery."""

from __future__ import annotations

import hashlib
import json
import logging
import os
import re
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any

from lit.storage import items_db
from lit.storage.project_fs import (
    list_project_slugs,
    list_workspaces,
    load_deliverables,
    load_fields,
    load_notes,
    load_project,
    project_dir,
)

logger = logging.getLogger("lit.text_snapshot")

SNAPSHOT_DIR_NAME = "hourly-text"
MAX_SNAPSHOTS = 50
HASH_NAME = "last-content.hash"
STEM_RE = re.compile(r"^\d{4}-\d{2}-\d{2}_\d{4}$")

_PANEL_LABELS = {
    "notes": "Notes",
    "all_items": "All Items",
    "deliverables": "Deliverables",
}


def seconds_until_next_hour(now: datetime | None = None) -> float:
    now = now or datetime.now().astimezone()
    nxt = now.replace(minute=0, second=0, microsecond=0) + timedelta(hours=1)
    return max(0.05, (nxt - now).total_seconds())


def snapshot_dir(slug: str) -> Path:
    return project_dir(slug) / SNAPSHOT_DIR_NAME


def snapshot_all_projects(*, force: bool = False, when: datetime | None = None) -> list[dict[str, Any]]:
    results: list[dict[str, Any]] = []
    for slug in list_project_slugs():
        try:
            result = snapshot_project(slug, force=force, when=when)
            if result:
                results.append(result)
        except Exception:
            logger.exception("Hourly text snapshot failed for %s", slug)
    return results


def snapshot_project(
    slug: str, *, force: bool = False, when: datetime | None = None
) -> dict[str, Any] | None:
    when = when or datetime.now().astimezone()
    stamp = when.replace(minute=0, second=0, microsecond=0)
    payload = collect_payload(slug)
    digest = payload_hash(payload)
    dest = snapshot_dir(slug)
    dest.mkdir(parents=True, exist_ok=True)

    stems = list_snapshot_stems(dest)
    if not force and stems and _read_hash(dest) == digest:
        logger.info("Hourly text snapshot for %s unchanged; skip", slug)
        return None

    stem = stamp.strftime("%Y-%m-%d_%H%M")
    txt_body = render_txt(payload, stamp)
    md_body = render_md(payload, stamp)
    txt_path = dest / f"{stem}.txt"
    md_path = dest / f"{stem}.md"
    _write_text(txt_path, txt_body)
    _write_text(md_path, md_body)
    _write_hash(dest, digest)
    _apply_retention(dest)
    logger.info("Wrote hourly text snapshot %s for project %s", stem, slug)
    return {"slug": slug, "stem": stem, "txt": str(txt_path), "md": str(md_path)}


def collect_payload(slug: str) -> dict[str, Any]:
    project = load_project(slug)
    field_defs = load_fields(slug).get("fields") or []
    db_path = items_db.items_db_path(project_dir(slug))

    def _list(conn):
        if not db_path.exists():
            return []
        return items_db.list_items(conn, field_defs, lean=False)

    items = items_db.run_db(db_path, _list) if db_path.exists() else []
    notes = load_notes(slug)
    deliverables = load_deliverables(slug)
    workspaces = list_workspaces(slug)
    by_id = {it["id"]: it for it in items}

    tickets = []
    for item in items:
        fields = dict(item.get("fields") or {})
        waiting = item.get("waiting") or {}
        tickets.append(
            {
                "ticket_key": str(fields.get("ticket_key") or "").strip(),
                "title": str(fields.get("title") or "").strip(),
                "fields": fields,
                "created_at": item.get("created_at"),
                "updated_at": item.get("updated_at"),
                "waiting": {
                    "is_waiting": bool(waiting.get("is_waiting")),
                    "current_started_at": waiting.get("current_started_at"),
                },
            }
        )
    tickets.sort(key=lambda t: _ticket_sort_key(t["ticket_key"]))

    boards = []
    for ws in workspaces:
        panels = []
        for panel in ws.get("panels") or []:
            kind = panel.get("kind")
            if kind == "item":
                item = by_id.get(panel.get("item_id"))
                key = ""
                if item:
                    key = str((item.get("fields") or {}).get("ticket_key") or "").strip()
                panels.append(key or "Ticket")
            else:
                panels.append(_PANEL_LABELS.get(kind, str(kind or "Panel")))
        boards.append({"name": ws.get("name") or ws.get("id") or "Board", "panels": panels})

    return {
        "project_name": project.get("name") or slug,
        "project_slug": slug,
        "tickets": tickets,
        "field_defs": field_defs,
        "notes": notes.get("content"),
        "deliverables": deliverables.get("items") or [],
        "boards": boards,
    }


def payload_hash(payload: dict[str, Any]) -> str:
    # Live waiting clocks must not trigger a new file every hour.
    canonical = {
        "project_name": payload.get("project_name"),
        "project_slug": payload.get("project_slug"),
        "tickets": [
            {
                "ticket_key": t.get("ticket_key"),
                "fields": t.get("fields"),
                "waiting": t.get("waiting"),
            }
            for t in payload.get("tickets") or []
        ],
        "notes": payload.get("notes"),
        "deliverables": payload.get("deliverables"),
        "boards": payload.get("boards"),
    }
    blob = json.dumps(canonical, ensure_ascii=False, sort_keys=True, default=str)
    return hashlib.sha256(blob.encode("utf-8")).hexdigest()


def render_txt(payload: dict[str, Any], stamp: datetime) -> str:
    lines: list[str] = []
    name = payload.get("project_name") or payload.get("project_slug") or "Project"
    lines.append("=" * 72)
    lines.append(f"Local Issue Tracker — {name}")
    lines.append(f"Saved: {stamp.strftime('%Y-%m-%d %H:%M')}")
    lines.append("=" * 72)

    lines.append("")
    lines.append("TICKETS")
    lines.append("-------")
    tickets = payload.get("tickets") or []
    if not tickets:
        lines.append("")
        lines.append("(none)")
    else:
        defs = payload.get("field_defs") or []
        for ticket in tickets:
            lines.append("")
            heading = _ticket_heading(ticket)
            lines.append(heading)
            lines.append("-" * max(8, len(heading)))
            body = _ticket_field_lines(ticket, defs, markdown=False)
            if body:
                lines.extend(body)
            else:
                lines.append("(no fields)")

    lines.append("")
    lines.append("PROJECT NOTES")
    lines.append("-------------")
    lines.append("")
    notes = tiptap_to_text(payload.get("notes")).strip()
    lines.append(notes or "(none)")

    lines.append("")
    lines.append("DELIVERABLES")
    lines.append("------------")
    dels = payload.get("deliverables") or []
    if not dels:
        lines.append("")
        lines.append("(none)")
    else:
        for item in dels:
            mark = "[x]" if item.get("done") else "[ ]"
            title = str(item.get("title") or "").strip() or "(untitled)"
            lines.append("")
            lines.append(f"{mark} {title}")
            extra = str(item.get("notes") or "").strip()
            if extra:
                for row in extra.splitlines():
                    lines.append(f"    {row}")

    lines.append("")
    lines.append("BOARDS")
    lines.append("------")
    boards = payload.get("boards") or []
    if not boards:
        lines.append("")
        lines.append("(none)")
    else:
        for board in boards:
            lines.append("")
            lines.append(str(board.get("name") or "Board"))
            panels = board.get("panels") or []
            if panels:
                lines.append("    " + ", ".join(str(p) for p in panels))
            else:
                lines.append("    (no panels)")

    lines.append("")
    return "\n".join(lines)


def render_md(payload: dict[str, Any], stamp: datetime) -> str:
    lines: list[str] = []
    name = payload.get("project_name") or payload.get("project_slug") or "Project"
    lines.append(f"# {name}")
    lines.append("")
    lines.append(f"Saved: {stamp.strftime('%Y-%m-%d %H:%M')}")
    lines.append("")
    lines.append("## Tickets")
    tickets = payload.get("tickets") or []
    if not tickets:
        lines.append("")
        lines.append("_None_")
    else:
        defs = payload.get("field_defs") or []
        for ticket in tickets:
            lines.append("")
            lines.append(f"### {_ticket_heading(ticket)}")
            lines.append("")
            body = _ticket_field_lines(ticket, defs, markdown=True)
            if body:
                lines.extend(body)
            else:
                lines.append("_No fields_")

    lines.append("")
    lines.append("## Project notes")
    lines.append("")
    notes = tiptap_to_markdown(payload.get("notes")).strip()
    lines.append(notes or "_None_")

    lines.append("")
    lines.append("## Deliverables")
    dels = payload.get("deliverables") or []
    if not dels:
        lines.append("")
        lines.append("_None_")
    else:
        for item in dels:
            mark = "x" if item.get("done") else " "
            title = str(item.get("title") or "").strip() or "(untitled)"
            lines.append("")
            lines.append(f"- [{mark}] {title}")
            extra = str(item.get("notes") or "").strip()
            if extra:
                for row in extra.splitlines():
                    lines.append(f"  {row}")

    lines.append("")
    lines.append("## Boards")
    boards = payload.get("boards") or []
    if not boards:
        lines.append("")
        lines.append("_None_")
    else:
        for board in boards:
            lines.append("")
            lines.append(f"### {board.get('name') or 'Board'}")
            panels = board.get("panels") or []
            if panels:
                lines.append("")
                lines.append(", ".join(str(p) for p in panels))
            else:
                lines.append("")
                lines.append("_No panels_")

    lines.append("")
    return "\n".join(lines)


def list_snapshot_stems(folder: Path) -> list[str]:
    if not folder.is_dir():
        return []
    stems = []
    for p in folder.iterdir():
        if p.suffix.lower() == ".txt" and STEM_RE.match(p.stem):
            stems.append(p.stem)
    return sorted(stems)


def _apply_retention(folder: Path) -> None:
    stems = list_snapshot_stems(folder)
    extra = len(stems) - MAX_SNAPSHOTS
    if extra <= 0:
        return
    for stem in stems[:extra]:
        for suffix in (".txt", ".md"):
            path = folder / f"{stem}{suffix}"
            try:
                path.unlink(missing_ok=True)
            except OSError:
                logger.warning("Could not remove old snapshot %s", path)
        logger.info("Pruned old hourly snapshot %s", stem)


def _ticket_heading(ticket: dict[str, Any]) -> str:
    key = ticket.get("ticket_key") or "(no ticket number)"
    title = ticket.get("title") or ""
    return f"{key}  {title}".strip() if title else str(key)


def _ticket_field_lines(ticket: dict[str, Any], defs: list[dict[str, Any]], *, markdown: bool) -> list[str]:
    fields = ticket.get("fields") or {}
    ordered = sorted(defs, key=_field_sort_key) if defs else [{"id": k, "label": k, "type": "text"} for k in fields]
    seen: set[str] = set()
    lines: list[str] = []
    for spec in ordered:
        fid = spec.get("id")
        if not fid or fid == "ticket_key" or fid in seen:
            continue
        seen.add(fid)
        value = fields.get(fid)
        ftype = spec.get("type") or "text"
        if _is_empty_value(value, ftype):
            continue
        label = spec.get("label") or fid
        if ftype == "richtext":
            body = tiptap_to_markdown(value).strip() if markdown else tiptap_to_text(value).strip()
            if not body:
                continue
            if markdown:
                lines.append(f"**{label}**")
                lines.append("")
                lines.extend(body.splitlines())
                lines.append("")
            else:
                lines.append(f"{label}:")
                for row in body.splitlines() or [""]:
                    lines.append(f"    {row}" if row else "")
            continue
        rendered = _format_scalar(value, ftype)
        if not rendered:
            continue
        if markdown:
            lines.append(f"- **{label}:** {rendered}")
        else:
            lines.append(f"{label}: {rendered}")
    waiting = ticket.get("waiting") or {}
    if waiting.get("is_waiting") and waiting.get("current_started_at"):
        started = str(waiting["current_started_at"])[:10]
        extra = f"Waiting since {started}"
        if markdown:
            if not any("Waiting Since" in ln for ln in lines):
                lines.append(f"- **Waiting since:** {started}")
        else:
            if not any(ln.startswith("Waiting Since:") for ln in lines):
                lines.append(extra)
    return lines


def _format_scalar(value: Any, ftype: str) -> str:
    if ftype == "checkbox":
        return "Yes" if value else "No"
    if ftype == "multiselect" and isinstance(value, list):
        return ", ".join(str(v) for v in value if v not in (None, ""))
    if isinstance(value, list):
        return ", ".join(str(v) for v in value if v not in (None, ""))
    if value is None:
        return ""
    return str(value).strip()


def _is_empty_value(value: Any, ftype: str) -> bool:
    if value is None:
        return True
    if ftype == "checkbox":
        return False
    if ftype == "richtext":
        return not tiptap_to_text(value).strip()
    if isinstance(value, str):
        return not value.strip()
    if isinstance(value, list):
        return len(value) == 0
    if isinstance(value, dict):
        return not value
    return False


def _field_sort_key(field: dict[str, Any]) -> tuple:
    order = field.get("order")
    fid = str(field.get("id") or "")
    if isinstance(order, (int, float)) and not isinstance(order, bool):
        return (int(order), 0, fid)
    s = str(order or "").strip()
    m = re.match(r"^(\d+)([a-zA-Z]*)$", s)
    if not m:
        return (10**9, 0, fid)
    row = int(m.group(1))
    letters = (m.group(2) or "a").lower()
    col = 0
    for ch in letters:
        col = col * 26 + (ord(ch) - 96)
    col = max(0, col - 1)
    return (row, col, fid)


def _ticket_sort_key(key: str) -> tuple:
    if not key:
        return (1, ())
    parts = tuple(int(p) if p.isdigit() else p.lower() for p in re.split(r"(\d+)", key) if p)
    return (0, parts)


def tiptap_to_text(doc: Any) -> str:
    return _render_node(doc, markdown=False).strip()


def tiptap_to_markdown(doc: Any) -> str:
    return _render_node(doc, markdown=True).strip()


def _render_node(node: Any, *, markdown: bool, list_depth: int = 0, ordered_index: int | None = None) -> str:
    if node is None:
        return ""
    if isinstance(node, str):
        return node
    if isinstance(node, list):
        return "".join(
            _render_node(n, markdown=markdown, list_depth=list_depth) for n in node
        )
    if not isinstance(node, dict):
        return str(node)

    ntype = node.get("type") or ""
    content = node.get("content") or []
    attrs = node.get("attrs") or {}

    if ntype == "text":
        text = node.get("text") or ""
        if not markdown:
            return text
        for mark in reversed(node.get("marks") or []):
            mtype = (mark or {}).get("type")
            if mtype in ("bold", "strong"):
                text = f"**{text}**"
            elif mtype in ("italic", "em"):
                text = f"*{text}*"
            elif mtype == "strike":
                text = f"~~{text}~~"
            elif mtype == "code":
                text = f"`{text}`"
            elif mtype == "link":
                href = ((mark or {}).get("attrs") or {}).get("href") or ""
                text = f"[{text}]({href})" if href else text
        return text

    if ntype == "hardBreak":
        return "\n"

    if ntype == "horizontalRule":
        return "\n---\n" if markdown else "\n----\n"

    inner = "".join(
        _render_node(n, markdown=markdown, list_depth=list_depth) for n in content
    )

    if ntype in ("doc",):
        blocks = [
            _render_node(n, markdown=markdown, list_depth=list_depth).rstrip()
            for n in content
        ]
        return "\n\n".join(b for b in blocks if b)

    if ntype == "paragraph":
        return inner

    if ntype == "heading":
        level = int(attrs.get("level") or 1)
        level = min(6, max(1, level))
        if markdown:
            return f"{'#' * level} {inner}".rstrip()
        return inner

    if ntype == "blockquote":
        body = _render_node({"type": "doc", "content": content}, markdown=markdown)
        quoted = "\n".join(f"> {row}" if markdown else f"    {row}" for row in body.splitlines())
        return quoted

    if ntype == "codeBlock":
        body = inner
        if markdown:
            return f"```\n{body}\n```"
        return body

    if ntype == "bulletList":
        rows = [
            _render_node(n, markdown=markdown, list_depth=list_depth, ordered_index=None)
            for n in content
        ]
        return "\n".join(r for r in rows if r)

    if ntype == "orderedList":
        rows = []
        start = int(attrs.get("start") or 1)
        for i, child in enumerate(content, start=start):
            rows.append(
                _render_node(child, markdown=markdown, list_depth=list_depth, ordered_index=i)
            )
        return "\n".join(r for r in rows if r)

    if ntype == "listItem":
        indent = "  " * list_depth
        bullet = f"{ordered_index}." if ordered_index is not None else "-"
        parts: list[str] = []
        first = True
        for child in content:
            ctype = child.get("type") if isinstance(child, dict) else ""
            if ctype in ("bulletList", "orderedList"):
                nested = _render_node(child, markdown=markdown, list_depth=list_depth + 1)
                if nested:
                    parts.append(nested)
                continue
            chunk = _render_node(child, markdown=markdown, list_depth=list_depth).strip()
            if not chunk:
                continue
            if first:
                parts.append(f"{indent}{bullet} {chunk}")
                first = False
            else:
                parts.append(f"{indent}  {chunk}")
        return "\n".join(parts)

    return inner


def _write_text(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if not content.endswith("\n"):
        content += "\n"
    tmp = path.with_suffix(path.suffix + ".tmp")
    # utf-8-sig so Windows Notepad detects encoding.
    with tmp.open("w", encoding="utf-8-sig", newline="\n") as f:
        f.write(content)
        f.flush()
        os.fsync(f.fileno())
    os.replace(tmp, path)


def _read_hash(folder: Path) -> str | None:
    path = folder / HASH_NAME
    if not path.is_file():
        return None
    try:
        return path.read_text(encoding="utf-8").strip() or None
    except OSError:
        return None


def _write_hash(folder: Path, digest: str) -> None:
    path = folder / HASH_NAME
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(digest + "\n", encoding="utf-8")
    os.replace(tmp, path)
