"""Optional WebView2 (Edge) window for the local app. Browser launch is unchanged."""

from __future__ import annotations

import ctypes
import logging
import socket
import sys
import threading
import time
import urllib.error
import urllib.request
from collections.abc import Callable
from typing import Any

logger = logging.getLogger("lit.webview")

# Do not hang a pywebview Window on js_api — JS enumeration of window.native
# (WinForms Form) recurses until it crashes (Empty.Empty… / ModifierKeys.A…).
_active: dict[str, Any] = {"window": None, "url": ""}

F5_RELOAD_JS = """
(function () {
  document.documentElement.setAttribute('data-webview', '1');
  if (window.__litReloadBound) return;
  window.__litReloadBound = true;
  window.addEventListener('keydown', function (e) {
    if (e.key === 'F5' && !e.ctrlKey && !e.altKey && !e.metaKey) {
      e.preventDefault();
      e.stopPropagation();
      location.reload();
    }
    if (e.key === 'F11' && !e.repeat && !e.ctrlKey && !e.altKey && !e.metaKey) {
      e.preventDefault();
      e.stopPropagation();
      if (window.pywebview && window.pywebview.api && window.pywebview.api.toggle_fullscreen) {
        window.pywebview.api.toggle_fullscreen();
      }
    }
  }, true);
})();
"""


def port_listening(host: str, port: int) -> bool:
    try:
        with socket.create_connection((host, port), timeout=0.4):
            return True
    except OSError:
        return False


def wait_for_port(host: str, port: int, timeout: float = 20.0) -> bool:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if port_listening(host, port):
            return True
        time.sleep(0.1)
    return False


def wait_for_http(host: str, port: int, timeout: float = 20.0) -> bool:
    """Wait until GET /health returns 200 so WebView2 does not load a blank page."""
    url = f"http://{host}:{port}/health"
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        try:
            with urllib.request.urlopen(url, timeout=0.6) as resp:
                if int(getattr(resp, "status", 200) or 200) == 200:
                    return True
        except (OSError, urllib.error.URLError, ValueError):
            pass
        time.sleep(0.1)
    return False


def reload_window(window: Any, url: str) -> None:
    """Navigate again so hashed UI assets are picked up (hard refresh)."""
    try:
        window.load_url(url)
        return
    except Exception:
        logger.exception("WebView load_url failed")
    try:
        window.evaluate_js("location.reload()")
    except Exception:
        logger.exception("WebView location.reload failed")


def make_view_menu(on_reload: Callable[[], Any]) -> list[Any]:
    from webview.menu import Menu, MenuAction

    return [Menu("View", [MenuAction("Reload\tF5", on_reload)])]


class WebviewBridge:
    """JS API only. No Window/Form attributes — those crash pywebview's JS bridge."""

    def reload(self) -> None:
        window = _active.get("window")
        url = str(_active.get("url") or "")
        if window is not None:
            reload_window(window, url)

    def toggle_fullscreen(self) -> None:
        now = time.monotonic()
        last = float(_active.get("fs_at") or 0)
        if now - last < 0.45:
            return
        _active["fs_at"] = now
        window = _active.get("window")
        if window is not None:
            window.toggle_fullscreen()

    def minimize(self) -> None:
        window = _active.get("window")
        if window is not None:
            window.minimize()

    def close_app(self) -> None:
        window = _active.get("window")
        if window is not None:
            window.destroy()

    def toggle_maximize(self) -> None:
        """Fill the monitor work area (taskbar stays). Not F11 fullscreen."""
        window = _active.get("window")
        if window is None:
            return
        try:
            form = window.native
        except Exception:
            return

        def _go() -> None:
            try:
                from System.Windows.Forms import Screen

                if _active.get("is_max"):
                    bounds = _active.get("restore_bounds")
                    if bounds:
                        x, y, w, h = bounds
                        form.SetBounds(int(x), int(y), int(w), int(h))
                    _active["is_max"] = False
                    return
                _active["restore_bounds"] = (
                    int(form.Left),
                    int(form.Top),
                    int(form.Width),
                    int(form.Height),
                )
                wa = Screen.FromControl(form).WorkingArea
                form.SetBounds(int(wa.X), int(wa.Y), int(wa.Width), int(wa.Height))
                _active["is_max"] = True
            except Exception:
                logger.exception("toggle_maximize failed")

        try:
            from System import Action

            if form.InvokeRequired:
                form.Invoke(Action(_go))
                return
        except Exception:
            pass
        _go()

    def start_resize(self, edge: str) -> None:
        """Begin a native Windows resize; must run on the UI thread while the button is down."""
        hit = _resize_hit(str(edge or ""))
        if hit is None:
            return
        _begin_ncl_resize(hit)

    def start_drag(self) -> None:
        """Drag the frameless window (HTCAPTION)."""
        _begin_ncl_resize(2)

    def main_ready(self) -> None:
        """Called from the UI after first paint so the splash can close."""
        from lit.branding import close_splash

        close_splash()


