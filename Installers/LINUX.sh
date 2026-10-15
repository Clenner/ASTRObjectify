#!/usr/bin/env bash

set -uo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT_DIR="$(dirname "$SCRIPT_DIR")"
cd "$ROOT_DIR"

echo "=== ASTRObjectify (AOY) Linux Installer ==="
echo "Working directory: $ROOT_DIR"
echo

for tool in curl unzip tar xz; do
    if ! command -v "$tool" >/dev/null 2>&1; then
        echo "ERROR: '$tool' is required but not installed." >&2
        echo "Please install it using your package manager (e.g. sudo apt install $tool / sudo dnf install $tool)." >&2
        exit 1
    fi
done

PYTHON_BIN=""
for candidate in python3 python; do
    if command -v "$candidate" >/dev/null 2>&1; then
        if "$candidate" -c "import sys; sys.exit(0 if sys.version_info >= (3, 10) else 1)" 2>/dev/null; then
            PYTHON_BIN="$candidate"
            break
        fi
    fi
done

if [ -z "$PYTHON_BIN" ]; then
    echo "Python 3.10+ not found. Attempting to install..."
    if command -v apt-get >/dev/null 2>&1; then
        echo "Detected apt — installing python3, python3-pip..."
        sudo apt-get update -qq
        sudo apt-get install -y python3 python3-pip
    elif command -v dnf >/dev/null 2>&1; then
        echo "Detected dnf — installing python3, python3-pip..."
        sudo dnf install -y python3 python3-pip
    elif command -v pacman >/dev/null 2>&1; then
        echo "Detected pacman — installing python, python-pip..."
        sudo pacman -Sy --noconfirm python python-pip
    elif command -v zypper >/dev/null 2>&1; then
        echo "Detected zypper — installing python3, python3-pip..."
        sudo zypper install -y python3 python3-pip
    else
        echo "ERROR: Could not detect a supported package manager (apt, dnf, pacman, zypper)." >&2
        echo "Please install Python 3.10+ manually and re-run this installer." >&2
        exit 1
    fi

    for candidate in python3 python; do
        if command -v "$candidate" >/dev/null 2>&1; then
            if "$candidate" -c "import sys; sys.exit(0 if sys.version_info >= (3, 10) else 1)" 2>/dev/null; then
                PYTHON_BIN="$candidate"
                break
            fi
        fi
    done

    if [ -z "$PYTHON_BIN" ]; then
        echo "ERROR: Python 3.10+ installation failed or is still not on PATH." >&2
        exit 1
    fi
fi

echo "Using Python: $($PYTHON_BIN --version) ($PYTHON_BIN)"

if ! "$PYTHON_BIN" -m pip --version >/dev/null 2>&1; then
    echo "pip not found. Attempting to install..."
    "$PYTHON_BIN" -m ensurepip --upgrade >/dev/null 2>&1 || true
    if ! "$PYTHON_BIN" -m pip --version >/dev/null 2>&1; then
        if command -v apt-get >/dev/null 2>&1; then
            sudo apt-get update -qq
            sudo apt-get install -y python3-pip python3-venv
        elif command -v dnf >/dev/null 2>&1; then
            sudo dnf install -y python3-pip
        elif command -v pacman >/dev/null 2>&1; then
            sudo pacman -Sy --noconfirm python-pip
        elif command -v zypper >/dev/null 2>&1; then
            sudo zypper install -y python3-pip
        fi
    fi
    if ! "$PYTHON_BIN" -m pip --version >/dev/null 2>&1; then
        echo "ERROR: pip is still missing for $PYTHON_BIN." >&2
        echo "Install it manually (e.g. sudo apt install python3-pip python3-venv) and re-run." >&2
        exit 1
    fi
fi
"$PYTHON_BIN" -m pip install --upgrade pip --quiet 2>/dev/null || \
    "$PYTHON_BIN" -m pip install --upgrade pip --user --quiet 2>/dev/null || true

