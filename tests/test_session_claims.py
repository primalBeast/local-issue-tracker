"""Project claims, the session event stream, and 423 write enforcement."""

from __future__ import annotations

import asyncio
import http.client
import json
import os
import socket
import sqlite3
import subprocess
import sys
import threading
import time
import urllib.error
import urllib.request
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

CLIENT_A = "client-a-11111111"
CLIENT_B = "client-b-22222222"
CLIENT_C = "client-c-33333333"
_TIMINGS = Path("/tmp/slice2-timings.txt")


def _note(line: str) -> None:
    print(line)
    with _TIMINGS.open("a", encoding="utf-8") as handle:
        handle.write(line + "\n")


@pytest.fixture(autouse=True)
def _reset_registry():
    from lit.session import registry

    registry.reset()
    yield
    registry.reset()


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

    with TestClient(create_app(), base_url="http://127.0.0.1:8765") as test_client:
        yield test_client


def _headers(client_id: str | None) -> dict[str, str]:
    if client_id is None:
        return {}
    return {"X-Lit-Client": client_id}


def _slug(client: TestClient) -> str:
    projects = client.get("/api/projects").json()
    assert projects
    return projects[0]["slug"]


def _create_item(client: TestClient, slug: str, title: str, *, client_id: str | None = None) -> dict:
    response = client.post(
        f"/api/projects/{slug}/items",
        json={"fields": {"ticket_key": "ABC-1", "title": title, "priority": 3, "state": "Submitted"}},
        headers=_headers(client_id),
    )
    assert response.status_code == 201, response.text
    return response.json()


def _snap(path: Path) -> tuple[int | None, bytes | None]:
    if not path.is_file():
        return None, None
    return path.stat().st_mtime_ns, path.read_bytes()


def test_claim_conflict_reclaim_and_release(client: TestClient) -> None:
    slug = _slug(client)
    first = client.post(f"/api/projects/{slug}/claim", headers=_headers(CLIENT_A))
    assert first.status_code == 200, first.text
    body = first.json()
    assert body["slug"] == slug
    assert body["holder"] == CLIENT_A
    assert body["claims"][slug] == CLIENT_A

    again = client.post(f"/api/projects/{slug}/claim", headers=_headers(CLIENT_A))
    assert again.status_code == 200, again.text
    assert again.json()["holder"] == CLIENT_A

    other = client.post(f"/api/projects/{slug}/claim", headers=_headers(CLIENT_B))
    assert other.status_code == 409, other.text
    assert other.json() == {
        "held_by_other": True,
        "detail": "Already open in another window",
    }

    not_ours = client.post(f"/api/projects/{slug}/release", headers=_headers(CLIENT_B))
    assert not_ours.status_code == 200, not_ours.text
    assert not_ours.json() == {"released": False}
    assert client.get("/api/session/claims").json()["claims"][slug] == CLIENT_A

    released = client.post(f"/api/projects/{slug}/release", headers=_headers(CLIENT_A))
    assert released.status_code == 200, released.text
    assert released.json() == {"released": True}
    assert slug not in client.get("/api/session/claims").json()["claims"]


def test_release_all_by_query_and_header(client: TestClient) -> None:
    slug = _slug(client)
    created = client.post("/api/projects", json={"slug": "side-board", "name": "Side"})
    assert created.status_code == 201, created.text
    assert client.post(f"/api/projects/{slug}/claim", headers=_headers(CLIENT_A)).status_code == 200
    assert client.post("/api/projects/side-board/claim", headers=_headers(CLIENT_A)).status_code == 200

    # No Origin header: this is how the window-close path calls it.
    freed = client.post("/api/session/release-all", params={"client": CLIENT_A})
    assert freed.status_code == 200, freed.text
    assert freed.json()["released"] == sorted([slug, "side-board"])
    assert client.get("/api/session/claims").json()["claims"] == {}

    assert client.post(f"/api/projects/{slug}/claim", headers=_headers(CLIENT_A)).status_code == 200
    by_header = client.post("/api/session/release-all", headers=_headers(CLIENT_A))
    assert by_header.status_code == 200, by_header.text
    assert by_header.json()["released"] == [slug]

    mismatch = client.post(
        "/api/session/release-all",
        params={"client": CLIENT_A},
        headers=_headers(CLIENT_B),
    )
    assert mismatch.status_code == 400


