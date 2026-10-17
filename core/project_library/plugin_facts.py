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
from core.project_library import console_keys, images
from core.project_library.cards import count_strings
from utils.constants import APP_VERSION, plugins_root
from utils.logging_utils import log_warning
from utils.plugin_import import PLUGIN_IMPORT_LOCK

LoadRules = Callable[[str], Any]
Cancelled = Callable[[], bool]
PLUGIN_MISSING = "plugin_missing"  # the count error of a project whose game plugin is not installed


class PluginMissing(Exception):
    """The project names a game plugin that is not installed. Not an error of the project; shown as a flag."""


def default_load_rules(plugin_name: str) -> Any:
    """The plugin's ``GameRules`` built without a main window.

    Imports the plugin on the calling thread, under ``PLUGIN_IMPORT_LOCK``, so the main window's load of the same
    plugin (which drops and re-imports its modules) cannot run in the middle.
    """
    with PLUGIN_IMPORT_LOCK:
        module = importlib.import_module(f"plugins.{plugin_name}.rules")
        return module.GameRules(None)


def roles_of(rules: Any) -> List[Dict[str, str]]:
    """The source roles of a plugin, ``[{"id", "label"}]``. A plugin that declares none gets one ``base`` role."""
    roles = []
    for role in rules.get_source_roles() or []:
        role_id = str(role.get("id") or "").strip()
        if role_id and role_id not in {r["id"] for r in roles}:
            roles.append({"id": role_id, "label": str(role.get("label") or role_id)})
    return roles or [{"id": "base", "label": "Base game"}]


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
    """For each path: ``{"path", "role", "platform", "key", "key_ready"}``.

    ``role`` is "" when the plugin does not recognise the file. A role the plugin did not declare is dropped, so the
    wizard never shows a role it cannot save. ``key`` is the console whose key file the file needs ("" when none);
    ``key_ready`` is True when Picoripi already has that console's key file. ``libraries`` lists the other stored
    paths the unpack of this file loads (an identity's ``"libraries"``, e.g. ``"oodle"``), only those the plugin lists
    in ``unpack_key_consoles``.
    """
    known = {role["id"] for role in roles_of(rules)}
    allowed = _unpack_consoles(rules)
    result: List[Dict[str, Any]] = []
    for path in paths:
        if is_cancelled():
            break
        role, platform, libraries = "", "", []
        try:
            identity = rules.identify_source(path)
        except Exception as exc:  # a plugin's bug must not stop the wizard; the user picks the role
            log_warning(f"identify_source failed for {path}: {exc}")
            identity = None
        if isinstance(identity, dict) and str(identity.get("role") or "") in known:
            role = str(identity["role"])
            platform = str(identity.get("platform") or "")
            libraries = [str(item) for item in identity.get("libraries") or [] if str(item) in allowed]
        console = _key_console(rules, path)
        result.append({"path": path, "role": role, "platform": platform, "key": console,
                       "key_ready": bool(console) and console_keys.path_for(console) is not None,
                       "libraries": libraries})
    return result


def _unpack_consoles(rules: Any) -> List[str]:
    """The stored paths this game's unpack reads (``unpack_key_consoles``); a plugin's bug gives none."""
    try:
        return [str(item) for item in rules.unpack_key_consoles()]
    except Exception as exc:  # a plugin's bug must not stop the wizard; no key is asked for
        log_warning(f"unpack_key_consoles failed: {exc}")
        return []


def _key_console(rules: Any, path: str) -> str:
    """The console whose key file an encrypted file needs, when the game's unpack reads that console; else ""."""
    console = images.needs_key(path) or ""
    return console if console and console in _unpack_consoles(rules) else ""


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
