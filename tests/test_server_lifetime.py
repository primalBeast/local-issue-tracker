"""Detached shared server command line, idle-exit watcher, and process lifetime."""

from __future__ import annotations

import os
import socket
import subprocess
import sys
import threading
import time
import urllib.error
import urllib.request
from pathlib import Path
from types import SimpleNamespace

import pytest


def _free_port() -> int:
    while True:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
            sock.bind(("127.0.0.1", 0))
            port = int(sock.getsockname()[1])
        if port not in (8765, 8799):
            return port


def _health(host: str, port: int) -> bool:
    try:
        with urllib.request.urlopen(f"http://{host}:{port}/health", timeout=0.4) as response:
            return int(getattr(response, "status", 200) or 200) == 200
    except (OSError, urllib.error.URLError, ValueError):
        return False


class _FakeProc:
    def __init__(self) -> None:
        self.pid = 4321
        self.returncode = 0

    def wait(self, timeout: float | None = None) -> int:
        return 0


def test_build_server_cmd_includes_headless_idle_and_data_dir(tmp_path: Path) -> None:
    from lit.server_launch import build_server_cmd

    data = tmp_path / "data"
    cmd = build_server_cmd(data, "127.0.0.1", 23456)
    assert cmd[0] == sys.executable
    assert cmd[1:3] == ["-m", "lit"]
    assert "--data-dir" in cmd
    assert str(data) in cmd
    assert "serve" in cmd
    assert "--headless" in cmd
    assert "--exit-when-idle" in cmd
    assert cmd[cmd.index("--host") + 1] == "127.0.0.1"
    assert cmd[cmd.index("--port") + 1] == "23456"


