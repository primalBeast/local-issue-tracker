"""Optional WebView2 (Edge) window for the local app. Browser launch is unchanged."""

from __future__ import annotations

import ctypes
import logging
import re
import socket
import sys
import threading
import time
import urllib.error
import urllib.parse
import urllib.request
from collections.abc import Callable
from typing import Any

logger = logging.getLogger("lit.webview")

# Do not hang a pywebview Window on js_api — JS enumeration of window.native
# (WinForms Form) recurses until it crashes (Empty.Empty… / ModifierKeys.A…).
# client_id / released / finalizing are guarded by _state_lock. The window
# close worker reads them from another thread.
_active: dict[str, Any] = {
    "window": None,
    "url": "",
    "client_id": None,
    "released": False,
    "finalizing": False,
    "close_started": False,
    "close_worker": None,
}
_state_lock = threading.Lock()

# Same shape the session API accepts (a uuid fits). Invalid ids are ignored.
CLIENT_ID_RE = re.compile(r"^[A-Za-z0-9_-]{8,64}$")
# Page helpers from the window. Missing helpers are a no-op (falsy pending).
CLOSE_FLUSH_JS = "window.__litCloseFlush && window.__litCloseFlush()"
SAVES_PENDING_JS = "!!(window.__litSavesPending && window.__litSavesPending())"
# Flush budget is 500 ms (Tracker Review). The release POST is capped at 1 s.
FLUSH_CAP_SECONDS = 0.5
FLUSH_POLL_SECONDS = 0.05
RELEASE_TIMEOUT_SECONDS = 1.0

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
        """Close after the page has already flushed and released.

        The ✕ path does flush-then-release in JS, then calls this. Marking
        ``released`` makes the closing hook let that close through instead of
        posting release-all a second time.
        """
        with _state_lock:
            _active["released"] = True
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

    def main_ready(self, client_id: str | None = None) -> None:
        """Called from the UI after first paint so the splash can close.

        ``client_id`` is this window's sessionStorage id. The closing hook
        posts release-all with it. An invalid id is ignored and does not
        clear one that was already stored.
        """
        remember_client_id(client_id)
        from lit.branding import close_splash

        close_splash()


class CloseIO:
    """Side effects for the close sequence. Tests replace these."""

    def __init__(self) -> None:
        self.poster: Callable[[str, float], None] = post_release_all
        self.clock: Callable[[], float] = time.monotonic
        self.sleep: Callable[[float], None] = time.sleep
        self.flush_cap = FLUSH_CAP_SECONDS
        self.poll_interval = FLUSH_POLL_SECONDS
        self.release_timeout = RELEASE_TIMEOUT_SECONDS


def remember_client_id(client_id: str | None) -> None:
    """Store ``client_id`` when it matches the session API. Otherwise keep the old one."""
    if client_id is None or client_id == "":
        return
    if not isinstance(client_id, str) or CLIENT_ID_RE.fullmatch(client_id) is None:
        logger.warning("Ignoring invalid webview client id")
        return
    with _state_lock:
        _active["client_id"] = client_id


def release_all_url(page_url: str, client_id: str) -> str | None:
    """POST target for release-all, from the URL passed to ``open_webview``."""
    try:
        parsed = urllib.parse.urlsplit(page_url)
        host = parsed.hostname
        port = parsed.port
    except ValueError:
        logger.error("Cannot parse server URL %r for session release", page_url)
        return None
    if not host:
        return None
    if port is None:
        port = 443 if parsed.scheme == "https" else 80
    scheme = parsed.scheme or "http"
    host_part = f"[{host}]" if ":" in host else host
    query = urllib.parse.urlencode({"client": client_id})
    return f"{scheme}://{host_part}:{port}/api/session/release-all?{query}"


def post_release_all(url: str, timeout: float) -> None:
    """POST release-all. No Origin header: this is not a browser fetch.

    Errors are logged and swallowed. The window still closes if the server
    is already gone.
    """
    request = urllib.request.Request(url, data=b"", method="POST")
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            response.read()
    except Exception:
        logger.exception("Session release-all failed: %s", url)


