"""Request and data guards for the local server.

The app is loopback-only. These checks still matter: a web page, a bad
import, or a huge body should not be able to write outside the data folder,
inject CSS, or exhaust the process.
"""

from __future__ import annotations

import re
from pathlib import Path
from urllib.parse import urlsplit

from lit.paths import SLUG_RE, validate_slug

_WORKSPACE_ID_RE = re.compile(r"^ws-[A-Za-z0-9_-]{1,64}$")

# Large enough for a rich-text ticket plus its wrapper. Small enough that a
# hostile page cannot pin the process on a multi-gigabyte body.
MAX_BODY_BYTES = 4_000_000

_THEME_RE = re.compile(r"^[A-Za-z0-9_-]{1,64}$")
_HEX_COLOR_RE = re.compile(r"^#[0-9A-Fa-f]{6}$")
_ITEM_ID_RE = re.compile(r"^[A-Za-z0-9_-]{1,80}$")

# Extensions the built UI is allowed to serve from frontend/dist.
_STATIC_SUFFIXES = frozenset(
    {
        ".html",
        ".js",
        ".css",
        ".map",
        ".json",
        ".svg",
        ".png",
        ".jpg",
        ".jpeg",
        ".gif",
        ".webp",
        ".ico",
        ".mp4",
        ".webm",
        ".woff",
        ".woff2",
        ".ttf",
        ".txt",
    }
)

_SETTINGS_KEYS = frozenset(
    {
        "last_project_slug",
        "last_workspace_by_project",
        "theme",
        "transparent_panels",
        "transparency_by_theme",
        "ticket_prefix_by_project",
        "backup_retention_days",
        "default_template",
        "window",
    }
)


class SettingsRejected(ValueError):
    """A known settings field was present but not safe to store."""


def valid_item_id(value: str) -> bool:
    return isinstance(value, str) and _ITEM_ID_RE.fullmatch(value) is not None


def normalize_url_prefix(raw: object) -> str:
    """Empty, or an http(s) URL with no userinfo and no control characters.

    The title bar concatenates this with a ticket key and opens it. ``javascript:``,
    ``file:``, and ``http://user:pass@host`` must not be stored.
    """
    if raw is None:
        return ""
    if not isinstance(raw, str):
        raise ValueError("URL prefix must be text")
    text = raw.strip()
    if not text:
        return ""
    if len(text) > 2048:
        raise ValueError("URL prefix is too long")
    if any(ord(ch) < 32 or ch in "\\" for ch in text):
        raise ValueError("URL prefix has invalid characters")
    parts = urlsplit(text)
    if parts.scheme not in ("http", "https"):
        raise ValueError("URL prefix must start with http:// or https://")
    if parts.username is not None or parts.password is not None:
        raise ValueError("URL prefix cannot include a username or password")
    if not parts.hostname:
        raise ValueError("URL prefix needs a host")
    return text


def sanitize_tab_color(value: object) -> str | None:
    """Hex colour only. Anything else becomes the default (no inline CSS)."""
    if value is None or value == "":
        return None
    if isinstance(value, str) and _HEX_COLOR_RE.fullmatch(value):
        return value.lower()
    return None


def safe_dist_file(dist: Path, full_path: str) -> Path | None:
    """A file under ``dist``, or None when the URL must not be served.

    Rejects absolute paths, ``..``, backslashes, nulls, symlinks, and suffixes
    the UI does not ship. Callers fall back to the SPA shell.
    """
    if not isinstance(full_path, str) or not full_path:
        return None
    if full_path.startswith(("/", "\\")) or "\\" in full_path or "\x00" in full_path:
        return None
    parts = full_path.split("/")
    if any(part in ("", ".", "..") for part in parts):
        return None
    suffix = Path(parts[-1]).suffix.lower()
    if suffix not in _STATIC_SUFFIXES:
        return None
    root = dist.resolve()
    candidate = root.joinpath(*parts)
    try:
        if candidate.is_symlink() or not candidate.is_file():
            return None
        resolved = candidate.resolve()
    except OSError:
        return None
    if not resolved.is_relative_to(root) or resolved == root:
        return None
    # A parent symlink could still resolve inside the folder while aliasing
    # another tree. Walk the declared parts and refuse any link.
    current = root
    for part in parts:
        current = current / part
        try:
            if current.is_symlink():
                return None
        except OSError:
            return None
    return resolved


