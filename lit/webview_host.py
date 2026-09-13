"""Optional WebView2 (Edge) window for the local app. Browser launch is unchanged."""

from __future__ import annotations

import logging
import socket
import sys
import time
from collections.abc import Callable
from typing import Any

logger = logging.getLogger("lit.webview")

# Do not hang a pywebview Window on js_api — JS enumeration of window.native
# (WinForms Form) recurses until it crashes (Empty.Empty… / ModifierKeys.A…).
_active: dict[str, Any] = {"window": None, "url": ""}

F5_RELOAD_JS = """
(function () {
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


def open_webview(url: str, title: str = "Local Issue Tracker") -> None:
    try:
        import webview
    except ImportError as exc:
        raise RuntimeError(
            "pywebview is not installed. From the repo folder run: uv sync"
        ) from exc

    bridge = WebviewBridge()
    window = webview.create_window(
        title,
        url,
        width=1400,
        height=900,
        min_size=(900, 600),
        js_api=bridge,
        background_color="#000000",
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

    window.events.loaded += bind_keys
    start_kwargs: dict[str, Any] = {}
    if sys.platform == "win32":
        start_kwargs["gui"] = "edgechromium"
    try:
        webview.start(**start_kwargs)
    except Exception:
        logger.exception("WebView2 (edgechromium) failed; retrying with the default GUI")
        webview.start()
    finally:
        _active["window"] = None
        _active["url"] = ""
