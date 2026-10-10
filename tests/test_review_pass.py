"""Security follow-ups and the desk features from the October 2026 review."""

from __future__ import annotations

from datetime import date
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from lit.security import MAX_BODY_BYTES, normalize_url_prefix, safe_dist_file
from lit.services.standup import build_standup, copy_ticket_key


@pytest.fixture()
def client(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    data = tmp_path / "data"
    data.mkdir()
    monkeypatch.setenv("LIT_DATA_DIR", str(data))

    from lit.config import AppConfig, set_config
    from lit.storage.project_fs import ensure_data_layout, maybe_seed_sample

    set_config(AppConfig(data_dir=data, host="127.0.0.1", port=8765))
    ensure_data_layout()
    maybe_seed_sample()

    from lit.app import create_app

    app = create_app()
    with TestClient(app, base_url="http://127.0.0.1:8765") as c:
        yield c


def _slug(client: TestClient) -> str:
    return client.get("/api/projects").json()[0]["slug"]


def test_openapi_is_not_published(client: TestClient):
    docs = client.get("/api/docs")
    assert docs.status_code == 404
    spec = client.get("/openapi.json")
    assert '"openapi"' not in spec.text
    health = client.get("/health")
    assert health.headers["x-content-type-options"] == "nosniff"
    assert "object-src 'none'" in health.headers["content-security-policy"]
    assert health.headers["cross-origin-resource-policy"] == "same-origin"


def test_rejects_non_json_writes_and_huge_bodies(client: TestClient):
    slug = _slug(client)
    plain = client.post(
        f"/api/projects/{slug}/open-folder",
        content=b"name=x",
        headers={"Content-Type": "text/plain"},
    )
    assert plain.status_code == 415
    huge = client.post(
        "/api/settings",
        content=b"{" + b"x" * (MAX_BODY_BYTES + 8),
        headers={"Content-Type": "application/json"},
    )
    assert huge.status_code == 413


def test_chunked_body_over_the_cap_is_refused():
    """Omitting Content-Length must not bypass the 4 MB cap."""
    import asyncio

    from lit.middleware import BodyLimitMiddleware

    called = False

    async def app(scope, receive, send):
        nonlocal called
        called = True

    mw = BodyLimitMiddleware(app, max_bytes=100)
    started: list[dict] = []

    async def send(message):
        started.append(message)

    pieces = [b"x" * 60, b"y" * 60]
    index = 0

    async def receive():
        nonlocal index
        if index >= len(pieces):
            return {"type": "http.disconnect"}
        chunk = pieces[index]
        index += 1
        return {"type": "http.request", "body": chunk, "more_body": index < len(pieces)}

    async def run():
        await mw({"type": "http", "headers": []}, receive, send)

    asyncio.run(run())
    assert called is False
    assert started[0]["status"] == 413


def test_url_prefix_rejects_scripts_and_userinfo(client: TestClient):
    slug = _slug(client)
    for bad in ("javascript:alert(1)", "file:///tmp/x", "http://user:pass@jira.example/browse/"):
        got = client.patch(f"/api/projects/{slug}", json={"url_prefix": bad})
        assert got.status_code == 400, bad
    assert normalize_url_prefix("  https://jira.example/browse/ ") == "https://jira.example/browse/"
    assert normalize_url_prefix("   ") == ""


def test_settings_reject_path_tricks_and_ignore_seed_flag(client: TestClient):
    before = client.get("/api/settings").json()
    assert before["seeded_sample"] is True
    kept = client.patch("/api/settings", json={"seeded_sample": False, "theme": "aurora"})
    assert kept.status_code == 200
    assert kept.json()["seeded_sample"] is True
    assert kept.json()["theme"] == "aurora"
    bad = client.patch("/api/settings", json={"theme": "../secrets"})
    assert bad.status_code == 422
    bad_days = client.patch("/api/settings", json={"backup_retention_days": 0})
    assert bad_days.status_code == 422


def test_tab_color_cannot_inject_css(client: TestClient):
    slug = _slug(client)
    ws = client.get(f"/api/projects/{slug}/workspaces").json()[0]
    ws["tab_color"] = "red;background:url(https://evil.example)"
    saved = client.put(f"/api/projects/{slug}/workspaces/{ws['id']}", json=ws)
    assert saved.status_code == 200
    assert saved.json()["tab_color"] is None
    ws["tab_color"] = "#3B82F6"
    saved = client.put(f"/api/projects/{slug}/workspaces/{ws['id']}", json=ws)
    assert saved.json()["tab_color"] == "#3b82f6"


def test_static_file_stays_inside_dist(tmp_path: Path):
    dist = tmp_path / "dist"
    (dist / "themes").mkdir(parents=True)
    (dist / "themes" / "hut.jpg").write_bytes(b"jpg")
    secret = tmp_path / "secret.txt"
    secret.write_text("nope", encoding="utf-8")
    link = dist / "themes" / "leak.jpg"
    link.symlink_to(secret)
    assert safe_dist_file(dist, "themes/hut.jpg") == (dist / "themes" / "hut.jpg").resolve()
    assert safe_dist_file(dist, "themes/leak.jpg") is None
    assert safe_dist_file(dist, "themes/../../secret.txt") is None
    assert safe_dist_file(dist, "themes/app.py") is None
    assert safe_dist_file(dist, "/etc/passwd") is None


def test_backup_skips_symlink(client: TestClient):
    from lit.storage.backup import backup_project, local_today
    from lit.paths import project_dir

    slug = _slug(client)
    root = project_dir(slug)
    secret = root.parent / "secret.json"
    secret.write_text("SECRET", encoding="utf-8")
    link = root / "workspaces" / "ws-leak.json"
    try:
        link.symlink_to(secret)
    except OSError:
        pytest.skip("symlinks are not available")
    manifest = backup_project(slug, force=True)
    assert manifest is not None
    copied = root / "backups" / local_today() / "workspaces"
    assert (copied / "ws-main.json").is_file()
    assert not (copied / "ws-leak.json").exists()
    blob = "\n".join(p.read_text(encoding="utf-8", errors="replace") for p in copied.glob("*.json"))
    assert "SECRET" not in blob


def test_item_id_and_oversized_text(client: TestClient):
    slug = _slug(client)
    assert client.get(f"/api/projects/{slug}/items/a.b").status_code == 400
    too_big = client.post(
        f"/api/projects/{slug}/items",
        json={
            "fields": {
                "ticket_key": "BIG-1",
                "title": "x" * 200_001,
                "priority": 1,
                "state": "Submitted",
            }
        },
    )
    assert too_big.status_code == 422


def test_duplicate_export_standup_and_due_pin(client: TestClient):
    slug = _slug(client)
    fields = client.get(f"/api/projects/{slug}/fields").json()
    ids = {field["id"] for field in fields["fields"]}
    assert "pinned" in ids
    assert "due_on" in ids
    created = client.post(
        f"/api/projects/{slug}/items",
        json={
            "fields": {
                "ticket_key": "SHOP-9",
                "title": "Drawer jam",
                "priority": 2,
                "urgency": 3,
                "state": "In fixing",
                "due_on": "2020-01-01",
                "pinned": True,
            }
        },
    )
    assert created.status_code == 201, created.text
    item_id = created.json()["id"]
    copied = client.post(f"/api/projects/{slug}/items/{item_id}/duplicate")
    assert copied.status_code == 201, copied.text
    body = copied.json()
    assert body["id"] != item_id
    assert body["fields"]["ticket_key"] == "SHOP-9-copy"
    assert body["fields"]["title"] == "Drawer jam (copy)"
    assert body["fields"]["pinned"] is False
    assert body["fields"]["due_on"] == "2020-01-01"

    exported = client.get(f"/api/projects/{slug}/export")
    assert exported.status_code == 200
    assert "attachment" in exported.headers["content-disposition"]
    payload = exported.json()
    assert "data_path" not in payload["project"]
    assert any(item["fields"]["ticket_key"] == "SHOP-9" for item in payload["items"])

    standup = client.get(f"/api/projects/{slug}/standup")
    assert standup.status_code == 200
    text = standup.json()["text"]
    assert "SHOP-9" in text
    assert "Overdue" in text
    assert "Drawer jam" in text


def test_standup_text_and_copy_key():
    text = build_standup(
        "Shop",
        [
            {
                "fields": {
                    "ticket_key": "A-1",
                    "title": "Open",
                    "state": "Submitted",
                    "priority": 4,
                    "due_on": "2026-10-01",
                },
                "waiting": {"is_waiting": False},
            },
            {
                "fields": {"ticket_key": "A-2", "title": "Finished", "state": "Done"},
                "waiting": {"is_waiting": False},
            },
        ],
        today=date(2026, 10, 10),
    )
    assert "A-1" in text
    assert "A-2" not in text
    assert "Overdue" in text
    assert copy_ticket_key({"A-1", "A-1-copy"}, "A-1") == "A-1-copy-2"


def test_notes_must_be_a_document(client: TestClient):
    slug = _slug(client)
    bad = client.put(f"/api/projects/{slug}/notes", json={"content": "<script>alert(1)</script>"})
    assert bad.status_code == 422