def sanitize_settings_updates(raw: dict) -> dict:
    """Copy only known settings, and reject values that are the wrong shape.

    ``seeded_sample`` is not client-writable. Unknown keys are ignored.
    """
    if not isinstance(raw, dict):
        raise SettingsRejected("Settings body must be an object")
    updates: dict = {}
    for key, value in raw.items():
        if key not in _SETTINGS_KEYS:
            continue
        updates[key] = _clean_setting(key, value)
    return updates


def _clean_setting(key: str, value: object) -> object:
    if key == "last_project_slug":
        if value is None or value == "":
            return None
        if not isinstance(value, str):
            raise SettingsRejected("last_project_slug must be text")
        try:
            return validate_slug(value)
        except ValueError as exc:
            raise SettingsRejected(str(exc)) from exc

    if key == "default_template":
        if not isinstance(value, str) or not value.strip():
            raise SettingsRejected("default_template must be a template id")
        try:
            return validate_slug(value.strip())
        except ValueError as exc:
            raise SettingsRejected(str(exc)) from exc

    if key == "theme":
        if not isinstance(value, str) or _THEME_RE.fullmatch(value) is None:
            raise SettingsRejected("theme id is not allowed")
        return value

    if key == "transparent_panels":
        if not isinstance(value, bool):
            raise SettingsRejected("transparent_panels must be true or false")
        return value

    if key == "backup_retention_days":
        if isinstance(value, bool) or not isinstance(value, int) or not 1 <= value <= 365:
            raise SettingsRejected("backup_retention_days must be from 1 to 365")
        return value

    if key == "transparency_by_theme":
        if not isinstance(value, dict):
            raise SettingsRejected("transparency_by_theme must be an object")
        cleaned: dict[str, float] = {}
        for theme_id, raw_n in value.items():
            if not isinstance(theme_id, str) or _THEME_RE.fullmatch(theme_id) is None:
                raise SettingsRejected("transparency theme id is not allowed")
            if isinstance(raw_n, bool) or not isinstance(raw_n, (int, float)):
                raise SettingsRejected("transparency must be a number")
            cleaned[theme_id] = float(raw_n)
        return cleaned

    if key == "ticket_prefix_by_project":
        return _slug_string_map(value, "ticket prefix", 64)

    if key == "last_workspace_by_project":
        if not isinstance(value, dict):
            raise SettingsRejected("last_workspace_by_project must be an object")
        cleaned_ws: dict[str, str] = {}
        for slug, ws_id in value.items():
            if not isinstance(slug, str) or SLUG_RE.fullmatch(slug) is None:
                raise SettingsRejected("workspace map has a bad project id")
            if not isinstance(ws_id, str) or _WORKSPACE_ID_RE.fullmatch(ws_id) is None:
                raise SettingsRejected("workspace map has a bad board id")
            cleaned_ws[slug] = ws_id
        return cleaned_ws

    if key == "window":
        if not isinstance(value, dict):
            raise SettingsRejected("window must be an object")
        cleaned_window: dict[str, object] = {}
        if "last_host" in value:
            host = value["last_host"]
            if not isinstance(host, str) or not host or len(host) > 255:
                raise SettingsRejected("window host is not allowed")
            if any(ord(ch) < 32 or ch in " /\\@*?#" for ch in host):
                raise SettingsRejected("window host is not allowed")
            cleaned_window["last_host"] = host
        if "last_port" in value:
            port = value["last_port"]
            if isinstance(port, bool) or not isinstance(port, int) or not 1 <= port <= 65535:
                raise SettingsRejected("window port is not allowed")
            cleaned_window["last_port"] = port
        return cleaned_window

    raise SettingsRejected(f"Unknown setting {key}")


def _slug_string_map(value: object, label: str, max_len: int) -> dict[str, str]:
    if not isinstance(value, dict):
        raise SettingsRejected(f"{label} map must be an object")
    cleaned: dict[str, str] = {}
    for slug, raw in value.items():
        if not isinstance(slug, str) or SLUG_RE.fullmatch(slug) is None:
            raise SettingsRejected(f"{label} map has a bad project id")
        if not isinstance(raw, str):
            raise SettingsRejected(f"{label} must be text")
        text = raw.strip()
        if not text:
            continue
        if len(text) > max_len or any(ord(ch) < 32 for ch in text):
            raise SettingsRejected(f"{label} is too long or has invalid characters")
        cleaned[slug] = text
    return cleaned
