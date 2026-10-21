"""What the Project Manager asks a game plugin: source roles, platforms, build targets and string counts.

Everything here runs on a worker thread. A plugin is built with ``GameRules(None)``: no main window, no widgets.
Callers pass ``load_rules`` so tests can supply an explicit fake; the default imports the real plugin.
"""
from __future__ import annotations

import hashlib
import importlib
import json
import os
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Sequence

from core import formats
from core.i18n import tr
from core.project_library import console_keys, images
from core.project_library.cards import count_strings
from utils.constants import APP_VERSION, plugins_root
from utils.logging_utils import log_warning
from utils.plugin_import import PLUGIN_IMPORT_LOCK

LoadRules = Callable[..., Any]  # (plugin name, optional main window) -> GameRules
Cancelled = Callable[[], bool]
PLUGIN_MISSING = "plugin_missing"  # the count error of a project whose game plugin is not installed


class PluginMissing(Exception):
    """The project names a game plugin that is not installed. Not an error of the project; shown as a flag."""


def default_load_rules(plugin_name: str, main_window: Any = None) -> Any:
    """The plugin's ``GameRules`` built without a main window, unless ``main_window`` is given.

    Imports the plugin on the calling thread, under ``PLUGIN_IMPORT_LOCK``, so the main window's load of the same
    plugin (which drops and re-imports its modules) cannot run in the middle. A headless caller gives a holder with
    the attributes its hooks read (the seed hooks read ``project_manager``).
    """
    with PLUGIN_IMPORT_LOCK:
        module = importlib.import_module(f"plugins.{plugin_name}.rules")
        return module.GameRules(main_window)


GENERIC_ROLES = (("base", "Base game"), ("update", "Update"), ("dlc", "DLC"))
MULTIPLE_ROLES = frozenset({"dlc"})   # roles that many files may share; each other role belongs to one file
N3DS_TITLE_KIND = {"00040000": "base", "0004000E": "update", "0004008C": "dlc"}   # 3DS title ID high word
KIND_WIIU = "wiiu"                    # a Wii U disc image (.wux): recognised for its platform, never read
WUX_MAGIC = b"WUX0"
STATUS_OK, STATUS_FOLDER, STATUS_UNREADABLE, STATUS_UNRECOGNISED = "ok", "folder", "unreadable", "unrecognised"


def roles_of(rules: Any) -> List[Dict[str, Any]]:
    """The source roles of a plugin, ``[{"id", "label", "multiple"}]``.

    The plugin's own roles come first. Base game, Update and DLC are always offered, so a user can add every file of
    a game at once; their names are not translated. ``multiple`` is True for a role that many files may share (DLC).
    """
    roles: List[Dict[str, Any]] = []
    for role in rules.get_source_roles() or []:
        role_id = str(role.get("id") or "").strip()
        if role_id and role_id not in {r["id"] for r in roles}:
            roles.append({"id": role_id, "label": str(role.get("label") or role_id)})
    for role_id, label in GENERIC_ROLES:
        if role_id not in {r["id"] for r in roles}:
            roles.append({"id": role_id, "label": label})
    generic_labels = dict(GENERIC_ROLES)   # these names stay English in every interface language
    for role in roles:
        role["label"] = generic_labels.get(role["id"], role["label"])
    for role in roles:
        role["multiple"] = role["id"] in MULTIPLE_ROLES
    return roles


def role_key(role: str, index: int) -> str:
    """The ``sources`` key of the ``index``-th file (from 1) of a role: ``dlc``, then ``dlc_2``, ``dlc_3``..."""
    return role if index <= 1 else f"{role}_{index}"


def paths_of_role(sources: Dict[str, str], role: str) -> List[str]:
    """Every path of ``role`` in a ``sources`` map, in order: ``dlc``, ``dlc_2``, ``dlc_3``..."""
    found = [(1, path) for key, path in sources.items() if key == role]
    for key, path in sources.items():
        prefix, _sep, number = key.rpartition("_")
        if prefix == role and number.isdigit():
            found.append((int(number), path))
    return [path for _index, path in sorted(found)]


def describe_file(path: str) -> Optional[Dict[str, Any]]:
    """The header fields of a game image (``images.identify``), a Wii U ``.wux`` (platform only), or None."""
    found = images.identify(path)
    if found is not None:
        return found
    try:
        with open(path, "rb") as stream:
            magic = stream.read(len(WUX_MAGIC))
    except OSError:
        return None
    return {"kind": KIND_WIIU, "game_id": "", "encrypted": True} if magic == WUX_MAGIC else None


