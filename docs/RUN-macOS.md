# Run Local Issue Tracker on macOS

Step-by-step guide to download everything you need and run the app in a browser on a Mac.

The app is **100% local**. It does not send data to the cloud. You only need a browser and a small Python toolchain.

---

## What you will install

| Tool | Required to run the app? | Why |
|------|--------------------------|-----|
| **Git** | Yes (to clone the repo) | Download the project source |
| **uv** | Yes | Installs Python 3.12+ and app dependencies |
| **A browser** | Yes | Safari, Chrome, Firefox, or Edge |
| **Node.js** | No (only if you edit the UI source) | Rebuild the frontend after code changes |

The production UI is already built and committed in `frontend/dist`, so **you do not need Node.js** just to run the app.

---

## 1. Install Git (if needed)

Open **Terminal** (`Applications → Utilities → Terminal`) and check:

```bash
git --version
```

If Git is missing, macOS will prompt you to install the **Command Line Tools**, or install them yourself:

```bash
xcode-select --install
```

Alternatively install Git via [Homebrew](https://brew.sh):

```bash
brew install git
```

---

## 2. Install uv (Python package runner)

**uv** downloads a modern Python and manages the app’s virtual environment.

Official install (recommended):

```bash
curl -LsSf https://astral.sh/uv/install.sh | sh
```

Then restart Terminal, or load the path:

```bash
source "$HOME/.local/bin/env" 2>/dev/null || true
export PATH="$HOME/.local/bin:$PATH"
```

Verify:

```bash
uv --version
```

Docs: [https://docs.astral.sh/uv/](https://docs.astral.sh/uv/)

> Do **not** rely on the system Python 3.9 that ships with older macOS. Always run this app through `uv`.

---

## 3. Clone the repository

```bash
cd ~/Documents   # or any folder you prefer
git clone https://github.com/primalBeast/local-issue-tracker.git
cd local-issue-tracker
```

If you already have a copy, update it instead:

```bash
cd path/to/local-issue-tracker
git pull
```

---

## 4. Install the app (Python deps)

From the project root:

```bash
uv sync
```

This creates a `.venv` folder and installs FastAPI, uvicorn, and the rest of the backend.

### macOS-only import fix (important)

If the repo lives under **Documents** (or similar), macOS can mark install files as “hidden.” Python then skips them and you get `No module named 'lit'`.

Always run this once after `uv sync` (and again if the error returns):

```bash
uv run python packaging/ensure_sitecustomize.py
```

Or:

```bash
uv run lit doctor
```

---

## 5. Start the web app

```bash
uv run lit serve --open
```

- Server binds to **http://127.0.0.1:8765** (local only)
- `--open` tries to open your default browser
- If the browser does not open, go to: [http://127.0.0.1:8765](http://127.0.0.1:8765)

Leave the Terminal window open while you use the app. Stop the server with **Ctrl+C**.

### Daily start (after the first setup)

```bash
cd ~/Documents/local-issue-tracker   # your clone path
uv run lit serve --open
```

If you see `ModuleNotFoundError: No module named 'lit'`:

```bash
uv run python packaging/ensure_sitecustomize.py
uv run lit serve --open
```

---

## 6. First-run behavior

On first start the app seeds a sample **Issue Tracker** project with:

- Configurable fields  
- A **Main Board** workspace  
- Daily backup folder under the data directory  

### Where data is stored (macOS)

```text
~/Library/Application Support/LocalIssueTracker/
```

Optional override:

```bash
export LIT_DATA_DIR="$HOME/MyIssueData"
uv run lit serve --open
```

---

## Optional: develop / rebuild the frontend

Only needed if you change files under `frontend/src/`.

1. Install **Node.js 20+** from [https://nodejs.org/](https://nodejs.org/) (LTS), or:

   ```bash
   brew install node
   ```

2. Build:

   ```bash
   cd frontend
   npm ci
   npm run build
   cd ..
   ```

3. Restart `uv run lit serve --open`.

For live UI development:

```bash
# Terminal 1
uv run lit serve --reload

# Terminal 2
cd frontend && npm ci && npm run dev
```

Open the Vite URL (usually http://127.0.0.1:5173).

---

## Useful commands

```bash
uv run lit serve --open              # start + open browser
uv run lit doctor                    # diagnose install / fix macOS .pth flags
uv run lit init-project my-proj --name "My Project"
uv run lit backup-now                # snapshot all projects for today
uv run lit backup-now --project issue-tracker --force
```

---

## Troubleshooting

| Problem | What to try |
|---------|-------------|
| `No module named 'lit'` | `uv run python packaging/ensure_sitecustomize.py` then retry |
| `uv: command not found` | Restart Terminal; ensure `~/.local/bin` is on `PATH` |
| Port already in use | `kill $(lsof -t -i :8765)` then start again |
| Blank or old UI after updates | Hard refresh: **⌘⇧R** in the browser |
| Frontend missing | Confirm `frontend/dist/index.html` exists; run `npm run build` in `frontend/` if you changed UI code |
| Lock / “another instance” | Stop other `lit serve` processes; delete stale lock only if no server is running |

---

## Security notes

- Listens on **127.0.0.1** only by default (not the internet).
- Do not port-forward or expose `:8765` without adding authentication.
- Prefer FileVault for full-disk encryption of local data.

---

## Next

- Architecture: [DESIGN.md](./DESIGN.md)  
- Windows guide: [RUN-Windows11.md](./RUN-Windows11.md)  
- Project overview: [../README.md](../README.md)
