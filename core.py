"""AOY backend functions. Keep GUI code out of this module."""
from __future__ import annotations

import importlib.util
import json
import os
import re
import shutil
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Sequence


def _clear_pycache() -> None:
    cache = Path(__file__).resolve().parent / "__pycache__"
    if cache.is_dir():
        shutil.rmtree(cache, ignore_errors=True)


_clear_pycache()


@dataclass(frozen=True)
class Check:
    name: str
    ready: bool
    detail: str


def _workspace_path(root: str | Path | None = None) -> Path:
    project_root = Path(root).expanduser().resolve() if root else Path(__file__).resolve().parent
    return project_root / "Workspaces"


def _resolve_workspace(workspace_path: str | Path, root: str | Path | None = None) -> Path:
    raw_workspace = Path(workspace_path).expanduser()
    workspace = raw_workspace.resolve()
    workspaces_root = _workspace_path(root).resolve()
    if raw_workspace.is_symlink() or workspace.parent != workspaces_root or not workspace.is_dir():
        raise FileNotFoundError(f"Mod workspace not found directly inside Workspaces: {workspace}")
    return workspace


def _validate_mod_id(mod_id: str) -> str:
    if not isinstance(mod_id, str):
        raise ValueError("Mod name must be text.")
    mod_id = mod_id.strip()
    if not re.fullmatch(r"[A-Za-z0-9.]+", mod_id) or not any(char.isalnum() for char in mod_id):
        raise ValueError("Mod name/ID may contain only ASCII letters, numbers, and periods.")
    return mod_id


def _validate_priority(priority: int | str) -> int:
    try:
        value = int(priority)
    except (TypeError, ValueError) as exc:
        raise ValueError("Priority must be a whole number from 0 to 799.") from exc
    if isinstance(priority, bool) or not 0 <= value <= 799:
        raise ValueError("Priority must be from 0 to 799. Priorities 800–999 are reserved.")
    return value


def _validate_mod_version(version: str) -> str:
    if not isinstance(version, str) or not re.fullmatch(r"[0-9]+\.[0-9]+\.[0-9]+", version.strip()):
        raise ValueError("Version must have three number parts, such as 1.0.0.")
    return version.strip()


def _package_folder_name(priority: int, mod_id: str, version: str) -> str:
    return f"{priority:03d}-{mod_id}-{version}"


def pak_filename(priority: int | str, mod_id: str, version: str) -> str:
    """Build the required Astroneer distributable .pak filename."""
    priority_value = _validate_priority(priority)
    mod_id = _validate_mod_id(mod_id)
    version = _validate_mod_version(version)
    return f"{_package_folder_name(priority_value, mod_id, version)}_P.pak"


def _write_json(path: Path, value: dict) -> None:
    temporary = path.with_name(path.name + ".tmp")
    try:
        temporary.write_text(json.dumps(value, indent=4, ensure_ascii=False) + "\n", encoding="utf-8")
        os.replace(temporary, path)
    finally:
        if temporary.exists():
            temporary.unlink()