close_io = CloseIO()


def _still_pending(value: Any) -> bool:
    if isinstance(value, str):
        return value.strip().lower() == "true"
    return bool(value)


def _flush_pending_saves(window: Any) -> None:
    """Run the page flush, then poll until saves are clear or the cap hits.

    Any ``evaluate_js`` failure means the page is already gone: stop waiting
    and let the caller release.
    """
    clock = close_io.clock
    sleep = close_io.sleep
    cap = close_io.flush_cap
    interval = close_io.poll_interval
    start = clock()

    try:
        window.evaluate_js(CLOSE_FLUSH_JS)
    except Exception:
        logger.exception("Close flush failed; treating the page as gone")
        return

    # Backstop if the clock barely moves, so a broken sleep cannot spin.
    polls = 0
    while clock() - start < cap:
        polls += 1
        if polls > 10000:
            logger.warning("Close-flush poll backstop hit; releasing anyway")
            return
        try:
            pending = window.evaluate_js(SAVES_PENDING_JS)
        except Exception:
            logger.exception("Save-pending poll failed; treating the page as gone")
            return
        if not _still_pending(pending):
            return
        remaining = cap - (clock() - start)
        if remaining <= 0:
            return
        before = clock()
        sleep(min(interval, remaining))
        # A clock that does not move would spin. Release instead.
        if clock() <= before:
            logger.warning("Close-flush clock did not advance; releasing anyway")
            return


def _post_client_release(page_url: str, client_id: str) -> None:
    url = release_all_url(page_url, client_id)
    if url is None:
        logger.error("No server URL for session release-all; skipping POST")
        return
    try:
        close_io.poster(url, close_io.release_timeout)
    except Exception:
        logger.exception("Session release-all failed: %s", url)


def _finish_close(window: Any, client_id: str, page_url: str) -> None:
    """Flush, then release, then destroy. Runs off the UI thread."""
    try:
        logger.info("Window closing: flush then release client %s", client_id)
        try:
            _flush_pending_saves(window)
        except Exception:
            logger.exception("Close flush failed")
        _post_client_release(page_url, client_id)
    finally:
        # Always mark the close finished before destroy, so the closing event
        # destroy() raises is allowed through even if the flush or POST failed.
        with _state_lock:
            _active["released"] = True
            _active["finalizing"] = True
        try:
            window.destroy()
        except Exception:
            logger.exception("Destroy after release failed")


def on_window_closing() -> bool | None:
    """pywebview ``closing`` handler.

    Return False to cancel the close once and finish it from a worker.
    Return None to let the close proceed.

    Do not evaluate JavaScript or join the worker here. The handler runs on
    the WinForms UI thread inside FormClosing, and a synchronous script call
    deadlocks EdgeChromium: the result is marshalled back onto that same thread.
    """
    with _state_lock:
        client_id = _active.get("client_id")
        if _active.get("released") or not client_id or _active.get("finalizing"):
            return None
        if _active.get("close_started"):
            return False
        window = _active.get("window")
        page_url = str(_active.get("url") or "")
        if window is None or not isinstance(client_id, str):
            return None
        _active["close_started"] = True
        thread = threading.Thread(
            target=_finish_close,
            args=(window, client_id, page_url),
            name="lit-close-release",
            daemon=True,
        )
        _active["close_worker"] = thread
    thread.start()
    return False


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
    with _state_lock:
        _active["window"] = window
        _active["url"] = url
        _active["client_id"] = None
        _active["released"] = False
        _active["finalizing"] = False
        _active["close_started"] = False
        _active["close_worker"] = None

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
    window.events.closing += on_window_closing
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
        with _state_lock:
            _active["window"] = None
            _active["url"] = ""
            _active["client_id"] = None
            _active["released"] = False
            _active["finalizing"] = False
            _active["close_started"] = False
            _active["close_worker"] = None
