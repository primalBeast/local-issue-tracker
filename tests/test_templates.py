"""User-saved templates for new projects."""

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


def test_list_includes_shipped_issue_tracker(client: TestClient):
    body = client.get("/api/templates").json()
    ids = {t["id"] for t in body["templates"]}
    assert "issue-tracker" in ids
    assert body["default"] == "issue-tracker"
    shipped = next(t for t in body["templates"] if t["id"] == "issue-tracker")
    assert shipped["origin"] == "shipped"
    assert shipped["editable"] is False


def test_save_as_template_and_create_project(client: TestClient):
    slug = client.get("/api/projects").json()[0]["slug"]
    fields = client.get(f"/api/projects/{slug}/fields").json()
    waiting = next(f for f in fields["fields"] if f["id"] == "waiting")
    waiting["label"] = "Blocked on"
    assert client.put(f"/api/projects/{slug}/fields", json=fields).status_code == 200

    saved = client.post(
        "/api/templates",
        json={
            "from_project": slug,
            "id": "blocked-tracker",
            "name": "Blocked Tracker",
            "set_default": True,
            "include_layout": True,
        },
    )
    assert saved.status_code == 201, saved.text
    assert saved.json()["id"] == "blocked-tracker"
    assert saved.json()["origin"] == "user"
    assert saved.json()["is_default"] is True

    listed = client.get("/api/templates").json()
    assert listed["default"] == "blocked-tracker"
    user = next(t for t in listed["templates"] if t["id"] == "blocked-tracker")
    assert user["editable"] is True

    created = client.post(
        "/api/projects",
        json={"slug": "from-tpl", "name": "From Template"},
    )
    assert created.status_code == 201, created.text
    new_fields = client.get("/api/projects/from-tpl/fields").json()
    label = next(f for f in new_fields["fields"] if f["id"] == "waiting")["label"]
    assert label == "Blocked on"

    named = client.post(
        "/api/projects",
        json={"slug": "from-shipped", "name": "Shipped", "template": "issue-tracker"},
    )
    assert named.status_code == 201, named.text
    shipped_fields = client.get("/api/projects/from-shipped/fields").json()
    shipped_label = next(f for f in shipped_fields["fields"] if f["id"] == "waiting")["label"]
    assert shipped_label == "Waiting for..."


def test_user_template_fields_round_trip(client: TestClient):
    slug = client.get("/api/projects").json()[0]["slug"]
    assert (
        client.post(
            "/api/templates",
            json={"from_project": slug, "id": "mine", "name": "Mine"},
        ).status_code
        == 201
    )
    fields = client.get("/api/templates/mine/fields").json()
    assert "waiting" in {f["id"] for f in fields["fields"]}
    fields["fields"][0]["label"] = "Renamed"
    assert client.put("/api/templates/mine/fields", json=fields).status_code == 200
    again = client.get("/api/templates/mine/fields").json()
    assert again["fields"][0]["label"] == "Renamed"
