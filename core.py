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


def find_game_pak() -> Path | None:
    override = os.environ.get("AOY_GAME_PAK")
    if override and Path(override).expanduser().is_file():
        return Path(override).expanduser().resolve()

    pak_names = ("Astro-WindowsNoEditor.pak", "pakchunk0-WindowsNoEditor.pak")
    search_dirs: list[Path] = []

    steam_env = os.environ.get("ASTRONEER_PATH")
    if steam_env:
        search_dirs.append(Path(steam_env).expanduser() / "Astro/Content/Paks")

    for env_name in ("ProgramFiles(x86)", "ProgramFiles"):
        base = os.environ.get(env_name)
        if base:
            search_dirs.append(Path(base) / "Steam/steamapps/common/ASTRONEER/Astro/Content/Paks")

    for drive in ("C:/", "D:/", "E:/", "F:/"):
        search_dirs.append(Path(drive) / "SteamLibrary/steamapps/common/ASTRONEER/Astro/Content/Paks")
        search_dirs.append(Path(drive) / "Steam/steamapps/common/ASTRONEER/Astro/Content/Paks")
        search_dirs.append(Path(drive) / "Program Files (x86)/Steam/steamapps/common/ASTRONEER/Astro/Content/Paks")

    for directory in search_dirs:
        for pak_name in pak_names:
            candidate = directory / pak_name
            if candidate.is_file():
                return candidate.resolve()
    return None


def get_game_version() -> str | None:
    override = os.environ.get("AOY_GAME_VERSION")
    if override and re.fullmatch(r"[0-9]+\.[0-9]+(\.[0-9]+){0,2}", override.strip()):
        return override.strip()
    for game_root in _game_roots():
        version_file = game_root / "build.version"
        if not version_file.is_file() or version_file.is_symlink():
            continue
        try:
            with version_file.open(encoding="utf-8", errors="replace") as handle:
                line = handle.readline()
        except OSError:
            continue
        if not line:
            continue
        for candidate in (line[:-10] if len(line) > 10 else "", line.strip()):
            candidate = candidate.strip()
            if re.fullmatch(r"[0-9]+\.[0-9]+(\.[0-9]+){0,2}", candidate):
                return candidate
    return None


def _game_roots() -> list[Path]:
    roots: list[Path] = []
    game_pak = find_game_pak()
    if game_pak is not None:
        roots.append(game_pak.parent.parent.parent.parent)
    steam_env = os.environ.get("ASTRONEER_PATH")
    if steam_env:
        roots.append(Path(steam_env).expanduser())
    for env_name in ("ProgramFiles(x86)", "ProgramFiles"):
        base = os.environ.get(env_name)
        if base:
            roots.append(Path(base) / "Steam/steamapps/common/ASTRONEER")
    for drive in ("C:/", "D:/", "E:/", "F:/"):
        roots.append(Path(drive) / "SteamLibrary/steamapps/common/ASTRONEER")
        roots.append(Path(drive) / "Steam/steamapps/common/ASTRONEER")
        roots.append(Path(drive) / "Program Files (x86)/Steam/steamapps/common/ASTRONEER")
    return roots


def _find_repak(custom_path: str | Path | None = None) -> Path | None:
    if custom_path:
        custom = Path(custom_path).expanduser().resolve()
        if custom.is_file():
            return custom
    local_dir = Path(__file__).resolve().parent / "local"
    candidates = [
        local_dir / "repak.exe",
        local_dir / "repak",
    ]
    which_repak = shutil.which("repak")
    if which_repak:
        candidates.append(Path(which_repak))
    for candidate in candidates:
        if candidate.is_file():
            return candidate.resolve()
    return None


def get_extracted_game_path(root: str | Path | None = None) -> Path:
    base = Path(root).expanduser().resolve() if root else Path(__file__).resolve().parent
    return (base / "local" / "Astro-WindowsNoEditor").resolve()


def _ensure_game_extracted() -> Path | None:
    target_dir = get_extracted_game_path()
    game_pak = find_game_pak()
    stamp_file = target_dir / ".pak_stamp.json"

    if game_pak and target_dir.is_dir() and any(target_dir.iterdir()):
        if stamp_file.is_file():
            try:
                stamp = json.loads(stamp_file.read_text(encoding="utf-8"))
                pak_stat = game_pak.stat()
                if stamp.get("mtime") == pak_stat.st_mtime and stamp.get("size") == pak_stat.st_size:
                    return target_dir
                print("Astroneer game update detected! Re-extracting game files...")
            except (OSError, json.JSONDecodeError):
                pass
        else:
            try:
                pak_stat = game_pak.stat()
                stamp_file.write_text(
                    json.dumps({"mtime": pak_stat.st_mtime, "size": pak_stat.st_size}, indent=2) + "\n",
                    encoding="utf-8",
                )
            except OSError:
                pass
            return target_dir

    elif not game_pak and target_dir.is_dir() and any(target_dir.iterdir()):
        return target_dir

    repak = _find_repak()
    if not repak or not game_pak:
        return target_dir if target_dir.is_dir() and any(target_dir.iterdir()) else None

    if target_dir.exists():
        shutil.rmtree(target_dir, ignore_errors=True)

    target_dir.mkdir(parents=True, exist_ok=True)
    try:
        print(f"Extracting Astroneer game files into {target_dir}...")
        subprocess.run(
            [str(repak), "unpack", str(game_pak), "--output", str(target_dir)],
            capture_output=True,
            check=False,
        )
    except OSError:
        return None

    if target_dir.is_dir() and any(target_dir.iterdir()):
        print("Game files extraction complete.")
        try:
            pak_stat = game_pak.stat()
            stamp_file.write_text(
                json.dumps({"mtime": pak_stat.st_mtime, "size": pak_stat.st_size}, indent=2) + "\n",
                encoding="utf-8",
            )
        except OSError:
            pass
        return target_dir
    return None


