"""Spawn the shared headless server detached from a WebView launcher.

The window process is only a client. The server process holds the data-root
lock and outlives any one window. A second launcher that loses the lock race
exits; its parent keeps waiting until ``/health`` answers.
"""

from __future__ import annotations

import logging
import os
import signal
import subprocess
import sys
import threading
import time
from pathlib import Path
from typing import Any

logger = logging.getLogger("lit.server")

_restart_lock = threading.Lock()

# CREATE_NO_WINDOW hides python.exe. Do not add DETACHED_PROCESS (it cancels
# the hide) or CREATE_NEW_PROCESS_GROUP (CreateProcess can reject the pair).
# Do not launch pythonw.exe: it was given a pid and then never answered.
CREATE_NO_WINDOW = 0x08000000


def windows_spawn_flags(executable: str) -> int:
    """Hide a console Python. ``pythonw.exe`` is not used: it was spawning and never answering."""
    return CREATE_NO_WINDOW


def server_interpreter() -> str:
    """The interpreter that is already running. ``pythonw.exe`` started and then never served."""
    return sys.executable


def build_server_cmd(data_dir: Path, host: str, port: int) -> list[str]:
    """Command line for the detached ``lit serve --headless --exit-when-idle``.

    ``-u`` flushes the log immediately so a crash is visible.
    """
    return [
        server_interpreter(),
        "-u",
        "-m",
        "lit",
        "--data-dir",
        str(data_dir),
        "serve",
        "--headless",
        "--exit-when-idle",
        "--host",
        str(host),
        "--port",
        str(port),
    ]


def _reap_in_background(proc: subprocess.Popen[Any]) -> None:
    """Collect the child when it exits so the window process does not leave a zombie."""

    def _reap() -> None:
        try:
            proc.wait()
        except Exception:
            logger.debug("Detached server reap failed", exc_info=True)

    threading.Thread(target=_reap, name="lit-server-reap", daemon=True).start()


def spawn_detached_server(cmd: list[str], data_dir: Path) -> subprocess.Popen[Any]:
    """Start ``cmd`` in its own session. Logs append to ``<data_dir>/logs/server.log``."""
    log_dir = Path(data_dir) / "logs"
    log_dir.mkdir(parents=True, exist_ok=True)
    log_path = log_dir / "server.log"
    log_fh = open(log_path, "ab", buffering=0)
    kwargs: dict[str, Any] = {
        "stdin": subprocess.DEVNULL,
        "stdout": log_fh,
        "stderr": subprocess.STDOUT,
        "close_fds": True,
    }
    if sys.platform == "win32":
        kwargs["creationflags"] = windows_spawn_flags(str(cmd[0]) if cmd else "")
    else:
        kwargs["start_new_session"] = True
    try:
        proc = subprocess.Popen(cmd, **kwargs)
    finally:
        log_fh.close()
    _reap_in_background(proc)
    logger.info("Spawned detached lit server pid=%s", getattr(proc, "pid", None))
    return proc


def _log_tail(path: Path, limit: int = 1200) -> str:
    try:
        text = path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return ""
    text = text.strip()
    if len(text) <= limit:
        return text
    return text[-limit:]


def _wait_for_spawned(proc: Any, host: str, port: int, timeout: float, log_path: Path) -> bool:
    from lit.webview_host import wait_for_http

    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if wait_for_http(host, port, timeout=0.4):
            return True
        if proc.poll() is not None:
            break
        time.sleep(0.15)
    code = proc.poll()
    tail = _log_tail(log_path)
    logger.error(
        "Shared server pid=%s exit=%s did not answer /health.\n%s",
        getattr(proc, "pid", None),
        code if code is not None else "still running",
        tail or "(server log is empty)",
    )
    return False


def ensure_server(host: str, port: int, data_dir: Path, *, timeout: float = 20.0) -> bool:
    """If ``/health`` is down, spawn the shared server and wait for it.

    Returns True when ``/health`` answers. A lock-race loser exits on its own;
    this wait still succeeds once the winner is serving.
    """
    from lit.webview_host import wait_for_http

    if wait_for_http(host, port, timeout=0.4):
        return True
    cmd = build_server_cmd(Path(data_dir), host, int(port))
    proc = spawn_detached_server(cmd, Path(data_dir))
    log_path = Path(data_dir) / "logs" / "server.log"
    return _wait_for_spawned(proc, host, int(port), timeout, log_path)


def maintain_server(
    stop: threading.Event,
    host: str,
    port: int,
    data_dir: Path,
    *,
    interval: float = 5.0,
    hard_after: float = 12.0,
    healthy: Any = None,
    revive: Any = None,
    restart: Any = None,
    clock: Any = None,
) -> None:
    """While the window is open, bring the shared server back if it stops answering.

    A clean exit is started again on the next check. If ``/health`` stays down
    for ``hard_after`` seconds, the stuck process is stopped and a new one starts.
    """
    from lit.webview_host import wait_for_http

    check = healthy if healthy is not None else (lambda: wait_for_http(host, port, timeout=1.0))
    start = revive if revive is not None else (lambda: ensure_server(host, port, Path(data_dir)))
    hard = restart if restart is not None else (lambda: restart_server(host, port, Path(data_dir)))
    now = clock if clock is not None else time.monotonic
    down_since: float | None = None
    while not stop.wait(interval):
        if stop.is_set():
            return
        try:
            ok = bool(check())
        except Exception:
            logger.exception("Server health check failed")
            ok = False
        if stop.is_set():
            return
        if ok:
            down_since = None
            continue
        seen = float(now())
        if down_since is None:
            down_since = seen
        try:
            if seen - down_since >= hard_after:
                hard()
                down_since = seen
            else:
                start()
        except Exception:
            logger.exception("Could not bring the server back")


