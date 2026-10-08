"""Cross-platform data-root lock and lock-aware backup/init tests.

CI on windows-latest should run this file: the Windows fail-closed lock is the
point of ``test_lock_busy_then_free_after_kill``.
"""

from __future__ import annotations

import argparse
import json
import socket
import sqlite3
import subprocess
import sys
import threading
import time
from collections.abc import Iterator
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

HOLDER_SCRIPT = "\n".join(
    [
        "import os, sys, time",
        "from pathlib import Path",
        "os.environ['LIT_DATA_DIR'] = sys.argv[1]",
        "from lit.locking import acquire_data_lock",
        "acquire_data_lock()",
        "Path(sys.argv[2]).write_text('ok', encoding='utf-8')",
        "time.sleep(float(sys.argv[3]))",
    ]
)

ACQUIRE_SCRIPT = "\n".join(
    [
        "import os, sys",
        "os.environ['LIT_DATA_DIR'] = sys.argv[1]",
        "from lit.locking import acquire_data_lock",
        "acquire_data_lock()",
        "print('ACQUIRED', flush=True)",
    ]
)


@pytest.fixture(autouse=True)
def _drop_process_lock() -> Iterator[None]:
    from lit.locking import release_data_lock

    release_data_lock()
    yield
    release_data_lock()


def _use_data(path: Path) -> None:
    from lit.config import AppConfig, set_config

    set_config(AppConfig(data_dir=path))


def _free_port() -> int:
    while True:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
            sock.bind(("127.0.0.1", 0))
            port = int(sock.getsockname()[1])
        if port not in (8765, 8799):
            return port


def _snapshot(root: Path) -> dict[str, bytes]:
    found: dict[str, bytes] = {}
    if not root.exists():
        return found
    for path in root.rglob("*"):
        if path.is_file() and path.name != ".data.lock":
            found[str(path.relative_to(root))] = path.read_bytes()
    return found


def _start_holder(data: Path, ready: Path, err_path: Path, seconds: float = 120.0) -> subprocess.Popen[str]:
    err_fh = open(err_path, "w", encoding="utf-8")
    try:
        proc = subprocess.Popen(
            [sys.executable, "-c", HOLDER_SCRIPT, str(data), str(ready), str(seconds)],
            stdout=subprocess.DEVNULL,
            stderr=err_fh,
        )
    finally:
        err_fh.close()
    deadline = time.monotonic() + 15
    while time.monotonic() < deadline:
        if ready.is_file():
            return proc
        if proc.poll() is not None:
            detail = err_path.read_text(encoding="utf-8") if err_path.is_file() else ""
            raise AssertionError(f"holder exited {proc.returncode}: {detail}")
        time.sleep(0.05)
    proc.kill()
    proc.wait(timeout=5)
    raise AssertionError("holder did not acquire the data lock")


def _stop_holder(proc: subprocess.Popen[str]) -> None:
    if proc.poll() is None:
        proc.kill()
    try:
        proc.wait(timeout=5)
    except subprocess.TimeoutExpired:
        proc.kill()
        proc.wait(timeout=5)


def _acquire_subprocess(data: Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, "-c", ACQUIRE_SCRIPT, str(data)],
        capture_output=True,
        text=True,
        timeout=20,
    )


def _lit(data: Path, *args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, "-m", "lit", "--data-dir", str(data), *args],
        capture_output=True,
        text=True,
        timeout=60,
    )


def _backup_args(data: Path, **overrides: object) -> argparse.Namespace:
    values: dict[str, object] = {
        "verbose": False,
        "data_dir": str(data),
        "host": None,
        "port": None,
        "project": None,
        "force": False,
    }
    values.update(overrides)
    return argparse.Namespace(**values)


def _init_args(data: Path, **overrides: object) -> argparse.Namespace:
    values: dict[str, object] = {
        "verbose": False,
        "data_dir": str(data),
        "host": None,
        "port": None,
        "slug": "beta",
        "name": "Beta",
        "template": "issue-tracker",
    }
    values.update(overrides)
    return argparse.Namespace(**values)


def test_lock_busy_then_free_after_kill(tmp_path: Path) -> None:
    """Subprocess A holds the lock, B exits 1, kill A, B acquires. No stale lock."""
    data = (tmp_path / "data").resolve()
    data.mkdir()
    ready = tmp_path / "ready"
    holder = _start_holder(data, ready, tmp_path / "holder-err.txt")
    try:
        busy = _acquire_subprocess(data)
        assert busy.returncode == 1
        assert "Another lit process holds the data directory" in busy.stderr
        assert "Close it first." in busy.stderr
        assert str(data) in busy.stderr
    finally:
        # SIGKILL / TerminateProcess. atexit must not be required to drop the lock.
        holder.kill()
        holder.wait(timeout=5)

    deadline = time.monotonic() + 3
    last = _acquire_subprocess(data)
    while last.returncode != 0 and time.monotonic() < deadline:
        time.sleep(0.1)
        last = _acquire_subprocess(data)
    assert last.returncode == 0, last.stderr
    assert "ACQUIRED" in last.stdout


