@echo off
setlocal
cd /d "%~dp0"

where winget >nul 2>&1
if errorlevel 1 (
    echo ERROR: winget is required to install Python, .NET, and Epic Games Launcher.
    pause
    exit /b 1
)

python --version >nul 2>&1
if errorlevel 1 (
    echo Installing Python 3.12...
    winget install --exact --id Python.Python.3.12 --scope user --silent --accept-package-agreements --accept-source-agreements
    if errorlevel 1 (
        echo ERROR: Python installation failed.
        pause
        exit /b 1
    )
    set "PATH=%LocalAppData%\Programs\Python\Python312;%LocalAppData%\Programs\Python\Python312\Scripts;%PATH%"
)

python -m pip install PySide6
if errorlevel 1 (
    echo ERROR: PySide6 installation failed.
    pause
    exit /b 1
)

if not exist "%~dp0Workspaces" mkdir "%~dp0Workspaces"

if not exist "%~dp0Workspaces\CAS" (
    echo Installing CAS release files...
    powershell -NoProfile -ExecutionPolicy Bypass -Command "$ErrorActionPreference='Stop'; $base='%~dp0Workspaces'; $dest=Join-Path $base 'CAS'; $release=Invoke-RestMethod 'https://api.github.com/repos/LongerWarrior/UEAssetToolkitGenerator/releases/latest'; $asset=$release.assets | Where-Object { $_.name -match '\.zip$' } | Select-Object -First 1; if (-not $asset) { throw 'No ZIP asset was found on the latest CAS release.' }; $zip=Join-Path $base $asset.name; Invoke-WebRequest $asset.browser_download_url -OutFile $zip; Expand-Archive -LiteralPath $zip -DestinationPath $dest -Force; Remove-Item -LiteralPath $zip -Force"
    if errorlevel 1 (
        echo ERROR: CAS download or extraction failed.
        pause
        exit /b 1
    )
)

where dotnet >nul 2>&1
dotnet --list-runtimes 2>nul | findstr /i /r /c:"Microsoft.WindowsDesktop.App 6\." >nul
if errorlevel 1 (
    echo Installing the .NET 6 Desktop Runtime required by CAS...
    winget install --exact --id Microsoft.DotNet.DesktopRuntime.6 --silent --accept-package-agreements --accept-source-agreements
    if errorlevel 1 (
        echo ERROR: .NET 6 Desktop Runtime installation failed.
        pause
        exit /b 1
    )
)

if not exist "%~dp0Workspaces\UEAssetToolkit-Fixes" (
    echo Downloading the Astroneer community UEAssetToolkit plugins...
    powershell -NoProfile -ExecutionPolicy Bypass -Command "$ErrorActionPreference='Stop'; $base='%~dp0Workspaces'; $dest=Join-Path $base 'UEAssetToolkit-Fixes'; $temp=Join-Path $base 'UEAssetToolkit-temp'; $zip=Join-Path $base 'UEAssetToolkit.zip'; Invoke-WebRequest 'https://api.github.com/repos/AstroTechies/UEAssetToolkit-Fixes/zipball' -OutFile $zip; Expand-Archive -LiteralPath $zip -DestinationPath $temp -Force; $root=Get-ChildItem -LiteralPath $temp -Directory | Select-Object -First 1; if (-not $root) { throw 'Toolkit archive was empty.' }; Move-Item -LiteralPath $root.FullName -Destination $dest; Remove-Item -LiteralPath $temp -Recurse -Force; Remove-Item -LiteralPath $zip -Force"
    if errorlevel 1 (
        echo ERROR: UEAssetToolkit download or extraction failed.
        pause
        exit /b 1
    )
)