def generic_identity(found: Optional[Dict[str, Any]]) -> Dict[str, str]:
    """``{"role", "platform"}`` read from an image's own header, for a file the plugin does not recognise.

    The role comes from the title ID: the low bits of a Switch title, the high word of a 3DS title. Any other image
    is a base game. Both are "" for a file that is not an image Picoripi recognises.
    """
    if not found:
        return {"role": "", "platform": ""}
    kind = str(found.get("kind") or "")
    role = str(found.get("title_kind") or "")
    if kind == images.KIND_3DS:
        role = N3DS_TITLE_KIND.get(str(found.get("title_id") or "")[:8].upper(), "base")
    return {"role": role or "base", "platform": kind}


PLATFORM_LABELS = {   # every platform id a plugin may name (config.json "platforms"), with its English name
    "gb": "Game Boy", "gbc": "Game Boy Color", "gba": "Game Boy Advance", "nds": "Nintendo DS", "3ds": "Nintendo 3DS",
    "snes": "Super Nintendo", "n64": "Nintendo 64", "gc": "GameCube", "wii": "Wii", "wiiu": "Wii U",
    "switch": "Nintendo Switch", "psx": "PlayStation", "ps2": "PlayStation 2", "psp": "PSP", "saturn": "Sega Saturn",
    "gdrom": "Dreamcast", "pc": "PC", "android": "Android", "other": "Other",
}
KNOWN_PLATFORMS = tuple(PLATFORM_LABELS)


def platform_label(platform_id: str) -> str:
    """The readable name of a platform id (``switch`` -> Nintendo Switch); an unknown id is shown as it is."""
    return tr(PLATFORM_LABELS.get(platform_id, platform_id))
# A file inside a folder that marks the platform of an unpacked game; sys/main.dol is GameCube or Wii (sys/boot.bin).
FOLDER_MARKERS = (("meta/meta.xml", KIND_WIIU), ("code/app.xml", KIND_WIIU), ("exheader.bin", images.KIND_3DS),
                  ("exefs/code.bin", images.KIND_3DS), ("exefs/main.npdm", images.KIND_SWITCH),
                  ("exefs/main", images.KIND_SWITCH), ("arm9.bin", images.KIND_NDS), ("sys/main.dol", ""))


def folder_platform(folder: str) -> str:
    """The platform of an unpacked game folder from the files it holds (the folder or one level below), or ""."""
    root = Path(folder)
    try:
        candidates = [root] + sorted(child for child in root.iterdir() if child.is_dir())
    except OSError:
        return ""
    for candidate in candidates:
        for marker, platform in FOLDER_MARKERS:
            if not (candidate / marker).is_file():
                continue
            if platform:
                return platform
            try:   # a Dolphin-style tree: the game id in sys/boot.bin starts with G or D on GameCube, R or S on Wii
                first = (candidate / "sys" / "boot.bin").read_bytes()[:1]
            except OSError:
                return ""
            return images.KIND_WII if first in (b"R", b"S") else images.KIND_GC
    return ""


def offered_platforms(rules: Any) -> List[Dict[str, str]]:
    """The platforms the wizard offers: the plugin's own, or every platform Picoripi knows when it declares none."""
    return platforms_of(rules) or [{"id": kind, "label": platform_label(kind)} for kind in KNOWN_PLATFORMS]


def platforms_of(rules: Any) -> List[Dict[str, str]]:
    """The platforms of a plugin, ``[{"id", "label"}]``."""
    platforms = []
    for platform in rules.get_platforms() or []:
        platform_id = str(platform.get("id") or "").strip()
        if platform_id:
            platforms.append({"id": platform_id, "label": str(platform.get("label") or platform_id)})
    return platforms


def targets_of(rules: Any) -> List[Dict[str, Any]]:
    """The build targets of a plugin: ``id``, ``label``, ``platforms`` (empty: all) and ``kind``."""
    targets = []
    for target in rules.get_build_targets() or []:
        target_id = str(target.get("id") or "").strip()
        if not target_id:
            continue
        targets.append({
            "id": target_id,
            "label": str(target.get("label") or target_id),
            "platforms": [str(p) for p in target.get("platforms") or []],
            "kind": str(target.get("kind") or "files"),
        })
    return targets


