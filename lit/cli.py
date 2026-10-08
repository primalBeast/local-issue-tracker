"""CLI entrypoint: lit serve | init-project | backup-now | doctor."""

from __future__ import annotations

import argparse
import json
import logging
import os
import sys
import threading
import time
import urllib.error
import urllib.request
import webbrowser
from pathlib import Path
from typing import Any

from lit import __version__
from lit.config import AppConfig, set_config
from lit.locking import acquire_data_lock, release_data_lock, try_acquire_data_lock
from lit.paths import settings_path
from lit.storage.backup import backup_all_projects, backup_project
from lit.storage.project_fs import create_project, ensure_data_layout, list_project_slugs, maybe_seed_sample
from lit.storage.settings_store import load_settings, patch_settings
from lit.storage.text_snapshot import seconds_until_next_hour, snapshot_all_projects


SERVER_UNREACHABLE = (
    "The app is running and holds the data folder, but its server did not answer. "
    "Close the app or run this from the app."
)


class ApiError(Exception):
    def __init__(self, status: int, body: str) -> None:
        self.status = status
        self.body = body
        super().__init__(f"HTTP {status}: {body}")


class ServerUnreachable(Exception):
    pass


def _setup_logging(verbose: bool = False) -> None:
    level = logging.DEBUG if verbose else logging.INFO
    logging.basicConfig(
        level=level,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
        datefmt="%H:%M:%S",
    )


def _env_float(name: str, default: float) -> float:
    raw = os.environ.get(name)
    if raw is None or not raw.strip():
        return default
    try:
        return float(raw)
    except ValueError:
        logging.getLogger("lit").warning("Ignoring invalid %s=%r", name, raw)
        return default


def _watch_idle(server: Any) -> None:
    """Exit after the startup window, or after the last event stream drops.

    ``LIT_IDLE_STARTUP_SECONDS`` (default 60) applies when no stream ever
    connects. ``LIT_IDLE_EXIT_SECONDS`` (default 10) applies after the last
    stream disconnects.
    """
    from lit.session import registry

    startup = _env_float("LIT_IDLE_STARTUP_SECONDS", 60.0)
    idle = _env_float("LIT_IDLE_EXIT_SECONDS", 10.0)
    log = logging.getLogger("lit")
    while not getattr(server, "should_exit", False):
        if registry.idle_exit_due(startup_seconds=startup, idle_seconds=idle):
            log.info(
                "No client event streams — exiting (startup %ss, idle %ss)",
                startup,
                idle,
            )
            server.should_exit = True
            return
        time.sleep(0.2)


def _settings_window() -> tuple[str, int]:
    """Host and port recorded by the running app. Does not create settings.json."""
    host, port = "127.0.0.1", 8765
    path = settings_path()
    if not path.is_file():
        return host, port
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError):
        return host, port
    window = data.get("window") if isinstance(data, dict) else None
    if not isinstance(window, dict):
        return host, port
    raw_host = window.get("last_host")
    raw_port = window.get("last_port")
    if isinstance(raw_host, str) and raw_host.strip():
        host = raw_host.strip()
    if raw_port is not None:
        try:
            port = int(raw_port)
        except (TypeError, ValueError):
            pass
    return host, port


def _server_endpoint(args: argparse.Namespace) -> tuple[str, int]:
    file_host, file_port = _settings_window()
    host = getattr(args, "host", None) or file_host
    port = getattr(args, "port", None)
    if port is None:
        port = file_port
    return str(host), int(port)