def test_serve_exits_without_writing_when_lock_held(tmp_path: Path) -> None:
    data = (tmp_path / "data").resolve()
    data.mkdir()
    before = _snapshot(data)
    holder = _start_holder(data, tmp_path / "ready", tmp_path / "holder-err.txt")
    port = _free_port()
    err_path = tmp_path / "serve-err.txt"
    err_fh = open(err_path, "w", encoding="utf-8")
    proc: subprocess.Popen[str] | None = None
    try:
        proc = subprocess.Popen(
            [
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
            ],
            stdout=err_fh,
            stderr=subprocess.STDOUT,
            text=True,
        )
        try:
            code = proc.wait(timeout=15)
        except subprocess.TimeoutExpired:
            proc.kill()
            proc.wait(timeout=5)
            raise AssertionError(f"serve stayed up while the lock was held\n{err_path.read_text(encoding='utf-8')}")
        assert code == 1
    finally:
        err_fh.close()
        if proc is not None and proc.poll() is None:
            proc.kill()
            proc.wait(timeout=5)
        _stop_holder(holder)
    detail = err_path.read_text(encoding="utf-8")
    assert "Another lit process holds the data directory" in detail
    assert "Close it first." in detail
    assert _snapshot(data) == before
    assert not (data / "projects").exists()
    assert not (data / "settings.json").exists()


def test_try_acquire_returns_false_when_busy(tmp_path: Path) -> None:
    from lit.locking import try_acquire_data_lock

    data = (tmp_path / "data").resolve()
    data.mkdir()
    _use_data(data)
    holder = _start_holder(data, tmp_path / "ready", tmp_path / "holder-err.txt")
    try:
        assert try_acquire_data_lock() is False
    finally:
        _stop_holder(holder)


def test_try_acquire_round_trip(tmp_path: Path) -> None:
    from lit.locking import release_data_lock, try_acquire_data_lock
    from lit.paths import lock_path

    data = (tmp_path / "data").resolve()
    data.mkdir()
    _use_data(data)
    assert try_acquire_data_lock() is True
    try:
        assert try_acquire_data_lock() is True
        assert lock_path().stat().st_size >= 1
    finally:
        release_data_lock()
    assert try_acquire_data_lock() is True
    release_data_lock()


def test_missing_lock_backend_exits_nonzero(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    from lit.locking import acquire_data_lock, release_data_lock

    release_data_lock()
    data = (tmp_path / "data").resolve()
    data.mkdir()
    _use_data(data)
    monkeypatch.setitem(sys.modules, "msvcrt", None)
    monkeypatch.setitem(sys.modules, "fcntl", None)
    with pytest.raises(SystemExit) as exc:
        acquire_data_lock()
    assert exc.value.code not in (0, None)
    assert "no file-locking backend" in capsys.readouterr().err


def test_direct_init_and_backup_release_the_lock(tmp_path: Path) -> None:
    data = (tmp_path / "data").resolve()
    data.mkdir()
    created = _lit(data, "init-project", "alpha", "--name", "Alpha")
    assert created.returncode == 0, created.stderr
    assert (data / "projects" / "alpha" / "project.json").is_file()
    backed = _lit(data, "backup-now", "--project", "alpha", "--force")
    assert backed.returncode == 0, backed.stderr
    backups = data / "projects" / "alpha" / "backups"
    assert backups.is_dir()
    assert list(backups.rglob("items.sqlite"))
    assert not list(backups.rglob("*-wal"))
    assert not list(backups.rglob("*-shm"))
    # The direct commands released the lock, so another process can take it.
    again = _acquire_subprocess(data)
    assert again.returncode == 0, again.stderr


def test_backup_now_does_not_write_when_lock_held_and_server_down(tmp_path: Path) -> None:
    from lit.storage.project_fs import create_project, ensure_data_layout

    data = (tmp_path / "data").resolve()
    data.mkdir()
    _use_data(data)
    ensure_data_layout()
    create_project("alpha", name="Alpha")
    before = _snapshot(data)
    holder = _start_holder(data, tmp_path / "ready", tmp_path / "holder-err.txt")
    try:
        port = _free_port()
        result = _lit(data, "backup-now", "--project", "alpha", "--force", "--host", "127.0.0.1", "--port", str(port))
        assert result.returncode == 1
        assert "Close the app or run this from the app." in result.stderr
        assert _snapshot(data) == before
        assert not (data / "projects" / "alpha" / "backups").exists()
    finally:
        _stop_holder(holder)


def test_backup_now_calls_api_when_lock_held(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]) -> None:
    from lit.cli import cmd_backup_now
    from lit.storage.project_fs import create_project, ensure_data_layout

    data = (tmp_path / "data").resolve()
    data.mkdir()
    _use_data(data)
    ensure_data_layout()
    create_project("alpha", name="Alpha")
    (data / "settings.json").write_text(
        json.dumps({"window": {"last_host": "10.0.0.8", "last_port": 23456}}),
        encoding="utf-8",
    )
    seen: dict[str, object] = {}

    def fake_post(host: str, port: int, path: str, payload: dict, timeout: float = 120.0) -> dict:
        seen["host"] = host
        seen["port"] = port
        seen["path"] = path
        seen["payload"] = payload
        return {"status": "ok", "count": 1, "manifest": []}

    monkeypatch.setattr("lit.cli._post_json", fake_post)
    before = _snapshot(data)
    holder = _start_holder(data, tmp_path / "ready", tmp_path / "holder-err.txt")
    try:
        code = cmd_backup_now(_backup_args(data, project="alpha", force=True))
    finally:
        _stop_holder(holder)
    assert code == 0
    assert seen["host"] == "10.0.0.8"
    assert seen["port"] == 23456
    assert seen["path"] == "/api/backups/now"
    assert seen["payload"] == {"project": "alpha", "force": True}
    assert "Created 1 backup(s)" in capsys.readouterr().out
    assert _snapshot(data) == before

    # An explicit --host/--port overrides settings.json.
    seen.clear()
    holder = _start_holder(data, tmp_path / "ready2", tmp_path / "holder-err2.txt")
    try:
        code = cmd_backup_now(
            _backup_args(data, project=None, force=False, host="127.0.0.1", port=25001)
        )
    finally:
        _stop_holder(holder)
    assert code == 0
    assert seen["host"] == "127.0.0.1"
    assert seen["port"] == 25001
    assert seen["payload"] == {"project": None, "force": False}


