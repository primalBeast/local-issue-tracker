from __future__ import annotations

from lit.branding import (
    APP_USER_MODEL_ID,
    SPLASH_TITLE,
    assets_dir,
    icon_path,
    splash_hta_path,
    splash_image_path,
)


def test_branding_assets_exist():
    assert assets_dir().is_dir()
    assert icon_path().is_file()
    assert icon_path().read_bytes()[:4] == b"\x00\x00\x01\x00"
    assert splash_image_path().is_file()
    hta = splash_hta_path()
    assert hta.is_file()
    text = hta.read_text(encoding="utf-8")
    assert SPLASH_TITLE in text
    assert "splash.png" in text
    assert "lit-splash.close" in text
    assert APP_USER_MODEL_ID == "primalBeast.LocalIssueTracker"


def test_cmd_serve_starts_splash_before_server():
    import inspect

    from lit.cli import cmd_serve

    src = inspect.getsource(cmd_serve)
    assert src.index("start_splash") < src.index("create_app")
    assert src.index("start_splash") < src.index("backup_all_projects")


def test_start_splash_skips_when_launcher_already_showed_it():
    import inspect

    from lit.branding import start_splash

    src = inspect.getsource(start_splash)
    assert 'os.environ.get("LIT_SPLASH")' in src
    assert src.index("LIT_SPLASH") < src.index("Popen")


def test_webview_launchers_start_splash_and_minimize_console():
    from pathlib import Path

    root = Path(__file__).resolve().parents[1]
    vbs = (root / "start-webview.vbs").read_text(encoding="utf-8")
    cmd = (root / "start-webview.cmd").read_text(encoding="utf-8")
    assert "splash.hta" in vbs
    assert "mshta.exe" in vbs
    assert "LIT_SPLASH" in vbs
    assert "lit-splash.close" in vbs
    assert "pythonw" not in vbs
    assert ", 7, True" in vbs
    assert "If rc = 1 Then" in vbs
    assert "splash.hta" in cmd
    assert "mshta.exe" in cmd
    assert "LIT_SPLASH" in cmd
    assert "pythonw" not in cmd
    assert "minimize-console.ps1" in cmd
