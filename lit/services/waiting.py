"""Waiting period transitions on the waiting checkbox field."""

from __future__ import annotations

import sqlite3
import uuid
from datetime import date, datetime, timezone
from typing import Any

LEGACY_WAITING_STATE = "Waiting For"
WAITING_FALLBACK_STATE = "Submitted"
DONE_STATE = "Done"


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


def is_waiting_flag(fields: dict[str, Any] | None) -> bool:
    if not fields:
        return False
    if fields.get("state") == LEGACY_WAITING_STATE:
        return True
    return bool(fields.get("waiting"))


def normalize_waiting_fields(fields: dict[str, Any]) -> dict[str, Any]:
    """Coerce legacy Waiting For state and keep Done tickets from waiting."""
    out = dict(fields)
    if out.get("state") == LEGACY_WAITING_STATE:
        out["state"] = WAITING_FALLBACK_STATE
        out["waiting"] = True
    if out.get("state") == DONE_STATE:
        out["waiting"] = False
    if out.get("waiting") and not str(out.get("waiting_since") or "").strip():
        out["waiting_since"] = date.today().isoformat()
    return out


def apply_waiting_flag(
    conn: sqlite3.Connection,
    item_id: str,
    *,
    was_waiting: bool,
    is_waiting: bool,
    waiting_for: str | None = None,
    reason: str | None = None,
    started_on: str | None = None,
) -> None:
    """Open/close waiting periods when the waiting checkbox changes."""
    was_waiting = bool(was_waiting)
    is_waiting = bool(is_waiting)
    now = _now()

    if was_waiting and not is_waiting:
        open_p = get_open_period(conn, item_id)
        if open_p:
            conn.execute(
                "UPDATE waiting_periods SET ended_at=? WHERE id=?",
                (now, open_p["id"]),
            )

    if is_waiting:
        open_p = get_open_period(conn, item_id)
        if not open_p:
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
        elif waiting_for is not None or reason is not None:
            conn.execute(
                "UPDATE waiting_periods SET waiting_for=COALESCE(?, waiting_for), "
                "reason=COALESCE(?, reason) WHERE id=?",
                (waiting_for, reason, open_p["id"]),
            )