def test_invalid_client_and_missing_project(client: TestClient) -> None:
    slug = _slug(client)
    missing_header = client.post(f"/api/projects/{slug}/claim")
    assert missing_header.status_code == 400
    short = client.post(f"/api/projects/{slug}/claim", headers=_headers("short"))
    assert short.status_code == 400
    punctuated = client.post(f"/api/projects/{slug}/claim", headers=_headers("bad id!!!!"))
    assert punctuated.status_code == 400
    absent = client.post("/api/projects/no-such-proj/claim", headers=_headers(CLIENT_A))
    assert absent.status_code == 404
    assert client.get("/api/session/claims").json()["claims"] == {}

    bad_stream = client.get("/api/session/events", params={"client": "nope"})
    assert bad_stream.status_code == 400
    missing_stream = client.get("/api/session/events")
    assert missing_stream.status_code == 400
    bad_release = client.post("/api/session/release-all")
    assert bad_release.status_code == 400

    foreign = client.post(
        f"/api/projects/{slug}/claim",
        headers={**_headers(CLIENT_A), "Origin": "https://evil.example"},
    )
    assert foreign.status_code == 403


def test_curl_claim_without_a_stream_is_kept(monkeypatch: pytest.MonkeyPatch) -> None:
    """A client that never opened a stream is not auto-released when grace elapses."""
    monkeypatch.setenv("LIT_CLAIM_GRACE_SECONDS", "0.2")
    from lit.session import registry

    assert registry.claim("curl-proj", "client-curl01") is True
    time.sleep(0.5)
    assert registry.holder("curl-proj") == "client-curl01"


