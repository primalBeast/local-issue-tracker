@echo off
setlocal EnableExtensions
cd /d "%~dp0"

echo.
echo ============================================
echo  Local Issue Tracker
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

netstat -ano | findstr ":8765" | findstr "LISTENING" >nul
if not errorlevel 1 (
  echo Already running on http://127.0.0.1:8765
  echo Opening the browser...
  start "" "http://127.0.0.1:8765"
  echo.
  pause
  exit /b 0
)

echo Starting local server and opening the browser.
echo Leave this window open while you use the app.
echo Press Ctrl+C to stop.
echo.
echo http://127.0.0.1:8765
echo.

uv run lit serve --open
set "RC=%ERRORLEVEL%"
echo.
if not "%RC%"=="0" (
  echo Server exited with an error ^(%RC%^).
  echo If you see "No module named lit", run install.cmd again.
)
pause
exit /b %RC%

:refresh_uv_path
if exist "%USERPROFILE%\.local\bin\uv.exe" set "PATH=%USERPROFILE%\.local\bin;%PATH%"
if exist "%USERPROFILE%\.cargo\bin\uv.exe" set "PATH=%USERPROFILE%\.cargo\bin;%PATH%"
exit /b 0
