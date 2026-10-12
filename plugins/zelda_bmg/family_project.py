"""Twilight Princess family project: one Picoripi project for the whole family, built from the family plan.

Layout of the project source root (the project's source_path):
    <root>/bmgres.arc, bmgres1.arc, ...            the base member (GameCube archives, copied as they are)
    <root>/<Label> only/<archive>/<file>.bmg       the messages only that member has (loose BMG files)
The translation root (translation_path) has the same layout. Shared messages live once, in the base archives.
A loose file holds the member's own messages in unit order; the plan says which unit each one is.

Only the TP plugin reads the archives; the project itself is created by Picoripi's own sync, so blocks and
virtual folders are the ones the app makes.
"""
from __future__ import annotations

import json
import shutil
import uuid
from collections import OrderedDict
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Sequence, Tuple

from core.containers.rarc_container import RarcContainer
from core.family_projects.model import FamilyPlan
from core.family_projects.store import fanout, links, seed
from utils.atomic_io import atomic_write_bytes, atomic_write_json

from .family import ARCHIVE_GLOB, Unit, editor_texts, family_of, scan, subset_bmg, write_member

PROJECT_FILE = "project.uiproj"
# Project files the family project carries over from the GameCube project (same messages, same tags).
CARRIED_FILES = ("translation_map.json", "project_settings.json")
# Block metadata carried over per GameCube block (keyed by archive and file name).
CARRIED_METADATA = ("story_context_assignments", "translation_status")


def own_units(plan: FamilyPlan, units: Dict[str, List[Unit]]) -> Dict[str, List[Unit]]:
    """Per member: the units that are not linked to a parent. The base keeps all of its units."""
    linked = links(family_of(plan))
    return {key: [u for u in items if key == plan.base or u.uid not in linked[key]]
            for key, items in units.items()}


def _groups(items: Sequence[Unit]) -> "OrderedDict[Tuple[str, str], List[Unit]]":
    """Units grouped by (archive, file), in order."""
    groups: "OrderedDict[Tuple[str, str], List[Unit]]" = OrderedDict()
    for unit in items:
        groups.setdefault((unit.archive, unit.member), []).append(unit)
    return groups


class _Archives:
    """Reads the original archives of one member folder, once each."""

    def __init__(self, folder: Path):
        self.folder = folder
        self._cache: Dict[str, RarcContainer] = {}

    def file(self, archive: str, inner: str) -> bytes:
        if archive not in self._cache:
            self._cache[archive] = RarcContainer((self.folder / archive).read_bytes())
        return self._cache[archive].read_file(inner)


def subset_path(root: Path, label: str, archive: str, inner: str) -> Path:
    return root / f"{label} only" / archive / inner


def build_sources(plan: FamilyPlan, units: Dict[str, List[Unit]], root: Path, rules) -> int:
    """Write the project source root. Returns the number of loose subset files."""
    root.mkdir(parents=True, exist_ok=True)
    base = plan.member(plan.base)
    for archive in sorted(Path(base.path).glob(ARCHIVE_GLOB)):
        shutil.copy2(archive, root / archive.name)
    written = 0
    own = own_units(plan, units)
    for member in plan.members:
        if member.base:
            continue
        original = _Archives(Path(member.path))
        for (archive, inner), group in _groups(own[member.key]).items():
            data = subset_bmg(original.file(archive, inner), [u.index for u in group],
                              [u.text for u in group], rules)
            atomic_write_bytes(subset_path(root, member.label, archive, inner), data)
            written += 1
    return written


def push(plan: FamilyPlan, store: dict, units: Dict[str, List[Unit]], translation_root: Path, rules) -> List[str]:
    """Write the store's texts into the translation root. Returns the warnings of the fan-out."""
    family = family_of(plan)
    warnings: List[str] = []
    base = plan.member(plan.base)
    base_out, base_warnings = fanout(family, store, plan.base)
    warnings += base_warnings
    write_member(Path(base.path), translation_root,
                 {uid: text for uid, text in base_out.items() if text is not None}, rules, always=True)
    own = own_units(plan, units)
    for member in plan.members:
        if member.base:
            continue
        out, member_warnings = fanout(family, store, member.key)
        warnings += member_warnings
        original = _Archives(Path(member.path))
        for (archive, inner), group in _groups(own[member.key]).items():
            texts = [out.get(u.uid) or u.text for u in group]
            data = subset_bmg(original.file(archive, inner), [u.index for u in group], texts, rules)
            atomic_write_bytes(subset_path(translation_root, member.label, archive, inner), data)
    return warnings