def read_mod_metafile(workspace_path: str | Path, root: str | Path | None = None) -> dict:
    """Read AOY's project metafile, using defaults for older workspaces."""
    workspace = _resolve_workspace(workspace_path, root)
    metafile = workspace / "aoy.json"
    if not metafile.is_file():
        return {"priority": 0, "mod_name": workspace.name, "version": "0.1.0"}
    try:
        value = json.loads(metafile.read_text(encoding="utf-8-sig"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ValueError(f"Could not read AOY metafile: {metafile}") from exc
    if not isinstance(value, dict):
        raise ValueError(f"AOY metafile must contain a JSON object: {metafile}")
    return {
        "priority": value.get("priority", 0),
        "mod_name": value.get("mod_name", workspace.name),
        "version": value.get("version", "0.1.0"),
        "package_folder": value.get("package_folder"),
    }


def create_mod_workspace(name: str, root: str | Path | None = None) -> Path:
    """Create an AOY workspace and its initial package folder and metadata."""
    mod_id = _validate_mod_id(name)
    priority = 0
    version = "0.1.0"
    workspaces = _workspace_path(root)
    workspaces.mkdir(parents=True, exist_ok=True)
    workspace = workspaces / mod_id
    workspace.mkdir(exist_ok=False)
    package_name = _package_folder_name(priority, mod_id, version)
    package = workspace / package_name
    package.mkdir()
    _write_json(workspace / "aoy.json", {
        "priority": priority,
        "mod_name": mod_id,
        "version": version,
        "package_folder": package_name,
    })
    _write_json(package / "metadata.json", {
        "schema_version": 2,
        "name": mod_id,
        "mod_id": mod_id,
        "version": version,
    })
    return workspace.resolve()


def list_mod_workspaces(root: str | Path | None = None) -> list[str]:
    """List existing mod folder names in AOY's Workspaces directory."""
    workspace = _workspace_path(root)
    if not workspace.is_dir():
        return []
    return sorted(
        (item.name for item in workspace.iterdir() if item.is_dir() and not item.is_symlink()),
        key=str.casefold,
    )


def get_mod_workspace(name: str, root: str | Path | None = None) -> Path:
    """Resolve an existing mod workspace contained directly in Workspaces."""
    if not isinstance(name, str) or not name or name in (".", "..") or any(char in name for char in "/\\"):
        raise ValueError("Mod workspace name must be a single folder name.")
    workspace_root = _workspace_path(root).resolve()
    workspace = workspace_root / name
    if workspace.is_symlink() or not workspace.is_dir() or workspace.resolve().parent != workspace_root:
        raise FileNotFoundError(f"Mod workspace not found in Workspaces: {name}")
    return workspace.resolve()


def update_mod_metafile(workspace_path: str | Path,
                        priority: int | str,
                        mod_name: str,
                        version: str,
                        root: str | Path | None = None) -> Path:
    """Update project fields, metadata.json, and the inner package-folder name."""
    workspace = _resolve_workspace(workspace_path, root)
    priority_value = _validate_priority(priority)
    mod_id = _validate_mod_id(mod_name)
    version_value = _validate_mod_version(version)
    metafile_data = read_mod_metafile(workspace, root)
    old_package_name = metafile_data.get("package_folder")
    old_package = None
    if old_package_name:
        if not isinstance(old_package_name, str) or Path(old_package_name).name != old_package_name:
            raise ValueError("AOY metafile contains an invalid package folder name.")
        old_package = workspace / old_package_name
        if old_package.is_symlink() or (old_package.exists() and not old_package.is_dir()):
            raise ValueError("The package folder recorded in aoy.json is invalid.")
    elif not (workspace / "aoy.json").exists():
        candidates = [item for item in workspace.iterdir() if item.is_dir() and not item.is_symlink()]
        if len(candidates) == 1:
            old_package = candidates[0]
            old_package_name = old_package.name

    new_package_name = _package_folder_name(priority_value, mod_id, version_value)
    new_package = workspace / new_package_name
    if old_package and old_package.exists() and old_package != new_package and new_package.exists():
        raise FileExistsError(f"Package folder already exists: {new_package}")

    new_workspace = workspace.parent / mod_id
    if new_workspace != workspace and new_workspace.exists():
        raise FileExistsError(f"A workspace named '{mod_id}' already exists.")

    if old_package and old_package.exists() and old_package != new_package:
        old_package.rename(new_package)
    else:
        new_package.mkdir(parents=True, exist_ok=True)

    metadata_path = new_package / "metadata.json"
    metadata = {}
    if metadata_path.is_file():
        try:
            metadata = json.loads(metadata_path.read_text(encoding="utf-8-sig"))
        except (OSError, json.JSONDecodeError) as exc:
            raise ValueError(f"Could not read mod metadata: {metadata_path}") from exc
        if not isinstance(metadata, dict):
            raise ValueError(f"Mod metadata must contain a JSON object: {metadata_path}")
    metadata.update({
        "schema_version": 2,
        "name": mod_id,
        "mod_id": mod_id,
        "version": version_value,
    })
    _write_json(metadata_path, metadata)

    metafile_data.update({
        "priority": priority_value,
        "mod_name": mod_id,
        "version": version_value,
        "package_folder": new_package_name,
    })
    _write_json(workspace / "aoy.json", metafile_data)

    if new_workspace != workspace:
        workspace.rename(new_workspace)
        workspace = new_workspace
    return workspace.resolve()

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
