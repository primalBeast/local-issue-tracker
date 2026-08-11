"""Advisory exclusive lock on the data root (K17)."""

from __future__ import annotations

import atexit
import logging
import sys
from pathlib import Path
from typing import BinaryIO

from lit.paths import lock_path

logger = logging.getLogger("lit.lock")

_lock_file: BinaryIO | None = None


def acquire_data_lock() -> None:
    """Acquire exclusive flock on data root. Exit if another process holds it."""
    global _lock_file
    path = lock_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    f = open(path, "a+b")
    try:
        import fcntl

        fcntl.flock(f.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
    except BlockingIOError:
        f.close()
        logger.error(
            "Another lit process holds the data directory (%s). Exiting.",
            path.parent,
        )
        sys.exit(1)
    except ImportError:
        # Windows fallback: best-effort exclusive create marker
        logger.warning("fcntl unavailable; using simple lock file")
    _lock_file = f
    f.seek(0)
    f.truncate()
    f.write(b"locked\n")
    f.flush()
    atexit.register(release_data_lock)
    logger.info("Acquired data lock at %s", path)


def release_data_lock() -> None:
    global _lock_file
    if _lock_file is None:
        return
    try:
        import fcntl

        fcntl.flock(_lock_file.fileno(), fcntl.LOCK_UN)
    except Exception:
        pass
    try:
        _lock_file.close()
    except Exception:
        pass
    _lock_file = None
