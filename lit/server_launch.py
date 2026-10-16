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
from pathlib import Path
from typing import Any

logger = logging.getLogger("lit.server")

# CREATE_NO_WINDOW is ignored if DETACHED_PROCESS is also set, and a console
# Python then opens its own terminal. Do not combine them.
CREATE_NO_WINDOW = 0x08000000
CREATE_NEW_PROCESS_GROUP = 0x00000200
WIN_DETACHED_FLAGS = CREATE_NO_WINDOW | CREATE_NEW_PROCESS_GROUP


def server_interpreter() -> str:
    """Prefer pythonw.exe next to the current interpreter on Windows."""
    if sys.platform == "win32":
        candidate = Path(sys.executable).with_name("pythonw.exe")
        if candidate.is_file():
            return str(candidate)
    return sys.executable


def build_server_cmd(data_dir: Path, host: str, port: int) -> list[str]:
    """Command line for the detached ``lit serve --headless --exit-when-idle``."""
    return [
        server_interpreter(),
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
        kwargs["creationflags"] = WIN_DETACHED_FLAGS
    else:
        kwargs["start_new_session"] = True
    try:
        proc = subprocess.Popen(cmd, **kwargs)
    finally:
        log_fh.close()
    _reap_in_background(proc)
    logger.info("Spawned detached lit server pid=%s", getattr(proc, "pid", None))
    return proc


def ensure_server(host: str, port: int, data_dir: Path, *, timeout: float = 20.0) -> bool:
    """If ``/health`` is down, spawn the shared server and wait for it.

    Returns True when ``/health`` answers. A lock-race loser exits on its own;
    this wait still succeeds once the winner is serving.
    """
    from lit.webview_host import wait_for_http

    if wait_for_http(host, port, timeout=0.4):
        return True
    cmd = build_server_cmd(Path(data_dir), host, int(port))
    spawn_detached_server(cmd, Path(data_dir))
    return wait_for_http(host, port, timeout=timeout)


def maintain_server(
    stop: threading.Event,
    host: str,
    port: int,
    data_dir: Path,
    *,
    interval: float = 5.0,
    healthy: Any = None,
    revive: Any = None,
) -> None:
    """While the window is open, start the shared server again if it has exited.

    Sleep drops the browser socket. The server then looks idle and exits.
    The window is still open, so this brings ``/health`` back.
    """
    from lit.webview_host import wait_for_http

    check = healthy if healthy is not None else (lambda: wait_for_http(host, port, timeout=1.0))
    start = revive if revive is not None else (lambda: ensure_server(host, port, Path(data_dir)))
    while not stop.wait(interval):
        if stop.is_set():
            return
        try:
            ok = bool(check())
        except Exception:
            logger.exception("Server health check failed")
            ok = False
        if ok or stop.is_set():
            continue
        try:
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


def restart_server(
    host: str,
    port: int,
    data_dir: Path,
    *,
    healthy: Any = None,
    stop_port: Any = None,
    start: Any = None,
) -> bool:
    """Bring the shared server back. A stuck listener is stopped first.

    Returns True when ``/health`` answers. Already-up does not kill anything.
    """
    from lit.webview_host import wait_for_http

    check = healthy if healthy is not None else (lambda: wait_for_http(host, port, timeout=0.6))
    stopper = stop_port if stop_port is not None else (lambda: stop_listeners(int(port)))
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


