"""Waiting period transitions on state field changes."""

from __future__ import annotations

import sqlite3
import uuid
from datetime import datetime, timezone
from typing import Any


def _now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def get_open_period(conn: sqlite3.Connection, item_id: str) -> sqlite3.Row | None:
    return conn.execute(
        "SELECT * FROM waiting_periods WHERE item_id=? AND ended_at IS NULL LIMIT 1",
        (item_id,),
    ).fetchone()


def started_at_from_date(date_str: str, existing: str | None = None) -> str:
    """Build an ISO timestamp from a YYYY-MM-DD value, keeping time when possible."""
    day = str(date_str).strip()[:10]
    if len(day) < 10:
        return existing or _now()
    if existing and "T" in existing:
        timepart = existing.split("T", 1)[1]
    else:
        timepart = "00:00:00Z"
    return f"{day}T{timepart}"


def set_open_started_at(conn: sqlite3.Connection, item_id: str, date_str: str) -> None:
    open_p = get_open_period(conn, item_id)
    if not open_p:
        return
    started = started_at_from_date(date_str, open_p["started_at"])
    conn.execute(
        "UPDATE waiting_periods SET started_at=? WHERE id=?",
        (started, open_p["id"]),
    )


def apply_state_transition(
    conn: sqlite3.Connection,
    item_id: str,
    *,
    old_state: Any,
    new_state: Any,
    waiting_state_value: str,
    waiting_for: str | None = None,
    reason: str | None = None,
    started_on: str | None = None,
) -> None:
    """Open/close waiting periods when fields['state'] enters/leaves waiting_state_value."""
    was_waiting = old_state == waiting_state_value
    is_waiting = new_state == waiting_state_value
    now = _now()

    if was_waiting and not is_waiting:
        open_p = get_open_period(conn, item_id)
        if open_p:
            conn.execute(
                "UPDATE waiting_periods SET ended_at=? WHERE id=?",
                (now, open_p["id"]),
            )

    if not was_waiting and is_waiting:
        open_p = get_open_period(conn, item_id)
        if open_p:
            return
        start = started_at_from_date(started_on, now) if started_on else now
        conn.execute(
            "INSERT INTO waiting_periods(id, item_id, started_at, ended_at, waiting_for, reason, created_at) "
            "VALUES(?,?,?,NULL,?,?,?)",
            (
                str(uuid.uuid4()),
                item_id,
                start,
                waiting_for or "",
                reason or "",
                now,
            ),
        )

    if was_waiting and is_waiting:
        open_p = get_open_period(conn, item_id)
        if open_p and (waiting_for is not None or reason is not None):
            conn.execute(
                "UPDATE waiting_periods SET waiting_for=COALESCE(?, waiting_for), "
                "reason=COALESCE(?, reason) WHERE id=?",
                (waiting_for, reason, open_p["id"]),
            )