if ! "$PYTHON_BIN" -c "import PySide6" >/dev/null 2>&1; then
    echo "Installing PySide6..."
    if ! "$PYTHON_BIN" -m pip install PySide6 --quiet 2>/dev/null; then
        if ! "$PYTHON_BIN" -m pip install --user PySide6 --quiet 2>/dev/null; then
            "$PYTHON_BIN" -m pip install PySide6 --break-system-packages --quiet || {
                echo "ERROR: PySide6 installation failed." >&2
                echo "Try installing manually: pip install PySide6 (or via virtualenv)" >&2
                exit 1
            }
        fi
    fi
fi

mkdir -p "$ROOT_DIR/Workspaces"
mkdir -p "$ROOT_DIR/local"

if [ ! -d "$ROOT_DIR/local/CAS" ] && [ -d "$ROOT_DIR/Workspaces/CAS" ]; then
    echo "Moving existing CAS files from Workspaces/ to local/..."
    mv "$ROOT_DIR/Workspaces/CAS" "$ROOT_DIR/local/CAS"
fi

if [ ! -d "$ROOT_DIR/local/UEAssetToolkit-Fixes" ] && [ -d "$ROOT_DIR/Workspaces/UEAssetToolkit-Fixes" ]; then
    echo "Moving existing UEAssetToolkit source from Workspaces/ to local/..."
    mv "$ROOT_DIR/Workspaces/UEAssetToolkit-Fixes" "$ROOT_DIR/local/UEAssetToolkit-Fixes"
fi

if [ ! -d "$ROOT_DIR/local/AOYAssetProject" ] && [ -d "$ROOT_DIR/Workspaces/AOYAssetProject" ]; then
    echo "Moving AOY's internal Unreal project from Workspaces/ to local/..."
    mv "$ROOT_DIR/Workspaces/AOYAssetProject" "$ROOT_DIR/local/AOYAssetProject"
fi

