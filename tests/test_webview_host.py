from __future__ import annotations

import inspect
import logging
import socket
import threading
import time
import urllib.error
import urllib.request
from collections.abc import Callable

import pytest

from lit.cli import main
from lit import webview_host
from lit.webview_host import (
    CLOSE_FLUSH_JS,
    F5_RELOAD_JS,
    SAVES_PENDING_JS,
    WebviewBridge,
    _hit_from_client_point,
    make_view_menu,
    on_window_closing,
    port_listening,
    post_release_all,
    release_all_url,
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


def test_open_webview_uses_app_icon_and_closes_splash():
    src = inspect.getsource(webview_host.open_webview)
    assert "icon_path" in src
    assert 'start_kwargs["icon"]' in src
    assert "close_splash" in src
    assert "hidden=True" not in src
    assert src.index("events.loaded") < src.index("webview.start")
    assert "on_window_closing" in src
    assert src.index("events.closing") < src.index("webview.start")
    shown = src[src.index("def on_shown") : src.index("def on_loaded")]
    assert "close_splash" not in shown


def test_serve_help_lists_webview(capsys: pytest.CaptureFixture[str]):
    with pytest.raises(SystemExit) as exc:
        main(["serve", "--help"])
    assert exc.value.code == 0
    assert "--webview" in capsys.readouterr().out


CLIENT = "550e8400-e29b-41d4-a716-446655440000"
PAGE = "http://10.0.0.8:23456/"


def _clear_close_state() -> None:
    worker = webview_host._active.get("close_worker")
    if isinstance(worker, threading.Thread) and worker.is_alive():
        worker.join(2)
    with webview_host._state_lock:
        webview_host._active["window"] = None
        webview_host._active["url"] = ""
        webview_host._active["client_id"] = None
        webview_host._active["released"] = False
        webview_host._active["finalizing"] = False
        webview_host._active["close_started"] = False
        webview_host._active["close_worker"] = None
    io = webview_host.close_io
    io.poster = post_release_all
    io.clock = time.monotonic
    io.sleep = time.sleep
    io.flush_cap = webview_host.FLUSH_CAP_SECONDS
    io.poll_interval = webview_host.FLUSH_POLL_SECONDS
    io.release_timeout = webview_host.RELEASE_TIMEOUT_SECONDS


@pytest.fixture(autouse=True)
def _reset_close_state():
    _clear_close_state()
    yield
    _clear_close_state()


class ManualClock:
    """Monotonic stand-in. ``sleep`` moves it by the requested delay."""

    def __init__(self, start: float = 0.0) -> None:
        self.now = start

    def __call__(self) -> float:
        return self.now

    def sleep(self, seconds: float) -> None:
        self.now += seconds


class FakeWindow:
    def __init__(self) -> None:
        self.order: list[object] = []
        self.destroyed = False
        self.pending: object = False
        self.fail_on: str | None = None
        self.poll_times: list[float] = []
        self.clock: Callable[[], float] = time.monotonic
        self.on_flush: Callable[[], None] | None = None
        self.second: bool | None = None
        self.released_at_destroy: object = None
        self.finalizing_at_destroy: object = None

    def evaluate_js(self, script: str) -> object:
        if script == CLOSE_FLUSH_JS:
            kind = "flush"
            self.order.append(kind)
            if self.on_flush is not None:
                self.on_flush()
        elif script == SAVES_PENDING_JS:
            kind = "pending"
            self.order.append(kind)
            self.poll_times.append(self.clock())
        else:
            kind = "other"
            self.order.append(("js", script))
        if self.fail_on == kind or self.fail_on == "all":
            raise RuntimeError("page gone")
        if script == SAVES_PENDING_JS:
            return self.pending
        return None

    def destroy(self) -> None:
        self.order.append("destroy")
        self.destroyed = True
        self.released_at_destroy = webview_host._active.get("released")
        self.finalizing_at_destroy = webview_host._active.get("finalizing")
        self.second = on_window_closing()

    def load_url(self, url: str) -> None:
        self.order.append(("load", url))


def _arm(window: FakeWindow, url: str = PAGE, client_id: str = CLIENT) -> WebviewBridge:
    webview_host._active["window"] = window
    webview_host._active["url"] = url
    bridge = WebviewBridge()
    bridge.main_ready(client_id)
    return bridge


def _poster(window: FakeWindow, posts: list[tuple[str, float]]):
    def poster(url: str, timeout: float) -> None:
        window.order.append("release")
        posts.append((url, timeout))

    return poster


def _join_worker() -> threading.Thread:
    worker = webview_host._active.get("close_worker")
    assert isinstance(worker, threading.Thread)
    worker.join(2)
    assert worker.is_alive() is False
    return worker


def test_main_ready_stores_validated_client_id():
    params = inspect.signature(WebviewBridge.main_ready).parameters
    assert list(params) == ["self", "client_id"]
    assert params["client_id"].default is None

    bridge = WebviewBridge()
    bridge.main_ready()
    bridge.main_ready(None)
    bridge.main_ready("")
    for bad in ("short", "abcdefg", "has space", "bad/id!!", "a" * 65):
        bridge.main_ready(bad)
    assert webview_host._active["client_id"] is None

    bridge.main_ready("abcdefgh")
    assert webview_host._active["client_id"] == "abcdefgh"
    bridge.main_ready("nope")
    bridge.main_ready(None)
    assert webview_host._active["client_id"] == "abcdefgh"
    bridge.main_ready("a" * 64)
    assert webview_host._active["client_id"] == "a" * 64
    bridge.main_ready(CLIENT)
    assert webview_host._active["client_id"] == CLIENT


def test_closing_without_a_client_id_allows_close(monkeypatch: pytest.MonkeyPatch):
    posts: list[tuple[str, float]] = []
    window = FakeWindow()
    monkeypatch.setattr(webview_host.close_io, "poster", _poster(window, posts))
    _arm(window, client_id="bad id")
    assert webview_host._active["client_id"] is None
    assert on_window_closing() is None
    assert webview_host._active.get("close_worker") is None
    assert posts == []
    assert window.destroyed is False


def test_closing_flushes_then_releases_then_destroys(monkeypatch: pytest.MonkeyPatch):
    posts: list[tuple[str, float]] = []
    window = FakeWindow()
    monkeypatch.setattr(webview_host.close_io, "poster", _poster(window, posts))
    _arm(window)

    assert on_window_closing() is False
    worker = _join_worker()

    assert worker.daemon is True
    assert worker.name == "lit-close-release"
    steps = [item for item in window.order if item in {"flush", "pending", "release", "destroy"}]
    assert steps == ["flush", "pending", "release", "destroy"]
    assert window.order.index("flush") < window.order.index("release") < window.order.index("destroy")
    assert window.released_at_destroy is True
    assert window.finalizing_at_destroy is True
    assert window.second is None
    assert posts == [
        (
            "http://10.0.0.8:23456/api/session/release-all?client=" + CLIENT,
            1.0,
        )
    ]
    assert on_window_closing() is None
    assert len(posts) == 1


def test_pending_saves_stop_at_the_flush_cap(monkeypatch: pytest.MonkeyPatch):
    assert webview_host.FLUSH_CAP_SECONDS == 0.5
    clock = ManualClock(start=10.0)
    monkeypatch.setattr(webview_host.close_io, "clock", clock)
    monkeypatch.setattr(webview_host.close_io, "sleep", clock.sleep)
    posts: list[tuple[str, float]] = []
    window = FakeWindow()
    window.pending = True
    window.clock = clock
    monkeypatch.setattr(webview_host.close_io, "poster", _poster(window, posts))
    _arm(window)

    assert on_window_closing() is False
    _join_worker()

    assert len(window.poll_times) == 10
    assert window.poll_times[0] == 10.0
    assert window.poll_times[-1] == pytest.approx(10.45)
    assert all(t < 10.5 for t in window.poll_times)
    assert clock.now == pytest.approx(10.5)
    assert window.order.index("flush") < window.order.index("release") < window.order.index("destroy")
    assert posts and posts[0][0].endswith("client=" + CLIENT)
    assert window.destroyed is True
    assert window.second is None


def test_stalled_flush_clock_still_releases(monkeypatch: pytest.MonkeyPatch):
    clock = ManualClock(start=3.0)
    monkeypatch.setattr(webview_host.close_io, "clock", clock)
    monkeypatch.setattr(webview_host.close_io, "sleep", lambda _seconds: None)
    posts: list[tuple[str, float]] = []
    window = FakeWindow()
    window.pending = True
    window.clock = clock
    monkeypatch.setattr(webview_host.close_io, "poster", _poster(window, posts))
    _arm(window)

    assert on_window_closing() is False
    _join_worker()

    assert window.poll_times == [3.0]
    assert posts
    assert window.destroyed is True


@pytest.mark.parametrize("where", ["flush", "pending"])
def test_evaluate_js_failure_still_releases_and_closes(
    where: str, monkeypatch: pytest.MonkeyPatch
):
    posts: list[tuple[str, float]] = []
    window = FakeWindow()
    window.fail_on = where
    monkeypatch.setattr(webview_host.close_io, "poster", _poster(window, posts))
    _arm(window)

    assert on_window_closing() is False
    _join_worker()

    assert "flush" in window.order
    assert window.order.index("flush") < window.order.index("release") < window.order.index("destroy")
    assert posts[0][0] == "http://10.0.0.8:23456/api/session/release-all?client=" + CLIENT
    assert window.destroyed is True
    assert window.second is None
    if where == "pending":
        assert window.order.index("flush") < window.order.index("pending") < window.order.index("release")


def test_close_app_marks_released_and_skips_post(monkeypatch: pytest.MonkeyPatch):
    posts: list[tuple[str, float]] = []
    window = FakeWindow()
    monkeypatch.setattr(webview_host.close_io, "poster", _poster(window, posts))
    bridge = _arm(window)

    bridge.close_app()

    assert window.destroyed is True
    assert webview_host._active["released"] is True
    assert window.second is None
    assert on_window_closing() is None
    assert posts == []
    assert webview_host._active.get("close_worker") is None


def test_second_close_during_flush_posts_once(monkeypatch: pytest.MonkeyPatch):
    entered = threading.Event()
    gate = threading.Event()
    posts: list[tuple[str, float]] = []
    window = FakeWindow()

    def _block_flush() -> None:
        entered.set()
        gate.wait(2)

    window.on_flush = _block_flush
    monkeypatch.setattr(webview_host.close_io, "poster", _poster(window, posts))
    _arm(window)
    try:
        assert on_window_closing() is False
        assert entered.wait(2)
        assert on_window_closing() is False
    finally:
        gate.set()
        worker = webview_host._active.get("close_worker")
        if isinstance(worker, threading.Thread):
            worker.join(2)
    assert len(posts) == 1
    assert window.destroyed is True
    assert on_window_closing() is None


def test_reload_does_not_release(monkeypatch: pytest.MonkeyPatch):
    posts: list[tuple[str, float]] = []
    window = FakeWindow()
    monkeypatch.setattr(webview_host.close_io, "poster", _poster(window, posts))
    bridge = _arm(window, url="http://127.0.0.1:8765/")

    bridge.reload()
    menu = make_view_menu(bridge.reload)
    menu[0].items[0].function()

    assert posts == []
    assert webview_host._active["released"] is False
    assert webview_host._active["close_started"] is False
    assert window.order.count(("load", "http://127.0.0.1:8765/")) == 2
    assert "release" not in window.order


def test_closing_handler_stays_off_the_ui_thread():
    src = inspect.getsource(on_window_closing)
    assert list(inspect.signature(on_window_closing).parameters) == []
    assert "evaluate_js" not in src
    assert "poster" not in src
    assert "release_all" not in src
    assert "return False" in src
    assert "Thread" in src


def test_release_all_url_uses_the_page_host():
    cid = "abcdefgh"
    assert release_all_url("http://10.0.0.8:23456/app?x=1", cid) == (
        "http://10.0.0.8:23456/api/session/release-all?client=abcdefgh"
    )
    assert release_all_url("http://[::1]:8765/", cid) == (
        "http://[::1]:8765/api/session/release-all?client=abcdefgh"
    )
    assert release_all_url("http://127.0.0.1:8765", cid) == (
        "http://127.0.0.1:8765/api/session/release-all?client=abcdefgh"
    )
    assert release_all_url("", cid) is None
    assert release_all_url("http://::1:8765", cid) is None


def test_closing_without_a_server_url_still_destroys(monkeypatch: pytest.MonkeyPatch):
    posts: list[tuple[str, float]] = []
    window = FakeWindow()
    monkeypatch.setattr(webview_host.close_io, "poster", _poster(window, posts))
    _arm(window, url="")

    assert on_window_closing() is False
    _join_worker()

    assert posts == []
    assert window.destroyed is True
    assert window.order.index("flush") < window.order.index("destroy")
    assert "release" not in window.order


def test_post_release_all_has_no_origin_and_swallows_errors(
    monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
):
    captured: dict[str, object] = {}

    class _Resp:
        def read(self) -> bytes:
            return b""

        def __enter__(self) -> _Resp:
            return self

        def __exit__(self, *_args: object) -> bool:
            return False

    def _urlopen(request: urllib.request.Request, timeout: float = 0) -> _Resp:
        captured["request"] = request
        captured["timeout"] = timeout
        return _Resp()

    monkeypatch.setattr(urllib.request, "urlopen", _urlopen)
    post_release_all("http://127.0.0.1:8765/api/session/release-all?client=abcdefgh", 1.0)
    request = captured["request"]
    assert isinstance(request, urllib.request.Request)
    assert request.get_method() == "POST"
    assert request.data == b""
    names = [name.lower() for name, _value in request.header_items()]
    assert "origin" not in names
    assert captured["timeout"] == 1.0

    def _boom(_request: urllib.request.Request, timeout: float = 0) -> _Resp:
        raise urllib.error.URLError("down")

    monkeypatch.setattr(urllib.request, "urlopen", _boom)
    with caplog.at_level(logging.ERROR, logger="lit.webview"):
        post_release_all("http://127.0.0.1:9/api/session/release-all?client=abcdefgh", 1.0)
    assert "Session release-all failed" in caplog.text