def identify_sources(rules: Any, paths: Sequence[str], is_cancelled: Cancelled = lambda: False) -> List[Dict[str, Any]]:
    """For each path: ``{"path", "role", "platform", "status", "title_id", "key", "key_ready", "libraries", ...}``.

    The plugin's ``identify_source`` answers first. A file it does not recognise gets the role and platform its own
    header gives (``generic_identity``). A role the plugin did not declare is dropped. ``status``: ``ok``; ``folder``
    (a folder, used as it is); ``unreadable`` (a game image this game cannot unpack: add the unpacked folder);
    ``unrecognised`` (an image the plugin's unpack does not recognise). ``key`` is the console whose key file the file
    needs ("" when none); ``key_ready`` is True when Picoripi already has that key file. ``libraries`` lists the other
    stored paths the unpack of this file loads (an identity's ``"libraries"``, e.g. ``"oodle"``), only those the
    plugin lists in ``unpack_key_consoles``.
    """
    known = {role["id"] for role in roles_of(rules)}
    declared = [platform["id"] for platform in platforms_of(rules)]
    allowed = _unpack_consoles(rules)
    unpacks = _has_unpack(rules) or bool(allowed)    # a game that reads console keys unpacks images
    result: List[Dict[str, Any]] = []
    for path in paths:
        if is_cancelled():
            break
        libraries: List[str] = []
        is_folder = os.path.isdir(path)
        found = None if is_folder else describe_file(path)
        try:
            identity = None if is_folder else rules.identify_source(path)
        except Exception as exc:  # a plugin's bug must not stop the wizard; the header or the user gives the role
            log_warning(f"identify_source failed for {path}: {exc}")
            identity = None
        if isinstance(identity, dict) and str(identity.get("role") or "") in known:
            role, platform = str(identity["role"]), str(identity.get("platform") or "")
            libraries = [str(item) for item in identity.get("libraries") or [] if str(item) in allowed]
            status = STATUS_OK
        else:
            generic = generic_identity(found)
            role = generic["role"] if generic["role"] in known else ""
            platform = generic["platform"]
            status = _status_of(found, is_folder, unpacks)
        if not platform and is_folder:
            platform = folder_platform(path)
        if not platform and len(declared) == 1:
            platform = declared[0]          # a game on one platform: every file of it is on that platform
        console = _key_console(found, allowed) if status in (STATUS_OK, STATUS_UNRECOGNISED) else ""
        result.append({"path": path, "role": role, "platform": platform, "status": status,
                       "title_id": str((found or {}).get("title_id") or (found or {}).get("game_id") or ""),
                       "key": console,
                       "key_ready": bool(console) and console_keys.path_for(console) is not None,
                       "libraries": libraries,
                       "libraries_ready": [item for item in libraries if console_keys.path_for(item) is not None]})
    return result


def _status_of(found: Optional[Dict[str, Any]], is_folder: bool, unpacks: bool) -> str:
    """The status of a file the plugin did not recognise (see ``identify_sources``)."""
    if is_folder:
        return STATUS_FOLDER
    kind = str((found or {}).get("kind") or "")
    if kind == KIND_WIIU or (kind in images.UNPACK_KINDS and not unpacks):
        return STATUS_UNREADABLE
    return STATUS_UNRECOGNISED if kind in images.UNPACK_KINDS else STATUS_OK


def _has_unpack(rules: Any) -> bool:
    """True when the plugin has its own ``unpack_sources``; without it a game image cannot become a source."""
    owner = next((cls for cls in type(rules).__mro__ if "unpack_sources" in vars(cls)), None)
    return owner is not None and owner.__name__ != "BaseGameRules"


def _unpack_consoles(rules: Any) -> List[str]:
    """The stored paths this game's unpack reads (``unpack_key_consoles``); a plugin's bug gives none."""
    try:
        return [str(item) for item in rules.unpack_key_consoles()]
    except Exception as exc:  # a plugin's bug must not stop the wizard; no key is asked for
        log_warning(f"unpack_key_consoles failed: {exc}")
        return []


def _key_console(found: Optional[Dict[str, Any]], allowed: Sequence[str]) -> str:
    """The console whose key file an encrypted image needs, when the game's unpack reads that console; else ""."""
    if not found or not found.get("encrypted") or found.get("kind") not in images.UNPACK_KINDS:
        return ""
    console = images.CONSOLE_OF_KIND.get(str(found["kind"]), "")
    return console if console in allowed else ""

def _root(base: Path, value: Any) -> Optional[Path]:
    if not value:
        return None
    path = Path(str(value))
    return path if path.is_absolute() else base / path


def _resolve(relative: str, roots: Sequence[Optional[Path]]) -> Optional[Path]:
    """The first existing file of ``relative`` under the roots (an absolute path is used as it is)."""
    if not relative:
        return None
    candidate = Path(relative)
    if candidate.is_absolute():
        return candidate if candidate.exists() else None
    for root in roots:
        if root is not None and (root / candidate).exists():
            return root / candidate
    return None


