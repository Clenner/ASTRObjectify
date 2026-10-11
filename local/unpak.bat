@echo off
setlocal
if "%~1"=="" (
    echo Usage: unpak.bat input.pak [output-folder]
    exit /b 2
)
if not exist "%~dp0repak.exe" (
    echo ERROR: repak.exe is missing beside this script.
    exit /b 1
)
if not exist "%~f1" (
    echo ERROR: PAK file not found: "%~f1"
    exit /b 1
)
if "%~2"=="" (
    "%~dp0repak.exe" unpack "%~f1"
) else (
    "%~dp0repak.exe" unpack -f -o "%~f2" "%~f1"
)
exit /b %errorlevel%