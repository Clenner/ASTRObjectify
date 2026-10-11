"""AOY backend functions. Keep GUI code out of this module."""
from __future__ import annotations

import importlib.util
import json
import os
import shutil
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Sequence


@dataclass(frozen=True)
class Check:
    name: str
    ready: bool
    detail: str


def find_unreal_cmd() -> Path | None:
    """Find the UE 4.27 command-line editor, including AOY_UE_CMD override."""
    override = os.environ.get("AOY_UE_CMD")
    candidates = [Path(override).expanduser()] if override else []
    for env_name in ("ProgramFiles", "ProgramFiles(x86)"):
        base = os.environ.get(env_name)
        if base:
            candidates.append(Path(base) / "Epic Games/UE_4.27/Engine/Binaries/Win64/UE4Editor-Cmd.exe")
    for drive in ("C:/", "D:/", "E:/"):
        candidates.append(Path(drive) / "Program Files/Epic Games/UE_4.27/Engine/Binaries/Win64/UE4Editor-Cmd.exe")
        candidates.append(Path(drive) / "Epic Games/UE_4.27/Engine/Binaries/Win64/UE4Editor-Cmd.exe")
    for candidate in candidates:
        if candidate.is_file():
            return candidate.resolve()
    return None


def _resolve_editor(ue_cmd: str | Path | None = None) -> Path:
    editor = Path(ue_cmd).expanduser() if ue_cmd else find_unreal_cmd()
    if editor is None or not editor.is_file():
        raise FileNotFoundError(
            "UE4Editor-Cmd.exe for Unreal Engine 4.27 was not found. "
            "Install UE 4.27 or set AOY_UE_CMD to its full path."
        )
    return editor.resolve()


