"""Exclusive OS lock on the data root.

One lit server may own a data directory. The lock is a byte lock on
``.data.lock`` (Windows ``msvcrt``) or ``flock`` (POSIX). The kernel drops it
when the process exits or crashes, so a dead process cannot leave a stale lock.
If neither backend imports, startup fails closed.
"""

from __future__ import annotations

import atexit
import errno
import logging
import os
import sys
from pathlib import Path
from typing import Any

from lit.paths import lock_path

logger = logging.getLogger("lit.lock")

# Raw CRT fd. msvcrt.locking uses the OS position, so a buffered file object
# would be the wrong cursor on Windows.
_lock_fd: int | None = None
_locked_path: Path | None = None
_backend_name: str | None = None
_atexit_registered = False

_BUSY_ERRNOS: set[int] = set()
for _name in ("EACCES", "EAGAIN", "EDEADLK", "EWOULDBLOCK"):
    _value = getattr(errno, _name, None)
    if isinstance(_value, int):
        _BUSY_ERRNOS.add(_value)
# Windows CRT: ERROR_LOCK_VIOLATION is often reported as errno 13 or 36.
_BUSY_ERRNOS.update({13, 36})

# Sharing / lock failures from the Windows API, when errno was not mapped.
_BUSY_WINERRORS = {32, 33, 36, 167}

_NO_BACKEND = "no file-locking backend; refusing to run without a data lock"


def _try_import(name: str) -> Any | None:
    try:
        return __import__(name)
    except ImportError:
        return None


def _load_backend() -> tuple[str, Any]:
    msvcrt = _try_import("msvcrt")
    if msvcrt is not None and hasattr(msvcrt, "locking"):
        return "msvcrt", msvcrt
    fcntl = _try_import("fcntl")
    if fcntl is not None and hasattr(fcntl, "flock"):
        return "fcntl", fcntl
    logger.error(_NO_BACKEND)
    print(_NO_BACKEND, file=sys.stderr, flush=True)
    raise SystemExit(1)


def _is_lock_busy(exc: BaseException) -> bool:
    if isinstance(exc, BlockingIOError):
        return True
    if not isinstance(exc, OSError):
        return False
    if exc.errno in _BUSY_ERRNOS:
        return True
    winerror = getattr(exc, "winerror", None)
    if isinstance(winerror, int) and winerror in _BUSY_WINERRORS:
        return True
    return "permission denied" in str(exc).lower()


def _open_lock_fd(path: Path) -> int:
    path.parent.mkdir(parents=True, exist_ok=True)
    flags = os.O_RDWR | os.O_CREAT
    # Do not let a child process inherit the lock fd and keep it after we exit.
    if hasattr(os, "O_CLOEXEC"):
        flags |= os.O_CLOEXEC
    if hasattr(os, "O_NOINHERIT"):
        flags |= os.O_NOINHERIT
    return os.open(os.fspath(path), flags, 0o644)


def _ensure_lock_byte(fd: int) -> None:
    """Byte 0 must exist before ``msvcrt.locking``. Never truncate the file."""
    os.lseek(fd, 0, os.SEEK_SET)
    if os.fstat(fd).st_size < 1:
        os.write(fd, b"\0")
        os.fsync(fd)
    os.lseek(fd, 0, os.SEEK_SET)


def _lock_fd_now(fd: int, name: str, backend: Any) -> None:
    # Lock byte 0 only. Never truncate: that drops the msvcrt lock region.
    _ensure_lock_byte(fd)
    if name == "msvcrt":
        backend.locking(fd, backend.LK_NBLCK, 1)
        return
    backend.flock(fd, backend.LOCK_EX | backend.LOCK_NB)


def _unlock_fd(fd: int, name: str | None) -> None:
    if name == "msvcrt":
        msvcrt = _try_import("msvcrt")
        if msvcrt is None:
            return
        os.lseek(fd, 0, os.SEEK_SET)
        msvcrt.locking(fd, msvcrt.LK_UNLCK, 1)
        return
    if name == "fcntl":
        fcntl = _try_import("fcntl")
        if fcntl is None:
            return
        fcntl.flock(fd, fcntl.LOCK_UN)


def try_acquire_data_lock() -> bool:
    """Acquire the data-root lock without exiting when it is busy.

    Returns True when this process holds the lock. Returns False when another
    process holds it. Exits non-zero when no file-locking backend imports.
    """
    global _lock_fd, _locked_path, _backend_name, _atexit_registered
    name, backend = _load_backend()
    path = lock_path().resolve()
    if _lock_fd is not None:
        if _locked_path == path:
            return True
        release_data_lock()
    try:
        fd = _open_lock_fd(path)
    except OSError as exc:
        if _is_lock_busy(exc):
            return False
        raise
    try:
        _lock_fd_now(fd, name, backend)
    except OSError as exc:
        os.close(fd)
        if _is_lock_busy(exc):
            return False
        raise
    _lock_fd = fd
    _locked_path = path
    _backend_name = name
    if not _atexit_registered:
        atexit.register(release_data_lock)
        _atexit_registered = True
    logger.info("Acquired data lock at %s", path)
    return True


def acquire_data_lock() -> None:
    """Acquire the data-root lock or exit 1 with a clear message."""
    if try_acquire_data_lock():
        return
    directory = lock_path().resolve().parent
    message = f"Another lit process holds the data directory ({directory}). Close it first."
    logger.error(message)
    print(message, file=sys.stderr, flush=True)
    raise SystemExit(1)


def release_data_lock() -> None:
    """Release the lock held by this process. Safe to call more than once."""
    global _lock_fd, _locked_path, _backend_name
    fd = _lock_fd
    name = _backend_name
    if fd is None:
        return
    _lock_fd = None
    _locked_path = None
    _backend_name = None
    try:
        _unlock_fd(fd, name)
    except Exception:
        logger.debug("Unlocking the data lock failed", exc_info=True)
    try:
        os.close(fd)
    except Exception:
        logger.debug("Closing the data lock file failed", exc_info=True)
