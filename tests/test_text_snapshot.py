"""Hourly readable .txt/.md snapshots."""

from __future__ import annotations

from datetime import datetime, timedelta
from pathlib import Path

import pytest

from lit.config import AppConfig, set_config
from lit.storage import items_db
from lit.storage.project_fs import (
    create_project,
    ensure_data_layout,
    load_fields,
    project_dir,
    save_deliverables,
    save_notes,
)
from lit.storage.text_snapshot import (
    MAX_SNAPSHOTS,
    seconds_until_next_hour,
    snapshot_dir,
    snapshot_project,
    tiptap_to_markdown,
    tiptap_to_text,
)


@pytest.fixture()
def data_dir(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    data = tmp_path / "data"
    data.mkdir()
    monkeypatch.setenv("LIT_DATA_DIR", str(data))
    set_config(AppConfig(data_dir=data, host="127.0.0.1", port=8765))
    ensure_data_layout()
    return data


def _seed_ticket(slug: str, fields: dict) -> None:
    defs = load_fields(slug).get("fields") or []
    db = items_db.items_db_path(project_dir(slug))

    def _create(conn):
        return items_db.create_item(conn, fields)

    items_db.run_db(db, _create)
    # keep defs used so lean/full paths stay valid
    assert defs


def test_seconds_until_next_hour_aligns() -> None:
    now = datetime(2026, 8, 19, 14, 17, 30)
    wait = seconds_until_next_hour(now)
    assert abs(wait - (42 * 60 + 30)) < 0.01
    on_the_hour = datetime(2026, 8, 19, 15, 0, 0)
    assert seconds_until_next_hour(on_the_hour) == pytest.approx(3600, abs=0.1)


def test_tiptap_keeps_lists_and_marks() -> None:
    doc = {
        "type": "doc",
        "content": [
            {
                "type": "paragraph",
                "content": [
                    {"type": "text", "text": "Hello ", "marks": [{"type": "bold"}]},
                    {"type": "text", "text": "world", "marks": [{"type": "italic"}]},
                ],
            },
            {
                "type": "bulletList",
                "content": [
                    {
                        "type": "listItem",
                        "content": [
                            {
                                "type": "paragraph",
                                "content": [{"type": "text", "text": "one"}],
                            }
                        ],
                    },
                    {
                        "type": "listItem",
                        "content": [
                            {
                                "type": "paragraph",
                                "content": [{"type": "text", "text": "two"}],
                            }
                        ],
                    },
                ],
            },
        ],
    }
    md = tiptap_to_markdown(doc)
    assert "**Hello **" in md or "**Hello**" in md or "Hello" in md
    assert "*world*" in md
    assert "- one" in md
    assert "- two" in md
    plain = tiptap_to_text(doc)
    assert "Hello" in plain
    assert "world" in plain
    assert "one" in plain
    assert "**" not in plain


def test_snapshot_writes_txt_and_md_by_ticket(data_dir: Path) -> None:
    create_project("shop", name="Shop Tracker")
    _seed_ticket(
        "shop",
        {
            "ticket_key": "SHOP-10",
            "title": "Later ticket",
            "priority": 2,
            "state": "Submitted",
        },
    )
    _seed_ticket(
        "shop",
        {
            "ticket_key": "SHOP-2",
            "title": "Earlier ticket",
            "priority": 8,
            "state": "In QA",
            "notes": {
                "type": "doc",
                "content": [
                    {
                        "type": "paragraph",
                        "content": [
                            {"type": "text", "text": "Need ", "marks": []},
                            {"type": "text", "text": "repro", "marks": [{"type": "bold"}]},
                        ],
                    }
                ],
            },
        },
    )
    save_notes(
        "shop",
        {
            "schema_version": 1,
            "content": {
                "type": "doc",
                "content": [
                    {
                        "type": "paragraph",
                        "content": [{"type": "text", "text": "Board-level note"}],
                    }
                ],
            },
        },
    )
    save_deliverables(
        "shop",
        {"schema_version": 1, "items": [{"id": "d1", "title": "Ship it", "done": False, "notes": ""}]},
    )

    when = datetime(2026, 8, 19, 14, 7, 0)
    result = snapshot_project("shop", when=when)
    assert result is not None
    assert result["stem"] == "2026-08-19_1400"
    txt = Path(result["txt"])
    md = Path(result["md"])
    assert txt.is_file()
    assert md.is_file()
    raw = txt.read_bytes()
    assert raw.startswith(b"\xef\xbb\xbf")
    text = txt.read_text(encoding="utf-8-sig")
    markdown = md.read_text(encoding="utf-8-sig")
    assert text.index("SHOP-2") < text.index("SHOP-10")
    assert "Earlier ticket" in text
    assert "Need" in text and "repro" in text
    assert "Board-level note" in text
    assert "Ship it" in text
    assert "Customer Assigned To: (none)" in text
    assert "SHOP-2" in text and "SHOP-10" in text
    assert "# Shop Tracker" in markdown
    assert "**repro**" in markdown
    assert "### SHOP-2" in markdown


def test_skip_when_unchanged_then_write_full_snapshot_on_change(data_dir: Path) -> None:
    create_project("alpha", name="Alpha")
    _seed_ticket("alpha", {"ticket_key": "A-1", "title": "First", "priority": 1, "state": "Submitted"})
    _seed_ticket("alpha", {"ticket_key": "A-2", "title": "Second", "priority": 4, "state": "Done"})
    t0 = datetime(2026, 8, 19, 10, 0, 0)
    first = snapshot_project("alpha", when=t0)
    assert first is not None
    first_text = Path(first["txt"]).read_text(encoding="utf-8-sig")
    assert "A-1" in first_text and "A-2" in first_text
    assert snapshot_project("alpha", when=t0 + timedelta(hours=1)) is None
    assert list(snapshot_dir("alpha").glob("*.txt")) == [Path(first["txt"])]

    defs = load_fields("alpha").get("fields") or []
    db = items_db.items_db_path(project_dir("alpha"))

    def _bump(conn):
        items = items_db.list_items(conn, defs, lean=False)
        item = next(it for it in items if it["fields"].get("ticket_key") == "A-1")
        fields = dict(item["fields"])
        fields["title"] = "Changed"
        return items_db.update_item_fields(conn, item["id"], fields, item["version"])

    items_db.run_db(db, _bump)
    second = snapshot_project("alpha", when=t0 + timedelta(hours=2))
    assert second is not None
    assert second["stem"] == "2026-08-19_1200"
    later = Path(second["txt"]).read_text(encoding="utf-8-sig")
    assert "Changed" in later
    assert "A-2" in later
    assert "Second" in later


def test_retention_keeps_fifty_pairs(data_dir: Path) -> None:
    create_project("keep", name="Keep")
    _seed_ticket("keep", {"ticket_key": "K-1", "title": "One", "priority": 1, "state": "Submitted"})
    folder = snapshot_dir("keep")
    folder.mkdir(parents=True)
    start = datetime(2026, 1, 1, 0, 0, 0)
    for i in range(MAX_SNAPSHOTS):
        stem = (start + timedelta(hours=i)).strftime("%Y-%m-%d_%H%M")
        (folder / f"{stem}.txt").write_text("old\n", encoding="utf-8")
        (folder / f"{stem}.md").write_text("old\n", encoding="utf-8")

    result = snapshot_project("keep", force=True, when=datetime(2026, 8, 19, 14, 0, 0))
    assert result is not None
    stems = sorted(p.stem for p in folder.glob("*.txt"))
    assert len(stems) == MAX_SNAPSHOTS
    assert "2026-01-01_0000" not in stems
    assert "2026-08-19_1400" in stems
    assert not (folder / "2026-01-01_0000.md").exists()


def test_waiting_clock_does_not_write_another_file(data_dir: Path) -> None:
    create_project("wait", name="Wait")
    _seed_ticket(
        "wait",
        {
            "ticket_key": "W-1",
            "title": "Blocked",
            "priority": 1,
            "state": "Waiting For",
            "waiting_for": "Pat",
        },
    )
    first = snapshot_project("wait", when=datetime(2026, 8, 19, 10, 0, 0))
    assert first is not None
    assert snapshot_project("wait", when=datetime(2026, 8, 19, 11, 0, 0)) is None
