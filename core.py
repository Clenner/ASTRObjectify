"""AOY backend functions. Keep GUI code out of this module."""
from __future__ import annotations

import importlib.util
import json
import os
import shutil
import subprocess
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class Check:
    name: str
    ready: bool
    detail: str


def find_unreal_cmd() -> Path | None:
    """Find the UE 4.27 command-line editor, including a user override."""
    override = os.environ.get("AOY_UE_CMD")
    candidates = [Path(override)] if override else []
    for env_name in ("ProgramFiles", "ProgramFiles(x86)"):
        base = os.environ.get(env_name)
        if base:
            candidates.append(Path(base) / "Epic Games/UE_4.27/Engine/Binaries/Win64/UE4Editor-Cmd.exe")
    for drive in ("C:/", "D:/", "E:/"):
        candidates.append(Path(drive) / "Epic Games/UE_4.27/Engine/Binaries/Win64/UE4Editor-Cmd.exe")
    for candidate in candidates:
        if candidate.is_file():
            return candidate
    return None


def check_setup(root: str | Path | None = None) -> list[Check]:
    """Report whether the local AOY toolchain components are available."""
    root_path = Path(root) if root else Path(__file__).resolve().parent
    workspaces = root_path / "Workspaces"
    checks = [
        Check("Python", True, f"{__import__('sys').version_info.major}.{__import__('sys').version_info.minor}"),
        Check("PySide6", importlib.util.find_spec("PySide6") is not None,
              "Importable" if importlib.util.find_spec("PySide6") else "Not installed for this Python"),
        Check("CAS", (workspaces / "CAS").is_dir() and any((workspaces / "CAS").iterdir()),
              "Release files staged" if (workspaces / "CAS").is_dir() and any((workspaces / "CAS").iterdir()) else "Release files not found"),
    ]
    project = workspaces / "AOYAssetProject"
    project_file = project / "AOYAssetProject.uproject"
    enabled_plugins: set[str] = set()
    if project_file.is_file():
        try:
            enabled_plugins = {item.get("Name", "") for item in json.loads(project_file.read_text(encoding="utf-8-sig")).get("Plugins", []) if item.get("Enabled")}
        except (OSError, json.JSONDecodeError):
            pass
    for plugin, filename in (("AssetGenerator", "AssetGenerator.uplugin"), ("AssetDumper", "AssetDumper.uplugin")):
        plugin_file = project / "Plugins" / plugin / filename
        enabled = plugin_file.is_file() and plugin in enabled_plugins
        checks.append(Check(plugin, enabled, "Copied and enabled in AOYAssetProject" if enabled else "Not copied/enabled in AOYAssetProject"))

    local = root_path / "local"
    for tool, filename in (("repak", "repak.exe"), ("unpak", "unpak.bat"), ("repack", "repack.bat")):
        tool_file = local / filename
        checks.append(Check(tool, tool_file.is_file(), str(tool_file) if tool_file.is_file() else "Not found in local/"))

    dotnet = shutil.which("dotnet")
    runtime_ok = False
    if dotnet:
        try:
            result = subprocess.run([dotnet, "--list-runtimes"], capture_output=True, text=True, timeout=10, check=False)
            runtime_ok = any("Microsoft.WindowsDesktop.App 6." in line for line in result.stdout.splitlines())
        except (OSError, subprocess.TimeoutExpired):
            pass
    checks.append(Check(".NET 6 Desktop Runtime", runtime_ok,
                        "Runtime detected" if runtime_ok else "Not detected on PATH"))

    ue_cmd = find_unreal_cmd()
    checks.append(Check("Unreal Engine 4.27", ue_cmd is not None,
                        str(ue_cmd) if ue_cmd else "UE4Editor-Cmd.exe not found"))
    return checks


def run_asset_generator(project_file: str | Path, dump_directory: str | Path,
                        ue_cmd: str | Path | None = None, timeout: int | None = None) -> subprocess.CompletedProcess[str]:
    """Run the toolkit commandlet without opening the interactive UE editor."""
    project = Path(project_file).expanduser().resolve()
    if not project.is_file() or project.suffix.lower() != ".uproject":
        raise FileNotFoundError(f"Unreal project file not found: {project}")
    editor = Path(ue_cmd) if ue_cmd else find_unreal_cmd()
    if editor is None or not editor.is_file():
        raise FileNotFoundError("UE4Editor-Cmd.exe for Unreal Engine 4.27 was not found")
    output = Path(dump_directory).expanduser().resolve()
    output.mkdir(parents=True, exist_ok=True)
    command = [str(editor), str(project), "-run=AssetGenerator",
               f"-DumpDirectory={output}", "-stdout", "-unattended", "-NoLogTimes"]
    return subprocess.run(command, capture_output=True, text=True, timeout=timeout, check=False)

if __name__ == "__main__": print("\n\n\nDo not independently run this module. This is an API. Open README.md for more information.\n\n\n")