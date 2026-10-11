#!/usr/bin/env bash
# ==============================================================================
# ASTRObjectify (AOY) Linux Installer & Environment Setup
# Ported from installer.bat for Linux systems.
# ==============================================================================

set -uo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

echo "=== ASTRObjectify (AOY) Linux Installer ==="
echo "Working directory: $SCRIPT_DIR"
echo

# ------------------------------------------------------------------------------
# 1. System tool dependencies check (curl, unzip, tar, xz)
# ------------------------------------------------------------------------------
for tool in curl unzip tar xz; do
    if ! command -v "$tool" >/dev/null 2>&1; then
        echo "ERROR: '$tool' is required but not installed." >&2
        echo "Please install it using your package manager (e.g. sudo apt install $tool / sudo dnf install $tool)." >&2
        exit 1
    fi
done

# ------------------------------------------------------------------------------
# 2. Python 3 check & package installation
# ------------------------------------------------------------------------------
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
    echo "ERROR: Python 3.10+ is required but was not found." >&2
    echo "Please install Python 3 (e.g. sudo apt install python3 python3-pip python3-tk)." >&2
    exit 1
fi

echo "Using Python: $($PYTHON_BIN --version) ($PYTHON_BIN)"

# Check PySide6
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

# Check Tkinter
if ! "$PYTHON_BIN" -c "import tkinter" >/dev/null 2>&1; then
    echo "ERROR: Tkinter is missing from this Python installation." >&2
    echo "Install Tkinter using your package manager:" >&2
    echo "  Debian/Ubuntu: sudo apt install python3-tk" >&2
    echo "  Fedora:        sudo dnf install python3-tkinter" >&2
    echo "  Arch Linux:    sudo pacman -S tk" >&2
    exit 1
fi

# ------------------------------------------------------------------------------
# 3. Directory creation & legacy migrations
# ------------------------------------------------------------------------------
mkdir -p "$SCRIPT_DIR/Workspaces"
mkdir -p "$SCRIPT_DIR/local"

if [ ! -d "$SCRIPT_DIR/local/CAS" ] && [ -d "$SCRIPT_DIR/Workspaces/CAS" ]; then
    echo "Moving existing CAS files from Workspaces/ to local/..."
    mv "$SCRIPT_DIR/Workspaces/CAS" "$SCRIPT_DIR/local/CAS"
fi

if [ ! -d "$SCRIPT_DIR/local/UEAssetToolkit-Fixes" ] && [ -d "$SCRIPT_DIR/Workspaces/UEAssetToolkit-Fixes" ]; then
    echo "Moving existing UEAssetToolkit source from Workspaces/ to local/..."
    mv "$SCRIPT_DIR/Workspaces/UEAssetToolkit-Fixes" "$SCRIPT_DIR/local/UEAssetToolkit-Fixes"
fi

if [ ! -d "$SCRIPT_DIR/local/AOYAssetProject" ] && [ -d "$SCRIPT_DIR/Workspaces/AOYAssetProject" ]; then
    echo "Moving AOY's internal Unreal project from Workspaces/ to local/..."
    mv "$SCRIPT_DIR/Workspaces/AOYAssetProject" "$SCRIPT_DIR/local/AOYAssetProject"
fi

# ------------------------------------------------------------------------------
# 4. CAS release files (UEAssetToolkitGenerator)
# ------------------------------------------------------------------------------
if [ ! -d "$SCRIPT_DIR/local/CAS" ]; then
    echo "Installing CAS release files..."
    CAS_DEST="$SCRIPT_DIR/local/CAS"
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
    CAS_ZIP="$SCRIPT_DIR/local/CAS_release.zip"
    curl -L "$CAS_URL" -o "$CAS_ZIP"
    unzip -q -o "$CAS_ZIP" -d "$CAS_DEST"
    rm -f "$CAS_ZIP"
fi

# ------------------------------------------------------------------------------
# 5. .NET 6 Runtime check
# ------------------------------------------------------------------------------
DOTNET_FOUND=0
if command -v dotnet >/dev/null 2>&1; then
    if dotnet --list-runtimes 2>/dev/null | grep -q -E "Microsoft\.(WindowsDesktop|NETCore)\.App 6\."; then
        DOTNET_FOUND=1
    fi
fi
if [ "$DOTNET_FOUND" -eq 0 ]; then
    echo "NOTE: .NET 6 runtime was not detected on PATH."
    echo "If running CAS (UEAssetToolkitGenerator), .NET 6 is required."
    echo "You can install it via your distro's package manager or Microsoft's dotnet-install script."
fi

# ------------------------------------------------------------------------------
# 6. UEAssetToolkit-Fixes plugins
# ------------------------------------------------------------------------------
if [ ! -d "$SCRIPT_DIR/local/UEAssetToolkit-Fixes" ]; then
    echo "Downloading the Astroneer community UEAssetToolkit plugins..."
    TEMP_DIR="$SCRIPT_DIR/local/UEAssetToolkit-temp"
    ZIP_FILE="$SCRIPT_DIR/local/UEAssetToolkit.zip"
    mkdir -p "$TEMP_DIR"
    curl -L "https://api.github.com/repos/AstroTechies/UEAssetToolkit-Fixes/zipball" -o "$ZIP_FILE"
    unzip -q -o "$ZIP_FILE" -d "$TEMP_DIR"
    EXTRACTED_ROOT=$(find "$TEMP_DIR" -mindepth 1 -maxdepth 1 -type d | head -n 1)
    if [ -z "$EXTRACTED_ROOT" ]; then
        echo "ERROR: Toolkit archive was empty." >&2
        rm -rf "$TEMP_DIR" "$ZIP_FILE"
        exit 1
    fi
    mv "$EXTRACTED_ROOT" "$SCRIPT_DIR/local/UEAssetToolkit-Fixes"
    rm -rf "$TEMP_DIR" "$ZIP_FILE"
