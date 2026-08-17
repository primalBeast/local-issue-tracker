"""Per-project SQLite items store (sync sqlite3 + to_thread)."""

from __future__ import annotations

import asyncio
import json
import sqlite3
import threading
import uuid
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Iterator, TypeVar

from lit.storage.migrations import apply_migrations

T = TypeVar("T")

_lock_registry: dict[str, threading.RLock] = {}
_registry_guard = threading.Lock()
_connections: dict[str, sqlite3.Connection] = {}


def _now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _project_lock(db_path: str) -> threading.RLock:
    with _registry_guard:
        if db_path not in _lock_registry:
            _lock_registry[db_path] = threading.RLock()
        return _lock_registry[db_path]


@contextmanager
def _conn(db_path: Path) -> Iterator[sqlite3.Connection]:
    key = str(db_path.resolve())
    lock = _project_lock(key)
    with lock:
        if key not in _connections:
            db_path.parent.mkdir(parents=True, exist_ok=True)
            c = sqlite3.connect(str(db_path), check_same_thread=False)
            c.row_factory = sqlite3.Row
            apply_migrations(c)
            _connections[key] = c
        yield _connections[key]


def close_all() -> None:
    with _registry_guard:
        for c in _connections.values():
            try:
                c.close()
            except Exception:
                pass
        _connections.clear()


def run_db(db_path: Path, fn: Callable[[sqlite3.Connection], T]) -> T:
    with _conn(db_path) as conn:
        return fn(conn)


async def run_db_async(db_path: Path, fn: Callable[[sqlite3.Connection], T]) -> T:
    return await asyncio.to_thread(run_db, db_path, fn)


def items_db_path(project_path: Path) -> Path:
    return project_path / "items.sqlite"


def _hydrate_waiting_since(item: dict[str, Any]) -> None:
    started = (item.get("waiting") or {}).get("current_started_at")
    if started:
        item.setdefault("fields", {})["waiting_since"] = str(started)[:10]


def _row_to_item(row: sqlite3.Row, fields: dict[str, Any] | None = None) -> dict[str, Any]:
    data = fields if fields is not None else json.loads(row["fields_json"])
    return {
        "id": row["id"],
        "sort_key": row["sort_key"],
        "fields": data,
        "created_at": row["created_at"],
        "updated_at": row["updated_at"],
        "version": row["version"],
    }


LEAN_OMIT_TYPES = frozenset({"richtext", "textarea"})


def lean_fields(fields: dict[str, Any], field_defs: list[dict[str, Any]]) -> dict[str, Any]:
    omit = {f["id"] for f in field_defs if f.get("type") in LEAN_OMIT_TYPES}
    return {k: v for k, v in fields.items() if k not in omit}


def list_waiting_for_items(
    conn: sqlite3.Connection, item_ids: list[str]
) -> dict[str, list[dict[str, Any]]]:
    if not item_ids:
        return {}
    out: dict[str, list[dict[str, Any]]] = {i: [] for i in item_ids}
    placeholders = ",".join("?" * len(item_ids))
    rows = conn.execute(
        f"SELECT * FROM waiting_periods WHERE item_id IN ({placeholders}) ORDER BY started_at",
        item_ids,
    ).fetchall()
    for r in rows:
        out[r["item_id"]].append(
            {
                "id": r["id"],
                "item_id": r["item_id"],
                "started_at": r["started_at"],
                "ended_at": r["ended_at"],
                "waiting_for": r["waiting_for"],
                "reason": r["reason"],
                "created_at": r["created_at"],
            }
        )
    return out


def compute_waiting_summary(
    periods: list[dict[str, Any]], *, include_history: bool
) -> dict[str, Any]:
    now = datetime.now(timezone.utc)

    def parse_ts(s: str | None) -> datetime | None:
        if not s:
            return None
        s2 = s.replace("Z", "+00:00")
        return datetime.fromisoformat(s2)

    open_period = next((p for p in periods if p.get("ended_at") is None), None)
    total = 0.0
    for p in periods:
        start = parse_ts(p["started_at"])
        end = parse_ts(p.get("ended_at")) or now
        if start:
            total += max(0.0, (end - start).total_seconds())

    current_started = open_period["started_at"] if open_period else None
    current_seconds = None
    if open_period:
        start = parse_ts(open_period["started_at"])
        if start:
            current_seconds = max(0.0, (now - start).total_seconds())

    result: dict[str, Any] = {
        "is_waiting": open_period is not None,
        "current_started_at": current_started,
        "current_seconds": current_seconds,
        "total_seconds": total,
    }
    if include_history:
        result["history"] = periods
    return result


def list_items(
    conn: sqlite3.Connection,
    field_defs: list[dict[str, Any]],
    *,
    lean: bool = True,
) -> list[dict[str, Any]]:
    rows = conn.execute("SELECT * FROM items ORDER BY sort_key, created_at").fetchall()
    ids = [r["id"] for r in rows]
    waiting_map = list_waiting_for_items(conn, ids)
    items = []
    for r in rows:
        fields = json.loads(r["fields_json"])
        if lean:
            fields = lean_fields(fields, field_defs)
        item = _row_to_item(r, fields)
        item["waiting"] = compute_waiting_summary(waiting_map.get(r["id"], []), include_history=False)
        _hydrate_waiting_since(item)
        items.append(item)
    return items


def get_item(conn: sqlite3.Connection, item_id: str) -> dict[str, Any] | None:
    row = conn.execute("SELECT * FROM items WHERE id=?", (item_id,)).fetchone()
    if not row:
        return None
    periods = list_waiting_for_items(conn, [item_id]).get(item_id, [])
    item = _row_to_item(row)
    item["waiting"] = compute_waiting_summary(periods, include_history=True)
    _hydrate_waiting_since(item)
    return item


def create_item(
    conn: sqlite3.Connection,
    fields: dict[str, Any],
    sort_key: float = 0,
) -> dict[str, Any]:
    item_id = str(uuid.uuid4())
    now = _now()
    conn.execute(
        "INSERT INTO items(id, sort_key, fields_json, created_at, updated_at, version) "
        "VALUES(?,?,?,?,?,1)",
        (item_id, sort_key, json.dumps(fields, ensure_ascii=False), now, now),
    )
    conn.commit()
    return get_item(conn, item_id)  # type: ignore[return-value]


def update_item_fields(
    conn: sqlite3.Connection,
    item_id: str,
    fields: dict[str, Any],
    version: int | None,
) -> dict[str, Any]:
    row = conn.execute("SELECT * FROM items WHERE id=?", (item_id,)).fetchone()
    if not row:
        raise KeyError(item_id)
    if version is not None and row["version"] != version:
        raise ConflictError(row["version"])
    now = _now()
    new_version = row["version"] + 1
    conn.execute(
        "UPDATE items SET fields_json=?, updated_at=?, version=? WHERE id=?",
        (json.dumps(fields, ensure_ascii=False), now, new_version, item_id),
    )
    conn.commit()
    return get_item(conn, item_id)  # type: ignore[return-value]


def delete_item(conn: sqlite3.Connection, item_id: str) -> bool:
    cur = conn.execute("DELETE FROM items WHERE id=?", (item_id,))
    conn.commit()
    return cur.rowcount > 0


def checkpoint(conn: sqlite3.Connection) -> None:
    conn.execute("PRAGMA wal_checkpoint(TRUNCATE)")


class ConflictError(Exception):
    def __init__(self, current_version: int) -> None:
        self.current_version = current_version
        super().__init__(f"Version conflict; current version is {current_version}")
