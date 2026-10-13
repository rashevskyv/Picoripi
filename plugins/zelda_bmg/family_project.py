"""Twilight Princess family project: one Picoripi project for the whole family, built from the family plan.

Every unit tree (one message, plus its linked copies in the other versions) is one project message. Its folder:
    "Shared" (base-rooted tree with more than one version), "Shared HD Msguk" (the same for a tree rooted in HD
    Msguk), or "<label> only" (a tree of one version: "GC only", "Wii only", "HD Msguk only", "HD Msgus only").
Each folder holds loose BMG files <folder>/<archive>/<file>.bmg with the root version's messages, in order.
The source root and the translation root have the same layout. Picoripi's sync makes the blocks.
"""
from __future__ import annotations

import json
import shutil
import uuid
from collections import OrderedDict
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Tuple

from core.containers.rarc_container import RarcContainer
from core.family_projects.model import FamilyPlan
from core.family_projects.store import fanout, normalize, seed, trees
from utils.atomic_io import atomic_write_bytes, atomic_write_json

from .family import Unit, editor_texts, family_of, subset_bmg

PROJECT_FILE = "project.uiproj"
# Project files the family project carries over from the GameCube project (same messages, same tags).
CARRIED_FILES = ("translation_map.json", "project_settings.json")
# Block metadata carried over per GameCube message (keyed by message index in its file).
CARRIED_METADATA = ("story_context_assignments", "translation_status")


class _Archives:
    """Reads the original archives of one member folder, once each."""

    def __init__(self, folder: Path):
        self.folder = folder
        self._cache: Dict[str, RarcContainer] = {}

    def file(self, archive: str, inner: str) -> bytes:
        if archive not in self._cache:
            self._cache[archive] = RarcContainer((self.folder / archive).read_bytes())
        return self._cache[archive].read_file(inner)


def folder_name(plan: FamilyPlan, root_member: str, shared: bool) -> str:
    label = plan.member(root_member).label
    if not shared:
        return f"{label} only"
    return "Shared" if root_member == plan.base else f"Shared {label}"


def _entries(plan: FamilyPlan, units: Dict[str, List[Unit]]) -> List[Tuple[str, str, Unit]]:
    """(folder, root member, root unit) for every tree, in family order."""
    by_uid = {m: {u.uid: u for u in items} for m, items in units.items()}
    out = []
    for (member, uid), nodes in trees(family_of(plan)):
        out.append((folder_name(plan, member, len(nodes) > 1), member, by_uid[member][uid]))
    return out


def _files(plan: FamilyPlan, units: Dict[str, List[Unit]]) -> "OrderedDict[Tuple[str, str, str], Tuple[str, List[Unit]]]":
    """Per project file (folder, archive, file): (root member, its units sorted by message index)."""
    files: "OrderedDict[Tuple[str, str, str], Tuple[str, List[Unit]]]" = OrderedDict()
    for folder, member, unit in _entries(plan, units):
        key = (folder, unit.archive, unit.member)
        files.setdefault(key, (member, []))[1].append(unit)
    for key, (member, group) in files.items():
        group.sort(key=lambda u: u.index)
    return files


def build_sources(plan: FamilyPlan, units: Dict[str, List[Unit]], root: Path, rules) -> int:
    """Write the project source root. Returns the number of project files."""
    originals = {m.key: _Archives(Path(m.path)) for m in plan.members}
    files = _files(plan, units)
    for (folder, archive, inner), (member, group) in files.items():
        data = subset_bmg(originals[member].file(archive, inner), [u.index for u in group],
                          [u.text for u in group], rules)
        atomic_write_bytes(root / folder / archive / inner, data)
    return len(files)


def push(plan: FamilyPlan, store: dict, units: Dict[str, List[Unit]], translation_root: Path, rules) -> None:
    """Write the store's texts into the translation root. Refuses a store with a text the project cannot show."""
    family = family_of(plan)
    store, overrides = normalize(family, store)
    if overrides:
        raise ValueError("the project cannot show these texts (they differ from the shared unit): "
                         + ", ".join(f"{m} {u}" for m, u in overrides))
    # Keyed by member too: a unit id is only unique inside one member (the same id exists in every version).
    texts = {}
    for member in {m for _f, m, _u in _entries(plan, units)}:
        out, _warnings = fanout(family, store, member)
        texts.update({(member, uid): text for uid, text in out.items() if text is not None})
    originals = {m.key: _Archives(Path(m.path)) for m in plan.members}
    for (folder, archive, inner), (member, group) in _files(plan, units).items():
        new = [texts.get((member, u.uid)) or u.text for u in group]
        data = subset_bmg(originals[member].file(archive, inner), [u.index for u in group], new, rules)
        atomic_write_bytes(translation_root / folder / archive / inner, data)