fi

# ------------------------------------------------------------------------------
# 7. Portable repak (Linux binary)
# ------------------------------------------------------------------------------
if [ ! -f "$SCRIPT_DIR/local/repak" ]; then
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

    REPAK_ARCHIVE="$SCRIPT_DIR/local/repak_dl"
    curl -L "$REPAK_URL" -o "$REPAK_ARCHIVE"
    REPAK_TEMP="$SCRIPT_DIR/local/repak-temp"
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

    cp "$REPAK_BIN" "$SCRIPT_DIR/local/repak"
    chmod +x "$SCRIPT_DIR/local/repak"
    # Provide repak.exe alias so existing cross-platform code references continue to resolve
    ln -sf "$SCRIPT_DIR/local/repak" "$SCRIPT_DIR/local/repak.exe"
    rm -rf "$REPAK_TEMP" "$REPAK_ARCHIVE"
fi

# ------------------------------------------------------------------------------
# 8. Repak wrapper scripts
# ------------------------------------------------------------------------------
echo "Creating repak wrappers in local/..."

cat << 'EOF' > "$SCRIPT_DIR/local/unpak.sh"
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
chmod +x "$SCRIPT_DIR/local/unpak.sh"
ln -sf "$SCRIPT_DIR/local/unpak.sh" "$SCRIPT_DIR/local/unpak.bat"

cat << 'EOF' > "$SCRIPT_DIR/local/repack.sh"
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
    "$REPAK" pack "$1" --version V11
else
    "$REPAK" pack "$1" "$2" --version V11
fi
EOF
chmod +x "$SCRIPT_DIR/local/repack.sh"
ln -sf "$SCRIPT_DIR/local/repack.sh" "$SCRIPT_DIR/local/repack.bat"

# ------------------------------------------------------------------------------
# 9. Configure AOYAssetProject with AssetGenerator plugins
# ------------------------------------------------------------------------------
if [ -f "$SCRIPT_DIR/local/UEAssetToolkit-Fixes/AssetGenerator/AssetGenerator.uplugin" ] && \
   [ -f "$SCRIPT_DIR/local/UEAssetToolkit-Fixes/AssetDumper/AssetDumper.uplugin" ]; then
    echo "Configuring AOY's Unreal project with the AssetGenerator plugins..."
    PROJECT_DIR="$SCRIPT_DIR/local/AOYAssetProject"
    PLUGINS_DIR="$PROJECT_DIR/Plugins"
    mkdir -p "$PLUGINS_DIR"
    cp -r "$SCRIPT_DIR/local/UEAssetToolkit-Fixes/AssetGenerator" "$PLUGINS_DIR/"
    cp -r "$SCRIPT_DIR/local/UEAssetToolkit-Fixes/AssetDumper" "$PLUGINS_DIR/"

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

# ------------------------------------------------------------------------------
# 10. Unreal Engine 4.27 check
# ------------------------------------------------------------------------------
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

# ------------------------------------------------------------------------------
# 11. Final Setup Verification
# ------------------------------------------------------------------------------
echo
echo "================= AOY Setup Check ================="
CHECK_FAIL=0

if [ -f "$SCRIPT_DIR/local/repak" ]; then
    echo "[OK] Portable repak is in local/."
else
    echo "[MISSING] repak binary is not in local/."
    CHECK_FAIL=1
fi

if [ -f "$SCRIPT_DIR/local/unpak.sh" ]; then
    echo "[OK] Portable unpak wrapper is in local/."
else
    echo "[MISSING] unpak.sh is not in local/."
    CHECK_FAIL=1
fi

if [ -f "$SCRIPT_DIR/local/repack.sh" ]; then
    echo "[OK] Portable repack wrapper is in local/."
else
    echo "[MISSING] repack.sh is not in local/."
    CHECK_FAIL=1
fi

if [ -f "$SCRIPT_DIR/local/AOYAssetProject/AOYAssetProject.uproject" ] && \
   [ -f "$SCRIPT_DIR/local/AOYAssetProject/Plugins/AssetGenerator/AssetGenerator.uplugin" ] && \
   [ -f "$SCRIPT_DIR/local/AOYAssetProject/Plugins/AssetDumper/AssetDumper.uplugin" ]; then
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

if [ -d "$SCRIPT_DIR/local/CAS" ]; then
    echo "[OK] CAS release files are staged in local/CAS."
else
    echo "[MISSING] CAS files are not staged."
    CHECK_FAIL=1
fi

if [ -f "$SCRIPT_DIR/local/UEAssetToolkit-Fixes/AssetGenerator/AssetGenerator.uplugin" ]; then
    echo "[OK] UEAssetToolkit AssetGenerator source is staged in local/."
else
    echo "[MISSING] UEAssetToolkit AssetGenerator plugin is not staged."
    CHECK_FAIL=1
fi

if [ -f "$SCRIPT_DIR/local/UEAssetToolkit-Fixes/AssetDumper/AssetDumper.uplugin" ]; then
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
