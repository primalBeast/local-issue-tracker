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
    assert "urgency" in ids
    assert "waiting_since" in ids
    by_id = {f["id"]: f for f in fields["fields"]}
    assert by_id["priority"]["order"] == "30a"
    assert by_id["urgency"]["order"] == "30b"
    assert by_id["state"]["order"] == "30c"


def test_item_crud_and_lean_list(client: TestClient):
    slug = client.get("/api/projects").json()[0]["slug"]
    created = client.post(
        f"/api/projects/{slug}/items",
        json={"fields": {"ticket_key": "ABC-1", "title": "Test", "priority": 3, "state": "Submitted"}},
    )
    assert created.status_code == 201, created.text
    item = created.json()
    assert item["fields"]["ticket_key"] == "ABC-1"

    wide = client.post(
        f"/api/projects/{slug}/items",
        json={"fields": {"ticket_key": "ABC-99", "title": "Wide", "priority": 42, "urgency": 0, "state": "Submitted"}},
    )
    assert wide.status_code == 201, wide.text
    assert wide.json()["fields"]["priority"] == 42
    assert wide.json()["fields"]["urgency"] == 0
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

    ws = client.get(f"/api/projects/{slug}/workspaces").json()[0]
    ws["panels"] = [
        {
            "id": "panel-del",
            "kind": "item",
            "item_id": item_id,
            "x": 0,
            "y": 0,
            "width": 400,
            "height": 300,
            "z_index": 1,
        }
    ]
    assert client.put(f"/api/projects/{slug}/workspaces/{ws['id']}", json=ws).status_code == 200
    deleted = client.delete(f"/api/projects/{slug}/items/{item_id}")
    assert deleted.status_code == 200, deleted.text
    assert all(x["id"] != item_id for x in client.get(f"/api/projects/{slug}/items").json())
    after = client.get(f"/api/projects/{slug}/workspaces/{ws['id']}").json()
    assert all(p.get("item_id") != item_id for p in after.get("panels") or [])


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
    assert body["fields"].get("waiting_since") == body["waiting"]["current_started_at"][:10]

    dated = client.patch(
        f"/api/projects/{slug}/items/{item_id}",
        json={"fields": {"waiting_since": "2024-01-15"}, "version": body["version"]},
    )
    assert dated.status_code == 200, dated.text
    body = dated.json()
    assert body["fields"]["waiting_since"] == "2024-01-15"
    assert body["waiting"]["current_started_at"].startswith("2024-01-15")

    done = client.patch(
        f"/api/projects/{slug}/items/{item_id}",
        json={"fields": {"state": "In fixing"}, "version": body["version"]},
    )
    assert done.status_code == 200
    body2 = done.json()
    assert body2["waiting"]["is_waiting"] is False
    assert body2["waiting"]["total_seconds"] >= 0
    assert len(body2["waiting"]["history"]) >= 1


def test_theme_setting_round_trip(client: TestClient):
    got = client.get("/api/settings")
    assert got.status_code == 200
    assert got.json()["theme"] == "dark"
    assert got.json()["transparent_panels"] is False
    patched = client.patch(
        "/api/settings", json={"theme": "aurora", "transparent_panels": True}
    )
    assert patched.status_code == 200
    assert patched.json()["theme"] == "aurora"
    assert patched.json()["transparent_panels"] is True
    again = client.get("/api/settings")
    assert again.json()["theme"] == "aurora"
    assert again.json()["transparent_panels"] is True
    by_theme = client.patch(
        "/api/settings", json={"transparency_by_theme": {"aurora": 0.35, "ember": 2}}
    )
    assert by_theme.status_code == 200
    assert by_theme.json()["transparency_by_theme"]["aurora"] == 0.35
    assert by_theme.json()["transparency_by_theme"]["ember"] == 1.0


def test_open_project_folder(client: TestClient, monkeypatch: pytest.MonkeyPatch):
    opened: list[str] = []
    monkeypatch.setattr(
        "lit.api.projects.reveal_folder",
        lambda path: opened.append(str(path)),
    )
    slug = client.get("/api/projects").json()[0]["slug"]
    r = client.post(f"/api/projects/{slug}/open-folder")
    assert r.status_code == 200, r.text
    assert r.json()["status"] == "opened"
    assert opened and opened[0].replace("\\", "/").endswith(f"/{slug}")
    missing = client.post("/api/projects/no-such-project/open-folder")
    assert missing.status_code == 404


def test_workspace_lww(client: TestClient):
    slug = client.get("/api/projects").json()[0]["slug"]
    ws_list = client.get(f"/api/projects/{slug}/workspaces").json()
    assert ws_list
    ws = ws_list[0]
    ws["ui"]["zoom"] = 0.8
    ws["ui"]["theme"] = "ember"
    ws["ui"]["transparent_panels"] = True
    saved = client.put(f"/api/projects/{slug}/workspaces/{ws['id']}", json=ws)
    assert saved.status_code == 200
    assert saved.json()["ui"]["zoom"] == 0.8
    assert saved.json()["ui"]["theme"] == "ember"
    assert saved.json()["ui"]["transparent_panels"] is True
    again = client.get(f"/api/projects/{slug}/workspaces/{ws['id']}")
    assert again.json()["ui"]["theme"] == "ember"


def test_project_name_and_ticket_prefix(client: TestClient):
    slug = client.get("/api/projects").json()[0]["slug"]
    got = client.get(f"/api/projects/{slug}")
    assert got.status_code == 200
    assert got.json()["ticket_prefix"] == "NEW-"
    assert got.json()["data_path"].replace("\\", "/").endswith(f"/{slug}")
    patched = client.patch(
        f"/api/projects/{slug}",
        json={"name": "Shop Tracker", "ticket_prefix": "SHOP-"},
    )
    assert patched.status_code == 200
    assert patched.json()["name"] == "Shop Tracker"
    assert patched.json()["ticket_prefix"] == "SHOP-"
    created = client.post(
        "/api/projects",
        json={"slug": "other-proj", "name": "Other", "ticket_prefix": "OT-"},
    )
    assert created.status_code == 201
    assert created.json()["name"] == "Other"
    assert created.json()["ticket_prefix"] == "OT-"
    settings = client.get("/api/settings").json()
    assert settings["ticket_prefix_by_project"]["other-proj"] == "OT-"


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