_ensure_game_extracted()


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
    if raw_workspace.is_symlink():
        raise FileNotFoundError(f"Mod workspace not found: {raw_workspace}")
    workspace = raw_workspace.resolve()
    if not workspace.is_dir():
        raise FileNotFoundError(f"Mod workspace not found: {workspace}")
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


METAFILE_CONTROLLED_KEYS = ("name", "mod_id", "version")

SELECT_MARKER = "SELECT.HERE"


def _find_package_dir(workspace: Path) -> Path | None:
    for item in workspace.iterdir():
        if item.is_dir() and not item.is_symlink():
            match = re.fullmatch(r"([0-9]{1,3})-(.+)-([0-9]+\.[0-9]+\.[0-9]+)", item.name)
            if match:
                return item
    candidates = [item for item in workspace.iterdir() if item.is_dir() and not item.is_symlink()]
    if len(candidates) == 1:
        return candidates[0]
    return None


def pak_filename(priority: int | str, mod_id: str, version: str) -> str:
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
    workspace = _resolve_workspace(workspace_path, root)

    legacy_metafile = workspace / "aoy.json"
    if legacy_metafile.is_file():
        try:
            legacy_metafile.unlink()
        except OSError:
            pass

    package_dir = None
    priority = 0
    mod_name = workspace.name
    version = "0.1.0"

    for item in workspace.iterdir():
        if item.is_dir() and not item.is_symlink():
            match = re.fullmatch(r"([0-9]{1,3})-(.+)-([0-9]+\.[0-9]+\.[0-9]+)", item.name)
            if match:
                package_dir = item
                priority = int(match.group(1))
                mod_name = match.group(2)
                version = match.group(3)
                break

    if package_dir is None:
        candidates = [item for item in workspace.iterdir() if item.is_dir() and not item.is_symlink()]
        if len(candidates) == 1:
            package_dir = candidates[0]

    if package_dir and (package_dir / "metadata.json").is_file():
        try:
            meta = json.loads((package_dir / "metadata.json").read_text(encoding="utf-8-sig"))
            if isinstance(meta, dict):
                mod_name = meta.get("mod_id") or meta.get("name") or mod_name
                version = meta.get("version") or version
        except (OSError, json.JSONDecodeError):
            pass

    return {
        "priority": priority,
        "mod_name": mod_name,
        "version": version,
        "package_folder": package_dir.name if package_dir else None,
    }


def create_mod_workspace(name: str, root: str | Path | None = None,
                         author: str = "") -> Path:
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
    initial_metadata = {
        "schema_version": 2,
        "name": mod_id,
        "mod_id": mod_id,
        "author": author.strip() if isinstance(author, str) else "",
        "version": version,
    }
    _write_json(package / "metadata.json", initial_metadata)
    try:
        (workspace / SELECT_MARKER).touch(exist_ok=True)
    except OSError:
        pass
    return workspace.resolve()


def ensure_select_marker(workspace_path: str | Path, root: str | Path | None = None) -> Path:
    workspace = _resolve_workspace(workspace_path, root)
    marker = workspace / SELECT_MARKER
    try:
        marker.touch(exist_ok=True)
    except OSError as exc:
        raise OSError(f"Could not create {SELECT_MARKER} in workspace: {workspace}") from exc
    return marker.resolve()


def list_mod_workspaces(root: str | Path | None = None) -> list[str]:
    workspace = _workspace_path(root)
    if not workspace.is_dir():
        return []
    return sorted(
        (item.name for item in workspace.iterdir() if item.is_dir() and not item.is_symlink()),
        key=str.casefold,
    )


def get_mod_workspace(name: str, root: str | Path | None = None) -> Path:
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
                        root: str | Path | None = None,
                        author: str | None = None) -> Path:
    workspace = _resolve_workspace(workspace_path, root)
    priority_value = _validate_priority(priority)
    mod_id = _validate_mod_id(mod_name)
    version_value = _validate_mod_version(version)
    metafile_data = read_mod_metafile(workspace, root)
    old_package_name = metafile_data.get("package_folder")
    old_package = None
    if old_package_name:
        old_package = workspace / old_package_name
        if old_package.is_symlink() or (old_package.exists() and not old_package.is_dir()):
            raise ValueError("The package folder is invalid.")
    else:
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
    if author is not None:
        metadata["author"] = author.strip() if isinstance(author, str) else ""
    _write_json(metadata_path, metadata)

    legacy_metafile = workspace / "aoy.json"
    if legacy_metafile.is_file():
        try:
            legacy_metafile.unlink()
        except OSError:
            pass

    if new_workspace != workspace:
        workspace.rename(new_workspace)
        workspace = new_workspace
    return workspace.resolve()


def read_mod_metadata(workspace_path: str | Path, root: str | Path | None = None) -> dict:
    workspace = _resolve_workspace(workspace_path, root)
    metafile = read_mod_metafile(workspace, root)
    package_name = metafile.get("package_folder")
    if not package_name:
        raise FileNotFoundError(f"No package folder found in workspace: {workspace}")
    package = workspace / package_name
    if not package.is_dir():
        raise FileNotFoundError(f"Package folder not found: {package}")
    metadata_path = package / "metadata.json"
    metadata: dict = {}
    if metadata_path.is_file():
        try:
            metadata = json.loads(metadata_path.read_text(encoding="utf-8-sig"))
        except (OSError, json.JSONDecodeError) as exc:
            raise ValueError(f"Could not read mod metadata: {metadata_path}") from exc
        if not isinstance(metadata, dict):
            raise ValueError(f"Mod metadata must contain a JSON object: {metadata_path}")
    return {
        "package_folder": package_name,
        "metadata": metadata,
        "controlled": {
            "name": metafile.get("mod_name"),
            "mod_id": metafile.get("mod_name"),
            "version": metafile.get("version"),
        },
    }


