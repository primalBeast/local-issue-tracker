"""Local boundary: workspace ids, Host allowlist, and Origin checks."""

from __future__ import annotations

import json
from contextlib import contextmanager
from pathlib import Path
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

# Ids that must never be joined onto the workspaces directory.
_BAD_WORKSPACE_IDS = [
    "..",
    "../x",
    "..\\x",
    "..\\..\\settings",
    "a/b",
    "C:\\evil",
    "C:evil",
    "\\\\host\\share\\x",
    "%5C..%5Cx",
    "x\x00y",
    "",
]

# Percent-encoded forms uvicorn would decode into the route parameter.
_BAD_WORKSPACE_URL_IDS = [
    "..%5C..%5Csettings",
    "C:%5Cevil",
    "%5C%5Chost%5Cshare%5Cx",
    "x%00y",
]


def _tree(root: Path) -> dict[str, bytes]:
    found: dict[str, bytes] = {}
    if not root.exists():
        return found
    for path in root.rglob("*"):
        if path.is_file():
            found[path.relative_to(root).as_posix()] = path.read_bytes()
    return found


@contextmanager
def _client(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    *,
    host: str = "127.0.0.1",
    port: int = 8765,
    dev_cors: bool = False,
    vite_port: int = 5173,
    seed: bool = True,
    base_url: str | None = None,
):
    data = tmp_path / "data"
    data.mkdir(exist_ok=True)
    monkeypatch.setenv("LIT_DATA_DIR", str(data))

    from lit.config import AppConfig, set_config
    from lit.storage.project_fs import ensure_data_layout, maybe_seed_sample

    set_config(
        AppConfig(
            data_dir=data,
            host=host,
            port=port,
            dev_cors=dev_cors,
            vite_port=vite_port,
        )
    )
    if seed:
        ensure_data_layout()
        maybe_seed_sample()

    from lit.app import create_app

    app = create_app()
    # Default TestClient host is "testserver", which is not on the allowlist.
    # Port 0 is an OS-assigned socket; base_url supplies the port the test scope reports.
    url = base_url or f"http://127.0.0.1:{port if port != 0 else 8765}"
    with TestClient(app, base_url=url) as c:
        yield c