def _sub_block_index(names: Dict[str, str], count: int, internal_key: str) -> int:
    """Which parsed block a project block split from a file is (same rule as the project load worker)."""
    for index in range(count):
        if names.get(str(index), f"Block {index}") == internal_key:
            return index
    return -1


def _parse(rules: Any, path: Path, cache: Dict[Any, Any], translation: bool = False) -> Any:
    """``(blocks, names)`` of one file, parsed once per count and role. ``None`` when the file cannot be read.

    A file no format of the plugin claims (fonts, images, archives) is skipped, never read as text. The default
    ``UNKNOWN_IS_ERROR`` policy answers "unsupported" without opening the file. A translation file is parsed in the
    translation role (``formats.translation_parse``): one file read in place can be both, and gives different text.
    """
    key = (str(path), translation)
    if key not in cache:
        content, error = formats.read_file(rules, path)
        if error or content is None:
            cache[key] = None
        else:
            if translation:
                with formats.translation_parse(rules):
                    blocks, names = rules.load_data_from_json_obj(content)
            else:
                blocks, names = rules.load_data_from_json_obj(content)
            cache[key] = (blocks or [], names or {})
    return cache[key]


def _block_of(parsed: Any, internal_key: Optional[str]) -> Optional[List[str]]:
    if parsed is None:
        return None
    blocks, names = parsed
    if internal_key is None:
        flat: List[str] = []
        for block in blocks:
            flat.extend(block if isinstance(block, list) else [])
        return flat
    index = _sub_block_index(names, len(blocks), internal_key)
    if index < 0 or not isinstance(blocks[index], list):
        return None
    return blocks[index]


def count_project(project_file: str | os.PathLike, load_rules: LoadRules = default_load_rules,
                  is_cancelled: Cancelled = lambda: False) -> Optional[Dict[str, Any]]:
    """Count the lines of a project with its plugin's parser. Returns None when cancelled.

    Result: ``counts`` (lines, needs_translation, translated), ``targets`` (the plugin's build targets),
    ``skipped`` (blocks not counted: archive members, and blocks whose file or sub-block is missing) and
    ``missing_translations`` (blocks that name a translation file which does not exist yet).

    ponytail: archive members are skipped (the load worker opens archives; a count does not yet); a file that
    holds several project blocks is parsed once and the blocks share it. Upgrade: reuse the load worker's
    archive handling when counts must match the open view exactly.
    """
    path = Path(project_file)
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError("project file is not a JSON object")
    plugin_name = str(data.get("plugin_name") or "")
    try:
        rules = load_rules(plugin_name)
    except ModuleNotFoundError as exc:
        if exc.name and exc.name.startswith("plugins." + plugin_name):
            raise PluginMissing(plugin_name) from exc
        raise
    base = path.parent
    metadata = data.get("metadata") or {}
    source_roots = [_root(base, metadata.get("source_path")), base]
    translation_roots = [_root(base, metadata.get("translation_path")), base]

    totals = {"lines": 0, "needs_translation": 0, "translated": 0}
    groups: Dict[str, Dict[str, int]] = {}
    skipped = 0
    missing_translations = 0
    cache: Dict[Any, Any] = {}
    for block in data.get("blocks") or []:
        if is_cancelled():
            return None
        block_meta = block.get("metadata") or {}
        if block_meta.get("is_archive_member"):
            skipped += 1
            continue
        internal_key = block.get("internal_key") or None
        source = _resolve(str(block.get("source_file") or ""), source_roots)
        original = _block_of(_parse(rules, source, cache), internal_key) if source else None
        if original is None:
            skipped += 1
            continue
        translation = _resolve(str(block.get("translation_file") or ""), translation_roots)
        if translation is None and block.get("translation_file"):
            missing_translations += 1
        translated = _block_of(_parse(rules, translation, cache, translation=True), internal_key) if translation else None
        counts = count_strings([original], [translated or []], {})
        for key in totals:
            totals[key] += counts[key]
        group = _group_name(str(block.get("source_file") or ""))
        row = groups.setdefault(group, {"blocks": 0, "lines": 0})
        row["blocks"] += 1
        row["lines"] += counts["lines"]
    return {"counts": totals, "targets": targets_of(rules), "skipped": skipped, "groups": groups,
            "missing_translations": missing_translations}


