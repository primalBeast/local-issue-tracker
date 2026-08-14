# Run Local Issue Tracker on Windows 11

Step-by-step guide to download everything you need and run the app in a browser on Windows 11.

The app is **100% local**. It does not send data to the cloud. You only need a browser and a small Python toolchain.

---

## What you will install

| Tool | Required to run the app? | Why |
|------|--------------------------|-----|
| **Git for Windows** | Yes (to clone the repo) | Download the project source |
| **uv** | Yes | Installs Python 3.12+ and app dependencies |
| **A browser** | Yes | Edge is built into Windows 11; Chrome/Firefox also fine |
| **Node.js** | No (only if you edit the UI source) | Rebuild the frontend after code changes |

The production UI is already built and committed in `frontend/dist`, so **you do not need Node.js** just to run the app.

---

## Quick fix: `ModuleNotFoundError: No module named 'lit.cli'`

This means either the clone is missing `lit\\cli.py`, or the editable install did not put the package on Python’s path.

**1. Confirm the file exists after a pull:**

```powershell
cd D:\\g\\IssueTracker\\local-issue-tracker   # your clone path
git pull
dir lit\\cli.py
```

If `dir` says the file is missing, the GitHub copy was incomplete — pull again after the fix is on `main`, or re-clone.

**2. Reinstall the package into the venv (recommended on Windows):**

```powershell
uv sync --reinstall --no-editable
uv run lit serve --open
```

**3. Fallback — run as a module with PYTHONPATH set to the repo root:**

```powershell
$env:PYTHONPATH = (Get-Location).Path
uv run python -m lit serve --open
```

---

## 1. Install Git for Windows

1. Download the installer:  
   **[https://git-scm.com/download/win](https://git-scm.com/download/win)**
2. Run it. Defaults are fine for most people.
   - Recommended: enable **“Git from the command line and also from 3rd-party software”**
3. Close and reopen any open terminals after install.

Verify in **PowerShell** or **Windows Terminal**:

```powershell
git --version
```

---

## 2. Install uv (Python package runner)

**uv** downloads a modern Python and manages the app’s virtual environment. You do **not** need to install Python from python.org first.

### Option A — PowerShell (recommended)

Open **Windows Terminal** or **PowerShell** and run:

```powershell
powershell -ExecutionPolicy ByPass -c "irm https://astral.sh/uv/install.ps1 | iex"
```

Close and reopen the terminal so `uv` is on your `PATH`.

### Option B — WinGet

```powershell
winget install --id=astral-sh.uv -e
```

Then reopen the terminal.

Verify:

```powershell
uv --version
```

Docs: [https://docs.astral.sh/uv/](https://docs.astral.sh/uv/)

> Avoid relying on random system Python installs. Always start this app with `uv run …`.

---

## 3. Clone the repository

In PowerShell:

```powershell
cd $HOME\Documents
git clone https://github.com/primalBeast/local-issue-tracker.git
cd local-issue-tracker
```

If you already have a copy:

```powershell
cd path\to\local-issue-tracker
git pull
```

---

## 4. Install the app (Python deps)

From the project root:

```powershell
uv sync --reinstall --no-editable
```

This creates a `.venv` folder and installs FastAPI, uvicorn, and the rest of the backend.

Optional health check:

```powershell
uv run lit doctor
```

---

## 5. Start the web app

```powershell
uv run lit serve --open
```

- Server binds to **http://127.0.0.1:8765** (local only)
- `--open` tries to open your default browser (Edge is fine)
- If the browser does not open, go to: [http://127.0.0.1:8765](http://127.0.0.1:8765)

Leave the PowerShell window open while you use the app. Stop the server with **Ctrl+C**.

### Daily start (after the first setup)

```powershell
cd D:\\g\\IssueTracker\\local-issue-tracker   # your clone path
uv run lit serve --open
```

---

## 6. First-run behavior

On first start the app seeds a sample **Issue Tracker** project with:

- Configurable fields  
- A **Main Board** workspace  
- Daily backup folder under the data directory  

### Where data is stored (Windows)

```text
%APPDATA%\LocalIssueTracker\
```

Typical full path:

```text
C:\Users\<YourName>\AppData\Roaming\LocalIssueTracker\
```

Optional override (PowerShell session):

```powershell
$env:LIT_DATA_DIR = "$HOME\MyIssueData"
uv run lit serve --open
```

---

## Optional: develop / rebuild the frontend

Only needed if you change files under `frontend\src\`.

1. Install **Node.js 20 LTS** from:  
   **[https://nodejs.org/](https://nodejs.org/)**  
   (or `winget install OpenJS.NodeJS.LTS`)
2. Rebuild:

   ```powershell
   cd frontend
   npm ci
   npm run build
   cd ..
   ```

3. Restart `uv run lit serve --open`.

---

## Troubleshooting

| Problem | What to try |
|---------|-------------|
| `No module named 'lit.cli'` | `git pull` then `uv sync --reinstall --no-editable` |
| `uv` not recognized | Close and reopen Terminal; confirm with `uv --version` |
| Port already in use | `netstat -ano \| findstr :8765` then `taskkill /PID <pid> /F` |
| Blank or old UI | Hard refresh in Edge: **Ctrl+Shift+R** |

---

## Next

- macOS guide: [RUN-macOS.md](./RUN-macOS.md)  
- Project overview: [../README.md](../README.md)
