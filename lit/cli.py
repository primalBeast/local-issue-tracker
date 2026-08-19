"""CLI entrypoint: lit serve | init-project | backup-now | doctor."""

from __future__ import annotations

import argparse
import logging
import sys
import threading
import time
import webbrowser
from pathlib import Path

from lit import __version__
from lit.config import AppConfig, set_config
from lit.locking import acquire_data_lock, release_data_lock
from lit.storage.backup import backup_all_projects, backup_project
from lit.storage.project_fs import create_project, ensure_data_layout, list_project_slugs, maybe_seed_sample
from lit.storage.settings_store import load_settings, patch_settings
from lit.storage.text_snapshot import seconds_until_next_hour, snapshot_all_projects


def _setup_logging(verbose: bool = False) -> None:
    level = logging.DEBUG if verbose else logging.INFO
    logging.basicConfig(
        level=level,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
        datefmt="%H:%M:%S",
    )


def cmd_serve(args: argparse.Namespace) -> int:
    _setup_logging(args.verbose)
    cfg = AppConfig(
        data_dir=Path(args.data_dir) if args.data_dir else AppConfig().data_dir,
        host=args.host,
        port=args.port,
        open_browser=args.open,
        reload=args.reload,
        dev_cors=args.reload or args.dev_cors,
    )
    set_config(cfg)

    if cfg.host not in ("127.0.0.1", "localhost", "::1"):
        logging.getLogger("lit").warning(
            "Binding to %s — this exposes your local data on the network with no auth. "
            "Prefer 127.0.0.1.",
            cfg.host,
        )

    ensure_data_layout()
    acquire_data_lock()
    maybe_seed_sample()
    patch_settings({"window": {"last_host": cfg.host, "last_port": cfg.port}})

    # Daily backup check on startup
    try:
        backup_all_projects(force=False)
    except Exception:
        logging.getLogger("lit").exception("Startup backup check failed")

    # On the hour: daily folder backup (skips if today exists) + readable text/md dump.
    def _backup_loop() -> None:
        log = logging.getLogger("lit")
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

    t = threading.Thread(target=_backup_loop, name="lit-backup", daemon=True)
    t.start()

    import uvicorn

    from lit.app import create_app

    app = create_app()
    url = f"http://{cfg.host}:{cfg.port}"
    logging.getLogger("lit").info("Local Issue Tracker v%s — %s", __version__, url)
    logging.getLogger("lit").info("Data directory: %s", cfg.data_dir)

    if cfg.open_browser:
        threading.Timer(0.8, lambda: webbrowser.open(url)).start()

    try:
        uvicorn.run(
            app,
            host=cfg.host,
            port=cfg.port,
            log_level="info",
            reload=False,  # reload not compatible with our lock easily
        )
    finally:
        release_data_lock()
    return 0


def cmd_init_project(args: argparse.Namespace) -> int:
    _setup_logging(args.verbose)
    cfg = AppConfig(data_dir=Path(args.data_dir) if args.data_dir else AppConfig().data_dir)
    set_config(cfg)
    ensure_data_layout()
    try:
        proj = create_project(args.slug, name=args.name, template=args.template)
    except FileExistsError:
        print(f"Project already exists: {args.slug}", file=sys.stderr)
        return 1
    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        return 1
    print(f"Created project {proj['slug']} ({proj['name']}) at {cfg.data_dir / 'projects' / proj['slug']}")
    return 0


def cmd_backup_now(args: argparse.Namespace) -> int:
    _setup_logging(args.verbose)
    cfg = AppConfig(data_dir=Path(args.data_dir) if args.data_dir else AppConfig().data_dir)
    set_config(cfg)
    ensure_data_layout()
    if args.project:
        m = backup_project(args.project, force=args.force)
        print(m or "skipped (already exists)")
    else:
        results = backup_all_projects(force=args.force)
        print(f"Created {len(results)} backup(s)")
    return 0


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
    p_serve.add_argument("--reload", action="store_true", help="Enable dev CORS (Vite)")
    p_serve.add_argument("--dev-cors", action="store_true")
    p_serve.set_defaults(func=cmd_serve)

    p_init = sub.add_parser("init-project", help="Create a project from template")
    p_init.add_argument("slug")
    p_init.add_argument("--name", default=None)
    p_init.add_argument("--template", default="issue-tracker")
    p_init.set_defaults(func=cmd_init_project)

    p_bak = sub.add_parser("backup-now", help="Run project backups")
    p_bak.add_argument("--project", default=None)
    p_bak.add_argument("--force", action="store_true")
    p_bak.set_defaults(func=cmd_backup_now)

    p_doc = sub.add_parser("doctor", help="Diagnose installation")
    p_doc.set_defaults(func=cmd_doctor)

    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
