@echo off
setlocal
if "%~1"=="" (
    echo Usage: repack.bat input-folder [output.pak]
    exit /b 2
)
if not exist "%~dp0repak.exe" (
    echo ERROR: repak.exe is missing beside this script.
    exit /b 1
)
if not exist "%~f1\" (
    echo ERROR: input folder not found: "%~f1"
    exit /b 1
)
if "%~2"=="" (
    "%~dp0repak.exe" pack --version V11 "%~f1"
) else (
    "%~dp0repak.exe" pack --version V11 "%~f1" "%~f2"
)
exit /b %errorlevel%