def update_mod_metadata(workspace_path: str | Path,
                        editable_fields: dict,
                        root: str | Path | None = None) -> Path:
    if not isinstance(editable_fields, dict):
        raise ValueError("Metadata fields must be a mapping.")
    workspace = _resolve_workspace(workspace_path, root)
    metafile = read_mod_metafile(workspace, root)
    package_name = metafile.get("package_folder")
    if not package_name:
        raise FileNotFoundError(f"No package folder found in workspace: {workspace}")
    package = workspace / package_name
    if not package.is_dir():
        raise FileNotFoundError(f"Package folder not found: {package}")
    cleaned = {key: value for key, value in editable_fields.items()
               if key not in METAFILE_CONTROLLED_KEYS}
    for key in cleaned:
        if not isinstance(key, str) or not key.strip() or key.strip() != key:
            raise ValueError(f"Invalid metadata key: {key!r}")
    new_metadata = dict(cleaned)
    new_metadata.update({
        "schema_version": 2,
        "name": metafile.get("mod_name"),
        "mod_id": metafile.get("mod_name"),
        "version": metafile.get("version"),
    })
    new_metadata.pop("astro_build", None)
    _write_json(package / "metadata.json", new_metadata)
    return package.resolve()


MASTER_ITEM_LIST = "/Game/Items/ItemTypes/MasterItemList"
PRINTER_T1_SMALL = "/Game/Components_Small/Printer_Breadboards_T1"
PRINTER_T2_MEDIUM = "/Game/Components_Medium/Printer_Breadboards_T2"
_MANAGED_INTEGRATOR_TARGETS = (MASTER_ITEM_LIST, PRINTER_T1_SMALL, PRINTER_T2_MEDIUM)


def _asset_ref_from_file(package_dir: Path, file: Path) -> str | None:
    if file.suffix.lower() != ".uasset":
        return None
    try:
        rel = file.resolve().relative_to(package_dir.resolve())
    except (ValueError, OSError):
        return None
    ref = rel.with_suffix("").as_posix()
    if re.fullmatch(r"Game/Mods/[A-Za-z0-9.]+/.+", ref):
        return "/" + ref
    if re.fullmatch(r"Astro/Content/.+", ref):
        return "/Game/" + ref[len("Astro/Content/"):]
    return None


def _iter_package_refs(package_dir: str | Path) -> list[str]:
    package = Path(package_dir).expanduser().resolve()
    if not package.is_dir():
        return []
    refs: set[str] = set()
    for file in sorted(package.rglob("*.uasset")):
        if file.is_symlink() or not file.is_file():
            continue
        ref = _asset_ref_from_file(package, file)
        if ref is not None:
            refs.add(ref)
    return sorted(refs)


def scan_mod_assets(package_dir: str | Path) -> tuple[list[str], list[str]]:
    item_types: set[str] = set()
    blueprints: set[str] = set()
    for ref in _iter_package_refs(package_dir):
        if not re.fullmatch(r"/Game/Mods/[A-Za-z0-9.]+/.+", ref):
            continue
        leaf = ref.rsplit("/", 1)[-1]
        if leaf.endswith("_IT"):
            item_types.add(ref)
        elif leaf.endswith("_BP"):
            blueprints.add(ref)
    return sorted(item_types), sorted(blueprints)


def asset_kind(ref: str) -> str:
    leaf = ref.rsplit("/", 1)[-1]
    if leaf.endswith("_IT"):
        return "Item"
    if leaf.endswith("_BP"):
        return "Blueprint"
    return "Asset"


def asset_base(ref: str) -> str:
    leaf = ref.rsplit("/", 1)[-1]
    for suffix in ("_IT", "_BP"):
        if leaf.endswith(suffix):
            return leaf[: -len(suffix)]
    return leaf


def list_mod_parts(package_dir: str | Path) -> dict[str, list[tuple[str, str]]]:
    parts: dict[str, list[tuple[str, str]]] = {}
    for ref in _iter_package_refs(package_dir):
        parts.setdefault(asset_base(ref), []).append((ref, asset_kind(ref)))
    return {base: sorted(entries) for base, entries in sorted(parts.items())}


def index_game_assets(root: str | Path | None = None) -> list[str]:
    extracted = get_extracted_game_path(root)
    if not extracted.is_dir():
        return []
    found: set[str] = set()
    for file in sorted(extracted.rglob("*.uasset")):
        if file.is_symlink() or not file.is_file():
            continue
        try:
            found.add(file.resolve().relative_to(extracted).as_posix())
        except (ValueError, OSError):
            continue
    return sorted(found)


def override_asset_from_game(workspace_path: str | Path, game_rel: str | Path,
                             root: str | Path | None = None,
                             mirror: bool = False) -> list[str]:
    workspace = _resolve_workspace(workspace_path, root)
    metafile = read_mod_metafile(workspace, root)
    package_name = metafile.get("package_folder")
    if not package_name:
        raise FileNotFoundError(f"No package folder found in workspace: {workspace}")
    package = workspace / package_name
    if not package.is_dir():
        raise FileNotFoundError(f"Package folder not found: {package}")
    extracted = get_extracted_game_path(root)
    src = (extracted / Path(game_rel)).resolve()
    try:
        src.relative_to(extracted)
    except (ValueError, OSError) as exc:
        raise ValueError(f"Game asset is outside the extracted game files: {game_rel}") from exc
    if src.is_symlink() or not src.is_file() or src.suffix.lower() != ".uasset":
        raise FileNotFoundError(f"Game asset not found: {game_rel}")
    rel_parts = src.relative_to(extracted).parts
    if mirror and len(rel_parts) >= 3 and rel_parts[0] == "Astro" and rel_parts[1] == "Content":
        dest_dir = package / Path(*rel_parts[:-1])
    elif mirror and rel_parts and rel_parts[0] == "Game":
        dest_dir = package / "Astro" / "Content" / Path(*rel_parts[1:-1])
    elif mirror:
        dest_dir = package / "Astro" / "Content" / Path(*rel_parts[:-1])
    elif rel_parts and rel_parts[0] == "Game":
        dest_dir = package / "Game" / "Mods" / metafile.get("mod_name") / Path(*rel_parts[1:-1])
    else:
        dest_dir = package / "Game" / "Mods" / metafile.get("mod_name") / Path(*rel_parts[:-1])
    dest_dir.mkdir(parents=True, exist_ok=True)
    for sibling in src.parent.glob(src.stem + ".*"):
        if sibling.is_symlink() or not sibling.is_file():
            continue
        shutil.copy2(sibling, dest_dir / sibling.name)
    dest_uasset = dest_dir / (src.stem + ".uasset")
    ref = _asset_ref_from_file(package, dest_uasset)
    return [ref] if ref else []


