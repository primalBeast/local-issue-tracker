"""Windows app icon, splash window, and taskbar identity."""

from __future__ import annotations

import ctypes
import logging
import subprocess
import sys
from pathlib import Path

logger = logging.getLogger("lit.branding")

APP_USER_MODEL_ID = "primalBeast.LocalIssueTracker"
SPLASH_CLOSE_EVENT = "LocalIssueTracker.SplashClose"


def assets_dir() -> Path:
    return Path(__file__).resolve().parent / "assets"


def icon_path() -> Path:
    return assets_dir() / "app.ico"


def splash_image_path() -> Path:
    return assets_dir() / "splash.png"


def splash_script_path() -> Path:
    return assets_dir() / "show-splash.ps1"


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


def _event_handle(*, create: bool, signaled: bool = False) -> int:
    kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
    kernel32.CreateEventW.restype = ctypes.c_void_p
    kernel32.OpenEventW.restype = ctypes.c_void_p
    if create:
        handle = kernel32.CreateEventW(None, True, signaled, SPLASH_CLOSE_EVENT)
    else:
        handle = kernel32.OpenEventW(0x0002, False, SPLASH_CLOSE_EVENT)
    return int(handle or 0)


def start_splash() -> None:
    if sys.platform != "win32":
        return
    script = splash_script_path()
    if not script.is_file():
        return
    try:
        handle = _event_handle(create=True, signaled=False)
        if handle:
            ctypes.windll.kernel32.ResetEvent(handle)
            ctypes.windll.kernel32.CloseHandle(handle)
        flags = 0
        if hasattr(subprocess, "CREATE_NO_WINDOW"):
            flags |= subprocess.CREATE_NO_WINDOW
        if hasattr(subprocess, "CREATE_NEW_PROCESS_GROUP"):
            flags |= subprocess.CREATE_NEW_PROCESS_GROUP
        subprocess.Popen(
            [
                "powershell.exe",
                "-STA",
                "-NoProfile",
                "-WindowStyle",
                "Hidden",
                "-ExecutionPolicy",
                "Bypass",
                "-File",
                str(script),
            ],
            cwd=str(script.parent),
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            creationflags=flags,
        )
    except Exception:
        logger.exception("Could not start splash")


def close_splash() -> None:
    if sys.platform != "win32":
        return
    try:
        handle = _event_handle(create=True, signaled=True)
        if handle:
            ctypes.windll.kernel32.SetEvent(handle)
            ctypes.windll.kernel32.CloseHandle(handle)
    except Exception:
        logger.exception("Could not close splash")