if [ ! -d "$ROOT_DIR/local/CAS" ]; then
    echo "Installing CAS release files..."
    CAS_DEST="$ROOT_DIR/local/CAS"
    mkdir -p "$CAS_DEST"
    CAS_URL=$(curl -sL -H "User-Agent: AOY-Installer" "https://api.github.com/repos/LongerWarrior/UEAssetToolkitGenerator/releases/latest" | "$PYTHON_BIN" -c "
import sys, json
try:
    data = json.load(sys.stdin)
    for asset in data.get('assets', []):
        if asset.get('name', '').endswith('.zip'):
            print(asset['browser_download_url'])
            break
except Exception:
    pass
")
    if [ -z "$CAS_URL" ]; then
        echo "ERROR: No ZIP asset was found on the latest CAS release." >&2
        exit 1
    fi
    CAS_ZIP="$ROOT_DIR/local/CAS_release.zip"
    curl -L "$CAS_URL" -o "$CAS_ZIP"
    unzip -q -o "$CAS_ZIP" -d "$CAS_DEST"
    rm -f "$CAS_ZIP"
fi

DOTNET_FOUND=0
if command -v dotnet >/dev/null 2>&1; then
    if dotnet --list-runtimes 2>/dev/null | grep -q -E "Microsoft\.(WindowsDesktop|NETCore)\.App 6\."; then
        DOTNET_FOUND=1
    fi
fi
if [ "$DOTNET_FOUND" -eq 0 ]; then
    echo ".NET 6 runtime not detected. Installing locally via dotnet-install script..."
    DOTNET_DIR="$HOME/.dotnet"
    mkdir -p "$DOTNET_DIR"
    if curl -sSL "https://dot.net/v1/dotnet-install.sh" -o /tmp/dotnet-install.sh; then
        bash /tmp/dotnet-install.sh --channel 6.0 --runtime dotnet --install-dir "$DOTNET_DIR" --no-path >/dev/null 2>&1 || true
        rm -f /tmp/dotnet-install.sh
    fi
    export PATH="$DOTNET_DIR:$PATH"
    export DOTNET_ROOT="$DOTNET_DIR"
    if command -v dotnet >/dev/null 2>&1; then
        if dotnet --list-runtimes 2>/dev/null | grep -q -E "Microsoft\.(WindowsDesktop|NETCore)\.App 6\."; then
            DOTNET_FOUND=1
            echo "Installed .NET 6 runtime to $DOTNET_DIR."
            echo "Add it to future terminals with: export PATH=\"\$HOME/.dotnet:\$PATH\""
        fi
    fi
fi
if [ "$DOTNET_FOUND" -eq 0 ]; then
    echo "NOTE: .NET 6 runtime was not detected on PATH."
    echo "If running CAS (UEAssetToolkitGenerator), .NET 6 is required."
    echo "Install it manually (e.g. rerun this installer) or via Microsoft's dotnet-install script."
fi

if [ ! -d "$ROOT_DIR/local/UEAssetToolkit-Fixes" ]; then
    echo "Downloading the Astroneer community UEAssetToolkit plugins..."
    TEMP_DIR="$ROOT_DIR/local/UEAssetToolkit-temp"
    ZIP_FILE="$ROOT_DIR/local/UEAssetToolkit.zip"
    mkdir -p "$TEMP_DIR"
    curl -L "https://api.github.com/repos/AstroTechies/UEAssetToolkit-Fixes/zipball" -o "$ZIP_FILE"
    unzip -q -o "$ZIP_FILE" -d "$TEMP_DIR"
    EXTRACTED_ROOT=$(find "$TEMP_DIR" -mindepth 1 -maxdepth 1 -type d | head -n 1)
    if [ -z "$EXTRACTED_ROOT" ]; then
        echo "ERROR: Toolkit archive was empty." >&2
        rm -rf "$TEMP_DIR" "$ZIP_FILE"
        exit 1
    fi
    mv "$EXTRACTED_ROOT" "$ROOT_DIR/local/UEAssetToolkit-Fixes"
    rm -rf "$TEMP_DIR" "$ZIP_FILE"
fi

if [ ! -f "$ROOT_DIR/local/repak" ]; then
    echo "Downloading portable repak for Linux into local/..."
    REPAK_URL=$(curl -sL -H "User-Agent: AOY-Installer" "https://api.github.com/repos/trumank/repak/releases/latest" | "$PYTHON_BIN" -c "
import sys, json
try:
    data = json.load(sys.stdin)
    for asset in data.get('assets', []):
        name = asset.get('name', '')
        if 'linux' in name and (name.endswith('.tar.xz') or name.endswith('.tar.gz') or name.endswith('.zip')):
            print(asset['browser_download_url'])
            break
except Exception:
    pass
")
    if [ -z "$REPAK_URL" ]; then
        echo "ERROR: No Linux repak release found." >&2
        exit 1
    fi

    REPAK_ARCHIVE="$ROOT_DIR/local/repak_dl"
    curl -L "$REPAK_URL" -o "$REPAK_ARCHIVE"
    REPAK_TEMP="$ROOT_DIR/local/repak-temp"
    mkdir -p "$REPAK_TEMP"

    if [[ "$REPAK_URL" == *.tar.xz ]]; then
        tar -xJf "$REPAK_ARCHIVE" -C "$REPAK_TEMP"
    elif [[ "$REPAK_URL" == *.tar.gz ]]; then
        tar -xzf "$REPAK_ARCHIVE" -C "$REPAK_TEMP"
    else
        unzip -q -o "$REPAK_ARCHIVE" -d "$REPAK_TEMP"
    fi

    REPAK_BIN=$(find "$REPAK_TEMP" -type f -name "repak" | head -n 1)
    if [ -z "$REPAK_BIN" ]; then
        echo "ERROR: repak binary not found in archive." >&2
        rm -rf "$REPAK_TEMP" "$REPAK_ARCHIVE"
        exit 1
    fi

    cp "$REPAK_BIN" "$ROOT_DIR/local/repak"
    chmod +x "$ROOT_DIR/local/repak"
    ln -sf "$ROOT_DIR/local/repak" "$ROOT_DIR/local/repak.exe"
    rm -rf "$REPAK_TEMP" "$REPAK_ARCHIVE"
fi

echo "Creating repak wrappers in local/..."

cat << 'EOF' > "$ROOT_DIR/local/unpak.sh"
#!/usr/bin/env bash
set -e
DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPAK="$DIR/repak"
if [ ! -f "$REPAK" ]; then
    echo "ERROR: repak binary is missing from $DIR." >&2
    exit 1
fi
if [ -z "${1:-}" ]; then
    echo "Usage: unpak.sh input.pak [output-directory]" >&2
    exit 2
fi
if [ -z "${2:-}" ]; then
    "$REPAK" unpack "$1"
else
    "$REPAK" unpack "$1" --output "$2"
fi
EOF
chmod +x "$ROOT_DIR/local/unpak.sh"
ln -sf "$ROOT_DIR/local/unpak.sh" "$ROOT_DIR/local/unpak.bat"

cat << 'EOF' > "$ROOT_DIR/local/repack.sh"
#!/usr/bin/env bash
set -e
DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPAK="$DIR/repak"
if [ ! -f "$REPAK" ]; then
    echo "ERROR: repak binary is missing from $DIR." >&2
    exit 1
fi
if [ -z "${1:-}" ]; then
    echo "Usage: repack.sh input-directory [output.pak]" >&2
    exit 2
fi
if [ -z "${2:-}" ]; then
    "$REPAK" pack "$1" --version V4 --compression Zlib
else
    "$REPAK" pack "$1" "$2" --version V4 --compression Zlib
fi
EOF
chmod +x "$ROOT_DIR/local/repack.sh"
ln -sf "$ROOT_DIR/local/repack.sh" "$ROOT_DIR/local/repack.bat"

if [ -f "$ROOT_DIR/local/UEAssetToolkit-Fixes/AssetGenerator/AssetGenerator.uplugin" ] && \
   [ -f "$ROOT_DIR/local/UEAssetToolkit-Fixes/AssetDumper/AssetDumper.uplugin" ]; then
    echo "Configuring AOY's Unreal project with the AssetGenerator plugins..."
    PROJECT_DIR="$ROOT_DIR/local/AOYAssetProject"
    PLUGINS_DIR="$PROJECT_DIR/Plugins"
    mkdir -p "$PLUGINS_DIR"
    cp -r "$ROOT_DIR/local/UEAssetToolkit-Fixes/AssetGenerator" "$PLUGINS_DIR/"
    cp -r "$ROOT_DIR/local/UEAssetToolkit-Fixes/AssetDumper" "$PLUGINS_DIR/"

    "$PYTHON_BIN" -c "
import json
from pathlib import Path
project = Path('$PROJECT_DIR')
uproject = project / 'AOYAssetProject.uproject'
data = {
    'FileVersion': 3,
    'EngineAssociation': '4.27',
    'Category': '',
    'Description': 'AOY Asset Toolkit host project',
    'Modules': [],
    'Plugins': [
        {'Name': 'AssetGenerator', 'Enabled': True},
        {'Name': 'AssetDumper', 'Enabled': True}
    ]
}
uproject.write_text(json.dumps(data, indent=4) + '\n', encoding='utf-8')
"
else
    echo "ERROR: Toolkit plugin source files are missing; cannot configure AOYAssetProject." >&2
    exit 1
fi

UE_CMD="${AOY_UE_CMD:-}"
if [ -z "$UE_CMD" ]; then
    for candidate in \
        "$HOME/UnrealEngine/Engine/Binaries/Linux/UE4Editor-Cmd" \
        "$HOME/UE_4.27/Engine/Binaries/Linux/UE4Editor-Cmd" \
        "/opt/unreal-engine/Engine/Binaries/Linux/UE4Editor-Cmd" \
        "/opt/UE_4.27/Engine/Binaries/Linux/UE4Editor-Cmd"; do
        if [ -f "$candidate" ]; then
            UE_CMD="$candidate"
            break
        fi
    done
fi

echo
echo "================= AOY Setup Check ================="
CHECK_FAIL=0

if [ -f "$ROOT_DIR/local/repak" ]; then
    echo "[OK] Portable repak is in local/."
else
    echo "[MISSING] repak binary is not in local/."
    CHECK_FAIL=1
fi

if [ -f "$ROOT_DIR/local/unpak.sh" ]; then
    echo "[OK] Portable unpak wrapper is in local/."
else
    echo "[MISSING] unpak.sh is not in local/."
    CHECK_FAIL=1
fi

if [ -f "$ROOT_DIR/local/repack.sh" ]; then
    echo "[OK] Portable repack wrapper is in local/."
else
    echo "[MISSING] repack.sh is not in local/."
    CHECK_FAIL=1
fi

if [ -f "$ROOT_DIR/local/AOYAssetProject/AOYAssetProject.uproject" ] && \
   [ -f "$ROOT_DIR/local/AOYAssetProject/Plugins/AssetGenerator/AssetGenerator.uplugin" ] && \
   [ -f "$ROOT_DIR/local/AOYAssetProject/Plugins/AssetDumper/AssetDumper.uplugin" ]; then
    echo "[OK] AssetGenerator and AssetDumper are enabled in AOYAssetProject."
else
    echo "[MISSING] AOYAssetProject or its enabled toolkit plugins are not configured."
    CHECK_FAIL=1
fi

if "$PYTHON_BIN" -c "import PySide6" >/dev/null 2>&1; then
    echo "[OK] Python and PySide6 are available."
else
    echo "[MISSING] PySide6 is not available."
    CHECK_FAIL=1
fi

if [ -d "$ROOT_DIR/local/CAS" ]; then
    echo "[OK] CAS release files are staged in local/CAS."
else
    echo "[MISSING] CAS files are not staged."
    CHECK_FAIL=1
fi

if [ -f "$ROOT_DIR/local/UEAssetToolkit-Fixes/AssetGenerator/AssetGenerator.uplugin" ]; then
    echo "[OK] UEAssetToolkit AssetGenerator source is staged in local/."
else
    echo "[MISSING] UEAssetToolkit AssetGenerator plugin is not staged."
    CHECK_FAIL=1
fi

if [ -f "$ROOT_DIR/local/UEAssetToolkit-Fixes/AssetDumper/AssetDumper.uplugin" ]; then
    echo "[OK] UEAssetToolkit AssetDumper source is staged in local/."
else
    echo "[MISSING] UEAssetToolkit AssetDumper plugin is not staged."
    CHECK_FAIL=1
fi

if [ "$DOTNET_FOUND" -eq 1 ]; then
    echo "[OK] .NET 6 Runtime detected."
else
    echo "[WARNING] .NET 6 Runtime not detected on PATH."
fi

if [ -n "$UE_CMD" ] && [ -f "$UE_CMD" ]; then
    echo "[OK] Unreal Engine 4.27 editor found: $UE_CMD"
else
    echo "[MISSING] Unreal Engine 4.27 command-line editor not found."
    echo "          Set AOY_UE_CMD to the path of UE4Editor-Cmd if installed."
    CHECK_FAIL=1
fi

echo
echo "Toolkit plugins are copied and enabled in local/AOYAssetProject."
if [ "$CHECK_FAIL" -eq 0 ]; then
    echo "Setup check: all required components were detected."
    echo "==================================================="
    exit 0
else
    echo "Setup check: one or more components are missing or require manual setup."
    echo "==================================================="
    exit 1
fi