if not exist "%~dp0local" mkdir "%~dp0local"
if not exist "%~dp0local\repak.exe" (
    echo Downloading portable repak into local\...
    powershell -NoProfile -ExecutionPolicy Bypass -Command "$ErrorActionPreference='Stop'; $base='%~dp0local'; $temp=Join-Path $base 'repak-temp'; $zip=Join-Path $base 'repak.zip'; $release=Invoke-RestMethod 'https://api.github.com/repos/trumank/repak/releases/latest'; $asset=$release.assets | Where-Object { $_.name -eq 'repak_cli-x86_64-pc-windows-msvc.zip' } | Select-Object -First 1; if (-not $asset) { throw 'No Windows x64 repak release ZIP was found.' }; Invoke-WebRequest $asset.browser_download_url -OutFile $zip; Expand-Archive -LiteralPath $zip -DestinationPath $temp -Force; $exe=Get-ChildItem -LiteralPath $temp -Filter 'repak.exe' -File -Recurse | Select-Object -First 1; if (-not $exe) { throw 'repak.exe was not found in the release ZIP.' }; Copy-Item -LiteralPath $exe.FullName -Destination (Join-Path $base 'repak.exe') -Force; Remove-Item -LiteralPath $temp -Recurse -Force; Remove-Item -LiteralPath $zip -Force"
    if errorlevel 1 (
        echo ERROR: repak download or extraction failed.
        pause
        exit /b 1
    )
)

if exist "%~dp0Workspaces\UEAssetToolkit-Fixes\AssetGenerator\AssetGenerator.uplugin" if exist "%~dp0Workspaces\UEAssetToolkit-Fixes\AssetDumper\AssetDumper.uplugin" (
    echo Configuring AOY's Unreal project with the AssetGenerator plugins...
    powershell -NoProfile -ExecutionPolicy Bypass -Command "$ErrorActionPreference='Stop'; $root='%~dp0Workspaces'; $source=Join-Path $root 'UEAssetToolkit-Fixes'; $project=Join-Path $root 'AOYAssetProject'; $plugins=Join-Path $project 'Plugins'; New-Item -ItemType Directory -Force -Path $plugins | Out-Null; Copy-Item -LiteralPath (Join-Path $source 'AssetGenerator') -Destination (Join-Path $plugins 'AssetGenerator') -Recurse -Force; Copy-Item -LiteralPath (Join-Path $source 'AssetDumper') -Destination (Join-Path $plugins 'AssetDumper') -Recurse -Force; $uproject=Join-Path $project 'AOYAssetProject.uproject'; $data=[ordered]@{FileVersion=3; EngineAssociation='4.27'; Category=''; Description='AOY Asset Toolkit host project'; Modules=@(); Plugins=@(@{Name='AssetGenerator';Enabled=$true},@{Name='AssetDumper';Enabled=$true})}; $json=$data | ConvertTo-Json -Depth 5; [IO.File]::WriteAllText($uproject,$json,[Text.UTF8Encoding]::new($false))"
    if errorlevel 1 (
        echo ERROR: AOY Unreal project plugin setup failed.
        pause
        exit /b 1
    )
) else (
    echo ERROR: Toolkit plugin source files are missing; cannot configure AOYAssetProject.
    pause
    exit /b 1
)
set "UE_CMD=%ProgramFiles%\Epic Games\UE_4.27\Engine\Binaries\Win64\UE4Editor-Cmd.exe"
if not exist "%UE_CMD%" set "UE_CMD=%ProgramFiles(x86)%\Epic Games\UE_4.27\Engine\Binaries\Win64\UE4Editor-Cmd.exe"
if not exist "%UE_CMD%" (
    echo UE 4.27 was not found. Epic Games Launcher will open so you can install it.
    set "EPIC_LAUNCHER=%ProgramFiles(x86)%\Epic Games\Launcher\Portal\Binaries\Win64\EpicGamesLauncher.exe"
    if not exist "%EPIC_LAUNCHER%" (
        winget install --exact --id EpicGames.EpicGamesLauncher --silent --accept-package-agreements --accept-source-agreements
    )
    if exist "%EPIC_LAUNCHER%" start "" "%EPIC_LAUNCHER%"
    echo In the Launcher, open Unreal Engine ^> Library, add an engine version, select 4.27.2, and install it.
) else (
    echo Found UE 4.27 at "%UE_CMD%".
)