def _post_json(host: str, port: int, path: str, payload: dict[str, Any], timeout: float = 120.0) -> Any:
    """POST JSON to the running server. No Origin header, so local scripts are allowed."""
    url = f"http://{host}:{port}{path}"
    body = json.dumps(payload).encode("utf-8")
    request = urllib.request.Request(
        url,
        data=body,
        headers={"Content-Type": "application/json", "Accept": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            raw = response.read().decode("utf-8")
            return json.loads(raw) if raw else {}
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")
        raise ApiError(int(exc.code), detail) from exc
    except (urllib.error.URLError, TimeoutError, OSError) as exc:
        raise ServerUnreachable(str(exc)) from exc


def _print_api_backup(result: Any) -> None:
    if isinstance(result, dict):
        status = result.get("status")
        if status == "skipped":
            print("skipped (already exists)")
            return
        if status == "ok" and "count" in result:
            print(f"Created {result['count']} backup(s)")
            return
        if status == "created":
            manifest = result.get("manifest")
            print(manifest if manifest is not None else result)
            return
    print(result)


def _config_from_args(args: argparse.Namespace, *, host: str | None = None, port: int | None = None) -> AppConfig:
    data_dir = Path(args.data_dir) if args.data_dir else AppConfig().data_dir
    kwargs: dict[str, Any] = {"data_dir": data_dir}
    if host is not None:
        kwargs["host"] = host
    if port is not None:
        kwargs["port"] = port
    if hasattr(args, "open"):
        kwargs["open_browser"] = bool(args.open)
    if hasattr(args, "reload"):
        kwargs["reload"] = bool(args.reload)
        kwargs["dev_cors"] = bool(args.reload or getattr(args, "dev_cors", False))
    return AppConfig(**kwargs)


def cmd_serve(args: argparse.Namespace) -> int:
    _setup_logging(args.verbose)
    cfg = _config_from_args(args, host=args.host, port=args.port)
    set_config(cfg)
    log = logging.getLogger("lit")

    if cfg.host not in ("127.0.0.1", "localhost", "::1"):
        log.warning(
            "Binding to %s — this exposes your local data on the network with no auth. "
            "Prefer 127.0.0.1.",
            cfg.host,
        )

    use_webview = bool(getattr(args, "webview", False))
    headless = bool(getattr(args, "headless", False))
    exit_when_idle = bool(getattr(args, "exit_when_idle", False))
    # --exit-when-idle is the shared server: no window and no browser.
    browserless = headless or exit_when_idle

    if use_webview:
        from lit.branding import apply_app_user_model_id, close_splash, minimize_console, start_splash

        apply_app_user_model_id()
        start_splash()
        minimize_console()
        url = f"http://{cfg.host}:{cfg.port}"
        from lit.webview_host import open_webview, port_listening, wait_for_http

        # The window is only a client. A detached server holds the data lock.
        if port_listening(cfg.host, cfg.port):
            if not wait_for_http(cfg.host, cfg.port, timeout=3.0):
                log.error("Port %s is in use but /health did not respond", url)
                close_splash()
                return 1
            log.info("Server already running — opening WebView2 at %s", url)
        else:
            from lit.server_launch import ensure_server

            log.info("Starting shared server at %s", url)
            try:
                started = ensure_server(cfg.host, cfg.port, cfg.data_dir)
            except Exception:
                log.exception("Could not spawn the shared server")
                close_splash()
                return 1
            if not started:
                log.error("Server did not start on %s", url)
                close_splash()
                return 1
        if cfg.open_browser:
            log.info("Ignoring --open because --webview was set")
        try:
            open_webview(url)
        except Exception as exc:
            log.exception("WebView failed")
            print(exc, file=sys.stderr)
            close_splash()
            return 1
        return 0

    # Startup writes happen only after this process owns the data directory.
    acquire_data_lock()
    try:
        ensure_data_layout()
        maybe_seed_sample()
        patch_settings({"window": {"last_host": cfg.host, "last_port": cfg.port}})

        try:
            backup_all_projects(force=False)
        except Exception:
            log.exception("Startup backup check failed")
        try:
            snapshot_all_projects()
        except Exception:
            log.exception("Startup text snapshot failed")

        def _backup_loop() -> None:
            while True:
                time.sleep(seconds_until_next_hour())
                try:
                    backup_all_projects(force=False)
                except Exception:
                    log.exception("Scheduled backup failed")
                try:
                    snapshot_all_projects()
                except Exception:
                    log.exception("Hourly text snapshot failed")

        threading.Thread(target=_backup_loop, name="lit-backup", daemon=True).start()

        import uvicorn

        from lit.app import create_app
        from lit.session import registry

        app = create_app()
        url = f"http://{cfg.host}:{cfg.port}"
        log.info("Local Issue Tracker v%s — %s", __version__, url)
        log.info("Data directory: %s", cfg.data_dir)
        if browserless and cfg.open_browser:
            log.info("Ignoring --open because the server is headless")
        elif cfg.open_browser:
            threading.Timer(0.8, lambda: webbrowser.open(url)).start()

        config = uvicorn.Config(
            app,
            host=cfg.host,
            port=cfg.port,
            log_level="warning" if browserless else "info",
            access_log=not browserless,
        )
        server = uvicorn.Server(config)
        # Clock starts when the server is about to accept clients, not during startup IO.
        registry.reset()
        if exit_when_idle:
            threading.Thread(target=_watch_idle, args=(server,), name="lit-idle", daemon=True).start()
        server.run()
    finally:
        release_data_lock()
    return 0


def _backup_now_local(args: argparse.Namespace) -> int:
    ensure_data_layout()
    if args.project:
        try:
            manifest = backup_project(args.project, force=args.force)
        except FileNotFoundError:
            print(f"Project not found: {args.project}", file=sys.stderr)
            return 1
        print(manifest or "skipped (already exists)")
        return 0
    results = backup_all_projects(force=args.force)
    print(f"Created {len(results)} backup(s)")
    return 0


def _backup_now_via_api(args: argparse.Namespace) -> int:
    host, port = _server_endpoint(args)
    try:
        result = _post_json(
            host,
            port,
            "/api/backups/now",
            {"project": args.project, "force": bool(args.force)},
        )
    except ServerUnreachable:
        print(SERVER_UNREACHABLE, file=sys.stderr)
        return 1
    except ApiError as exc:
        print(exc.body or f"Error: HTTP {exc.status}", file=sys.stderr)
        return 1
    _print_api_backup(result)
    return 0


def cmd_backup_now(args: argparse.Namespace) -> int:
    _setup_logging(args.verbose)
    cfg = _config_from_args(args)
    set_config(cfg)
    if try_acquire_data_lock():
        try:
            return _backup_now_local(args)
        finally:
            release_data_lock()
    return _backup_now_via_api(args)


def _init_project_local(args: argparse.Namespace, cfg: AppConfig) -> int:
    ensure_data_layout()
    try:
        proj = create_project(args.slug, name=args.name, template=args.template)
    except FileExistsError:
        print(f"Project already exists: {args.slug}", file=sys.stderr)
        return 1
    except Exception as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1
    print(f"Created project {proj['slug']} ({proj['name']}) at {cfg.data_dir / 'projects' / proj['slug']}")
    return 0


def _init_project_via_api(args: argparse.Namespace, cfg: AppConfig) -> int:
    host, port = _server_endpoint(args)
    try:
        result = _post_json(
            host,
            port,
            "/api/projects",
            {"slug": args.slug, "name": args.name, "template": args.template},
        )
    except ServerUnreachable:
        print(SERVER_UNREACHABLE, file=sys.stderr)
        return 1
    except ApiError as exc:
        if exc.status == 409:
            print("Project already exists", file=sys.stderr)
            return 1
        print(exc.body or f"Error: HTTP {exc.status}", file=sys.stderr)
        return 1
    if isinstance(result, dict):
        slug = str(result.get("slug") or args.slug)
        name = str(result.get("name") or args.name or slug)
    else:
        slug = str(args.slug)
        name = str(args.name or slug)
    print(f"Created project {slug} ({name}) at {cfg.data_dir / 'projects' / slug}")
    return 0


def cmd_init_project(args: argparse.Namespace) -> int:
    _setup_logging(args.verbose)
    cfg = _config_from_args(args)
    set_config(cfg)
    if try_acquire_data_lock():
        try:
            return _init_project_local(args, cfg)
        finally:
            release_data_lock()
    return _init_project_via_api(args, cfg)


def cmd_doctor(args: argparse.Namespace) -> int:
    cfg = AppConfig(data_dir=Path(args.data_dir) if args.data_dir else AppConfig().data_dir)
    set_config(cfg)
    print(f"Local Issue Tracker v{__version__}")
    print(f"Data dir: {cfg.data_dir} (exists={cfg.data_dir.exists()})")
    settings = load_settings()
    print(f"Settings: theme={settings.get('theme')} seeded={settings.get('seeded_sample')}")
    slugs = list_project_slugs()
    print(f"Projects ({len(slugs)}): {', '.join(slugs) or '(none)'}")
    from lit.app import frontend_dist

    dist = frontend_dist()
    print(f"Frontend dist: {dist} index={ (dist / 'index.html').exists() }")

    # macOS: Python skips .pth files marked UF_HIDDEN (common under ~/Documents
    # after uv editable installs). Clear the flag and re-seed path hooks.
    try:
        import os
        import stat
        from pathlib import Path as _Path

        fixed = 0
        for p in sys.path:
            if not p.endswith("site-packages"):
                continue
            sp = _Path(p)
            for pth in sp.glob("*.pth"):
                try:
                    st = os.lstat(pth)
                    if getattr(st, "st_flags", 0) & stat.UF_HIDDEN:
                        os.chflags(pth, st.st_flags & ~stat.UF_HIDDEN)
                        fixed += 1
                except OSError:
                    pass
            # Ensure project root is importable even if editable .pth is broken
            root = _Path(sys.prefix).resolve().parent
            if (root / "lit" / "__init__.py").is_file():
                path_pth = sp / "local_issue_tracker_path.pth"
                path_pth.write_text(str(root) + "\n", encoding="utf-8")
                try:
                    os.chflags(path_pth, 0)
                except OSError:
                    pass
        if fixed:
            print(f"Fixed UF_HIDDEN on {fixed} .pth file(s) in the venv (macOS import fix)")
        else:
            print("Venv .pth flags: OK")
    except Exception as e:
        print(f"Venv .pth check skipped: {e}")

    # Verify import path
    try:
        import lit.cli as _cli  # noqa: F401
        print("Import lit.cli: OK")
    except Exception as e:
        print(f"Import lit.cli: FAILED — {e}")
        print("Try: uv sync --reinstall --no-editable")
        print(" Or: set PYTHONPATH to the repo root, then: uv run python -m lit serve --open")
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="lit", description="Local Issue Tracker")
    parser.add_argument("--version", action="version", version=f"%(prog)s {__version__}")
    parser.add_argument("-v", "--verbose", action="store_true")
    parser.add_argument(
        "--data-dir",
        default=None,
        help="Override data directory (or set LIT_DATA_DIR)",
    )
    sub = parser.add_subparsers(dest="command", required=True)

    p_serve = sub.add_parser("serve", help="Start local server")
    p_serve.add_argument("--host", default="127.0.0.1")
    p_serve.add_argument("--port", type=int, default=8765)
    p_serve.add_argument("--open", action="store_true", help="Open browser")
    p_serve.add_argument(
        "--webview",
        action="store_true",
        help="Open a WebView2 window instead of a browser (Windows Edge engine)",
    )
    p_serve.add_argument(
        "--headless",
        action="store_true",
        help="Run the server with no window and no browser",
    )
    p_serve.add_argument(
        "--exit-when-idle",
        action="store_true",
        help="Exit after the last client stream disconnects (shared WebView server)",
    )
    p_serve.add_argument("--reload", action="store_true", help="Enable dev CORS (Vite)")
    p_serve.add_argument("--dev-cors", action="store_true")
    p_serve.set_defaults(func=cmd_serve)

    p_init = sub.add_parser("init-project", help="Create a project from template")
    p_init.add_argument("slug")
    p_init.add_argument("--name", default=None)
    p_init.add_argument("--template", default="issue-tracker")
    p_init.add_argument("--host", default=None, help="Server host when the app already holds the data lock")
    p_init.add_argument("--port", type=int, default=None, help="Server port when the app already holds the data lock")
    p_init.set_defaults(func=cmd_init_project)

    p_bak = sub.add_parser("backup-now", help="Run project backups")
    p_bak.add_argument("--project", default=None)
    p_bak.add_argument("--force", action="store_true")
    p_bak.add_argument("--host", default=None, help="Server host when the app already holds the data lock")
    p_bak.add_argument("--port", type=int, default=None, help="Server port when the app already holds the data lock")
    p_bak.set_defaults(func=cmd_backup_now)

    p_doc = sub.add_parser("doctor", help="Diagnose installation")
    p_doc.set_defaults(func=cmd_doctor)

    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