def parse_listening_pids(text: str, port: int) -> list[int]:
    """PIDs from ``netstat -ano`` that are listening on ``port`` locally.

    Other addresses are left alone. Established connections are not listeners.
    """
    wanted = int(port)
    found: list[int] = []
    for line in text.splitlines():
        parts = line.split()
        if len(parts) < 5 or parts[0].upper() != "TCP":
            continue
        if parts[3].upper() != "LISTENING":
            continue
        local = parts[1]
        host, sep, raw_port = local.rpartition(":")
        if not sep:
            continue
        try:
            if int(raw_port) != wanted:
                continue
        except ValueError:
            continue
        if host not in ("127.0.0.1", "localhost", "[::1]", "0.0.0.0", "[::]"):
            continue
        try:
            pid = int(parts[4])
        except ValueError:
            continue
        if pid > 0 and pid not in found:
            found.append(pid)
    return found


def listening_pids(port: int) -> list[int]:
    """PIDs listening on ``port`` on this machine. Empty when we cannot tell."""
    if sys.platform != "win32":
        return []
    try:
        out = subprocess.check_output(
            ["netstat", "-ano", "-p", "tcp"],
            text=True,
            errors="replace",
            stdin=subprocess.DEVNULL,
            creationflags=CREATE_NO_WINDOW,
        )
    except (OSError, subprocess.SubprocessError):
        logger.exception("Could not list listeners on port %s", port)
        return []
    me = os.getpid()
    return [pid for pid in parse_listening_pids(out, port) if pid != me]


def stop_headless_servers() -> None:
    """Stop a previous ``lit serve --headless`` that is holding the data lock but not listening.

    ``pythonw`` did this: the process stayed up and the next start could not take the lock.
    """
    if sys.platform != "win32":
        return
    script = (
        "Get-CimInstance Win32_Process | "
        "Where-Object { $_.CommandLine -and $_.CommandLine -match 'headless' "
        "-and $_.CommandLine -match 'serve' } | "
        "ForEach-Object { Stop-Process -Id $_.ProcessId -Force -ErrorAction SilentlyContinue }"
    )
    try:
        subprocess.run(
            ["powershell", "-NoProfile", "-Command", script],
            stdin=subprocess.DEVNULL,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            check=False,
            timeout=15,
            creationflags=CREATE_NO_WINDOW,
        )
    except (OSError, subprocess.SubprocessError):
        logger.exception("Could not stop a stuck headless server")


def stop_listeners(port: int) -> None:
    """End processes that are still holding ``port`` after /health has failed."""
    for pid in listening_pids(port):
        logger.info("Stopping process %s holding port %s", pid, port)
        if sys.platform == "win32":
            subprocess.run(
                ["taskkill", "/PID", str(pid), "/F"],
                stdin=subprocess.DEVNULL,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                check=False,
                creationflags=CREATE_NO_WINDOW,
            )
            continue
        try:
            os.kill(pid, signal.SIGTERM)
        except OSError:
            logger.debug("Could not stop pid %s", pid, exc_info=True)


def release_stuck_server(port: int) -> None:
    stop_listeners(port)
    stop_headless_servers()
    time.sleep(0.4)


def restart_server(
    host: str,
    port: int,
    data_dir: Path,
    *,
    healthy: Any = None,
    stop_port: Any = None,
    start: Any = None,
    probe: float = 0.6,
) -> bool:
    """Bring the shared server back. A stuck listener is stopped first.

    Returns True when ``/health`` answers. Already-up does not kill anything.
    Overlapping calls wait, so the window and the keeper cannot kill each other.
    """
    with _restart_lock:
        return _restart_server(host, port, data_dir, healthy=healthy, stop_port=stop_port, start=start, probe=probe)


def _restart_server(
    host: str,
    port: int,
    data_dir: Path,
    *,
    healthy: Any = None,
    stop_port: Any = None,
    start: Any = None,
    probe: float = 0.6,
) -> bool:
    from lit.webview_host import wait_for_http

    check = healthy if healthy is not None else (lambda: wait_for_http(host, port, timeout=probe))
    stopper = stop_port if stop_port is not None else (lambda: release_stuck_server(int(port)))
    starter = start if start is not None else (lambda: ensure_server(host, port, Path(data_dir)))
    try:
        if bool(check()):
            return True
    except Exception:
        logger.exception("Server health check failed before restart")
    try:
        stopper()
    except Exception:
        logger.exception("Could not stop the stuck server")
    try:
        return bool(starter())
    except Exception:
        logger.exception("Could not restart the server")
        return False


