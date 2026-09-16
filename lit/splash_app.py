"""Standalone splash process: pythonw -m lit.splash_app

A separate process is required so Application/Tk can run its own loop.
PowerShell WinForms is often blocked on locked-down work PCs (Constrained Language).
"""

from __future__ import annotations

import ctypes
import logging
import os
import sys
import time
from pathlib import Path

APP_USER_MODEL_ID = "primalBeast.LocalIssueTracker"
SPLASH_CLOSE_EVENT = "LocalIssueTracker.SplashClose"
SPLASH_MUTEX = "LocalIssueTracker.Splash"
ERROR_ALREADY_EXISTS = 183
WAIT_OBJECT_0 = 0


def _log(message: str) -> None:
    try:
        path = Path(os.environ.get("TEMP") or os.environ.get("TMP") or ".") / "local-issue-tracker-splash.log"
        with path.open("a", encoding="utf-8") as fh:
            fh.write(time.strftime("%H:%M:%S ") + message + "\n")
    except Exception:
        pass


def assets_dir() -> Path:
    return Path(__file__).resolve().parent / "assets"


def _mutex_already_running() -> bool:
    kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
    kernel32.CreateMutexW.restype = ctypes.c_void_p
    handle = kernel32.CreateMutexW(None, True, SPLASH_MUTEX)
    if not handle:
        return False
    return ctypes.get_last_error() == ERROR_ALREADY_EXISTS


def _close_event():
    kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
    kernel32.CreateEventW.restype = ctypes.c_void_p
    kernel32.WaitForSingleObject.argtypes = [ctypes.c_void_p, ctypes.c_uint]
    kernel32.WaitForSingleObject.restype = ctypes.c_uint
    handle = kernel32.CreateEventW(None, True, False, SPLASH_CLOSE_EVENT)
    if handle:
        kernel32.ResetEvent(handle)
    return kernel32, handle


def run() -> int:
    if sys.platform != "win32":
        return 0
    try:
        ctypes.windll.ole32.CoInitializeEx(None, 0x2)  # STA
    except Exception:
        pass
    try:
        ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID(APP_USER_MODEL_ID)
    except Exception:
        pass
    try:
        ctypes.windll.shcore.SetProcessDpiAwareness(1)
    except Exception:
        try:
            ctypes.windll.user32.SetProcessDPIAware()
        except Exception:
            pass

    if _mutex_already_running():
        _log("another splash already running")
        return 0

    try:
        import tkinter as tk
    except Exception as exc:
        _log(f"tkinter import failed: {exc}")
        return 1

    kernel32, close_h = _close_event()

    root = tk.Tk()
    root.title("Local Issue Tracker")
    root.overrideredirect(True)
    root.configure(bg="#0b0d12")
    try:
        root.attributes("-topmost", True)
    except tk.TclError:
        pass

    width, height = 720, 430
    sw = int(root.winfo_screenwidth() or 1280)
    sh = int(root.winfo_screenheight() or 720)
    root.geometry(f"{width}x{height}+{(sw - width) // 2}+{(sh - height) // 2}")

    photo = None
    img_path = assets_dir() / "splash.png"
    if img_path.is_file():
        try:
            from PIL import Image, ImageTk

            im = Image.open(img_path).convert("RGBA")
            im.thumbnail((720, 378), Image.Resampling.LANCZOS)
            photo = ImageTk.PhotoImage(im)
        except Exception as exc:
            _log(f"PIL splash image failed: {exc}")
            try:
                photo = tk.PhotoImage(file=str(img_path))
            except Exception as exc2:
                _log(f"tk PhotoImage failed: {exc2}")

    if photo is not None:
        pic = tk.Label(root, image=photo, bg="#0b0d12", bd=0)
        pic.image = photo
        pic.place(x=0, y=0, width=720, height=378)
    else:
        tk.Label(
            root,
            text="Local Issue Tracker",
            fg="#e8eaed",
            bg="#0b0d12",
            font=("Segoe UI", 22, "bold"),
        ).place(x=0, y=140, width=720, height=40)

    bar = tk.Frame(root, bg="#12151c")
    bar.place(x=0, y=378, width=720, height=52)
    tk.Label(
        bar,
        text="Local Issue Tracker",
        fg="#e8eaed",
        bg="#12151c",
        font=("Segoe UI", 12, "bold"),
    ).pack(side="left", padx=18, pady=12)
    tk.Label(
        bar,
        text="Starting...",
        fg="#6ea8fe",
        bg="#12151c",
        font=("Segoe UI", 10),
    ).pack(side="right", padx=18, pady=12)

    ico = assets_dir() / "app.ico"
    if ico.is_file():
        try:
            root.iconbitmap(default=str(ico))
        except tk.TclError:
            try:
                root.iconbitmap(str(ico))
            except tk.TclError:
                pass

    started = time.monotonic()

    def tick() -> None:
        signaled = False
        if close_h:
            try:
                signaled = int(kernel32.WaitForSingleObject(close_h, 0)) == WAIT_OBJECT_0
            except Exception:
                signaled = False
        if signaled or (time.monotonic() - started) > 90:
            root.destroy()
            return
        root.after(200, tick)

    tick()
    try:
        root.mainloop()
    except Exception as exc:
        _log(f"mainloop failed: {exc}")
        return 1
    return 0


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    try:
        raise SystemExit(run())
    except Exception as exc:
        _log(f"splash crashed: {exc}")
        raise