def _resolve_project(project_file: str | Path) -> Path:
    project = Path(project_file).expanduser().resolve()
    if not project.is_file() or project.suffix.lower() != ".uproject":
        raise FileNotFoundError(f"Unreal project file not found: {project}")
    try:
        data = json.loads(project.read_text(encoding="utf-8-sig"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ValueError(f"Could not read Unreal project descriptor: {project}") from exc
    if not isinstance(data, dict):
        raise ValueError(f"Unreal project descriptor must contain a JSON object: {project}")
    return project


def check_setup(root: str | Path | None = None) -> list[Check]:
    """Return readiness checks for AOY's locally staged toolchain."""
    root_path = Path(root).expanduser().resolve() if root else Path(__file__).resolve().parent
    local = root_path / "local"
    python_version = f"{sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}"
    pyside_installed = importlib.util.find_spec("PySide6") is not None
    checks = [
        Check("Python", True, python_version),
        Check("PySide6", pyside_installed,
              "Importable" if pyside_installed else "Not installed for this Python"),
    ]

    cas_dir = local / "CAS"
    cas_ready = cas_dir.is_dir() and any(cas_dir.iterdir())
    checks.append(Check("CAS", cas_ready,
                        "Release files staged" if cas_ready else "Release files not found in local/CAS"))

    project = local / "AOYAssetProject"
    project_file = project / "AOYAssetProject.uproject"
    enabled_plugins: set[str] = set()
    project_readable = False
    if project_file.is_file():
        try:
            project_data = json.loads(project_file.read_text(encoding="utf-8-sig"))
            project_readable = isinstance(project_data, dict)
            enabled_plugins = {
                item.get("Name", "")
                for item in project_data.get("Plugins", [])
                if isinstance(item, dict) and item.get("Enabled")
            }
        except (OSError, json.JSONDecodeError):
            pass
    checks.append(Check("AOY asset project", project_readable,
                        str(project_file) if project_readable else "Missing or invalid .uproject in local/AOYAssetProject"))

    for plugin, filename in (("AssetGenerator", "AssetGenerator.uplugin"),
                             ("AssetDumper", "AssetDumper.uplugin")):
        plugin_file = project / "Plugins" / plugin / filename
        enabled = plugin_file.is_file() and plugin in enabled_plugins
        checks.append(Check(plugin, enabled,
                            "Copied and enabled in AOYAssetProject" if enabled else "Not copied/enabled in AOYAssetProject"))

    for tool, filename in (("repak", "repak.exe"), ("unpak", "unpak.bat"), ("repack", "repack.bat")):
        tool_file = local / filename
        checks.append(Check(tool, tool_file.is_file(),
                            str(tool_file) if tool_file.is_file() else f"Not found in {tool_file}"))

    dotnet = shutil.which("dotnet")
    runtime_ok = False
    if dotnet:
        try:
            result = subprocess.run([dotnet, "--list-runtimes"], capture_output=True,
                                    text=True, timeout=10, check=False)
            runtime_ok = any("Microsoft.WindowsDesktop.App 6." in line
                             for line in result.stdout.splitlines())
        except (OSError, subprocess.TimeoutExpired):
            pass
    checks.append(Check(".NET 6 Desktop Runtime", runtime_ok,
                        "Runtime detected" if runtime_ok else "Not detected on PATH"))

    ue_cmd = find_unreal_cmd()
    checks.append(Check("Unreal Engine 4.27", ue_cmd is not None,
                        str(ue_cmd) if ue_cmd else "UE4Editor-Cmd.exe not found"))
    return checks


def _run(command: Sequence[str], timeout: int | None = None) -> subprocess.CompletedProcess[str]:
    """Run a tool without opening a shell and return its captured output and exit code."""
    return subprocess.run(list(command), capture_output=True, text=True,
                          encoding="utf-8", errors="replace", timeout=timeout, check=False)


def run_asset_generator(project_file: str | Path, dump_directory: str | Path,
                        ue_cmd: str | Path | None = None,
                        timeout: int | None = None) -> subprocess.CompletedProcess[str]:
    """Run UEAssetToolkit's AssetGenerator commandlet without the editor window."""
    project = _resolve_project(project_file)
    editor = _resolve_editor(ue_cmd)
    output = Path(dump_directory).expanduser().resolve()
    output.mkdir(parents=True, exist_ok=True)
    command = [str(editor), str(project), "-run=AssetGenerator",
               f"-DumpDirectory={output}", "-stdout", "-unattended", "-NoLogTimes"]
    return _run(command, timeout)


def cook_project(project_file: str | Path,
                 ue_cmd: str | Path | None = None,
                 target_platform: str = "WindowsNoEditor",
                 cook_all: bool = True,
                 iterative: bool = False,
                 timeout: int | None = None) -> subprocess.CompletedProcess[str]:
    """Cook a valid Unreal project using UE4Editor-Cmd, without opening the GUI.

    Unreal writes cooked files beneath the project's Saved/Sandboxes directory.
    This cooks assets already in the project; it does not create AOY item assets
    or guarantee that the result is a ready-to-install Astroneer mod.
    """
    project = _resolve_project(project_file)
    editor = _resolve_editor(ue_cmd)
    if not target_platform or any(char.isspace() for char in target_platform):
        raise ValueError("target_platform must be one Unreal platform name, such as WindowsNoEditor")
    command = [str(editor), str(project), "-run=Cook",
               f"-TargetPlatform={target_platform}", "-unattended", "-nop4",
               "-stdout", "-NoLogTimes"]
    if cook_all:
        command.append("-CookAll")
    if iterative:
        command.append("-iterate")
    return _run(command, timeout)


def pack_pak(input_directory: str | Path, output_pak: str | Path,
             repak_path: str | Path | None = None,
             version: str = "V11",
             timeout: int | None = None) -> subprocess.CompletedProcess[str]:
    """Pack a directory into a .pak archive with AOY's portable repak binary."""
    root = Path(__file__).resolve().parent / "local"
    repak = Path(repak_path).expanduser() if repak_path else root / "repak.exe"
    source = Path(input_directory).expanduser().resolve()
    destination = Path(output_pak).expanduser().resolve()
    if not repak.is_file():
        raise FileNotFoundError(f"repak executable not found: {repak}")
    if not source.is_dir():
        raise FileNotFoundError(f"Pak input directory not found: {source}")
    if destination.suffix.lower() != ".pak":
        raise ValueError("output_pak must have a .pak extension")
    destination.parent.mkdir(parents=True, exist_ok=True)
    return _run([str(repak.resolve()), "pack", str(source), str(destination), "--version", version], timeout)


def unpack_pak(input_pak: str | Path, output_directory: str | Path,
               repak_path: str | Path | None = None,
               timeout: int | None = None) -> subprocess.CompletedProcess[str]:
    """Extract a .pak archive with AOY's portable repak binary."""
    root = Path(__file__).resolve().parent / "local"
    repak = Path(repak_path).expanduser() if repak_path else root / "repak.exe"
    archive = Path(input_pak).expanduser().resolve()
    output = Path(output_directory).expanduser().resolve()
    if not repak.is_file():
        raise FileNotFoundError(f"repak executable not found: {repak}")
    if not archive.is_file():
        raise FileNotFoundError(f"Pak file not found: {archive}")
    output.mkdir(parents=True, exist_ok=True)
    return _run([str(repak.resolve()), "unpack", str(archive), "--output", str(output)], timeout)


def format_process_result(result: subprocess.CompletedProcess[str]) -> str:
    """Combine captured tool output for display in the AOY interface/log panel."""
    return "\n".join(part.strip() for part in (result.stdout, result.stderr) if part and part.strip())


if __name__ == "__main__":
    print("This module provides AOY backend functions. Start interface.py to use AOY.")