def build_integrator_entries(item_types: Sequence[str],
                             blueprints: Sequence[str]) -> dict:
    entries: dict = {}
    clean_it = sorted({ref for ref in item_types if isinstance(ref, str) and ref.startswith("/Game/")})
    if clean_it:
        entries[MASTER_ITEM_LIST] = {"ItemTypes": clean_it}
    small: list[str] = []
    medium: list[str] = []
    for ref in sorted({ref for ref in blueprints if isinstance(ref, str) and ref.startswith("/Game/")}):
        leaf = ref.rsplit("/", 1)[-1]
        match = re.search(r"_T(\d+)(?:_|$)", leaf)
        tier = int(match.group(1)) if match else 1
        (medium if tier >= 3 else small).append(ref)
    if small:
        entries[PRINTER_T1_SMALL] = {"PrinterComponent.Blueprints": small}
    if medium:
        entries[PRINTER_T2_MEDIUM] = {"PrinterComponent.Blueprints": medium}
    return entries


def rebuild_integrator(workspace_path: str | Path,
                       root: str | Path | None = None) -> dict:
    workspace = _resolve_workspace(workspace_path, root)
    metafile = read_mod_metafile(workspace, root)
    package_name = metafile.get("package_folder")
    if not package_name:
        raise FileNotFoundError(f"No package folder found in workspace: {workspace}")
    package = workspace / package_name
    if not package.is_dir():
        raise FileNotFoundError(f"Package folder not found: {package}")
    item_types, blueprints = scan_mod_assets(package)
    entries = build_integrator_entries(item_types, blueprints)

    metadata_path = package / "metadata.json"
    metadata: dict = {}
    if metadata_path.is_file():
        try:
            metadata = json.loads(metadata_path.read_text(encoding="utf-8-sig"))
        except (OSError, json.JSONDecodeError) as exc:
            raise ValueError(f"Could not read mod metadata: {metadata_path}") from exc
        if not isinstance(metadata, dict):
            raise ValueError(f"Mod metadata must contain a JSON object: {metadata_path}")
    metadata.setdefault("sync", "serverclient")
    metadata.pop("astro_build", None)
    integrator = metadata.get("integrator")
    if not isinstance(integrator, dict):
        integrator = {}
    item_entries = integrator.get("item_list_entries")
    if not isinstance(item_entries, dict):
        item_entries = {}
    for target in _MANAGED_INTEGRATOR_TARGETS:
        item_entries.pop(target, None)
    item_entries.update(entries)
    integrator["item_list_entries"] = item_entries
    metadata["integrator"] = integrator
    metadata.update({
        "schema_version": 2,
        "name": metafile.get("mod_name"),
        "mod_id": metafile.get("mod_name"),
        "version": metafile.get("version"),
    })
    _write_json(metadata_path, metadata)
    return integrator


TRADE_VALUE_TABLE_LEAF = "ItemTradeValueTable"


def _read_uasset_tables(uasset_path: str | Path) -> tuple[list[str], list[tuple[int, int, int]]]:
    import struct
    raw = Path(uasset_path).expanduser().resolve().read_bytes()
    if len(raw) < 72 or struct.unpack_from("<I", raw, 0)[0] != 0x9E2A83C1:
        raise ValueError(f"Not a UE package file: {uasset_path}")

    def ri(off: int) -> int:
        return struct.unpack_from("<i", raw, off)[0]

    name_count, name_off = ri(41), ri(45)
    imp_count, imp_off = ri(65), ri(69)
    if not (0 < name_count < 100000 and 0 < name_off < len(raw)):
        raise ValueError(f"Could not read name table: {uasset_path}")
    names: list[str] = []
    o = name_off
    for _ in range(name_count):
        n = struct.unpack_from("<i", raw, o)[0]
        o += 4
        if n == 0:
            names.append("")
            continue
        if n < 0 or o + abs(n) > len(raw):
            raise ValueError(f"Corrupt name table: {uasset_path}")
        names.append(raw[o:o + abs(n)].decode("ascii", "replace").rstrip("\x00"))
        o += abs(n) + 4
    imports: list[tuple[int, int, int]] = []
    o = imp_off
    for _ in range(imp_count):
        if o + 28 > len(raw):
            raise ValueError(f"Corrupt import table: {uasset_path}")
        cname = struct.unpack_from("<i", raw, o + 8)[0]
        oname = struct.unpack_from("<i", raw, o + 20)[0]
        outer = struct.unpack_from("<i", raw, o + 16)[0]
        imports.append((cname, oname, outer))
        o += 28
    return names, imports


def _import_game_path(names: list[str], imports: list[tuple[int, int, int]], ref: int) -> str | None:
    seen: set[int] = set()
    while ref < 0 and -ref - 1 < len(imports) and ref not in seen:
        seen.add(ref)
        _, oname, outer = imports[-ref - 1]
        name = names[oname] if 0 <= oname < len(names) else ""
        if name.startswith("/Game/"):
            return name
        if outer == 0:
            return name or None
        ref = outer
    return None


def _import_display_name(names: list[str], imports: list[tuple[int, int, int]], ref: int) -> str:
    path = _import_game_path(names, imports, ref)
    if path:
        return pretty_item_name(path.rsplit("/", 1)[-1])
    if ref < 0 and -ref - 1 < len(imports):
        _, oname, _ = imports[-ref - 1]
        if 0 <= oname < len(names) and names[oname]:
            return pretty_item_name(names[oname])
    return f"ref {ref}"


