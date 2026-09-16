from __future__ import annotations

from lit.branding import (
    APP_USER_MODEL_ID,
    assets_dir,
    icon_path,
    splash_image_path,
    splash_script_path,
)


def test_branding_assets_exist():
    assert assets_dir().is_dir()
    assert icon_path().is_file()
    assert icon_path().read_bytes()[:4] == b"\x00\x00\x01\x00"
    assert splash_image_path().is_file()
    assert splash_script_path().is_file()
    assert "LocalIssueTracker.SplashClose" in splash_script_path().read_text(encoding="utf-8")
    assert APP_USER_MODEL_ID == "primalBeast.LocalIssueTracker"


def test_cmd_serve_starts_splash_before_server():
    import inspect

    from lit.cli import cmd_serve

    src = inspect.getsource(cmd_serve)
    assert src.index("start_splash") < src.index("create_app")
    assert src.index("start_splash") < src.index("backup_all_projects")


def test_webview_launchers_start_splash_and_minimize_console():
    from pathlib import Path

    root = Path(__file__).resolve().parents[1]
    vbs = (root / "start-webview.vbs").read_text(encoding="utf-8")
    cmd = (root / "start-webview.cmd").read_text(encoding="utf-8")
    assert "lit\\assets\\show-splash.ps1" in vbs
    assert ", 7, True" in vbs
    assert "If rc = 1 Then" in vbs
    assert "show-splash.ps1" in cmd
    assert "minimize-console.ps1" in cmd