def _resize_hit(edge: str) -> int | None:
    return {
        "left": 10,
        "right": 11,
        "top": 12,
        "top-left": 13,
        "top-right": 14,
        "bottom": 15,
        "bottom-left": 16,
        "bottom-right": 17,
    }.get(edge)


def _begin_ncl_resize(hit: int) -> None:
    window = _active.get("window")
    if window is None:
        return
    try:
        form = window.native
        hwnd = int(form.Handle.ToInt64())
    except Exception:
        return

    def _go() -> None:
        user32 = ctypes.windll.user32
        user32.ReleaseCapture()
        user32.SendMessageW(hwnd, 0x00A1, hit, 0)  # WM_NCLBUTTONDOWN

    try:
        from System import Action

        if form.InvokeRequired:
            form.BeginInvoke(Action(_go))
            return
    except Exception:
        pass
    _go()


def _hit_from_client_point(
    x: int,
    y: int,
    width: int,
    height: int,
    border: int,
    top_border: int | None = None,
    bottom_border: int | None = None,
) -> int | None:
    side = border
    top_b = border if top_border is None else top_border
    bot_b = border if bottom_border is None else bottom_border
    left = x <= side
    right = x >= width - side
    top = y <= top_b
    bottom = y >= height - bot_b
    if top and left:
        return 13
    if top and right:
        return 14
    if bottom and left:
        return 16
    if bottom and right:
        return 17
    if left:
        return 10
    if right:
        return 11
    if top:
        return 12
    if bottom:
        return 15
    return None


def _apply_dark_frame(form: Any, hwnd: int) -> None:
    """Paint resize inset + Win11 DWM caption/border the same dark chrome as the toolbar."""
    try:
        from System.Drawing import Color

        dark = Color.FromArgb(255, 18, 21, 28)  # #12151c
        form.BackColor = dark
    except Exception:
        logger.exception("Could not set form BackColor")
    try:
        dwm = ctypes.windll.dwmapi
        # COLORREF is 0x00BBGGRR for #12151c
        color = ctypes.c_int(0x001C1512)
        dwm.DwmSetWindowAttribute.argtypes = [
            ctypes.c_void_p,
            ctypes.c_uint,
            ctypes.c_void_p,
            ctypes.c_uint,
        ]
        dwm.DwmSetWindowAttribute(hwnd, 20, ctypes.byref(ctypes.c_int(1)), 4)  # immersive dark
        dwm.DwmSetWindowAttribute(hwnd, 34, ctypes.byref(color), 4)  # border
        dwm.DwmSetWindowAttribute(hwnd, 35, ctypes.byref(color), 4)  # caption (top strip)
        dwm.DwmSetWindowAttribute(hwnd, 38, ctypes.byref(ctypes.c_int(2)), 4)  # backdrop
        class _MARGINS(ctypes.Structure):
            _fields_ = [
                ("cxLeftWidth", ctypes.c_int),
                ("cxRightWidth", ctypes.c_int),
                ("cyTopHeight", ctypes.c_int),
                ("cyBottomHeight", ctypes.c_int),
            ]

        # Don't extend a 1px DWM glass caption over the top inset.
        dwm.DwmExtendFrameIntoClientArea(hwnd, ctypes.byref(_MARGINS(0, 0, 0, 0)))
    except Exception:
        logger.exception("Could not set dark DWM frame colors")