echo.
echo ================= AOY Setup Check =================
set "CHECK_FAIL=0"
if exist "%~dp0local\repak.exe" (
    echo [OK] Portable repak is in local\.
) else (
    echo [MISSING] repak.exe is not in local\.
    set "CHECK_FAIL=1"
)
if exist "%~dp0local\unpak.bat" (
    echo [OK] Portable unpak wrapper is in local\.
) else (
    echo [MISSING] unpak.bat is not in local\.
    set "CHECK_FAIL=1"
)
if exist "%~dp0local\repack.bat" (
    echo [OK] Portable repack wrapper is in local\.
) else (
    echo [MISSING] repack.bat is not in local\.
    set "CHECK_FAIL=1"
)
if exist "%~dp0Workspaces\AOYAssetProject\AOYAssetProject.uproject" if exist "%~dp0Workspaces\AOYAssetProject\Plugins\AssetGenerator\AssetGenerator.uplugin" if exist "%~dp0Workspaces\AOYAssetProject\Plugins\AssetDumper\AssetDumper.uplugin" (
    echo [OK] AssetGenerator and AssetDumper are enabled in AOYAssetProject.
) else (
    echo [MISSING] AOYAssetProject or its enabled toolkit plugins are not configured.
    set "CHECK_FAIL=1"
)
python -c "import PySide6" >nul 2>&1
if errorlevel 1 (
    echo [MISSING] Python or PySide6 is not available from this terminal.
    set "CHECK_FAIL=1"
) else (
    echo [OK] Python and PySide6 are available.
)
if exist "%~dp0Workspaces\CAS" (
    echo [OK] CAS release files are staged in Workspaces\CAS.
) else (
    echo [MISSING] CAS files are not staged.
    set "CHECK_FAIL=1"
)
if exist "%~dp0Workspaces\UEAssetToolkit-Fixes\AssetGenerator\AssetGenerator.uplugin" (
    echo [OK] UEAssetToolkit AssetGenerator plugin is staged.
) else (
    echo [MISSING] UEAssetToolkit AssetGenerator plugin is not staged.
    set "CHECK_FAIL=1"
)
if exist "%~dp0Workspaces\UEAssetToolkit-Fixes\AssetDumper\AssetDumper.uplugin" (
    echo [OK] UEAssetToolkit AssetDumper plugin is staged.
) else (
    echo [MISSING] UEAssetToolkit AssetDumper plugin is not staged.
    set "CHECK_FAIL=1"
)
where dotnet >nul 2>&1
if errorlevel 1 (
    echo [MISSING] .NET is not on PATH.
    set "CHECK_FAIL=1"
) else (
    dotnet --list-runtimes 2>nul | findstr /i /r /c:"Microsoft.WindowsDesktop.App 6\." >nul
    if errorlevel 1 (
        echo [MISSING] .NET 6 Desktop Runtime is not detected.
        set "CHECK_FAIL=1"
    ) else (
        echo [OK] .NET 6 Desktop Runtime is installed.
    )
)
if exist "%UE_CMD%" (
    echo [OK] Unreal Engine 4.27 command-line editor found: "%UE_CMD%"
) else (
    echo [MISSING] Unreal Engine 4.27 command-line editor not found.
    set "CHECK_FAIL=1"
)
echo.
echo Toolkit plugins are copied and enabled in Workspaces\AOYAssetProject.
echo Plugins may still need compiling with UE 4.27 C++ build tools before use.
if "%CHECK_FAIL%"=="0" (
    echo Setup check: all required components were detected.
) else (
    echo Setup check: one or more components are missing; see messages above.
)
echo ===================================================
pause
if "%CHECK_FAIL%"=="0" exit /b 0
exit /b 1

