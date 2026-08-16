# Local Issue Tracker

A beautiful, fully local web app for personal ticket/issue tracking and notes.
**No Jira, no cloud, no external services** — you enter ticket keys and track
your own states, priorities, waiting time, and rich notes.

Data lives on disk under per-project folders. Field definitions are configurable
per project (`fields.json`), so the same shell works for other personal tracking
needs, not only issues.

## Features

- **Projects** with isolated data folders and daily dated backups
- **Workspaces** with independent floating layouts over the same items
- **Free-floating panels** — drag, resize, snap to a 5px screen-pixel grid, overlap
- **CTRL + mouse wheel** zoom; compact mode when zoomed out
- **Configurable fields** — forms generated from `fields.json`
- **Waiting metrics** — enter/leave “Waiting For”, live duration, totals, history
- **Color coding** by state with intensity from priority
- **All Items list**, project notes, and deliverables panels
- **Filters & presets** saved per workspace
- Dark-mode-first UI

## How to run (full install guides)

**Start here** — downloads, install steps, and troubleshooting:

| OS | Guide |
|----|--------|
| **macOS** | **[docs/RUN-macOS.md](docs/RUN-macOS.md)** |
| **Windows 11** | **[docs/RUN-Windows11.md](docs/RUN-Windows11.md)** |
| Index | [docs/RUN.md](docs/RUN.md) |

## Requirements (summary)

- **Git** — to clone this repository  
- **[uv](https://docs.astral.sh/uv/)** — installs Python 3.12+ and app dependencies  
- A modern desktop browser (Chrome, Firefox, Safari, Edge)  
- **Node.js 20+** only if you change the frontend source (production `frontend/dist` is committed)

> Do **not** use system Python 3.9. Always run via `uv`.

## Clone and run (short version)

```bash
git clone https://github.com/primalBeast/local-issue-tracker.git
cd local-issue-tracker

# Install Python deps (creates .venv)
uv sync

# Start the local server and open the browser
uv run lit serve --open
```

Then open [http://127.0.0.1:8765](http://127.0.0.1:8765) if it did not open automatically.

Windows (PowerShell) is the same `uv` / `git` commands after installing [Git for Windows](https://git-scm.com/download/win) and [uv](https://docs.astral.sh/uv/getting-started/installation/). See **[docs/RUN-Windows11.md](docs/RUN-Windows11.md)**.

If you ever see `ModuleNotFoundError: No module named 'lit'` (especially on macOS):

```bash
uv run python packaging/ensure_sitecustomize.py
# or
uv run lit doctor
```

### First run

On first start, a sample **Issue Tracker** project is seeded under the app data
directory with default fields and a Main Board workspace.

### Data location

| Platform | Default data directory |
|----------|------------------------|
| macOS | `~/Library/Application Support/LocalIssueTracker` |
| Linux | `~/.local/share/local-issue-tracker` |
| Windows | `%APPDATA%\\LocalIssueTracker` |

Override with:

```bash
export LIT_DATA_DIR=/path/to/data
# or
uv run lit serve --data-dir /path/to/data
```

### CLI

```bash
uv run lit serve --open          # start server
uv run lit init-project my-proj --name "My Project"
uv run lit backup-now            # snapshot all projects for today
uv run lit backup-now --project issue-tracker --force
uv run lit doctor                # diagnose install
```

## Frontend development

```bash
# Install Node 20+ once, then:
cd frontend
npm ci
npm run dev          # Vite on :5173, proxies /api to :8765
```

In another terminal:

```bash
uv run lit serve --reload   # enables CORS for Vite
```

Build and commit the production bundle (required for clone-and-run):

```bash
cd frontend && npm ci && npm run build
# commit frontend/dist
```

## Security

- Binds to **127.0.0.1** by default (local only, no auth)
- Do **not** expose the port to the network without adding auth
- Prefer full-disk encryption (FileVault / LUKS / BitLocker) for data at rest
- Path access is sandboxed under the data root

## Project layout

```text
lit/                     Python package (FastAPI + storage + CLI)
frontend/                Svelte 5 + Vite SPA
frontend/dist/           Committed production build (clone-and-run)
lit/templates/           Project templates (issue-tracker fields, etc.)
docs/RUN-macOS.md        Install & run on Mac
docs/RUN-Windows11.md    Install & run on Windows 11
packaging/               Venv import fallback (macOS hidden .pth files)
tests/                   pytest suite
```

## Tests

```bash
uv sync --extra dev
uv run pytest
```

## Publishing local commits to GitHub

If this machine is not logged into GitHub CLI/SSH, push with:

```bash
./scripts/push-to-github.sh
```

## License

MIT