def pull(plan: FamilyPlan, units: Dict[str, List[Unit]], translation_root: Path, rules) -> Dict[str, Dict[str, str]]:
    """Translated text per member and unit id, read back from the translation root (for seed).

    A message that still reads as its source is untranslated (""). A base archive not in the root is untranslated.
    """
    translations: Dict[str, Dict[str, str]] = {}
    source = {key: {u.uid: u.text for u in items} for key, items in units.items()}
    translations[plan.base] = {
        u.uid: ("" if source[plan.base][u.uid] == u.text else u.text)
        for u in scan(translation_root, rules)
    } if translation_root.is_dir() else {}
    own = own_units(plan, units)
    for member in plan.members:
        if member.base:
            continue
        values: Dict[str, str] = {}
        for (archive, inner), group in _groups(own[member.key]).items():
            path = subset_path(translation_root, member.label, archive, inner)
            if not path.is_file():
                continue
            texts = editor_texts(path.read_bytes(), rules)
            for unit, text in zip(group, texts):
                values[unit.uid] = "" if text == unit.text else text
        translations[member.key] = values
    return translations


def seed_from_project(plan: FamilyPlan, units: Dict[str, List[Unit]], translation_root: Path, rules):
    """The store built from the translation root (see pull)."""
    return seed(family_of(plan), pull(plan, units, translation_root, rules))


def create_project(project_dir: Path, source_root: Path, translation_root: Path, name: str, rules,
                   carry_from: Path | None = None, plugin_name: str = "zelda_bmg") -> Path:
    """Create the project file for the two roots and let Picoripi's sync make the blocks. Returns the .uiproj path.

    carry_from: a GameCube project folder. Its translation map, settings and block metadata are copied over.
    plugin_name: the plugin that opens the project (its rules are the ones passed in).
    """
    from core.project.manager import ProjectManager

    project_dir.mkdir(parents=True, exist_ok=True)
    now = datetime.now().isoformat()
    project_file = project_dir / PROJECT_FILE
    if not project_file.exists():
        atomic_write_json(project_file, {
            "id": str(uuid.uuid4()), "name": name, "description": "", "plugin_name": plugin_name,
            "blocks": [], "virtual_folders": [],
            "metadata": {"source_path": str(source_root), "translation_path": str(translation_root),
                         "is_directory_mode": True, "auto_create_translations": False,
                         "root_block_ids": [], "settings": {}},
            "created_at": now, "modified_at": now, "version": "1.1",
        })
    manager = ProjectManager(str(project_dir))
    manager.sync_project_files(plugin=rules)
    manager.save()
    if carry_from is not None:
        carry_project_data(carry_from, project_dir)
        manager = ProjectManager(str(project_dir))
        manager.sync_project_files(plugin=rules)
        manager.save()
    return project_file


def carry_project_data(old_dir: Path, new_dir: Path) -> int:
    """Copy the translation map and settings, and the GameCube block metadata. Returns the blocks updated."""
    for name in CARRIED_FILES:
        if (old_dir / name).is_file() and not (new_dir / name).exists():
            shutil.copy2(old_dir / name, new_dir / name)
    old = json.loads((old_dir / PROJECT_FILE).read_text(encoding="utf-8"))
    by_file = {(b["metadata"].get("archive_rel_path"), b["metadata"].get("archive_file_name")): b
               for b in old["blocks"] if b.get("metadata", {}).get("is_archive_member")}
    new = json.loads((new_dir / PROJECT_FILE).read_text(encoding="utf-8"))
    updated = 0
    for block in new["blocks"]:
        meta = block.get("metadata", {})
        source = by_file.get((meta.get("archive_rel_path"), meta.get("archive_file_name")))
        if not meta.get("is_archive_member") or source is None:
            continue
        for key in CARRIED_METADATA:
            if key in source.get("metadata", {}):
                meta[key] = source["metadata"][key]
                updated += 1
    atomic_write_json(new_dir / PROJECT_FILE, new, ensure_ascii=False, indent=4)
    return updated


def count_messages(project_dir: Path, rules) -> Dict[str, int]:
    """Messages per top-level folder of the project (the base archives count under "base"), read through the project."""
    from core.project.manager import ProjectManager

    manager = ProjectManager(str(project_dir))
    counts: Dict[str, int] = {}
    for block in manager.project.blocks:
        meta = block.metadata
        if meta.get("is_archive_member"):
            data = manager.get_archive_container(meta["archive_rel_path"]).read_file(meta["archive_file_name"])
        else:
            data = Path(manager.get_absolute_path(block.source_file)).read_bytes()
        texts = editor_texts(data, rules)
        top = block.source_file.replace("\\", "/").split("/")
        folder = top[0] if top[0].endswith(" only") else "base"
        counts[folder] = counts.get(folder, 0) + len(texts)
    return counts
