"""Windows app icon, splash window, and taskbar identity."""

from __future__ import annotations

import ctypes
import logging
import os
import subprocess
import sys
from pathlib import Path

logger = logging.getLogger("lit.branding")

APP_USER_MODEL_ID = "primalBeast.LocalIssueTracker"
SPLASH_TITLE = "Local Issue Tracker Starting"
WM_CLOSE = 0x0010


def assets_dir() -> Path:
    return Path(__file__).resolve().parent / "assets"


def icon_path() -> Path:
    return assets_dir() / "app.ico"


def splash_image_path() -> Path:
    return assets_dir() / "splash.png"


def splash_hta_path() -> Path:
    return assets_dir() / "splash.hta"


def splash_close_path() -> Path:
    return Path(os.environ.get("TEMP") or os.environ.get("TMP") or ".") / "lit-splash.close"


def apply_app_user_model_id() -> None:
    if sys.platform != "win32":
        return
    try:
        ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID(APP_USER_MODEL_ID)
    except Exception:
        logger.exception("Could not set AppUserModelID")


def minimize_console() -> None:
    """Keep the helper console off-screen; restore from the taskbar for logs."""
    if sys.platform != "win32":
        return
    try:
        hwnd = ctypes.windll.kernel32.GetConsoleWindow()
        if hwnd:
            ctypes.windll.user32.ShowWindow(hwnd, 6)  # SW_MINIMIZE
    except Exception:
        logger.exception("Could not minimize console")


def _find_splash_hwnd() -> int:
    user32 = ctypes.windll.user32
    user32.FindWindowW.argtypes = [ctypes.c_wchar_p, ctypes.c_wchar_p]
    user32.FindWindowW.restype = ctypes.c_void_p
    return int(user32.FindWindowW(None, SPLASH_TITLE) or 0)


def start_splash() -> None:
    if sys.platform != "win32":
        return
    hta = splash_hta_path()
    if not hta.is_file():
        return
    try:
        splash_close_path().unlink(missing_ok=True)
    except OSError:
        pass
    if _find_splash_hwnd():
        return
    try:
        # GUI subsystem: do not use CREATE_NO_WINDOW / SW_HIDE (those hide the splash).
        subprocess.Popen(
            ["mshta.exe", str(hta)],
            cwd=str(hta.parent),
            close_fds=True,
        )
    except Exception:
        logger.exception("Could not start splash")


def close_splash() -> None:
    if sys.platform != "win32":
        return
    try:
        splash_close_path().write_text("1", encoding="ascii")
    except OSError:
        logger.exception("Could not write splash close marker")
    hwnd = _find_splash_hwnd()
    if hwnd:
        ctypes.windll.user32.PostMessageW(hwnd, WM_CLOSE, 0, 0)