def pretty_item_name(leaf: str) -> str:
    text = leaf.strip()
    if text in ITEM_NAME_OVERRIDES:
        return ITEM_NAME_OVERRIDES[text]
    text = re.sub(r"^(ItemType)[_ ]?", "", text)
    text = re.sub(r"[_\s]+IT$", "", text)
    text = text.replace("_", " ")
    text = re.sub(r"(?<=[a-z0-9])(?=[A-Z])", " ", text)
    text = re.sub(r"\s+", " ", text).strip()
    return ITEM_NAME_OVERRIDES.get(text, text) or leaf


ITEM_NAME_OVERRIDES = {
    "Nano Carbon Alloy": "Nanocarbon Alloy",
    "NanoCarbonAlloy": "Nanocarbon Alloy",
    "RTG_T1_IT": "RTG",
    "Object_Ball_Beach_LargeB_IT": "Beach Ball",
    "ItemType_Seed_SuperRose": "Hybrid Rose Seed",
    "ItemType_Firework_Rocket_Base_Red": "Red Firework",
    "ItemType_Firework_Rocket_Base_Orange": "Orange Firework",
    "ItemType_Firework_Rocket_Base_Yellow": "Yellow Firework",
    "ItemType_Firework_Rocket_Base_Green": "Green Firework",
    "ItemType_Firework_Rocket_Base_Blue": "Blue Firework",
    "ItemType_Firework_Rocket_Base_Teal": "Teal Firework",
    "ItemType_Firework_Rocket_Base_Violet": "Violet Firework",
    "Repackager_T1": "Packager",
    "ConsumableJumpjet_IT": "Solid-Fuel Jumpjet",
    "Fuel": "Hydrazine",
    "SmelterSmall": "Portable Smelting Furnace",
    "GravitySphere_Large_IT": "Gravity Globe",
}


def read_trade_values(uasset_path: str | Path) -> list[dict]:
    sections = read_trade_sections(uasset_path)
    if not sections:
        raise ValueError(f"No trade value map found in: {Path(uasset_path).name}")
    return sections[-1]["rows"]


def read_trade_sections(uasset_path: str | Path) -> list[dict]:
    import struct
    asset = Path(uasset_path).expanduser().resolve()
    uexp_path = asset.with_suffix(".uexp")
    if asset.suffix.lower() != ".uasset" or not uexp_path.is_file():
        raise ValueError(f"Trade table needs its .uasset + .uexp pair: {asset}")
    names, imports = _read_uasset_tables(asset)
    ux = uexp_path.read_bytes()
    n = len(ux) // 4
    ints = struct.unpack("<%di" % n, ux[:n * 4])
    flts = struct.unpack("<%df" % n, ux[:n * 4])

    def sane(v: float) -> bool:
        return v == v and 0 <= v < 1000000 and (v == 0 or v >= 1e-6)

    sections: list[dict] = []
    cursor = 0
    while cursor <= len(ux) - 8:
        count = struct.unpack_from("<i", ux, cursor)[0]
        if 0 <= count <= 500 and cursor + 4 + count * 8 <= len(ux):
            rows = []
            ok = True
            for j in range(count):
                key = struct.unpack_from("<i", ux, cursor + 4 + j * 8)[0]
                val = struct.unpack_from("<f", ux, cursor + 8 + j * 8)[0]
                if not -len(imports) <= key <= 1 or not sane(val):
                    ok = False
                    break
                rows.append((key, val, cursor + 8 + j * 8))
            if not ok:
                cursor += 1
                continue
            pairs_start = cursor + 4
            size_off = pairs_start - 33
            value_off = pairs_start - 8
            key_off = pairs_start - 53
            top_off = pairs_start - 57
            if size_off < 0 or key_off < 0:
                cursor += 1
                continue
            if struct.unpack_from("<i", ux, size_off)[0] != 8 + count * 8:
                cursor += 1
                continue
            key_ref = struct.unpack_from("<i", ux, key_off)[0]
            if not -len(imports) <= key_ref <= 1:
                cursor += 1
                continue
            decoded = []
            for key, val, offset in rows:
                leaf = None
                path = _import_game_path(names, imports, key)
                if path and path.startswith("/Game/"):
                    leaf = path.rsplit("/", 1)[-1]
                elif -len(imports) <= key <= 1 and key < 0:
                    _, oname, _ = imports[-key - 1]
                    if 0 <= oname < len(names) and names[oname]:
                        leaf = names[oname]
                decoded.append({
                    "display": _import_display_name(names, imports, key),
                    "leaf": leaf,
                    "ref": key,
                    "value": val,
                    "offset": offset,
                })
            sections.append({"offset": cursor, "count": count, "rows": decoded,
                             "key_ref": key_ref, "key_offset": key_off,
                             "value_offset": value_off, "size_offset": size_off,
                             "top_offset": top_off, "pairs_end": pairs_start + count * 8,
                             "label": trade_section_label(names, imports, key_ref)})
            cursor += 4 + count * 8
            continue
        cursor += 1
    if not sections:
        raise ValueError(f"No trade value map found in: {asset.name}")
    return sections


def describe_ref(uasset_path: str | Path, ref: int) -> str:
    asset = Path(uasset_path).expanduser().resolve()
    names, imports = _read_uasset_tables(asset)
    if -len(imports) <= ref <= 1 and ref < 0:
        _, oname, _ = imports[-ref - 1]
        if 0 <= oname < len(names) and names[oname]:
            text = names[oname]
            if text.endswith("_C"):
                text = text[:-2]
            return pretty_item_name(text)
    return f"ref {ref}"


