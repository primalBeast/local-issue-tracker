from __future__ import annotations

import socket

import pytest

from lit.cli import main
from lit.webview_host import F5_RELOAD_JS, WebviewBridge, make_view_menu, port_listening, wait_for_port


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


def test_js_api_does_not_hold_a_window_attribute():
    assert not hasattr(WebviewBridge(), "window")


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


def test_serve_help_lists_webview(capsys: pytest.CaptureFixture[str]):
    with pytest.raises(SystemExit) as exc:
        main(["serve", "--help"])
    assert exc.value.code == 0
    assert "--webview" in capsys.readouterr().out
