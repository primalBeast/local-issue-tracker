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
set "LIT_START_LOG=%TEMP%\lit-webview-start.log"
break>"%LIT_START_LOG%"
powershell -NoProfile -WindowStyle Hidden -ExecutionPolicy Bypass -File "%~dp0scripts\minimize-console.ps1" -Action hide

echo.
echo ============================================
echo  Local Issue Tracker  (WebView2 window)
echo ============================================
echo.

call :refresh_uv_path
where uv >nul 2>&1
if errorlevel 1 (
  echo uv is not installed. Double-click install.cmd first.>> "%LIT_START_LOG%"
  goto :failed
)

if not exist ".venv\" (
  echo App is not installed yet. Double-click install.cmd first.>> "%LIT_START_LOG%"
  goto :failed
)

if not exist "frontend\dist\index.html" (
  echo frontend\dist is missing. Double-click install.cmd, or run: git pull>> "%LIT_START_LOG%"
  goto :failed
)

echo Starting the local server in a WebView2 window.>> "%LIT_START_LOG%"
uv run lit serve --webview >> "%LIT_START_LOG%" 2>&1
if errorlevel 1 goto :failed
exit /b 0

:failed
if defined LIT_FROM_VBS exit /b 1
powershell -NoProfile -WindowStyle Hidden -Command "Add-Type -AssemblyName System.Windows.Forms; $t = Get-Content -Raw -ErrorAction SilentlyContinue $env:TEMP\lit-webview-start.log; if (-not $t) { $t = 'Local Issue Tracker failed to start.' }; [System.Windows.Forms.MessageBox]::Show($t, 'Local Issue Tracker') | Out-Null"
exit /b 1

:refresh_uv_path
if exist "%USERPROFILE%\.local\bin\uv.exe" set "PATH=%USERPROFILE%\.local\bin;%PATH%"
if exist "%USERPROFILE%\.cargo\bin\uv.exe" set "PATH=%USERPROFILE%\.cargo\bin;%PATH%"
exit /b 0