def trade_section_label(names: list[str], imports: list[tuple[int, int, int]], key_ref: int) -> str:
    if -len(imports) <= key_ref <= 1 and key_ref < 0:
        _, oname, _ = imports[-key_ref - 1]
        if 0 <= oname < len(names) and names[oname]:
            text = names[oname]
            if text.endswith("_C"):
                text = text[:-2]
            for keyword, label in (("Scrap", "Scrap"), ("Astronium", "Astronium"),
                                   ("FaultFinder", "Fault Finder")):
                if keyword.lower() in text.lower():
                    return label
            return pretty_item_name(text)
    return "Section"


def _bump_trade_outer_size(raw: bytearray, delta: int) -> None:
    """Update the top-level trade-map size at .uexp offset 16.

    Verified against working OrbitalMadness pak: game base 535,
    +1 row = 543. Manual edits must keep this in sync or the game
    silently falls back to vanilla values.
    """
    import struct
    if len(raw) < 20:
        raise ValueError("Trade .uexp too small, refusing to modify.")
    size = struct.unpack_from("<i", raw, 16)[0]
    if not 0 < size < 100000:
        raise ValueError("Unexpected outer trade size, refusing to modify.")
    struct.pack_into("<i", raw, 16, size + delta)


def _bump_trade_uasset(asset_path: str | Path, delta: int) -> None:
    """Update ItemTradeValueTable .uasset size fields after .uexp size change.

    Byte-verified against working OrbitalMadness pak (game base vs +1 row):
    two little-endian i32 fields, at offsets 169 and 11770, each +8 per
    added row (588 -> 596 is the exact value in the crash log when stale).
    Only valid for edits that reuse existing imports/names (no table growth),
    which is all AOY trade-row edits.
    """
    import struct
    asset = Path(asset_path).expanduser().resolve()
    raw = bytearray(asset.read_bytes())
    if len(raw) < 11774:
        raise ValueError("Unexpected trade .uasset size, refusing to modify.")
    for off in (169, 11770):
        size = struct.unpack_from("<i", raw, off)[0]
        if not 0 < size < 100000:
            raise ValueError("Unexpected trade .uasset field, refusing to modify.")
        struct.pack_into("<i", raw, off, size + delta)
    asset.write_bytes(bytes(raw))


def _resolve_item_ref(names: list[str], imports: list[tuple[int, int, int]], item: str | int) -> int:
    if isinstance(item, bool):
        raise ValueError(f"Unknown item: {item!r}")
    if isinstance(item, int):
        if -len(imports) <= item <= 1 and item != 0:
            return item
        raise ValueError(f"Unknown item reference: {item!r}")
    for index, (_, oname, _) in enumerate(imports):
        if 0 <= oname < len(names) and names[oname] == item:
            return -index - 1
    raise ValueError(f"Item is not referenced by this file: {item!r}")


def add_trade_row(uasset_path: str | Path, section_index: int,
                  item: str | int, value: float) -> list[dict]:
    import struct
    asset = Path(uasset_path).expanduser().resolve()
    uexp_path = asset.with_suffix(".uexp")
    if asset.suffix.lower() != ".uasset" or not uexp_path.is_file():
        raise ValueError(f"Trade table needs its .uasset + .uexp pair: {asset}")
    names, imports = _read_uasset_tables(asset)
    sections = read_trade_sections(asset)
    if not 0 <= section_index < len(sections):
        raise ValueError(f"No such trade section: {section_index}")
    section = sections[section_index]
    ref = _resolve_item_ref(names, imports, item)
    if not isinstance(value, (int, float)) or not 0 <= float(value) <= 1000000:
        raise ValueError(f"Bad trade value: {value!r}")
    if any(row["ref"] == ref for row in section["rows"]):
        raise ValueError("That item is already in this section.")
    raw = bytearray(uexp_path.read_bytes())
    insert_at = section["pairs_end"]
    raw[insert_at:insert_at] = struct.pack("<i", ref) + struct.pack("<f", float(value))
    struct.pack_into("<i", raw, section["offset"], section["count"] + 1)
    struct.pack_into("<i", raw, section["size_offset"],
                     struct.unpack_from("<i", raw, section["size_offset"])[0] + 8)
    _bump_trade_outer_size(raw, 8)
    uexp_path.write_bytes(bytes(raw))
    _bump_trade_uasset(asset, 8)
    before = {(row["ref"], row["value"]) for sec in sections for row in sec["rows"]}
    return _verify_trade_write(asset, [s["count"] for s in sections[:section_index]]
                               + [sections[section_index]["count"] + 1]
                               + [s["count"] for s in sections[section_index + 1:]],
                               before)


def add_trade_section(uasset_path: str | Path, key_item: str | int,
                      value: float = 0.0) -> list[dict]:
    import struct
    asset = Path(uasset_path).expanduser().resolve()
    uexp_path = asset.with_suffix(".uexp")
    if asset.suffix.lower() != ".uasset" or not uexp_path.is_file():
        raise ValueError(f"Trade table needs its .uasset + .uexp pair: {asset}")
    names, imports = _read_uasset_tables(asset)
    sections = read_trade_sections(asset)
    key_ref = _resolve_item_ref(names, imports, key_item)
    if any(sec["key_ref"] == key_ref for sec in sections):
        raise ValueError("That section already exists.")
    if not isinstance(value, (int, float)) or not 0 <= float(value) <= 1000000:
        raise ValueError(f"Bad trade value: {value!r}")
    template = sections[-1]
    lead = bytes(uexp_path.read_bytes()[template["key_offset"] + 4:template["value_offset"]])
    if len(lead) != 41:
        raise ValueError("Unexpected section layout, refusing to modify.")
    raw = bytearray(uexp_path.read_bytes())
    insert_at = template["pairs_end"]
    raw[insert_at:insert_at] = (
        struct.pack("<i", key_ref) + lead +
        struct.pack("<f", float(value)) + struct.pack("<i", 0)
    )
    struct.pack_into("<i", raw, insert_at + 4 + 16, 8)
    struct.pack_into("<i", raw, sections[0]["top_offset"], len(sections) + 1)
    _bump_trade_outer_size(raw, 4 + len(lead) + 8)
    uexp_path.write_bytes(bytes(raw))
    _bump_trade_uasset(asset, 4 + len(lead) + 8)
    before = {(row["ref"], row["value"]) for sec in sections for row in sec["rows"]}
    return _verify_trade_write(asset, [s["count"] for s in sections] + [0], before)