def _enable_edge_resize(window: Any, border_px: int = 8, top_px: int = 4) -> None:
    """Inset WebView2 and handle Form.MouseDown so edge grabs run on the UI thread."""
    form = getattr(window, "native", None)
    if form is None:
        return
    hwnd = int(form.Handle.ToInt64())
    user32 = ctypes.windll.user32
    user32.GetWindowLongPtrW.restype = ctypes.c_void_p
    user32.SetWindowLongPtrW.restype = ctypes.c_void_p
    style = int(user32.GetWindowLongPtrW(hwnd, -16) or 0)
    user32.SetWindowLongPtrW(hwnd, -16, style | 0x00040000 | 0x00010000)
    user32.SetWindowPos(hwnd, 0, 0, 0, 0, 0, 0x0027)
    _apply_dark_frame(form, hwnd)

    wv = getattr(form, "webview", None)
    if wv is None:
        browser = getattr(form, "browser", None)
        wv = getattr(browser, "webview", None) if browser is not None else None
    try:
        from System.Drawing import Color as _Color

        if wv is not None and hasattr(wv, "DefaultBackgroundColor"):
            wv.DefaultBackgroundColor = _Color.FromArgb(255, 18, 21, 28)
    except Exception:
        pass

    from System.Windows.Forms import Cursors, DockStyle, MouseButtons

    if wv is not None:
        try:
            wv.Dock = getattr(DockStyle, "None")
        except Exception:
            pass

        def layout(_s: Any = None, _e: Any = None) -> None:
            try:
                maximized = bool(_active.get("is_max")) or int(form.WindowState) == 2
                w, h = int(form.ClientSize.Width), int(form.ClientSize.Height)
                if w < 80 or h < 80:
                    return
                if maximized:
                    wv.SetBounds(0, 0, w, h)
                else:
                    wv.SetBounds(
                        border_px,
                        top_px,
                        max(0, w - 2 * border_px),
                        max(0, h - top_px - border_px),
                    )
                _apply_dark_frame(form, hwnd)
            except Exception:
                logger.exception("WebView layout for resize border failed")

        form.Resize += layout
        layout()
        _active["resize_layout"] = layout

    def on_mouse_down(_s: Any, e: Any) -> None:
        try:
            if bool(_active.get("is_max")) or int(form.WindowState) == 2:
                return
            if e.Button != MouseButtons.Left:
                return
            hit = _hit_from_client_point(
                int(e.X),
                int(e.Y),
                int(form.ClientSize.Width),
                int(form.ClientSize.Height),
                border_px + 2,
                top_border=top_px + 1,
                bottom_border=border_px + 2,
            )
            if hit is None:
                return
            _begin_ncl_resize(hit)
        except Exception:
            logger.exception("Edge resize mouse-down failed")

    def on_mouse_move(_s: Any, e: Any) -> None:
        try:
            if bool(_active.get("is_max")) or int(form.WindowState) == 2:
                form.Cursor = Cursors.Default
                return
            hit = _hit_from_client_point(
                int(e.X),
                int(e.Y),
                int(form.ClientSize.Width),
                int(form.ClientSize.Height),
                border_px + 2,
                top_border=top_px + 1,
                bottom_border=border_px + 2,
            )
            cursors = {
                10: Cursors.SizeWE,
                11: Cursors.SizeWE,
                12: Cursors.SizeNS,
                15: Cursors.SizeNS,
                13: Cursors.SizeNWSE,
                17: Cursors.SizeNWSE,
                14: Cursors.SizeNESW,
                16: Cursors.SizeNESW,
            }
            form.Cursor = cursors.get(hit, Cursors.Default)
        except Exception:
            pass

    form.MouseDown += on_mouse_down
    form.MouseMove += on_mouse_move
    _active["resize_mouse"] = on_mouse_down
    _active["resize_move"] = on_mouse_move


def scale_window_to_monitor(
    monitor_w: int, monitor_h: int, fraction: float = 0.75, min_size: tuple[int, int] = (900, 600)
) -> tuple[int, int]:
    return max(min_size[0], int(monitor_w * fraction)), max(min_size[1], int(monitor_h * fraction))


def _startup_window_size() -> tuple[int, int]:
    """Logical pixels: 3/4 of the primary monitor. pywebview applies DPI after this."""
    user32 = ctypes.windll.user32
    try:
        user32.SetProcessDPIAware()
    except Exception:
        pass
    try:
        dpi = int(user32.GetDpiForSystem() or 96)
    except Exception:
        dpi = 96
    scale = (dpi / 96.0) if dpi > 0 else 1.0
    cx = int(user32.GetSystemMetrics(0) / scale)
    cy = int(user32.GetSystemMetrics(1) / scale)
    return scale_window_to_monitor(cx, cy)


def open_webview(url: str, title: str = "Local Issue Tracker") -> None:
    try:
        import webview
    except ImportError as exc:
        raise RuntimeError(
            "pywebview is not installed. From the repo folder run: uv sync"
        ) from exc

    bridge = WebviewBridge()
    width, height = _startup_window_size()
    from lit.branding import close_splash, icon_path

    ico = icon_path()
    window = webview.create_window(
        title,
        url,
        width=width,
        height=height,
        min_size=(900, 600),
        js_api=bridge,
        background_color="#0b0d12",
        frameless=True,
        easy_drag=False,
        shadow=True,
        resizable=True,
    )
    if window is None:
        raise RuntimeError("Could not create the WebView2 window")
    _active["window"] = window
    _active["url"] = url

    def bind_keys() -> None:
        try:
            window.evaluate_js(F5_RELOAD_JS)
        except Exception:
            logger.exception("Could not bind F5/F11 in WebView")

    def on_shown() -> None:
        try:
            _enable_edge_resize(window)
        except Exception:
            logger.exception("Could not enable resize frame on the frameless window")

    def on_loaded() -> None:
        bind_keys()
        # Keep the splash until JS main_ready (first paint). Closing on shown
        # revealed an empty black window. Fallback if the UI never calls in.
        def _fallback_close() -> None:
            time.sleep(12)
            try:
                close_splash()
            except Exception:
                pass

        threading.Thread(target=_fallback_close, name="lit-splash-fallback", daemon=True).start()

    window.events.shown += on_shown
    window.events.loaded += on_loaded
    start_kwargs: dict[str, Any] = {}
    if sys.platform == "win32":
        start_kwargs["gui"] = "edgechromium"
    if ico.is_file():
        start_kwargs["icon"] = str(ico)
    try:
        webview.start(**start_kwargs)
    except Exception:
        logger.exception("WebView2 (edgechromium) failed; retrying with the default GUI")
        retry_kwargs: dict[str, Any] = {}
        if ico.is_file():
            retry_kwargs["icon"] = str(ico)
        webview.start(**retry_kwargs)
    finally:
        try:
            close_splash()
        except Exception:
            pass
        _active["window"] = None
        _active["url"] = ""