@pytest.fixture()
def client(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    with _client(tmp_path, monkeypatch) as c:
        yield c


def _forbid_disk(name: str):
    def _boom(self, *args, **kwargs):
        raise AssertionError(f"{name} touched the filesystem: {self}")

    return _boom


def test_storage_rejects_workspace_id_traversal(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    """Bad ids raise ValueError before any filesystem access and write nothing."""
    data = tmp_path / "data"
    data.mkdir()
    monkeypatch.setenv("LIT_DATA_DIR", str(data))

    from lit.config import AppConfig, set_config
    from lit.storage.project_fs import delete_workspace, load_workspace, save_workspace

    set_config(AppConfig(data_dir=data, host="127.0.0.1", port=8765))
    sentinel = data / "sentinel.json"
    sentinel.write_text("untouched", encoding="utf-8")
    # Naive joins of the bad ids would land on these files.
    decoy_settings = data / "projects" / "settings.json"
    decoy_settings.parent.mkdir(parents=True)
    decoy_settings.write_text("settings-sentinel", encoding="utf-8")
    decoy_x = data / "projects" / "issue-tracker" / "x.json"
    decoy_x.parent.mkdir(parents=True)
    decoy_x.write_text("x-sentinel", encoding="utf-8")
    before = _tree(data)

    disk_methods = ("resolve", "exists", "mkdir", "unlink", "open")
    for workspace_id in _BAD_WORKSPACE_IDS:
        patches = [patch.object(Path, method, _forbid_disk(method)) for method in disk_methods]
        for item in patches:
            item.start()
        try:
            with pytest.raises(ValueError):
                load_workspace("issue-tracker", workspace_id)
            with pytest.raises(ValueError):
                save_workspace("issue-tracker", workspace_id, {"name": "pwn"})
            with pytest.raises(ValueError):
                delete_workspace("issue-tracker", workspace_id)
        finally:
            for item in reversed(patches):
                item.stop()

    assert _tree(data) == before
    assert sentinel.read_text(encoding="utf-8") == "untouched"
    assert decoy_settings.read_text(encoding="utf-8") == "settings-sentinel"
    assert decoy_x.read_text(encoding="utf-8") == "x-sentinel"

    saved = save_workspace("issue-tracker", "ws-main", {"name": "Main", "panels": []})
    assert saved["id"] == "ws-main"
    created = data / "projects" / "issue-tracker" / "workspaces" / "ws-main.json"
    assert created.is_file()
    extra = set(_tree(data)) - set(before)
    assert extra == {"projects/issue-tracker/workspaces/ws-main.json"}
    assert load_workspace("issue-tracker", "ws-main")["name"] == "Main"
    assert delete_workspace("issue-tracker", "ws-main") is True
    assert not created.exists()
    assert sentinel.read_text(encoding="utf-8") == "untouched"


def test_workspace_symlink_cannot_escape_directory(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    """A valid id whose file is a symlink still cannot read or write outside."""
    data = tmp_path / "data"
    data.mkdir()
    monkeypatch.setenv("LIT_DATA_DIR", str(data))

    from lit.config import AppConfig, set_config
    from lit.storage.project_fs import delete_workspace, load_workspace, save_workspace

    set_config(AppConfig(data_dir=data, host="127.0.0.1", port=8765))
    secret = data / "secret.json"
    secret.write_text("secret", encoding="utf-8")
    ws_dir = data / "projects" / "issue-tracker" / "workspaces"
    ws_dir.mkdir(parents=True)
    link = ws_dir / "ws-main.json"
    link.symlink_to(secret)

    with pytest.raises(ValueError):
        load_workspace("issue-tracker", "ws-main")
    with pytest.raises(ValueError):
        save_workspace("issue-tracker", "ws-main", {"name": "pwn"})
    with pytest.raises(ValueError):
        delete_workspace("issue-tracker", "ws-main")

    assert secret.read_text(encoding="utf-8") == "secret"
    assert link.is_symlink()


def test_strip_item_skips_bad_stored_workspace_id(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    data = tmp_path / "data"
    data.mkdir()
    monkeypatch.setenv("LIT_DATA_DIR", str(data))

    from lit.config import AppConfig, set_config
    from lit.storage.project_fs import strip_item_from_workspaces

    set_config(AppConfig(data_dir=data, host="127.0.0.1", port=8765))
    ws_dir = data / "projects" / "issue-tracker" / "workspaces"
    ws_dir.mkdir(parents=True)
    sentinel = data / "projects" / "settings.json"
    sentinel.write_text("settings-sentinel", encoding="utf-8")
    good = {"id": "ws-main", "name": "Main", "panels": [{"kind": "item", "item_id": "item-1"}]}
    bad = {"id": "..\\..\\settings", "name": "Bad", "panels": [{"kind": "item", "item_id": "item-1"}]}
    (ws_dir / "ws-main.json").write_text(json.dumps(good), encoding="utf-8")
    (ws_dir / "ws-evil.json").write_text(json.dumps(bad), encoding="utf-8")

    strip_item_from_workspaces("issue-tracker", "item-1")

    main = json.loads((ws_dir / "ws-main.json").read_text(encoding="utf-8"))
    evil = json.loads((ws_dir / "ws-evil.json").read_text(encoding="utf-8"))
    assert main["panels"] == []
    assert evil["panels"][0]["item_id"] == "item-1"
    assert sentinel.read_text(encoding="utf-8") == "settings-sentinel"
    assert not (data / "projects" / "issue-tracker" / "settings.json").exists()


def test_api_rejects_encoded_workspace_id_traversal(client: TestClient):
    from lit.config import get_config

    slug = client.get("/api/projects").json()[0]["slug"]
    data = get_config().data_dir
    sentinel = data / "sentinel-outside.json"
    sentinel.write_text("untouched", encoding="utf-8")
    before = _tree(data)

    for raw_id in _BAD_WORKSPACE_URL_IDS:
        url = f"/api/projects/{slug}/workspaces/{raw_id}"
        got = client.get(url)
        assert 400 <= got.status_code < 500, (raw_id, got.status_code, got.text)
        assert got.status_code != 500
        put = client.put(url, json={"name": "pwn", "panels": []})
        assert 400 <= put.status_code < 500, (raw_id, put.status_code, put.text)
        deleted = client.delete(url)
        assert 400 <= deleted.status_code < 500, (raw_id, deleted.status_code, deleted.text)

    assert _tree(data) == before
    assert sentinel.read_text(encoding="utf-8") == "untouched"


def test_generated_workspace_ids_round_trip(client: TestClient):
    import re

    from lit.storage.project_fs import WORKSPACE_ID_RE, list_workspaces

    assert WORKSPACE_ID_RE.fullmatch("ws-main")
    root = Path(__file__).resolve().parents[1]
    shipped = sorted((root / "lit" / "templates").glob("**/workspaces/*.json"))
    assert shipped
    for path in shipped:
        assert WORKSPACE_ID_RE.fullmatch(path.stem), path.name

    slug = client.get("/api/projects").json()[0]["slug"]
    stored = list_workspaces(slug)
    assert stored
    for ws in stored:
        assert WORKSPACE_ID_RE.fullmatch(str(ws.get("id")))
        loaded = client.get(f"/api/projects/{slug}/workspaces/{ws['id']}")
        assert loaded.status_code == 200, loaded.text

    created = client.post(f"/api/projects/{slug}/workspaces", json={"name": "Slice"})
    assert created.status_code == 201, created.text
    ws_id = created.json()["id"]
    assert re.fullmatch(r"ws-[0-9a-f]{8}", ws_id)
    assert WORKSPACE_ID_RE.fullmatch(ws_id)
    assert client.get(f"/api/projects/{slug}/workspaces/{ws_id}").status_code == 200
    body = created.json()
    body["name"] = "Slice 2"
    put = client.put(f"/api/projects/{slug}/workspaces/{ws_id}", json=body)
    assert put.status_code == 200, put.text
    assert put.json()["name"] == "Slice 2"
    assert put.json()["id"] == ws_id
    deleted = client.delete(f"/api/projects/{slug}/workspaces/{ws_id}")
    assert deleted.status_code == 200, deleted.text
    assert client.get(f"/api/projects/{slug}/workspaces/{ws_id}").status_code == 404


def test_untrusted_host_is_rejected(client: TestClient):
    slug = client.get("/api/projects").json()[0]["slug"]
    ws = client.get(f"/api/projects/{slug}/workspaces").json()[0]
    before_name = ws["name"]
    before_updated = ws.get("updated_at")
    foreign = {"Host": "attacker.example"}

    health = client.get("/health", headers=foreign)
    assert health.status_code == 400
    assert "Invalid host header" in health.text

    listing = client.get("/api/projects", headers=foreign)
    assert listing.status_code == 400

    put = client.put(
        f"/api/projects/{slug}/workspaces/{ws['id']}",
        json={"name": "hacked"},
        headers=foreign,
    )
    assert put.status_code == 400

    # Host is outermost: a foreign Host is 400 even when Origin would be 403.
    both = client.post(
        f"/api/projects/{slug}/open-folder",
        headers={"Host": "attacker.example", "Origin": "http://evil.example"},
    )
    assert both.status_code == 400

    again = client.get(f"/api/projects/{slug}/workspaces/{ws['id']}")
    assert again.status_code == 200
    assert again.json()["name"] == before_name
    assert again.json().get("updated_at") == before_updated

    # Production allowlist must not grow to include the TestClient default.
    assert client.get("/health", headers={"Host": "testserver"}).status_code == 400


def test_loopback_hosts_are_allowed(client: TestClient):
    for host in ("127.0.0.1", "127.0.0.1:8765", "localhost", "localhost:5173"):
        response = client.get("/health", headers={"Host": host})
        assert response.status_code == 200, (host, response.status_code, response.text)
        assert response.json()["status"] == "ok"
    api = client.get("/api/projects", headers={"Host": "localhost:5173"})
    assert api.status_code == 200, api.text


def test_ipv6_loopback_host_is_allowed(client: TestClient):
    """Starlette 1.7 keeps brackets on IPv6, so ``[::1]`` can be allowlisted.

    A bare ``::1`` Host header is not valid (the parser rejects it).
    """
    for host in ("[::1]", "[::1]:8765"):
        response = client.get("/health", headers={"Host": host})
        assert response.status_code == 200, (host, response.status_code, response.text)
    projects = client.get("/api/projects", headers={"Host": "[::1]:8765"})
    assert projects.status_code == 200, projects.text
    bare = client.get("/health", headers={"Host": "::1"})
    assert bare.status_code == 400


def test_configured_bind_host_allowlist(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setattr("lit.api.projects.reveal_folder", lambda path: None)
    with _client(tmp_path, monkeypatch, host="192.168.9.9") as bound:
        assert bound.get("/health", headers={"Host": "192.168.9.9"}).status_code == 200
        assert bound.get("/health", headers={"Host": "192.168.9.9:8765"}).status_code == 200
        assert bound.get("/health", headers={"Host": "10.1.2.3"}).status_code == 400
        assert bound.get("/health", headers={"Host": "0.0.0.0"}).status_code == 400
        assert bound.get("/health", headers={"Host": "127.0.0.1:8765"}).status_code == 200
        slug = bound.get("/api/projects").json()[0]["slug"]
        ok = bound.post(
            f"/api/projects/{slug}/open-folder",
            headers={"Origin": "http://192.168.9.9:8765"},
        )
        assert ok.status_code == 200, ok.text
        wrong_port = bound.post(
            f"/api/projects/{slug}/open-folder",
            headers={"Origin": "http://192.168.9.9:9090"},
        )
        assert wrong_port.status_code == 403, wrong_port.text
        blocked = bound.post(
            f"/api/projects/{slug}/open-folder",
            headers={"Origin": "http://10.1.2.3:8765"},
        )
        assert blocked.status_code == 403

    with _client(tmp_path, monkeypatch, host="0.0.0.0", seed=False) as wildcard:
        assert wildcard.get("/health", headers={"Host": "0.0.0.0"}).status_code == 400
        assert wildcard.get("/health", headers={"Host": "0.0.0.0:8765"}).status_code == 400
        assert wildcard.get("/health", headers={"Host": "10.1.2.3:8765"}).status_code == 400
        assert wildcard.get("/health", headers={"Host": "127.0.0.1"}).status_code == 200

    with _client(tmp_path, monkeypatch, host="::", seed=False) as wildcard_v6:
        assert wildcard_v6.get("/health", headers={"Host": "[::]"}).status_code == 400
        assert wildcard_v6.get("/health", headers={"Host": "[::]:8765"}).status_code == 400
        assert wildcard_v6.get("/health", headers={"Host": "[::1]"}).status_code == 200


def _patch_reveal(monkeypatch: pytest.MonkeyPatch) -> list[str]:
    opened: list[str] = []
    monkeypatch.setattr("lit.api.projects.reveal_folder", lambda path: opened.append(str(path)))
    return opened


def test_foreign_origin_does_not_open_folder(client: TestClient, monkeypatch: pytest.MonkeyPatch):
    opened = _patch_reveal(monkeypatch)
    slug = client.get("/api/projects").json()[0]["slug"]
    response = client.post(
        f"/api/projects/{slug}/open-folder",
        headers={"Origin": "http://evil.example"},
    )
    assert response.status_code == 403, response.text
    assert opened == []


def test_null_origin_does_not_open_folder(client: TestClient, monkeypatch: pytest.MonkeyPatch):
    opened = _patch_reveal(monkeypatch)
    slug = client.get("/api/projects").json()[0]["slug"]
    response = client.post(
        f"/api/projects/{slug}/open-folder",
        headers={"Origin": "null"},
    )
    assert response.status_code == 403, response.text
    assert opened == []
    disguised = client.post(
        f"/api/projects/{slug}/open-folder",
        headers={"Origin": "http://evil.example@127.0.0.1"},
    )
    assert disguised.status_code == 403, disguised.text
    assert opened == []


def test_foreign_origin_does_not_mutate_workspace(client: TestClient):
    slug = client.get("/api/projects").json()[0]["slug"]
    ws = client.get(f"/api/projects/{slug}/workspaces").json()[0]
    url = f"/api/projects/{slug}/workspaces/{ws['id']}"
    before = client.get(url).json()

    put = client.put(url, json={"name": "hacked", "panels": [{"id": "x"}]}, headers={"Origin": "http://evil.example"})
    assert put.status_code == 403, put.text
    after_put = client.get(url).json()
    assert after_put["name"] == before["name"]
    assert after_put.get("updated_at") == before.get("updated_at")
    assert after_put.get("panels") == before.get("panels")

    deleted = client.delete(url, headers={"Origin": "http://evil.example"})
    assert deleted.status_code == 403, deleted.text
    assert client.get(url).status_code == 200
    assert client.get(url).json()["name"] == before["name"]


def test_foreign_origin_blocks_patch(client: TestClient):
    slug = client.get("/api/projects").json()[0]["slug"]
    before = client.get(f"/api/projects/{slug}").json()["name"]
    patched = client.patch(
        f"/api/projects/{slug}",
        json={"name": "Hacked"},
        headers={"Origin": "http://evil.example"},
    )
    assert patched.status_code == 403, patched.text
    assert client.get(f"/api/projects/{slug}").json()["name"] == before


def test_missing_and_local_origins_can_open_folder(client: TestClient, monkeypatch: pytest.MonkeyPatch):
    opened = _patch_reveal(monkeypatch)
    slug = client.get("/api/projects").json()[0]["slug"]
    url = f"/api/projects/{slug}/open-folder"
    origins = [
        None,
        "http://127.0.0.1:8765",
        "http://localhost:8765",
        "http://[::1]:8765",
    ]
    for origin in origins:
        opened.clear()
        headers = {} if origin is None else {"Origin": origin}
        response = client.post(url, headers=headers)
        assert response.status_code == 200, (origin, response.status_code, response.text)
        assert response.json()["status"] == "opened"
        assert opened

    # GET is not subject to the origin check.
    health = client.get("/health", headers={"Origin": "http://evil.example"})
    assert health.status_code == 200
    listing = client.get("/api/projects", headers={"Origin": "http://evil.example", "Sec-Fetch-Site": "cross-site"})
    assert listing.status_code == 200


def test_sec_fetch_site_cross_site_without_origin_is_blocked(client: TestClient, monkeypatch: pytest.MonkeyPatch):
    opened = _patch_reveal(monkeypatch)
    slug = client.get("/api/projects").json()[0]["slug"]
    url = f"/api/projects/{slug}/open-folder"
    blocked = client.post(url, headers={"Sec-Fetch-Site": "cross-site"})
    assert blocked.status_code == 403, blocked.text
    assert opened == []

    # A trusted Origin stays allowed when the browser marks the request cross-site
    # (page on localhost, API on 127.0.0.1, same app port). Vite's port is not
    # trusted unless dev CORS is on.
    allowed = client.post(
        url,
        headers={"Origin": "http://localhost:8765", "Sec-Fetch-Site": "cross-site"},
    )
    assert allowed.status_code == 200, allowed.text
    assert opened

    opened.clear()
    vite = client.post(url, headers={"Origin": "http://localhost:5173", "Sec-Fetch-Site": "cross-site"})
    assert vite.status_code == 403, vite.text
    assert opened == []

    opened.clear()
    same = client.post(url, headers={"Sec-Fetch-Site": "same-origin"})
    assert same.status_code == 200, same.text
    assert opened


def test_dev_cors_vite_origins_still_accepted(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    opened = _patch_reveal(monkeypatch)
    with _client(tmp_path, monkeypatch, dev_cors=True) as client:
        slug = client.get("/api/projects").json()[0]["slug"]
        url = f"/api/projects/{slug}/open-folder"
        preflight = client.options(
            url,
            headers={
                "Origin": "http://localhost:5173",
                "Access-Control-Request-Method": "POST",
            },
        )
        assert preflight.status_code == 200, preflight.text
        assert preflight.headers.get("access-control-allow-origin") == "http://localhost:5173"

        # Host check stays outside CORS: a foreign Host is not a successful preflight.
        foreign_host = client.options(
            url,
            headers={
                "Host": "attacker.example",
                "Origin": "http://localhost:5173",
                "Access-Control-Request-Method": "POST",
            },
        )
        assert foreign_host.status_code == 400

        for origin in ("http://localhost:5173", "http://127.0.0.1:5173"):
            opened.clear()
            response = client.post(
                url,
                headers={"Origin": origin, "Sec-Fetch-Site": "cross-site"},
            )
            assert response.status_code == 200, (origin, response.status_code, response.text)
            assert response.headers.get("access-control-allow-origin") == origin
            assert opened

        opened.clear()
        foreign = client.post(url, headers={"Origin": "http://evil.example"})
        assert foreign.status_code == 403, foreign.text
        assert opened == []


def test_get_ignores_foreign_origin(client: TestClient):
    assert client.get("/health", headers={"Origin": "http://evil.example"}).status_code == 200
    assert client.get("/health", headers={"Origin": "http://localhost:3000"}).status_code == 200
    assert client.options("/health", headers={"Origin": "http://evil.example"}).status_code != 403


def _open_folder(client: TestClient, origin: str | None):
    slug = client.get("/api/projects").json()[0]["slug"]
    headers = {} if origin is None else {"Origin": origin}
    return client.post(f"/api/projects/{slug}/open-folder", headers=headers)


def test_origin_must_match_the_bound_port(client: TestClient, monkeypatch: pytest.MonkeyPatch):
    """State-changing requests trust only http on the app port."""
    opened = _patch_reveal(monkeypatch)
    slug = client.get("/api/projects").json()[0]["slug"]
    folder = f"/api/projects/{slug}/open-folder"
    name = client.get(f"/api/projects/{slug}").json()["name"]

    for method_response in (
        client.post(folder, headers={"Origin": "http://localhost:3000"}),
        client.patch(
            f"/api/projects/{slug}",
            json={"name": "Hacked"},
            headers={"Origin": "http://localhost:3000"},
        ),
    ):
        assert method_response.status_code == 403, method_response.text
    assert client.get(f"/api/projects/{slug}").json()["name"] == name
    assert opened == []

    for origin in (
        "http://127.0.0.1:8765",
        "http://localhost:8765",
        "http://[::1]:8765",
    ):
        opened.clear()
        response = _open_folder(client, origin)
        assert response.status_code == 200, (origin, response.status_code, response.text)
        assert opened

    # No Origin is still a local script / webview call.
    opened.clear()
    assert _open_folder(client, None).status_code == 200
    assert opened

    # A missing port is 80, and this app is not on 80. https is not this server.
    for origin in (
        "http://127.0.0.1",
        "http://localhost",
        "https://127.0.0.1:8765",
        "https://localhost:8765",
        "http://127.0.0.1:8765/path",
    ):
        opened.clear()
        response = _open_folder(client, origin)
        assert response.status_code == 403, (origin, response.status_code, response.text)
        assert opened == []

    # Host stays hostname-only: a foreign port in Host is fine, the same port in Origin is not.
    assert client.get("/health", headers={"Host": "localhost:3000"}).status_code == 200


def test_bare_http_origin_matches_only_port_80(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    opened = _patch_reveal(monkeypatch)
    with _client(tmp_path, monkeypatch, port=80) as client:
        slug = client.get("/api/projects").json()[0]["slug"]
        url = f"/api/projects/{slug}/open-folder"
        bare = client.post(url, headers={"Origin": "http://127.0.0.1"})
        assert bare.status_code == 200, bare.text
        explicit = client.post(url, headers={"Origin": "http://localhost:80"})
        assert explicit.status_code == 200, explicit.text
        other = client.post(url, headers={"Origin": "http://127.0.0.1:8765"})
        assert other.status_code == 403, other.text
        assert opened


def test_custom_port_is_the_only_trusted_origin_port(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    opened = _patch_reveal(monkeypatch)
    with _client(tmp_path, monkeypatch, port=23456) as client:
        slug = client.get("/api/projects").json()[0]["slug"]
        url = f"/api/projects/{slug}/open-folder"
        ok = client.post(url, headers={"Origin": "http://127.0.0.1:23456"})
        assert ok.status_code == 200, ok.text
        local = client.post(url, headers={"Origin": "http://localhost:23456"})
        assert local.status_code == 200, local.text
        v6 = client.post(url, headers={"Origin": "http://[::1]:23456"})
        assert v6.status_code == 200, v6.text
        default_port = client.post(url, headers={"Origin": "http://127.0.0.1:8765"})
        assert default_port.status_code == 403, default_port.text
        assert opened


def test_port_zero_trusts_the_listening_socket(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    """``--port 0`` binds an OS port. The origin check uses that socket port."""
    opened = _patch_reveal(monkeypatch)
    with _client(tmp_path, monkeypatch, port=0, base_url="http://127.0.0.1:32111") as client:
        slug = client.get("/api/projects").json()[0]["slug"]
        url = f"/api/projects/{slug}/open-folder"
        ok = client.post(url, headers={"Origin": "http://127.0.0.1:32111"})
        assert ok.status_code == 200, ok.text
        also = client.post(url, headers={"Origin": "http://localhost:32111"})
        assert also.status_code == 200, also.text
        other = client.post(url, headers={"Origin": "http://127.0.0.1:8765"})
        assert other.status_code == 403, other.text
        assert opened


def test_vite_origin_requires_dev_cors(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    opened = _patch_reveal(monkeypatch)
    with _client(tmp_path, monkeypatch, dev_cors=False, vite_port=5173) as client:
        slug = client.get("/api/projects").json()[0]["slug"]
        url = f"/api/projects/{slug}/open-folder"
        blocked = client.post(url, headers={"Origin": "http://localhost:5173"})
        assert blocked.status_code == 403, blocked.text
        assert opened == []
        # The app port is still trusted with dev CORS off.
        opened.clear()
        allowed = client.post(url, headers={"Origin": "http://127.0.0.1:8765"})
        assert allowed.status_code == 200, allowed.text
        assert opened


def test_vite_port_override_is_the_dev_origin(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    opened = _patch_reveal(monkeypatch)
    monkeypatch.setenv("LIT_VITE_PORT", "5999")
    with _client(tmp_path, monkeypatch, dev_cors=True) as client:
        from lit.config import get_config

        assert get_config().vite_port == 5999
        slug = client.get("/api/projects").json()[0]["slug"]
        url = f"/api/projects/{slug}/open-folder"
        preflight = client.options(
            url,
            headers={
                "Origin": "http://localhost:5999",
                "Access-Control-Request-Method": "POST",
            },
        )
        assert preflight.status_code == 200, preflight.text
        assert preflight.headers.get("access-control-allow-origin") == "http://localhost:5999"
        for origin in ("http://localhost:5999", "http://127.0.0.1:5999"):
            opened.clear()
            response = client.post(url, headers={"Origin": origin})
            assert response.status_code == 200, (origin, response.status_code, response.text)
            assert response.headers.get("access-control-allow-origin") == origin
            assert opened
        opened.clear()
        default_vite = client.post(url, headers={"Origin": "http://localhost:5173"})
        assert default_vite.status_code == 403, default_vite.text
        assert opened == []

    monkeypatch.delenv("LIT_VITE_PORT", raising=False)
    with _client(tmp_path, monkeypatch, dev_cors=True, vite_port=4242, seed=False) as client:
        from lit.config import get_config

        assert get_config().vite_port == 4242
        # No project was seeded; a state-changing settings write still carries Origin.
        saved = client.patch(
            "/api/settings",
            json={"backup_retention_days": 14},
            headers={"Origin": "http://localhost:4242"},
        )
        assert saved.status_code == 200, saved.text
        blocked = client.patch(
            "/api/settings",
            json={"backup_retention_days": 14},
            headers={"Origin": "http://localhost:5173"},
        )
        assert blocked.status_code == 403, blocked.text


def test_invalid_vite_port_env_is_ignored(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("LIT_VITE_PORT", "nope")
    from lit.config import AppConfig

    cfg = AppConfig(data_dir=tmp_path / "data", vite_port=4242)
    assert cfg.vite_port == 4242
    monkeypatch.setenv("LIT_VITE_PORT", "70000")
    cfg = AppConfig(data_dir=tmp_path / "data", vite_port=4242)
    assert cfg.vite_port == 4242