def pull(plan: FamilyPlan, units: Dict[str, List[Unit]], translation_root: Path, rules) -> Dict[str, Dict[str, str]]:
    """Translated text per root member and unit id, read back from the translation root (for seed).

    A message that still reads as its source is untranslated (""). A file that is not in the root is untranslated.
    """
    translations: Dict[str, Dict[str, str]] = {}
    originals = {m.key: _Archives(Path(m.path)) for m in plan.members}
    for (folder, archive, inner), (member, group) in _files(plan, units).items():
        path = translation_root / folder / archive / inner
        if not path.is_file():
            continue
        # An untouched message reads back in the writer's form, which can differ from its source text.
        # Compare with that form, or every such message would look translated.
        written = subset_bmg(originals[member].file(archive, inner), [u.index for u in group],
                             [u.text for u in group], rules)
        baseline = editor_texts(written, rules)
        values = translations.setdefault(member, {})
        for unit, base, text in zip(group, baseline, editor_texts(path.read_bytes(), rules)):
            values[unit.uid] = "" if text == base else text
    return translations


def seed_from_project(plan: FamilyPlan, units: Dict[str, List[Unit]], translation_root: Path, rules):
    """The store built from the translation root (see pull). Returns (store, warnings)."""
    return seed(family_of(plan), pull(plan, units, translation_root, rules))


def carry_mapping(plan: FamilyPlan, units: Dict[str, List[Unit]]) -> Dict[Tuple[str, str, str], Dict[int, int]]:
    """For each project file of the base version: GameCube message index -> index in the project file."""
    mapping = {}
    for key, (member, group) in _files(plan, units).items():
        if member == plan.base:
            mapping[key] = {unit.index: pos for pos, unit in enumerate(group)}
    return mapping


def create_project(project_dir: Path, source_root: Path, translation_root: Path, name: str, rules,
                   carry_from: Optional[Path] = None, mapping: Optional[dict] = None) -> Path:
    """Create the project file for the two roots and let Picoripi's sync make the blocks. Returns the .uiproj path.

    carry_from: a GameCube project folder. Its translation map, settings and message metadata are copied over,
    with the message indexes moved to the project file (mapping, see carry_mapping).
    """
    from core.project.manager import ProjectManager

    project_dir.mkdir(parents=True, exist_ok=True)
    now = datetime.now().isoformat()
    project_file = project_dir / PROJECT_FILE
    if not project_file.exists():
        atomic_write_json(project_file, {
            "id": str(uuid.uuid4()), "name": name, "description": "", "plugin_name": "zelda_bmg",
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
        carry_project_data(carry_from, project_dir, mapping or {})
    return project_file


def carry_project_data(old_dir: Path, new_dir: Path, mapping: dict) -> int:
    """Copy the translation map and settings, and the GameCube message metadata, to the project file.

    The metadata is keyed by message index; each index moves to the index the message has in the new file.
    Returns the number of metadata entries carried.
    """
    for name in CARRIED_FILES:
        if (old_dir / name).is_file() and not (new_dir / name).exists():
            shutil.copy2(old_dir / name, new_dir / name)
    old = json.loads((old_dir / PROJECT_FILE).read_text(encoding="utf-8"))
    by_file = {(b["metadata"].get("archive_rel_path"), b["metadata"].get("archive_file_name")): b
               for b in old["blocks"] if b.get("metadata", {}).get("is_archive_member")}
    new = json.loads((new_dir / PROJECT_FILE).read_text(encoding="utf-8"))
    carried = 0
    for block in new["blocks"]:
        parts = block["source_file"].replace("\\", "/").split("/")
        key = (parts[0], parts[1], "/".join(parts[2:])) if len(parts) > 2 else None
        if key not in mapping:
            continue
        source = by_file.get((parts[1], parts[-1]))
        if source is None:
            continue
        meta = block.setdefault("metadata", {})
        for name in CARRIED_METADATA:
            values = source.get("metadata", {}).get(name)
            if not values:
                continue
            moved = {str(mapping[key][int(idx)]): value for idx, value in values.items()
                     if idx.isdigit() and int(idx) in mapping[key]}
            if moved:
                meta[name] = moved
                carried += len(moved)
    atomic_write_json(new_dir / PROJECT_FILE, new, ensure_ascii=False, indent=4)
    return carried


def count_messages(project_dir: Path, rules) -> Dict[str, int]:
    """Messages per top-level folder of the project, read through the project's own manager."""
    from core.project.manager import ProjectManager

    manager = ProjectManager(str(project_dir))
    counts: Dict[str, int] = {}
    for block in manager.project.blocks:
        meta = block.metadata
        if meta.get("is_archive_member"):
            data = manager.get_archive_container(meta["archive_rel_path"]).read_file(meta["archive_file_name"])
        else:
            data = Path(manager.get_absolute_path(block.source_file)).read_bytes()
        folder = block.source_file.replace("\\", "/").split("/")[0]
        counts[folder] = counts.get(folder, 0) + len(editor_texts(data, rules))
    return counts
