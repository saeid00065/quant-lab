@echo off
setlocal

rem Always run from this project's folder, even when double-clicked elsewhere.
cd /d "%~dp0"

echo Starting Quant Lab dashboard...
py -3 -m http.server 8502 --directory dist

if errorlevel 1 (
    echo.
    echo The dashboard could not start. Check the message above, then press any key to close.
    pause >nul
)
