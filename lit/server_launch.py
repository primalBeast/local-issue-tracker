"""Spawn the shared headless server detached from a WebView launcher.

The window process is only a client. The server process holds the data-root
lock and outlives any one window. A second launcher that loses the lock race
exits; its parent keeps waiting until ``/health`` answers.
"""

from __future__ import annotations

import logging
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

