from __future__ import annotations

import inspect
import socket

import pytest

from lit.cli import main
from lit import webview_host
from lit.webview_host import (
    F5_RELOAD_JS,
    WebviewBridge,
    _hit_from_client_point,
    make_view_menu,
    port_listening,
    scale_window_to_monitor,
    wait_for_http,
    wait_for_port,
)


def test_port_listening_false_on_unused_port():
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.bind(("127.0.0.1", 0))
    port = sock.getsockname()[1]
    sock.close()
    assert port_listening("127.0.0.1", port) is False


def test_wait_for_port_times_out_quickly():
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.bind(("127.0.0.1", 0))
    port = sock.getsockname()[1]
    sock.close()
    assert wait_for_port("127.0.0.1", port, timeout=0.2) is False


def test_wait_for_http_times_out_quickly():
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.bind(("127.0.0.1", 0))
    port = sock.getsockname()[1]
    sock.close()
    assert wait_for_http("127.0.0.1", port, timeout=0.2) is False


def test_js_api_does_not_hold_a_window_attribute():
    bridge = WebviewBridge()
    assert not hasattr(bridge, "window")
    assert callable(bridge.minimize)
    assert callable(bridge.close_app)
    assert callable(bridge.toggle_fullscreen)
    assert callable(bridge.toggle_maximize)
    assert callable(bridge.start_resize)
    assert callable(bridge.start_drag)
    assert callable(bridge.main_ready)


def test_scale_window_to_monitor_is_three_quarters():
    assert scale_window_to_monitor(1920, 1080) == (1440, 810)
    assert scale_window_to_monitor(1280, 720) == (960, 600)


def test_hit_from_client_point_edges():
    assert _hit_from_client_point(0, 50, 400, 300, 10) == 10
    assert _hit_from_client_point(399, 50, 400, 300, 10) == 11
    assert _hit_from_client_point(50, 0, 400, 300, 10) == 12
    assert _hit_from_client_point(50, 299, 400, 300, 10) == 15
    assert _hit_from_client_point(0, 0, 400, 300, 10) == 13
    assert _hit_from_client_point(200, 150, 400, 300, 10) is None
    assert _hit_from_client_point(50, 3, 400, 300, 8, top_border=4) == 12
    assert _hit_from_client_point(50, 6, 400, 300, 8, top_border=4) is None


def test_view_menu_has_reload():
    called = []
    menu = make_view_menu(lambda: called.append(True))
    assert menu[0].title == "View"
    action = menu[0].items[0]
    assert "Reload" in action.title
    assert "F5" in action.title
    action.function()
    assert called == [True]


def test_f5_script_listens_for_f5():
    assert "F5" in F5_RELOAD_JS
    assert "location.reload" in F5_RELOAD_JS
    assert "F11" in F5_RELOAD_JS
    assert "toggle_fullscreen" in F5_RELOAD_JS


def test_open_webview_does_not_pass_icon_to_pywebview():
    src = inspect.getsource(webview_host.open_webview)
    # pywebview WinForms does Form.Icon = Icon(path) when icon= is passed; that
    # pythonnet call stack-overflows (exit -805306369) on some Windows PCs.
    assert 'start_kwargs["icon"]' not in src
    assert "form.Icon" not in src
    assert "close_splash" in src
    assert "hidden=True" not in src
    assert src.index("events.loaded") < src.index("webview.start")
    shown = src[src.index("def on_shown") : src.index("def on_loaded")]
    assert "close_splash" not in shown


def test_serve_help_lists_webview(capsys: pytest.CaptureFixture[str]):
    with pytest.raises(SystemExit) as exc:
        main(["serve", "--help"])
    assert exc.value.code == 0
    assert "--webview" in capsys.readouterr().out
