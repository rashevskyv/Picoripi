"""What the Project Manager asks a game plugin: source roles, platforms, build targets and string counts.

Everything here runs on a worker thread. A plugin is built with ``GameRules(None)``: no main window, no widgets.
Callers pass ``load_rules`` so tests can supply an explicit fake; the default imports the real plugin.
"""
from __future__ import annotations

import importlib
import json
import os
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Sequence

from core import formats
from core.project_library.cards import count_strings
from utils.logging_utils import log_warning

LoadRules = Callable[[str], Any]
Cancelled = Callable[[], bool]


def default_load_rules(plugin_name: str) -> Any:
    """The plugin's ``GameRules`` built without a main window. Imports the plugin module on the calling thread."""
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
    """For each path: ``{"path", "role", "platform"}``. ``role`` is "" when the plugin does not recognise the file.

    A role the plugin did not declare is dropped, so the wizard never shows a role it cannot save.
    """
    known = {role["id"] for role in roles_of(rules)}
    result: List[Dict[str, Any]] = []
    for path in paths:
        if is_cancelled():
            break
        role, platform = "", ""
        try:
            identity = rules.identify_source(path)
        except Exception as exc:  # a plugin's bug must not stop the wizard; the user picks the role
            log_warning(f"identify_source failed for {path}: {exc}")
            identity = None
        if isinstance(identity, dict) and str(identity.get("role") or "") in known:
            role = str(identity["role"])
            platform = str(identity.get("platform") or "")
        result.append({"path": path, "role": role, "platform": platform})
    return result


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


def _parse(rules: Any, path: Path, cache: Dict[str, Any]) -> Any:
    """``(blocks, names)`` of one file, parsed once per count. ``None`` when the file cannot be read."""
    key = str(path)
    if key not in cache:
        content, error = formats.read_file(rules, path, unknown=formats.UNKNOWN_IS_TEXT)
        if error or content is None:
            cache[key] = None
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

    Result: ``counts`` (lines, needs_translation, translated), ``targets`` (the plugin's build targets) and
    ``skipped`` (blocks not counted: archive members, and blocks whose file or sub-block is missing).

    ponytail: archive members are skipped (the load worker opens archives; a count does not yet); a file that
    holds several project blocks is parsed once and the blocks share it. Upgrade: reuse the load worker's
    archive handling when counts must match the open view exactly.
    """
    path = Path(project_file)
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError("project file is not a JSON object")
    rules = load_rules(str(data.get("plugin_name") or ""))
    base = path.parent
    metadata = data.get("metadata") or {}
    source_roots = [_root(base, metadata.get("source_path")), base]
    translation_roots = [_root(base, metadata.get("translation_path")), base]

    totals = {"lines": 0, "needs_translation": 0, "translated": 0}
    skipped = 0
    cache: Dict[str, Any] = {}
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
        translated = _block_of(_parse(rules, translation, cache), internal_key) if translation else None
        counts = count_strings([original], [translated or []], {})
        for key in totals:
            totals[key] += counts[key]
    return {"counts": totals, "targets": targets_of(rules), "skipped": skipped}