def test_build_server_cmd_prefers_pythonw_on_windows(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from lit.server_launch import build_server_cmd

    monkeypatch.setattr(sys, "platform", "win32")
    target = Path(sys.executable).with_name("pythonw.exe")

    def is_file(self: Path) -> bool:
        return self == target

    monkeypatch.setattr(Path, "is_file", is_file)
    cmd = build_server_cmd(tmp_path, "127.0.0.1", 25011)
    assert Path(cmd[0]) == target
    assert "--headless" in cmd
    assert "--exit-when-idle" in cmd


def test_spawn_detached_uses_windows_creation_flags(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    import subprocess

    from lit.server_launch import WIN_DETACHED_FLAGS, spawn_detached_server

    monkeypatch.setattr(sys, "platform", "win32")
    captured: dict[str, object] = {}

    def fake_popen(cmd: list[str], **kwargs: object) -> _FakeProc:
        captured["cmd"] = cmd
        captured["kwargs"] = kwargs
        stdout = kwargs.get("stdout")
        captured["stdout_name"] = getattr(stdout, "name", "")
        return _FakeProc()

    monkeypatch.setattr(subprocess, "Popen", fake_popen)
    spawn_detached_server(["lit", "serve"], tmp_path)
    kwargs = captured["kwargs"]
    assert isinstance(kwargs, dict)
    assert kwargs["creationflags"] == WIN_DETACHED_FLAGS
    assert "start_new_session" not in kwargs
    assert kwargs["stdin"] is subprocess.DEVNULL
    assert kwargs["stderr"] is subprocess.STDOUT
    assert kwargs["close_fds"] is True
    log_path = Path(str(captured["stdout_name"]))
    assert log_path.name == "server.log"
    assert log_path.parent.name == "logs"


def test_spawn_detached_uses_new_session_on_posix(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    import subprocess

    from lit.server_launch import spawn_detached_server

    monkeypatch.setattr(sys, "platform", "linux")
    captured: dict[str, object] = {}

    def fake_popen(cmd: list[str], **kwargs: object) -> _FakeProc:
        captured["kwargs"] = kwargs
        return _FakeProc()

    monkeypatch.setattr(subprocess, "Popen", fake_popen)
    spawn_detached_server(["lit", "serve"], tmp_path)
    kwargs = captured["kwargs"]
    assert isinstance(kwargs, dict)
    assert kwargs["start_new_session"] is True
    assert "creationflags" not in kwargs


def test_ensure_server_skips_spawn_when_already_healthy(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from lit.server_launch import ensure_server

    monkeypatch.setattr("lit.webview_host.wait_for_http", lambda *args, **kwargs: True)

    def boom(*args: object, **kwargs: object) -> None:
        raise AssertionError("should not spawn when /health is up")

    monkeypatch.setattr("lit.server_launch.spawn_detached_server", boom)
    assert ensure_server("127.0.0.1", 25012, tmp_path) is True


def test_ensure_server_spawns_then_waits(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    from lit.server_launch import ensure_server

    calls = {"n": 0}

    def fake_health(host: str, port: int, timeout: float = 20.0) -> bool:
        calls["n"] += 1
        calls["last_timeout"] = timeout
        return calls["n"] >= 2

    spawned: dict[str, object] = {}

    def fake_spawn(cmd: list[str], data_dir: Path) -> _FakeProc:
        spawned["cmd"] = cmd
        spawned["data_dir"] = data_dir
        return _FakeProc()

    monkeypatch.setattr("lit.webview_host.wait_for_http", fake_health)
    monkeypatch.setattr("lit.server_launch.spawn_detached_server", fake_spawn)
    data = tmp_path / "data"
    assert ensure_server("127.0.0.1", 25013, data) is True
    cmd = spawned["cmd"]
    assert isinstance(cmd, list)
    assert "--headless" in cmd
    assert "--exit-when-idle" in cmd
    assert "--data-dir" in cmd
    assert str(data) in cmd
    assert calls["n"] == 2


def test_idle_registry_startup_window_and_last_disconnect() -> None:
    from lit.session import registry

    registry.reset()
    assert registry.active_streams() == 0
    since = registry.idle_since()
    assert since is not None
    assert registry.ever_connected() is False
    registry.stream_closed("nobody")
    assert registry.idle_since() == since
    assert registry.idle_exit_due(startup_seconds=60, idle_seconds=10, now=since + 59) is False
    assert registry.idle_exit_due(startup_seconds=60, idle_seconds=10, now=since + 60) is True

    registry.stream_opened("a")
    registry.stream_opened("b")
    assert registry.active_streams() == 2
    assert registry.idle_since() is None
    assert registry.idle_exit_due(startup_seconds=0, idle_seconds=0, now=since + 1000) is False
    registry.stream_closed("a")
    assert registry.active_streams() == 1
    assert registry.idle_since() is None
    registry.stream_closed("b")
    dropped = registry.idle_since()
    assert dropped is not None
    assert registry.ever_connected() is True
    # After a real session, the short idle timeout applies, not the startup window.
    assert registry.idle_exit_due(startup_seconds=1000, idle_seconds=10, now=dropped + 9.9) is False
    assert registry.idle_exit_due(startup_seconds=1000, idle_seconds=10, now=dropped + 10) is True

    registry.reset()
    registry.stream_opened("a")
    registry.stream_opened("a")
    assert registry.active_streams() == 2
    registry.stream_closed("a")
    assert registry.active_streams() == 1
    assert registry.idle_since() is None
    registry.stream_closed("a")
    assert registry.active_streams() == 0
    assert registry.idle_since() is not None


def test_watch_idle_stays_up_until_the_last_stream_closes(monkeypatch: pytest.MonkeyPatch) -> None:
    from lit.cli import _watch_idle
    from lit.session import registry

    monkeypatch.setenv("LIT_IDLE_STARTUP_SECONDS", "30")
    monkeypatch.setenv("LIT_IDLE_EXIT_SECONDS", "0.4")
    registry.reset()
    registry.stream_opened("c1")
    registry.stream_opened("c2")
    server = SimpleNamespace(should_exit=False)
    thread = threading.Thread(target=_watch_idle, args=(server,), name="lit-idle-test", daemon=True)
    thread.start()
    try:
        time.sleep(0.8)
        assert server.should_exit is False
        registry.stream_closed("c1")
        time.sleep(0.8)
        assert server.should_exit is False
        registry.stream_closed("c2")
        deadline = time.monotonic() + 3
        while time.monotonic() < deadline and not server.should_exit:
            time.sleep(0.05)
        assert server.should_exit is True
    finally:
        server.should_exit = True
        thread.join(timeout=2)


def test_headless_exit_when_idle_frees_the_lock(tmp_path: Path) -> None:
    """No event stream connects, so the server exits on the startup window and drops the lock."""
    from lit.server_launch import build_server_cmd

    data = (tmp_path / "data").resolve()
    data.mkdir()
    port = _free_port()
    cmd = build_server_cmd(data, "127.0.0.1", port)
    env = os.environ.copy()
    env["LIT_IDLE_STARTUP_SECONDS"] = "3"
    env["LIT_IDLE_EXIT_SECONDS"] = "10"
    env["PYTHONUNBUFFERED"] = "1"
    env.pop("LIT_DATA_DIR", None)
    log_path = tmp_path / "server-out.log"
    log_fh = open(log_path, "w", encoding="utf-8")
    proc: subprocess.Popen[str] | None = None
    try:
        proc = subprocess.Popen(
            cmd,
            stdout=log_fh,
            stderr=subprocess.STDOUT,
            env=env,
            text=True,
        )
        log_fh.close()
        saw_health = False
        deadline = time.monotonic() + 20
        while time.monotonic() < deadline and proc.poll() is None:
            if _health("127.0.0.1", port):
                saw_health = True
                break
            time.sleep(0.1)
        assert saw_health, f"server never became healthy\n{log_path.read_text(encoding='utf-8')}"
        exit_deadline = time.monotonic() + 20
        while time.monotonic() < exit_deadline and proc.poll() is None:
            time.sleep(0.1)
        assert proc.poll() is not None, f"server did not exit\n{log_path.read_text(encoding='utf-8')}"
        assert proc.returncode == 0, log_path.read_text(encoding="utf-8")
    finally:
        if proc is not None and proc.poll() is None:
            proc.kill()
            proc.wait(timeout=5)
        if not log_fh.closed:
            log_fh.close()

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
