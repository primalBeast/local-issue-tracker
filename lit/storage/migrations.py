"""Ordered SQLite schema migrations."""

from __future__ import annotations

import sqlite3

CURRENT_SCHEMA_VERSION = 1

MIGRATIONS: dict[int, str] = {
    1: """
PRAGMA foreign_keys=ON;

CREATE TABLE IF NOT EXISTS meta (
  key   TEXT PRIMARY KEY,
  value TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS items (
  id            TEXT PRIMARY KEY,
  sort_key      REAL NOT NULL DEFAULT 0,
  fields_json   TEXT NOT NULL,
  created_at    TEXT NOT NULL,
  updated_at    TEXT NOT NULL,
  version       INTEGER NOT NULL DEFAULT 1
);

CREATE TABLE IF NOT EXISTS waiting_periods (
  id            TEXT PRIMARY KEY,
  item_id       TEXT NOT NULL REFERENCES items(id) ON DELETE CASCADE,
  started_at    TEXT NOT NULL,
  ended_at      TEXT,
  waiting_for   TEXT,
  reason        TEXT,
  created_at    TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_waiting_item ON waiting_periods(item_id);
CREATE INDEX IF NOT EXISTS idx_waiting_open ON waiting_periods(item_id) WHERE ended_at IS NULL;
"""
}


def get_schema_version(conn: sqlite3.Connection) -> int:
    row = conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name='meta'"
    ).fetchone()
    if not row:
        return 0
    r = conn.execute("SELECT value FROM meta WHERE key='schema_version'").fetchone()
    if not r:
        return 0
    return int(r[0])


def apply_migrations(conn: sqlite3.Connection) -> int:
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    version = get_schema_version(conn)
    if version > CURRENT_SCHEMA_VERSION:
        raise RuntimeError(
            f"Database schema_version {version} is newer than app "
            f"({CURRENT_SCHEMA_VERSION}). Upgrade Local Issue Tracker."
        )
    for v in range(version + 1, CURRENT_SCHEMA_VERSION + 1):
        sql = MIGRATIONS.get(v)
        if not sql:
            raise RuntimeError(f"Missing migration for schema version {v}")
        conn.executescript(sql)
        conn.execute(
            "INSERT INTO meta(key, value) VALUES('schema_version', ?) "
            "ON CONFLICT(key) DO UPDATE SET value=excluded.value",
            (str(v),),
        )
        conn.commit()
    return CURRENT_SCHEMA_VERSION
