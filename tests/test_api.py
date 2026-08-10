"""API integration tests using temporary data dir."""

from __future__ import annotations

from pathlib import Path

import pytest
from fastapi.testclient import TestClient


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
    with TestClient(app) as c:
        yield c


def test_health(client: TestClient):
    r = client.get("/health")
    assert r.status_code == 200
    assert r.json()["status"] == "ok"


def test_seeded_project_and_fields(client: TestClient):
    r = client.get("/api/projects")
    assert r.status_code == 200
    projects = r.json()
    assert len(projects) >= 1
    slug = projects[0]["slug"]
    fields = client.get(f"/api/projects/{slug}/fields").json()
    ids = {f["id"] for f in fields["fields"]}
    assert "ticket_key" in ids
    assert "state" in ids
    assert "notes" in ids


def test_item_crud_and_lean_list(client: TestClient):
    slug = client.get("/api/projects").json()[0]["slug"]
    created = client.post(
        f"/api/projects/{slug}/items",
        json={"fields": {"ticket_key": "ABC-1", "title": "Test", "priority": 3, "state": "Submitted"}},
    )
    assert created.status_code == 201, created.text
    item = created.json()
    assert item["fields"]["ticket_key"] == "ABC-1"
    item_id = item["id"]

    patched = client.patch(
        f"/api/projects/{slug}/items/{item_id}",
        json={
            "fields": {"notes": {"type": "doc", "content": [{"type": "paragraph", "content": [{"type": "text", "text": "hi"}]}]}},
            "version": item["version"],
        },
    )
    assert patched.status_code == 200, patched.text

    lean = client.get(f"/api/projects/{slug}/items").json()
    match = next(x for x in lean if x["id"] == item_id)
    assert "notes" not in match["fields"]

    detail = client.get(f"/api/projects/{slug}/items/{item_id}").json()
    assert "notes" in detail["fields"]


def test_waiting_transition(client: TestClient):
    slug = client.get("/api/projects").json()[0]["slug"]
    created = client.post(
        f"/api/projects/{slug}/items",
        json={"fields": {"ticket_key": "W-1", "priority": 2, "state": "In fixing"}},
    ).json()
    item_id = created["id"]
    waiting = client.patch(
        f"/api/projects/{slug}/items/{item_id}",
        json={
            "fields": {"state": "Waiting For", "waiting_for": "Alice"},
            "version": created["version"],
        },
    )
    assert waiting.status_code == 200, waiting.text
    body = waiting.json()
    assert body["waiting"]["is_waiting"] is True
    assert body["waiting"]["current_started_at"]

    done = client.patch(
        f"/api/projects/{slug}/items/{item_id}",
        json={"fields": {"state": "In fixing"}, "version": body["version"]},
    )
    assert done.status_code == 200
    body2 = done.json()
    assert body2["waiting"]["is_waiting"] is False
    assert body2["waiting"]["total_seconds"] >= 0
    assert len(body2["waiting"]["history"]) >= 1


def test_workspace_lww(client: TestClient):
    slug = client.get("/api/projects").json()[0]["slug"]
    ws_list = client.get(f"/api/projects/{slug}/workspaces").json()
    assert ws_list
    ws = ws_list[0]
    ws["ui"]["zoom"] = 0.8
    saved = client.put(f"/api/projects/{slug}/workspaces/{ws['id']}", json=ws)
    assert saved.status_code == 200
    assert saved.json()["ui"]["zoom"] == 0.8


def test_delete_project_confirm(client: TestClient):
    created = client.post("/api/projects", json={"slug": "temp-proj", "name": "Temp"})
    assert created.status_code == 201
    bad = client.request(
        "DELETE",
        "/api/projects/temp-proj",
        json={"confirm_slug": "wrong"},
    )
    assert bad.status_code == 400
    ok = client.request(
        "DELETE",
        "/api/projects/temp-proj",
        json={"confirm_slug": "temp-proj"},
    )
    assert ok.status_code == 200