def test_init_project_does_not_create_dir_when_lock_held(tmp_path: Path) -> None:
    data = (tmp_path / "data").resolve()
    data.mkdir()
    before = _snapshot(data)
    holder = _start_holder(data, tmp_path / "ready", tmp_path / "holder-err.txt")
    try:
        port = _free_port()
        result = _lit(
            data,
            "init-project",
            "beta",
            "--name",
            "Beta",
            "--host",
            "127.0.0.1",
            "--port",
            str(port),
        )
        assert result.returncode == 1
        assert "Close the app or run this from the app." in result.stderr
        assert not (data / "projects" / "beta").exists()
        assert _snapshot(data) == before
    finally:
        _stop_holder(holder)


def test_init_project_calls_api_and_maps_409(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    from lit.cli import ApiError, cmd_init_project

    data = (tmp_path / "data").resolve()
    data.mkdir()
    _use_data(data)
    calls: list[dict] = []

    def conflict(host: str, port: int, path: str, payload: dict, timeout: float = 120.0) -> dict:
        calls.append({"host": host, "port": port, "path": path, "payload": payload})
        raise ApiError(409, '{"detail":"Project already exists"}')

    monkeypatch.setattr("lit.cli._post_json", conflict)
    holder = _start_holder(data, tmp_path / "ready", tmp_path / "holder-err.txt")
    try:
        code = cmd_init_project(_init_args(data, host="127.0.0.1", port=25002))
    finally:
        _stop_holder(holder)
    assert code == 1
    assert calls[0]["path"] == "/api/projects"
    assert calls[0]["payload"] == {"slug": "beta", "name": "Beta", "template": "issue-tracker"}
    assert capsys.readouterr().err.strip() == "Project already exists"
    assert not (data / "projects" / "beta").exists()


def test_backup_uses_sqlite_backup_api(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    from lit.storage import backup as backup_mod
    from lit.storage import items_db
    from lit.storage.backup import backup_project
    from lit.storage.project_fs import create_project, ensure_data_layout, project_dir

    data = (tmp_path / "data").resolve()
    data.mkdir()
    _use_data(data)
    ensure_data_layout()
    create_project("alpha", name="Alpha")
    proj = project_dir("alpha")
    db = items_db.items_db_path(proj)

    def _tune(conn: sqlite3.Connection) -> None:
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("PRAGMA wal_autocheckpoint=0")

    items_db.run_db(db, _tune)
    items_db.run_db(db, lambda conn: items_db.create_item(conn, {"title": "Hello"}))
    assert (proj / "items.sqlite-wal").is_file()

    copied: list[str] = []
    real_copy = backup_mod.shutil.copy2

    def spy(src: Path, dst: Path, *args: object, **kwargs: object) -> object:
        copied.append(Path(src).name)
        return real_copy(src, dst, *args, **kwargs)

    monkeypatch.setattr(backup_mod.shutil, "copy2", spy)
    manifest = backup_project("alpha", force=True)
    assert manifest is not None
    day = manifest["local_date"]
    dest = proj / "backups" / day
    sqlite_file = dest / "items.sqlite"
    assert sqlite_file.is_file()
    assert sqlite_file.read_bytes().startswith(b"SQLite format 3")
    assert not (dest / "items.sqlite-wal").exists()
    assert not (dest / "items.sqlite-shm").exists()
    assert (dest / "project.json").is_file()
    assert (dest / "workspaces" / "ws-main.json").is_file()
    assert "items.sqlite" not in copied
    assert "items.sqlite-wal" not in copied
    assert "items.sqlite-shm" not in copied
    assert "project.json" in copied

    conn = sqlite3.connect(sqlite_file)
    try:
        assert conn.execute("PRAGMA integrity_check").fetchone()[0] == "ok"
        rows = [row[0] for row in conn.execute("SELECT fields_json FROM items")]
    finally:
        conn.close()
    assert any("Hello" in row for row in rows)


def test_backup_stays_consistent_while_another_thread_writes(tmp_path: Path) -> None:
    from lit.storage import items_db
    from lit.storage.backup import backup_project
    from lit.storage.project_fs import create_project, ensure_data_layout, project_dir

    data = (tmp_path / "data").resolve()
    data.mkdir()
    _use_data(data)
    ensure_data_layout()
    create_project("alpha", name="Alpha")
    proj = project_dir("alpha")
    db = items_db.items_db_path(proj)
    items_db.run_db(db, lambda conn: items_db.create_item(conn, {"title": "seed"}))

    stop = threading.Event()
    errors: list[BaseException] = []

    def writer() -> None:
        n = 0
        while not stop.is_set():
            title = f"row-{n}"
            n += 1

            def _write(conn: sqlite3.Connection, title: str = title) -> None:
                items_db.create_item(conn, {"title": title})

            try:
                items_db.run_db(db, _write)
            except BaseException as exc:  # noqa: BLE001 — surface writer failures
                errors.append(exc)
                return

    thread = threading.Thread(target=writer, name="lit-backup-writer")
    thread.start()
    try:
        time.sleep(0.05)
        manifest = backup_project("alpha", force=True)
    finally:
        stop.set()
        thread.join(timeout=5)
    assert not thread.is_alive()
    assert errors == []
    assert manifest is not None
    sqlite_file = proj / "backups" / manifest["local_date"] / "items.sqlite"
    conn = sqlite3.connect(sqlite_file)
    try:
        assert conn.execute("PRAGMA integrity_check").fetchone()[0] == "ok"
        rows = [json.loads(row[0]) for row in conn.execute("SELECT fields_json FROM items")]
    finally:
        conn.close()
    assert rows
    assert any(row.get("title") == "seed" for row in rows)
    assert not (sqlite_file.parent / "items.sqlite-wal").exists()
    assert not (sqlite_file.parent / "items.sqlite-shm").exists()


def test_api_backups_now(tmp_path: Path) -> None:
    from lit.app import create_app
    from lit.storage import items_db
    from lit.storage.project_fs import create_project, ensure_data_layout, project_dir

    data = (tmp_path / "data").resolve()
    data.mkdir()
    _use_data(data)
    ensure_data_layout()
    create_project("alpha", name="Alpha")
    db = items_db.items_db_path(project_dir("alpha"))
    items_db.run_db(db, lambda conn: items_db.create_item(conn, {"title": "via-api"}))

    with TestClient(create_app(), base_url="http://127.0.0.1:8765") as client:
        missing = client.post("/api/backups/now", json={"project": "missing", "force": True})
        assert missing.status_code == 404
        created = client.post("/api/backups/now", json={"project": "alpha", "force": True})
        assert created.status_code == 200, created.text
        body = created.json()
        assert body["status"] == "created"
        assert body["count"] == 1
        assert body["manifest"]["project_slug"] == "alpha"
        again = client.post("/api/backups/now", json={"force": False})
        assert again.status_code == 200, again.text
        assert again.json()["status"] == "ok"
        assert again.json()["count"] == 0
        per_project = client.post("/api/projects/alpha/backups", json={"force": True})
        assert per_project.status_code == 200, per_project.text

    sqlite_file = next((project_dir("alpha") / "backups").rglob("items.sqlite"))
    conn = sqlite3.connect(sqlite_file)
    try:
        rows = [row[0] for row in conn.execute("SELECT fields_json FROM items")]
    finally:
        conn.close()
    assert any("via-api" in row for row in rows)
