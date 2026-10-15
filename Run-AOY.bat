@echo off
cd /d "%~dp0"
where py >nul 2>&1
if not errorlevel 1 (
    py interface.py
) else (
    python interface.py
)
if errorlevel 1 (
    echo.
    echo AOY failed to start. If Python is missing, run Installers\WINDOWS.bat,
    echo then close and reopen this window and try again.
    pause
)