def test_grace_timer_releases_unless_the_client_reconnects(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("LIT_CLAIM_GRACE_SECONDS", "0.3")
    from lit.session import registry

    async def scenario() -> tuple[float, float]:
        loop = asyncio.get_running_loop()
        queue: asyncio.Queue[dict] = asyncio.Queue()
        registry.connect_stream(CLIENT_B, loop, queue)
        started = time.monotonic()
        assert registry.claim("proj-1", CLIENT_A) is True
        payload = await asyncio.wait_for(queue.get(), 1.0)
        claim_s = time.monotonic() - started
        assert payload["claims"]["proj-1"] == CLIENT_A

        registry.stream_opened(CLIENT_A)
        registry.stream_closed(CLIENT_A)
        await asyncio.sleep(0.1)
        registry.stream_opened(CLIENT_A)
        await asyncio.sleep(0.5)
        assert registry.holder("proj-1") == CLIENT_A
        leftover: list[dict] = []
        while not queue.empty():
            leftover.append(queue.get_nowait())
        assert all(item["claims"].get("proj-1") == CLIENT_A for item in leftover)

        registry.stream_closed(CLIENT_A)
        dropped = time.monotonic()
        released = await asyncio.wait_for(queue.get(), 2.0)
        grace_s = time.monotonic() - dropped
        assert "proj-1" not in released["claims"]
        registry.disconnect_stream(CLIENT_B, queue)
        return claim_s, grace_s

    claim_s, grace_s = asyncio.run(scenario())
    _note(f"TIMING inproc_claim_broadcast={claim_s:.3f}s inproc_grace_release={grace_s:.3f}s")
    assert claim_s < 1.0
    assert grace_s < 1.0


def test_explicit_release_cancels_pending_grace(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("LIT_CLAIM_GRACE_SECONDS", "0.3")
    from lit.session import registry

    assert registry.claim("proj-1", CLIENT_A) is True
    assert registry.claim("proj-2", CLIENT_A) is True
    registry.stream_opened(CLIENT_A)
    registry.stream_closed(CLIENT_A)
    assert registry.release("proj-1", CLIENT_A) is True
    time.sleep(1.0)
    # The partial release left proj-2 under the original grace timer.
    assert registry.holder("proj-1") is None
    assert registry.holder("proj-2") is None

    assert registry.claim("proj-1", CLIENT_A) is True
    registry.stream_opened(CLIENT_A)
    registry.stream_closed(CLIENT_A)
    assert registry.release_all(CLIENT_A) == ["proj-1"]
    time.sleep(0.5)
    assert registry.holder("proj-1") is None
    assert registry.claims_snapshot() == {}


def test_enforcement_rejects_other_client_without_writing(client: TestClient) -> None:
    from lit.paths import project_dir

    slug = _slug(client)
    item = _create_item(client, slug, "Original")
    root = project_dir(slug)
    notes = client.get(f"/api/projects/{slug}/notes").json()
    fields = client.get(f"/api/projects/{slug}/fields").json()
    workspace = client.get(f"/api/projects/{slug}/workspaces").json()[0]
    project = client.get(f"/api/projects/{slug}").json()

    notes_path = root / "notes.json"
    fields_path = root / "fields.json"
    project_path = root / "project.json"
    db_path = root / "items.sqlite"
    workspace_path = root / "workspaces" / f"{workspace['id']}.json"
    paths = [notes_path, fields_path, project_path, db_path, workspace_path]
    for path in paths:
        assert path.is_file(), path

    assert client.post(f"/api/projects/{slug}/claim", headers=_headers(CLIENT_A)).status_code == 200
    before = {path: _snap(path) for path in paths}

    notes_body = json.loads(json.dumps(notes))
    notes_body["content"] = {
        "type": "doc",
        "content": [{"type": "paragraph", "content": [{"type": "text", "text": "stolen"}]}],
    }
    fields_body = json.loads(json.dumps(fields))
    fields_body["fields"][0]["label"] = str(fields_body["fields"][0]["label"]) + " stolen"
    workspace_body = json.loads(json.dumps(workspace))
    workspace_body["ui"]["zoom"] = 0.42

    rejected = [
        client.patch(
            f"/api/projects/{slug}/items/{item['id']}",
            json={"fields": {"title": "Stolen"}, "version": item["version"]},
            headers=_headers(CLIENT_B),
        ),
        client.post(
            f"/api/projects/{slug}/items",
            json={"fields": {"ticket_key": "ABC-2", "title": "Extra", "priority": 3, "state": "Submitted"}},
            headers=_headers(CLIENT_B),
        ),
        client.delete(
            f"/api/projects/{slug}/items/{item['id']}",
            headers=_headers(CLIENT_B),
        ),
        client.put(f"/api/projects/{slug}/notes", json=notes_body, headers=_headers(CLIENT_B)),
        client.put(f"/api/projects/{slug}/fields", json=fields_body, headers=_headers(CLIENT_B)),
        client.put(
            f"/api/projects/{slug}/workspaces/{workspace['id']}",
            json=workspace_body,
            headers=_headers(CLIENT_B),
        ),
        client.patch(f"/api/projects/{slug}", json={"name": "Stolen"}, headers=_headers(CLIENT_B)),
        client.patch(
            f"/api/projects/{slug}/items/{item['id']}",
            json={"fields": {"title": "No header"}, "version": item["version"]},
        ),
    ]
    for response in rejected:
        assert response.status_code == 423, response.text
        assert response.json()["detail"] == "Project is open in another window"
    for path, snapshot in before.items():
        assert _snap(path) == snapshot, path

    kept = client.get(f"/api/projects/{slug}/items/{item['id']}")
    assert kept.status_code == 200
    assert kept.json()["fields"]["title"] == "Original"
    listed = client.get(f"/api/projects/{slug}/items").json()
    assert [row["id"] for row in listed] == [item["id"]]


def test_enforcement_allows_holder_and_unclaimed_headerless_writes(client: TestClient) -> None:
    slug = _slug(client)
    created = client.post("/api/projects", json={"slug": "open-board", "name": "Open"})
    assert created.status_code == 201, created.text
    headerless = _create_item(client, "open-board", "Scripted")
    assert headerless["fields"]["title"] == "Scripted"

    item = _create_item(client, slug, "Original")
    assert client.post(f"/api/projects/{slug}/claim", headers=_headers(CLIENT_A)).status_code == 200
    patched = client.patch(
        f"/api/projects/{slug}/items/{item['id']}",
        json={"fields": {"title": "Kept"}, "version": item["version"]},
        headers=_headers(CLIENT_A),
    )
    assert patched.status_code == 200, patched.text
    assert patched.json()["fields"]["title"] == "Kept"

    # Global settings are not a project write.
    settings = client.patch("/api/settings", json={"theme": "ember"})
    assert settings.status_code == 200, settings.text
    assert settings.json()["theme"] == "ember"


def test_backup_from_another_client_is_allowed(client: TestClient) -> None:
    from lit.paths import project_dir

    slug = _slug(client)
    _create_item(client, slug, "Backed up")
    assert client.post(f"/api/projects/{slug}/claim", headers=_headers(CLIENT_A)).status_code == 200
    response = client.post(
        f"/api/projects/{slug}/backups",
        json={"force": True},
        headers=_headers(CLIENT_B),
    )
    assert response.status_code == 200, response.text
    assert response.json()["status"] == "created"
    backups = project_dir(slug) / "backups"
    days = [path for path in backups.iterdir() if path.is_dir() and not path.name.endswith(".partial")]
    assert days
    snapshot = days[0] / "items.sqlite"
    assert snapshot.is_file()
    assert (days[0] / "backup_manifest.json").is_file()
    with sqlite3.connect(snapshot) as conn:
        assert conn.execute("PRAGMA integrity_check").fetchone()[0] == "ok"
        assert conn.execute("select count(*) from items").fetchone()[0] >= 1


def test_delete_by_holder_releases_the_claim(client: TestClient) -> None:
    created = client.post("/api/projects", json={"slug": "doomed", "name": "Doomed"})
    assert created.status_code == 201, created.text
    assert client.post("/api/projects/doomed/claim", headers=_headers(CLIENT_A)).status_code == 200
    blocked = client.request(
        "DELETE",
        "/api/projects/doomed",
        json={"confirm_slug": "doomed"},
        headers=_headers(CLIENT_B),
    )
    assert blocked.status_code == 423, blocked.text
    assert client.get("/api/projects/doomed").status_code == 200
    wrong = client.request(
        "DELETE",
        "/api/projects/doomed",
        json={"confirm_slug": "nope"},
        headers=_headers(CLIENT_A),
    )
    assert wrong.status_code == 400
    assert client.get("/api/session/claims").json()["claims"]["doomed"] == CLIENT_A
    removed = client.request(
        "DELETE",
        "/api/projects/doomed",
        json={"confirm_slug": "doomed"},
        headers=_headers(CLIENT_A),
    )
    assert removed.status_code == 200, removed.text
    assert "doomed" not in client.get("/api/session/claims").json()["claims"]
    assert client.get("/api/projects/doomed").status_code == 404


def test_open_folder_is_exempt(client: TestClient, monkeypatch: pytest.MonkeyPatch) -> None:
    slug = _slug(client)
    monkeypatch.setattr("lit.api.projects.reveal_folder", lambda path: None)
    assert client.post(f"/api/projects/{slug}/claim", headers=_headers(CLIENT_A)).status_code == 200
    opened = client.post(f"/api/projects/{slug}/open-folder", headers=_headers(CLIENT_B))
    assert opened.status_code == 200, opened.text


def _free_port() -> int:
    while True:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
            sock.bind(("127.0.0.1", 0))
            port = int(sock.getsockname()[1])
        if port not in (8765, 8799):
            return port


def _health(port: int) -> bool:
    try:
        with urllib.request.urlopen(f"http://127.0.0.1:{port}/health", timeout=0.4) as response:
            return int(getattr(response, "status", 200) or 200) == 200
    except (OSError, urllib.error.URLError, ValueError):
        return False


def _request(
    port: int,
    method: str,
    path: str,
    payload: dict | None = None,
    headers: dict[str, str] | None = None,
) -> tuple[int, dict]:
    data = None if payload is None else json.dumps(payload).encode("utf-8")
    request_headers = {"Accept": "application/json"}
    if payload is not None:
        request_headers["Content-Type"] = "application/json"
    if headers:
        request_headers.update(headers)
    request = urllib.request.Request(
        f"http://127.0.0.1:{port}{path}",
        data=data,
        headers=request_headers,
        method=method,
    )
    try:
        with urllib.request.urlopen(request, timeout=10) as response:
            raw = response.read().decode("utf-8")
            return int(response.status), json.loads(raw) if raw else {}
    except urllib.error.HTTPError as exc:
        raw = exc.read().decode("utf-8", errors="replace")
        try:
            parsed = json.loads(raw) if raw else {}
        except json.JSONDecodeError:
            parsed = {"raw": raw}
        return int(exc.code), parsed


class _SSE:
    def __init__(self, port: int, client_id: str) -> None:
        self.conn = http.client.HTTPConnection("127.0.0.1", port, timeout=10)
        self.conn.request(
            "GET",
            f"/api/session/events?client={client_id}",
            headers={"Accept": "text/event-stream", "Cache-Control": "no-cache"},
        )
        self.resp = self.conn.getresponse()
        if self.resp.status != 200:
            body = self.resp.read()
            raise AssertionError(f"SSE status {self.resp.status}: {body!r}")
        self.headers = {key.lower(): value for key, value in self.resp.getheaders()}
        # A short socket timeout aborts chunked reads between events and
        # drops the next chunk (the heartbeat). Block until a full line
        # arrives; close() unblocks the reader.
        if self.conn.sock is not None:
            self.conn.sock.settimeout(None)
        self.events: list[tuple[float, str, str]] = []
        self.comments: list[tuple[float, str]] = []
        self.retries: list[str] = []
        self._lock = threading.Lock()
        self._stop = threading.Event()
        self._thread = threading.Thread(target=self._read, name=f"sse-{client_id}", daemon=True)
        self._thread.start()

    def _read(self) -> None:
        event_name = "message"
        data: list[str] = []
        while not self._stop.is_set():
            try:
                line = self.resp.readline()
            except (OSError, http.client.HTTPException, AttributeError, ValueError):
                break
            if not line:
                break
            now = time.monotonic()
            text = line.decode("utf-8", "replace").rstrip("\r\n")
            if text == "":
                if data:
                    with self._lock:
                        self.events.append((now, event_name, "\n".join(data)))
                event_name = "message"
                data = []
                continue
            if text.startswith(":"):
                with self._lock:
                    self.comments.append((now, text[1:].strip()))
                continue
            if text.startswith("event:"):
                event_name = text.split(":", 1)[1].strip()
            elif text.startswith("data:"):
                data.append(text.split(":", 1)[1].lstrip())
            elif text.startswith("retry:"):
                with self._lock:
                    self.retries.append(text.split(":", 1)[1].strip())

    def snapshot(self) -> tuple[list[tuple[float, str, str]], list[tuple[float, str]], list[str]]:
        with self._lock:
            return list(self.events), list(self.comments), list(self.retries)

    def wait_until(self, predicate, timeout: float):
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            snap = self.snapshot()
            if predicate(*snap):
                return snap
            time.sleep(0.02)
        snap = self.snapshot()
        raise AssertionError(f"SSE wait timed out; events={snap[0]!r} comments={snap[1]!r} retries={snap[2]!r}")

    def close(self) -> None:
        self._stop.set()
        try:
            self.conn.close()
        except OSError:
            pass
        self._thread.join(timeout=2)


def _claims_after(events: list[tuple[float, str, str]], t0: float) -> list[tuple[float, dict]]:
    found = []
    for ts, name, data in events:
        if ts >= t0 and name == "claims":
            found.append((ts, json.loads(data)))
    return found


def _start_server(
    data: Path,
    port: int,
    log_path: Path,
    *,
    idle: bool,
    env_extra: dict[str, str] | None = None,
) -> tuple[subprocess.Popen[str], object]:
    cmd = [
        sys.executable,
        "-m",
        "lit",
        "--data-dir",
        str(data),
        "serve",
        "--headless",
        "--host",
        "127.0.0.1",
        "--port",
        str(port),
    ]
    if idle:
        cmd.append("--exit-when-idle")
    env = os.environ.copy()
    env.pop("LIT_DATA_DIR", None)
    env.pop("LIT_CLAIM_GRACE_SECONDS", None)
    env.pop("LIT_SSE_HEARTBEAT_SECONDS", None)
    env["PYTHONUNBUFFERED"] = "1"
    if env_extra:
        env.update(env_extra)
    log_handle = open(log_path, "w", encoding="utf-8")
    proc = subprocess.Popen(
        cmd,
        stdout=log_handle,
        stderr=subprocess.STDOUT,
        env=env,
        text=True,
    )
    return proc, log_handle


def _stop_server(proc: subprocess.Popen[str] | None, log_handle: object) -> None:
    if proc is not None and proc.poll() is None:
        proc.kill()
        try:
            proc.wait(timeout=5)
        except subprocess.TimeoutExpired:
            proc.kill()
            proc.wait(timeout=5)
    close = getattr(log_handle, "close", None)
    if close is not None and not getattr(log_handle, "closed", True):
        close()


def _wait_health(port: int, log_path: Path, proc: subprocess.Popen[str]) -> None:
    deadline = time.monotonic() + 25
    while time.monotonic() < deadline:
        if proc.poll() is not None:
            break
        if _health(port):
            return
        time.sleep(0.1)
    tail = log_path.read_text(encoding="utf-8", errors="replace")[-4000:] if log_path.is_file() else ""
    raise AssertionError(f"server did not become healthy (rc={proc.poll()})\n{tail}")


def test_live_sse_claim_release_grace_and_reconnect(tmp_path: Path) -> None:
    """Real uvicorn stream. Defaults: 1s heartbeat, 1.5s grace."""
    data = (tmp_path / "data").resolve()
    data.mkdir()
    port = _free_port()
    log_path = tmp_path / "server.log"
    proc, log_handle = _start_server(data, port, log_path, idle=False)
    streams: list[_SSE] = []
    try:
        _wait_health(port, log_path, proc)
        status, projects = _request(port, "GET", "/api/projects")
        assert status == 200 and projects
        slug = projects[0]["slug"]
        created, _body = _request(port, "POST", "/api/projects", {"slug": "side-board", "name": "Side"})
        assert created == 201

        opened = time.monotonic()
        watcher = _SSE(port, CLIENT_B)
        holder = _SSE(port, CLIENT_A)
        streams.extend([watcher, holder])
        for stream, client_id in ((watcher, CLIENT_B), (holder, CLIENT_A)):
            events, _comments, retries = stream.wait_until(
                lambda ev, _co, re, client_id=client_id: (
                    "500" in re
                    and any(name == "hello" and json.loads(data).get("client") == client_id for _ts, name, data in ev)
                    and any(name == "claims" for _ts, name, _data in ev)
                ),
                5,
            )
            hello_at = next(ts for ts, name, _data in events if name == "hello")
            hello_delay = hello_at - opened
            _note(f"TIMING sse_hello_{client_id}={hello_delay:.3f}s")
            assert hello_delay < 1.0, hello_delay
        assert "text/event-stream" in watcher.headers.get("content-type", "")
        assert "no-cache" in watcher.headers.get("cache-control", "")
        assert watcher.headers.get("x-accel-buffering") == "no"

        def _wait_claim(t0: float, predicate, timeout: float) -> float:
            events, _comments, _retries = watcher.wait_until(
                lambda ev, _co, _re: any(predicate(payload) for _ts, payload in _claims_after(ev, t0)),
                timeout,
            )
            ts = next(ts for ts, payload in _claims_after(events, t0) if predicate(payload))
            return ts - t0

        t0 = time.monotonic()
        status, body = _request(port, "POST", f"/api/projects/{slug}/claim", headers=_headers(CLIENT_A))
        assert status == 200, body
        claim_s = _wait_claim(t0, lambda payload: payload["claims"].get(slug) == CLIENT_A, 1.0)
        _note(f"TIMING sse_claim_broadcast={claim_s:.3f}s")
        assert claim_s < 1.0

        t0 = time.monotonic()
        status, body = _request(port, "POST", f"/api/projects/{slug}/release", headers=_headers(CLIENT_A))
        assert status == 200 and body["released"] is True
        release_s = _wait_claim(t0, lambda payload: slug not in payload["claims"], 1.0)
        _note(f"TIMING sse_release_broadcast={release_s:.3f}s")
        assert release_s < 1.0

        assert _request(port, "POST", f"/api/projects/{slug}/claim", headers=_headers(CLIENT_A))[0] == 200
        assert _request(port, "POST", "/api/projects/side-board/claim", headers=_headers(CLIENT_A))[0] == 200
        t0 = time.monotonic()
        status, body = _request(port, "POST", f"/api/session/release-all?client={CLIENT_A}")
        assert status == 200, body
        assert body["released"] == sorted([slug, "side-board"])

        def _both_free(payload: dict) -> bool:
            return slug not in payload["claims"] and "side-board" not in payload["claims"]

        release_all_s = _wait_claim(t0, _both_free, 1.0)
        _note(f"TIMING sse_release_all_broadcast={release_all_s:.3f}s")
        assert release_all_s < 1.0

        # Heartbeat uses the real 1s default. The stream has been up through the calls above.
        _comments = watcher.snapshot()[1]
        if len(_comments) < 2:
            watcher.wait_until(lambda _ev, co, _re: len(co) >= 2, 3.0)
            _comments = watcher.snapshot()[1]
        gaps = [_comments[i][0] - _comments[i - 1][0] for i in range(1, len(_comments))]
        _note(f"TIMING sse_heartbeat_gaps={[round(gap, 3) for gap in gaps]}")
        assert gaps, "no heartbeat comments"
        # Default cadence is 1s. Allow a short interval and a stalled runner.
        # A 15s heartbeat, or a spin, still fails.
        assert min(gaps) >= 0.25
        assert min(gaps) <= 3.0

        assert _request(port, "POST", f"/api/projects/{slug}/claim", headers=_headers(CLIENT_A))[0] == 200
        _wait_claim(time.monotonic() - 1, lambda payload: payload["claims"].get(slug) == CLIENT_A, 1.0)
        # Stamp this before close(). A fast grace broadcast can land in the
        # watcher before close() returns, and a later stamp would miss it.
        closed = time.monotonic()
        holder.close()
        streams.remove(holder)
        grace_s = _wait_claim(closed, lambda payload: slug not in payload["claims"], 3.0)
        _note(f"TIMING sse_grace_release={grace_s:.3f}s")
        assert grace_s <= 3.0

        # Reconnect inside the default 1.5s grace keeps the claim, and the other
        # window never sees a snapshot where the project is free.
        assert _request(port, "POST", f"/api/projects/{slug}/claim", headers=_headers(CLIENT_A))[0] == 200
        reholder = _SSE(port, CLIENT_A)
        streams.append(reholder)
        reholder.wait_until(
            lambda ev, _co, _re: any(
                name == "claims" and json.loads(data)["claims"].get(slug) == CLIENT_A
                for _ts, name, data in ev
            ),
            2,
        )
        mark = len(watcher.snapshot()[0])
        reholder.close()
        streams.remove(reholder)
        closed = time.monotonic()
        time.sleep(0.2)
        reopened = time.monotonic()
        again = _SSE(port, CLIENT_A)
        streams.append(again)
        again_events, _co, _re = again.wait_until(
            lambda ev, _co, _re: any(name == "hello" for _ts, name, _data in ev)
            and any(name == "claims" for _ts, name, _data in ev),
            2,
        )
        hello_delay = next(ts for ts, name, _data in again_events if name == "hello") - reopened
        _note(f"TIMING sse_reconnect_hello={hello_delay:.3f}s")
        held = next(json.loads(data) for _ts, name, data in again_events if name == "claims")
        assert held["claims"].get(slug) == CLIENT_A
        remain = 3.2 - (time.monotonic() - closed)
        if remain > 0:
            time.sleep(remain)
        fresh = watcher.snapshot()[0][mark:]
        free = [
            json.loads(data)
            for _ts, name, data in fresh
            if name == "claims" and json.loads(data).get("claims", {}).get(slug) != CLIENT_A
        ]
        assert free == [], fresh
        status, claims = _request(port, "GET", "/api/session/claims")
        assert status == 200
        assert claims["claims"].get(slug) == CLIENT_A
    finally:
        for stream in streams:
            stream.close()
        _stop_server(proc, log_handle)


def test_live_idle_exit_after_last_stream(tmp_path: Path) -> None:
    """Two streams: one disconnect leaves the server up; the last one exits it and frees the lock."""
    data = (tmp_path / "data").resolve()
    data.mkdir()
    port = _free_port()
    log_path = tmp_path / "idle-server.log"
    proc, log_handle = _start_server(
        data,
        port,
        log_path,
        idle=True,
        env_extra={"LIT_IDLE_EXIT_SECONDS": "2", "LIT_IDLE_STARTUP_SECONDS": "30"},
    )
    first: _SSE | None = None
    second: _SSE | None = None
    try:
        _wait_health(port, log_path, proc)
        first = _SSE(port, CLIENT_A)
        second = _SSE(port, CLIENT_B)
        for stream, client_id in ((first, CLIENT_A), (second, CLIENT_B)):
            stream.wait_until(
                lambda ev, _co, _re, client_id=client_id: any(
                    name == "hello" and json.loads(data).get("client") == client_id for _ts, name, data in ev
                ),
                5,
            )
        first.close()
        first = None
        time.sleep(2.6)
        assert proc.poll() is None, log_path.read_text(encoding="utf-8", errors="replace")[-2000:]
        assert _health(port)
        closed = time.monotonic()
        second.close()
        second = None
        deadline = closed + 8
        while time.monotonic() < deadline and proc.poll() is None:
            time.sleep(0.05)
        elapsed = time.monotonic() - closed
        _note(f"TIMING idle_exit_after_last_stream={elapsed:.3f}s")
        assert proc.poll() is not None, log_path.read_text(encoding="utf-8", errors="replace")[-2000:]
        assert elapsed <= 5.0
        assert elapsed >= 1.0
        assert proc.returncode == 0
    finally:
        if first is not None:
            first.close()
        if second is not None:
            second.close()
        if proc.poll() is None:
            _stop_server(proc, log_handle)
        elif not getattr(log_handle, "closed", True):
            log_handle.close()

    # The server unlocks in ``finally`` before it exits. Retry so a slow OS
    # drop of the handle (Windows) is not a stale-lock failure.
    deadline = time.monotonic() + 5
    acquired = subprocess.run(
        [
            sys.executable,
            "-c",
            "\n".join(
                [
                    "import os, sys",
                    "os.environ['LIT_DATA_DIR'] = sys.argv[1]",
                    "from lit.locking import acquire_data_lock",
                    "acquire_data_lock()",
                    "print('ACQUIRED', flush=True)",
                ]
            ),
            str(data),
        ],
        capture_output=True,
        text=True,
        timeout=20,
    )
    while acquired.returncode != 0 and time.monotonic() < deadline:
        time.sleep(0.1)
        acquired = subprocess.run(
            [
                sys.executable,
                "-c",
                "\n".join(
                    [
                        "import os, sys",
                        "os.environ['LIT_DATA_DIR'] = sys.argv[1]",
                        "from lit.locking import acquire_data_lock",
                        "acquire_data_lock()",
                        "print('ACQUIRED', flush=True)",
                    ]
                ),
                str(data),
            ],
            capture_output=True,
            text=True,
            timeout=20,
        )
    assert acquired.returncode == 0, acquired.stderr
    assert "ACQUIRED" in acquired.stdout
