@echo off
setlocal EnableExtensions
cd /d "%~dp0"
title Local Issue Tracker
if not defined LIT_SPLASH if exist "%~dp0lit\assets\splash.hta" (
  if exist "%TEMP%\lit-splash.close" del /q "%TEMP%\lit-splash.close"
  start "" mshta.exe "%~dp0lit\assets\splash.hta"
  set "LIT_SPLASH=1"
)

REM Hide THIS console. It is not a log window and does not belong on the taskbar.
set "LIT_HIDE_CONSOLE=1"
powershell -NoProfile -WindowStyle Hidden -ExecutionPolicy Bypass -File "%~dp0scripts\minimize-console.ps1" -Action hide

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
  call :show_console
  pause
  exit /b 1
)

if not exist ".venv\" (
  echo App is not installed yet. Double-click install.cmd first.
  echo.
  call :show_console
  pause
  exit /b 1
)

if not exist "frontend\dist\index.html" (
  echo frontend\dist is missing. Double-click install.cmd, or run: git pull
  echo.
  call :show_console
  pause
  exit /b 1
)

echo Starting the local server in a WebView2 window (not a browser tab).
echo Close the app window to stop. You can still use start.cmd for the browser.
echo.
echo http://127.0.0.1:8765
echo.

uv run lit serve --webview
exit /b %ERRORLEVEL%

:show_console
powershell -NoProfile -WindowStyle Hidden -ExecutionPolicy Bypass -File "%~dp0scripts\minimize-console.ps1" -Action show
exit /b 0

:refresh_uv_path
if exist "%USERPROFILE%\.local\bin\uv.exe" set "PATH=%USERPROFILE%\.local\bin;%PATH%"
if exist "%USERPROFILE%\.cargo\bin\uv.exe" set "PATH=%USERPROFILE%\.cargo\bin;%PATH%"
exit /b 0