def remove_trade_row(uasset_path: str | Path, section_index: int,
                     item: str | int) -> list[dict]:
    import struct
    asset = Path(uasset_path).expanduser().resolve()
    uexp_path = asset.with_suffix(".uexp")
    if asset.suffix.lower() != ".uasset" or not uexp_path.is_file():
        raise ValueError(f"Trade table needs its .uasset + .uexp pair: {asset}")
    names, imports = _read_uasset_tables(asset)
    sections = read_trade_sections(asset)
    if not 0 <= section_index < len(sections):
        raise ValueError(f"No such trade section: {section_index}")
    section = sections[section_index]
    ref = _resolve_item_ref(names, imports, item)
    matches = [row for row in section["rows"] if row["ref"] == ref]
    if not matches:
        raise ValueError("That item is not in this section.")
    victim = matches[0]
    raw = bytearray(uexp_path.read_bytes())
    del raw[victim["offset"] - 4:victim["offset"] + 4]
    struct.pack_into("<i", raw, section["offset"], section["count"] - 1)
    struct.pack_into("<i", raw, section["size_offset"],
                     struct.unpack_from("<i", raw, section["size_offset"])[0] - 8)
    _bump_trade_outer_size(raw, -8)
    uexp_path.write_bytes(bytes(raw))
    _bump_trade_uasset(asset, -8)
    before = {(row["ref"], row["value"]) for sec in sections for row in sec["rows"]}
    before.discard((victim["ref"], victim["value"]))
    return _verify_trade_write(asset, [s["count"] - (1 if s is section else 0) for s in sections],
                               before)


def remove_trade_section(uasset_path: str | Path, section_index: int) -> list[dict]:
    import struct
    asset = Path(uasset_path).expanduser().resolve()
    uexp_path = asset.with_suffix(".uexp")
    if asset.suffix.lower() != ".uasset" or not uexp_path.is_file():
        raise ValueError(f"Trade table needs its .uasset + .uexp pair: {asset}")
    sections = read_trade_sections(asset)
    if not 0 <= section_index < len(sections):
        raise ValueError(f"No such trade section: {section_index}")
    if len(sections) <= 1:
        raise ValueError("Cannot remove the last remaining section.")
    victim = sections[section_index]
    start = victim["key_offset"]
    end = victim["pairs_end"]
    raw = bytearray(uexp_path.read_bytes())
    removed_len = end - start
    del raw[start:end]
    struct.pack_into("<i", raw, sections[0]["top_offset"], len(sections) - 1)
    _bump_trade_outer_size(raw, -removed_len)
    uexp_path.write_bytes(bytes(raw))
    _bump_trade_uasset(asset, -removed_len)
    before = {(row["ref"], row["value"]) for sec in sections for row in sec["rows"]}
    before -= {(row["ref"], row["value"]) for row in victim["rows"]}
    return _verify_trade_write(asset, [s["count"] for i, s in enumerate(sections) if i != section_index],
                               before)


def _verify_trade_write(asset: Path, expected_counts: list[int],
                        must_keep: set[tuple[int, float]] | None = None) -> list[dict]:
    check = read_trade_sections(asset)
    if [s["count"] for s in check] != expected_counts:
        raise ValueError("Write verification failed, file may be damaged.")
    if must_keep is not None:
        after = {(row["ref"], row["value"]) for sec in check for row in sec["rows"]}
        if not must_keep <= after:
            raise ValueError("Write verification failed, file may be damaged.")
    return check


def write_trade_values(uasset_path: str | Path, changes: dict[int, float]) -> list[dict]:
    import struct
    asset = Path(uasset_path).expanduser().resolve()
    uexp_path = asset.with_suffix(".uexp")
    if asset.suffix.lower() != ".uasset" or not uexp_path.is_file():
        raise ValueError(f"Trade table needs its .uasset + .uexp pair: {asset}")
    before_rows = []
    for section in read_trade_sections(asset):
        before_rows.extend(section["rows"])
    known = {row["offset"] for row in before_rows}
    for offset, value in changes.items():
        if offset not in known:
            raise ValueError(f"Unknown trade value offset: {offset}")
        if not isinstance(value, (int, float)) or not 0 <= float(value) <= 1000000:
            raise ValueError(f"Bad trade value for offset {offset}: {value!r}")
    raw = bytearray(uexp_path.read_bytes())
    patched = dict(changes)
    for offset, value in patched.items():
        struct.pack_into("<f", raw, offset, float(value))
    uexp_path.write_bytes(bytes(raw))
    try:
        after_rows = []
        for section in read_trade_sections(asset):
            after_rows.extend(section["rows"])
    except ValueError as exc:
        raise ValueError(f"Write verification failed, file may be damaged: {exc}") from exc
    after = {row["offset"]: row["value"] for row in after_rows}
    if len(after_rows) != len(before_rows) or any(
            abs(after[row["offset"]] - float(patched.get(row["offset"], row["value"]))) > 1e-6
            for row in before_rows):
        raise ValueError("Write verification failed, file may be damaged.")
    return after_rows


def find_trade_value_table(root: str | Path | None = None) -> str | None:
    extracted = get_extracted_game_path(root)
    direct = extracted / "Astro" / "Content" / "Globals" / (TRADE_VALUE_TABLE_LEAF + ".uasset")
    try:
        if direct.is_file() and not direct.is_symlink():
            return direct.resolve().relative_to(extracted).as_posix()
    except (ValueError, OSError):
        pass
    for rel in index_game_assets(root):
        if Path(rel).stem == TRADE_VALUE_TABLE_LEAF:
            return rel
    return None


