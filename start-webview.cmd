@echo off
setlocal EnableExtensions
cd /d "%~dp0"
title Local Issue Tracker
if exist "%~dp0lit\assets\splash.hta" start "" mshta.exe "%~dp0lit\assets\splash.hta"

REM Minimize THIS console (do not hide it). Logs stay in the window; restore from the taskbar.
powershell -NoProfile -WindowStyle Hidden -ExecutionPolicy Bypass -File "%~dp0scripts\minimize-console.ps1"

echo.
echo ============================================
echo  Local Issue Tracker  (WebView2 window)
echo ============================================
echo.

call :refresh_uv_path
where uv >nul 2>&1
if errorlevel 1 (
  echo uv is not installed. Double-click install.cmd first.
  echo.
  pause
  exit /b 1
)

if not exist ".venv\" (
  echo App is not installed yet. Double-click install.cmd first.
  echo.
  pause
  exit /b 1
)

if not exist "frontend\dist\index.html" (
  echo frontend\dist is missing. Double-click install.cmd, or run: git pull
  echo.
  pause
  exit /b 1
)

echo Starting the local server in a WebView2 window (not a browser tab).
echo Close the app window to stop. You can still use start.cmd for the browser.
echo This console is minimized — restore "Local Issue Tracker" from the taskbar for logs.
echo.
echo http://127.0.0.1:8765
echo.

uv run lit serve --webview
exit /b %ERRORLEVEL%

:refresh_uv_path
if exist "%USERPROFILE%\.local\bin\uv.exe" set "PATH=%USERPROFILE%\.local\bin;%PATH%"
if exist "%USERPROFILE%\.cargo\bin\uv.exe" set "PATH=%USERPROFILE%\.cargo\bin;%PATH%"
exit /b 0
