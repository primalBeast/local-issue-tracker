@echo off
setlocal EnableExtensions
cd /d "%~dp0"

echo.
echo ============================================
echo  Local Issue Tracker - Windows install
echo ============================================
echo.
echo This installs uv (if needed) and the app.
echo Git is assumed already installed because you cloned the repo.
echo Node.js is not required to run the app.
echo.

set "FAILED=0"

call :refresh_uv_path
where uv >nul 2>&1
if errorlevel 1 (
  echo [..] uv not found. Installing uv...
  call :install_uv
  call :refresh_uv_path
)

where uv >nul 2>&1
if errorlevel 1 (
  echo [FAIL] uv is not on PATH after install.
  echo        Close this window, open a new Command Prompt, and run install.cmd again.
  echo        Or install from: https://docs.astral.sh/uv/getting-started/installation/
  set "FAILED=1"
  goto :summary
)

echo [OK]   uv found
uv --version
echo.

if not exist "pyproject.toml" (
  echo [FAIL] pyproject.toml missing. Run this from the cloned repo folder.
  set "FAILED=1"
  goto :summary
)
if not exist "lit\cli.py" (
  echo [FAIL] lit\cli.py missing. The clone looks incomplete. Run: git pull
  set "FAILED=1"
  goto :summary
)
echo [OK]   repo files present
echo.

echo [..] Installing Python 3.12+ and app dependencies (uv sync^)
uv sync
if errorlevel 1 (
  echo [FAIL] uv sync failed.
  set "FAILED=1"
  goto :summary
)
echo [OK]   uv sync finished
echo.

echo [..] Checking Python version
uv run python -c "import sys; assert sys.version_info >= (3, 12), sys.version; print(sys.version)"
if errorlevel 1 (
  echo [FAIL] Python 3.12+ is required.
  set "FAILED=1"
  goto :summary
)
echo [OK]   Python 3.12+
echo.

echo [..] Checking lit import
uv run python -c "from lit.cli import main; print('import lit.cli: OK')"
if errorlevel 1 (
  echo [FAIL] Could not import lit.cli. Try: uv sync --reinstall
  set "FAILED=1"
  goto :summary
)
echo.

if not exist "frontend\dist\index.html" (
  echo [FAIL] frontend\dist\index.html missing. The UI bundle is not in this clone.
  echo        Run: git pull
  set "FAILED=1"
  goto :summary
)
dir /b "frontend\dist\assets\*.js" >nul 2>&1
if errorlevel 1 (
  echo [FAIL] No JS files in frontend\dist\assets. The UI bundle is incomplete.
  echo        Run: git pull
  set "FAILED=1"
  goto :summary
)
echo [OK]   frontend production build present
echo.

echo [..] lit doctor
uv run lit doctor
if errorlevel 1 (
  echo [FAIL] lit doctor failed.
  set "FAILED=1"
  goto :summary
)
echo [OK]   lit doctor finished
echo.

:summary
echo ============================================
if "%FAILED%"=="0" (
  echo  Install checks passed.
  echo  Double-click start.cmd to launch the app.
  echo  Or run:  uv run lit serve --open
  echo  Then open http://127.0.0.1:8765
) else (
  echo  Install checks FAILED. See messages above.
)
echo ============================================
echo.
pause
exit /b %FAILED%

:refresh_uv_path
if exist "%USERPROFILE%\.local\bin\uv.exe" set "PATH=%USERPROFILE%\.local\bin;%PATH%"
if exist "%USERPROFILE%\.cargo\bin\uv.exe" set "PATH=%USERPROFILE%\.cargo\bin;%PATH%"
exit /b 0

:install_uv
where winget >nul 2>&1
if not errorlevel 1 (
  echo [..] Trying winget...
  winget install --id=astral-sh.uv -e --accept-package-agreements --accept-source-agreements
  call :refresh_uv_path
  where uv >nul 2>&1
  if not errorlevel 1 exit /b 0
)

echo [..] Trying the official uv installer...
powershell -NoProfile -ExecutionPolicy Bypass -Command "irm https://astral.sh/uv/install.ps1 | iex"
exit /b %ERRORLEVEL%