def find_unreal_cmd() -> Path | None:
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

    game_pak = find_game_pak()
    checks.append(Check("Astroneer game pak", game_pak is not None,
                        str(game_pak) if game_pak else "Astro-WindowsNoEditor.pak not found"))

    extracted_dir = local / "Astro-WindowsNoEditor"
    extracted_ready = extracted_dir.is_dir() and any(extracted_dir.iterdir())
    checks.append(Check("Extracted game files", extracted_ready,
                        str(extracted_dir) if extracted_ready else "Not extracted in local/Astro-WindowsNoEditor"))

    ue_cmd = find_unreal_cmd()
    checks.append(Check("Unreal Engine 4.27", ue_cmd is not None,
                        str(ue_cmd) if ue_cmd else "UE4Editor-Cmd.exe not found"))
    return checks


def _run(command: Sequence[str], timeout: int | None = None) -> subprocess.CompletedProcess[str]:
    return subprocess.run(list(command), capture_output=True, text=True,
                          encoding="utf-8", errors="replace", timeout=timeout, check=False)


def run_asset_generator(project_file: str | Path, dump_directory: str | Path,
                        ue_cmd: str | Path | None = None,
                        timeout: int | None = None) -> subprocess.CompletedProcess[str]:
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
             version: str = "V4",
             compression: str = "Zlib",
             timeout: int | None = None) -> subprocess.CompletedProcess[str]:
    import tempfile
    repak = _find_repak(repak_path)
    source = Path(input_directory).expanduser().resolve()
    destination = Path(output_pak).expanduser().resolve()
    if not repak or not repak.is_file():
        raise FileNotFoundError(f"repak executable not found: {repak or 'repak'}")
    if not source.is_dir():
        raise FileNotFoundError(f"Pak input directory not found: {source}")
    if destination.suffix.lower() != ".pak":
        raise ValueError("output_pak must have a .pak extension")
    destination.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="aoy-pack-") as tmp:
        clean = Path(tmp) / source.name
        shutil.copytree(source, clean, ignore=shutil.ignore_patterns("*.bak", "*.bak.*", "*~", "versions"),
                         symlinks=False)
        return _run([str(repak.resolve()), "pack", str(clean), str(destination),
                     "--version", version, "--compression", compression], timeout)


def unpack_pak(input_pak: str | Path, output_directory: str | Path,
               repak_path: str | Path | None = None,
               timeout: int | None = None) -> subprocess.CompletedProcess[str]:
    repak = _find_repak(repak_path)
    archive = Path(input_pak).expanduser().resolve()
    output = Path(output_directory).expanduser().resolve()
    if not repak or not repak.is_file():
        raise FileNotFoundError(f"repak executable not found: {repak or 'repak'}")
    if not archive.is_file():
        raise FileNotFoundError(f"Pak file not found: {archive}")
    output.mkdir(parents=True, exist_ok=True)
    return _run([str(repak.resolve()), "unpack", str(archive), "--output", str(output)], timeout)


def import_mod_from_pak(pak_path: str | Path, root: str | Path | None = None,
                        repak_path: str | Path | None = None,
                        timeout: int | None = None) -> Path:
    import tempfile
    archive = Path(pak_path).expanduser().resolve()
    if not archive.is_file() or archive.suffix.lower() != ".pak":
        raise ValueError(f"Select a .pak file: {archive}")
    match = re.fullmatch(r"([0-9]{1,3})-(.+)-([0-9]+\.[0-9]+\.[0-9]+)(?:_P)?", archive.stem)
    if match:
        priority_value = _validate_priority(match.group(1))
        mod_id = _validate_mod_id(match.group(2))
        version_value = _validate_mod_version(match.group(3))
    else:
        stem = archive.stem
        for suffix in ("_P", "-P"):
            if stem.endswith(suffix):
                stem = stem[: -len(suffix)]
                break
        mod_id = _validate_mod_id(stem)
        priority_value = 0
        version_value = "0.1.0"
    workspaces = _workspace_path(root)
    workspaces.mkdir(parents=True, exist_ok=True)
    workspace = workspaces / mod_id
    if workspace.exists():
        raise FileExistsError(f"A workspace named '{mod_id}' already exists.")
    tmpdir = Path(tempfile.mkdtemp(prefix="aoy-import-"))
    try:
        result = unpack_pak(archive, tmpdir, repak_path, timeout)
        if result.returncode != 0:
            detail = format_process_result(result) or f"repak exited with code {result.returncode}"
            raise RuntimeError(detail)
        children = [item for item in tmpdir.iterdir()]
        if not children:
            raise ValueError(f"Nothing inside this .pak: {archive.name}")
        workspace.mkdir(exist_ok=False)
        package = workspace / _package_folder_name(priority_value, mod_id, version_value)
        package.mkdir()
        for item in children:
            shutil.move(str(item), str(package / item.name))
        metadata_path = package / "metadata.json"
        metadata: dict = {}
        if metadata_path.is_file():
            try:
                metadata = json.loads(metadata_path.read_text(encoding="utf-8-sig"))
            except (OSError, json.JSONDecodeError):
                metadata = {}
            if not isinstance(metadata, dict):
                metadata = {}
        metadata.update({
            "schema_version": 2,
            "name": mod_id,
            "mod_id": mod_id,
            "version": version_value,
        })
        _write_json(metadata_path, metadata)
        try:
            (workspace / SELECT_MARKER).touch(exist_ok=True)
        except OSError:
            pass
    except BaseException:
        if workspace.exists():
            shutil.rmtree(workspace, ignore_errors=True)
        raise
    finally:
        shutil.rmtree(tmpdir, ignore_errors=True)
    return workspace.resolve()


def format_process_result(result: subprocess.CompletedProcess[str]) -> str:
    return "\n".join(part.strip() for part in (result.stdout, result.stderr) if part and part.strip())


if __name__ == "__main__":
    print("This module provides AOY backend functions. Start interface.py to use AOY.")
