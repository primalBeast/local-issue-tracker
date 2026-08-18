"""Windows OneDrive data-dir resolution and AppData migration."""

from __future__ import annotations

from pathlib import Path

import pytest

from lit import config


def test_onedrive_root_prefers_env(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    od = tmp_path / "OneDrive"
    od.mkdir()
    monkeypatch.setenv("OneDrive", str(od))
    monkeypatch.delenv("OneDriveConsumer", raising=False)
    monkeypatch.delenv("OneDriveCommercial", raising=False)
    assert config.onedrive_root() == od


def test_default_windows_dir_is_onedrive(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    od = tmp_path / "OneDrive"
    od.mkdir()
    monkeypatch.setenv("OneDrive", str(od))
    monkeypatch.delenv("LIT_DATA_DIR", raising=False)
    monkeypatch.setattr(config.platform, "system", lambda: "Windows")
    got = config.default_data_dir()
    assert got == od / "Local Issue Tracker"


def test_lit_data_dir_still_wins(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    custom = tmp_path / "custom"
    custom.mkdir()
    monkeypatch.setenv("LIT_DATA_DIR", str(custom))
    monkeypatch.setattr(config.platform, "system", lambda: "Windows")
    assert config.default_data_dir() == custom.resolve()


def test_migrate_copies_then_removes_legacy(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    appdata = tmp_path / "AppData"
    onedrive = tmp_path / "OneDrive"
    appdata.mkdir()
    onedrive.mkdir()
    legacy = appdata / "LocalIssueTracker"
    dest = onedrive / "Local Issue Tracker"
    (legacy / "projects" / "issue-tracker").mkdir(parents=True)
    (legacy / "settings.json").write_text('{"theme":"aurora"}', encoding="utf-8")
    (legacy / "projects" / "issue-tracker" / "project.json").write_text("{}", encoding="utf-8")
    (legacy / ".data.lock").write_text("old", encoding="utf-8")

    monkeypatch.setenv("APPDATA", str(appdata))
    config.migrate_windows_appdata_to_onedrive(dest)

    assert (dest / "settings.json").read_text(encoding="utf-8") == '{"theme":"aurora"}'
    assert (dest / "projects" / "issue-tracker" / "project.json").is_file()
    assert not (dest / ".data.lock").exists()
    assert not legacy.exists()


def test_migrate_skips_when_dest_already_has_data(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    appdata = tmp_path / "AppData"
    dest = tmp_path / "OneDrive" / "Local Issue Tracker"
    dest.mkdir(parents=True)
    (dest / "settings.json").write_text('{"theme":"ember"}', encoding="utf-8")
    legacy = appdata / "LocalIssueTracker"
    legacy.mkdir(parents=True)
    (legacy / "settings.json").write_text('{"theme":"aurora"}', encoding="utf-8")
    monkeypatch.setenv("APPDATA", str(appdata))

    config.migrate_windows_appdata_to_onedrive(dest)

    assert (dest / "settings.json").read_text(encoding="utf-8") == '{"theme":"ember"}'
    assert (legacy / "settings.json").is_file()