def project_block_strings(project_file: str | os.PathLike, load_rules: LoadRules = default_load_rules,
                          is_cancelled: Cancelled = lambda: False) -> Optional[Dict[str, Any]]:
    """The strings of every block of a project, read with its plugin's parser. None when cancelled.

    Result: ``plugin`` (the plugin name) and ``blocks``: ``(source_file, internal_key, source strings, translation
    strings or None)`` per block whose source parses. The translation strings are read in the translation role, as
    ``count_project`` does; None when the block has no readable translation file. Archive members and unparsed blocks
    are left out. A list index is the editor's string index (the parser's own list, empty strings included). Used by
    the series term fill (D45), which must know what a project already translates before it writes anything.
    """
    path = Path(project_file)
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError("project file is not a JSON object")
    plugin_name = str(data.get("plugin_name") or "")
    rules = load_rules(plugin_name)
    base = path.parent
    metadata = data.get("metadata") or {}
    source_roots = [_root(base, metadata.get("source_path")), base]
    translation_roots = [_root(base, metadata.get("translation_path")), base]
    cache: Dict[Any, Any] = {}
    blocks = []
    for block in data.get("blocks") or []:
        if is_cancelled():
            return None
        if (block.get("metadata") or {}).get("is_archive_member"):
            continue
        internal_key = block.get("internal_key") or None
        source = _resolve(str(block.get("source_file") or ""), source_roots)
        original = _block_of(_parse(rules, source, cache), internal_key) if source else None
        if original is None:
            continue
        translation = _resolve(str(block.get("translation_file") or ""), translation_roots)
        translated = _block_of(_parse(rules, translation, cache, translation=True), internal_key) if translation else None
        blocks.append((str(block.get("source_file") or ""), internal_key or "", list(original), translated))
    return {"plugin": plugin_name, "blocks": blocks}


def _stat_part(path: Optional[Path]) -> Optional[List[int]]:
    """``[mtime_ns, size]`` of a file, or None when it is missing."""
    if path is None:
        return None
    try:
        stat = os.stat(path)
    except OSError:
        return None
    return [stat.st_mtime_ns, stat.st_size]


def _code_stamp(plugin_name: str, folder: Path) -> List[Any]:
    """``[path, [mtime_ns, size]]`` of each Python file of the plugin and of the shared plugin code (``common``).

    A parser lives in these files, so an edit or an update of them changes the stamp and the counts are redone.
    Only ``stat`` is called. The folders are small (a few dozen files each).
    """
    roots = [folder / "common"]
    if plugin_name:
        roots.insert(0, folder / plugin_name)
    stamps: List[Any] = []
    for root in roots:
        if root.is_dir():
            for module in sorted(root.rglob("*.py")):
                stamps.append([module.relative_to(folder).as_posix(), _stat_part(module)])
    return stamps


def input_signature(project_file: str | os.PathLike, plugins_folder: Optional[Path] = None) -> str:
    """A fingerprint of everything a count reads: the project file, the plugin's config, the plugin's Python files
    and the shared ``common`` plugin files, the Picoripi version, and for each block its source and translation file
    (the path that resolves, with its size and modification time).

    Equal fingerprints mean equal counts, so a cached count is reused only while this value is unchanged. Only
    ``stat`` is called; no file content is read. Folder modification times are not used: on NTFS they do not change
    when a file inside is edited. Raises ``OSError`` or ``ValueError`` when the project file cannot be read.

    The version covers the core parsers (``core/formats``), which are not in the plugin folders; a release changes it.
    """
    path = Path(project_file)
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError("project file is not a JSON object")
    plugin_name = str(data.get("plugin_name") or "")
    folder = plugins_folder if plugins_folder is not None else plugins_root()
    metadata = data.get("metadata") or {}
    base = path.parent
    source_roots = [_root(base, metadata.get("source_path")), base]
    translation_roots = [_root(base, metadata.get("translation_path")), base]
    parts: List[Any] = [["project", _stat_part(path)], ["plugin", plugin_name,
                                                         _stat_part(folder / plugin_name / "config.json")],
                        ["code", _code_stamp(plugin_name, folder)], ["version", APP_VERSION]]
    for block in data.get("blocks") or []:
        if (block.get("metadata") or {}).get("is_archive_member"):
            continue
        for kind, roots, relative in (("source", source_roots, block.get("source_file")),
                                      ("translation", translation_roots, block.get("translation_file"))):
            found = _resolve(str(relative or ""), roots)
            parts.append([kind, str(relative or ""), str(found) if found else "", _stat_part(found)])
    return hashlib.sha1(json.dumps(parts, ensure_ascii=False).encode("utf-8")).hexdigest()


def _group_name(source_file: str) -> str:
    """The folder a block's source file sits in, for the resource tree of a row. Top-level files share one group."""
    parts = source_file.replace("\\", "/").split("/")
    return parts[0] if len(parts) > 1 and parts[0] else "(top level)"
