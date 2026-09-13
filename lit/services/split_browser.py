"""Open two http(s) URLs in Microsoft Edge, side by side (Windows)."""

from __future__ import annotations

import ctypes
import logging
import os
import shutil
import time
from pathlib import Path
from urllib.parse import urlparse

logger = logging.getLogger("lit.split_browser")

_EDGE_REL = Path("Microsoft") / "Edge" / "Application" / "msedge.exe"
SW_RESTORE = 9
SWP_SHOWWINDOW = 0x0040


def launchable_http_url(raw: str | None) -> str | None:
    s = str(raw or "").strip()
    if not s or len(s) > 2048 or '"' in s:
        return None
    try:
        parsed = urlparse(s)
    except Exception:
        return None
    if parsed.scheme not in ("http", "https") or not parsed.netloc:
        return None
    if parsed.username or parsed.password:
        return None
    return s


def find_msedge() -> str | None:
    for root in (
        os.environ.get("PROGRAMFILES(X86)"),
        os.environ.get("PROGRAMFILES"),
        os.environ.get("LOCALAPPDATA"),
    ):
        if not root:
            continue
        candidate = Path(root) / _EDGE_REL
        if candidate.is_file():
            return str(candidate)
    return shutil.which("msedge")


def split_rects(work: tuple[int, int, int, int]) -> tuple[tuple[int, int, int, int], tuple[int, int, int, int]]:
    left, top, right, bottom = work
    width = max(1, right - left)
    height = max(1, bottom - top)
    mid = left + width // 2
    return (left, top, mid - left, height), (mid, top, right - mid, height)


class _RECT(ctypes.Structure):
    _fields_ = [
        ("left", ctypes.c_long),
        ("top", ctypes.c_long),
        ("right", ctypes.c_long),
        ("bottom", ctypes.c_long),
    ]


def _work_area() -> tuple[int, int, int, int]:
    rect = _RECT()
    SPI_GETWORKAREA = 0x0030
    ok = ctypes.windll.user32.SystemParametersInfoW(SPI_GETWORKAREA, 0, ctypes.byref(rect), 0)
    if not ok:
        sm = ctypes.windll.user32.GetSystemMetrics
        return (0, 0, int(sm(0)), int(sm(1)))
    return (int(rect.left), int(rect.top), int(rect.right), int(rect.bottom))


def _visible_edge_hwnds() -> list[int]:
    user32 = ctypes.windll.user32
    hwnds: list[int] = []
    GWL_EXSTYLE = -20
    WS_EX_TOOLWINDOW = 0x00000080
    get_long = getattr(user32, "GetWindowLongPtrW", user32.GetWindowLongW)
    get_long.restype = ctypes.c_ssize_t

    @ctypes.WINFUNCTYPE(ctypes.c_bool, ctypes.c_void_p, ctypes.c_void_p)
    def callback(hwnd: int, _lparam: int) -> bool:
        if not user32.IsWindowVisible(hwnd):
            return True
        name = ctypes.create_unicode_buffer(256)
        user32.GetClassNameW(hwnd, name, 256)
        if name.value != "Chrome_WidgetWin_1":
            return True
        try:
            ex = int(get_long(hwnd, GWL_EXSTYLE) or 0)
        except Exception:
            ex = 0
        if ex & WS_EX_TOOLWINDOW:
            return True
        rect = _RECT()
        user32.GetWindowRect(hwnd, ctypes.byref(rect))
        if (rect.right - rect.left) < 240 or (rect.bottom - rect.top) < 180:
            return True
        hwnds.append(int(hwnd))
        return True

    user32.EnumWindows(callback, 0)
    return hwnds


def _wait_new_hwnd(before: set[int], timeout: float = 8.0) -> int | None:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        for hwnd in _visible_edge_hwnds():
            if hwnd not in before:
                return hwnd
        time.sleep(0.12)
    return None


def _place_window(hwnd: int, x: int, y: int, w: int, h: int) -> None:
    user32 = ctypes.windll.user32
    user32.ShowWindow(hwnd, SW_RESTORE)
    user32.SetWindowPos(hwnd, 0, x, y, w, h, SWP_SHOWWINDOW)


def open_edge_split(left_url: str, right_url: str, edge_path: str | None = None) -> dict[str, bool]:
    """Launch two Edge windows and snap them left/right."""
    import subprocess

    edge = edge_path or find_msedge()
    if not edge:
        raise FileNotFoundError("Microsoft Edge was not found")
    try:
        ctypes.windll.user32.SetProcessDPIAware()
    except Exception:
        pass

    left_rect, right_rect = split_rects(_work_area())
    before = set(_visible_edge_hwnds())
    positioned = True

    def launch(url: str, rect: tuple[int, int, int, int], known: set[int]) -> set[int]:
        nonlocal positioned
        x, y, w, h = rect
        subprocess.Popen(
            [
                edge,
                "--new-window",
                f"--window-position={x},{y}",
                f"--window-size={w},{h}",
                url,
            ],
            close_fds=False,
        )
        hwnd = _wait_new_hwnd(known)
        if hwnd is None:
            positioned = False
            logger.warning("Timed out waiting for a new Edge window for %s", url)
            return known
        try:
            _place_window(hwnd, x, y, w, h)
        except Exception:
            logger.exception("Could not position Edge window")
            positioned = False
        return known | {hwnd}

    after_left = launch(left_url, left_rect, before)
    launch(right_url, right_rect, after_left)
    return {"positioned": positioned}
