"""Wind Waker family plan: GameCube (BMG in ``bmgres*.arc``) and Wind Waker HD (68 MSBT files).

The GameCube folder is the base. A message of HD links to a GameCube message when both have the same family match
key: the editor text with tags read in one syntax and colour removed (``family_tags.match_key``). Units with equal
keys pair in order; a key that repeats gets a count suffix, so the engine's order alignment pairs them exactly.

A linked message lives once, in the base archives (the shared translation). An HD message with no partner lives in
the project folder "HD only", as an MSBT subset file of its own messages. The HD output is written by
``write_hd_output``: each message takes its family text (converted to HD tags) or its own subset text.

Sources are recognised by content: GameCube by its 4426 BMG messages, HD by its 68 MSBT files and 5040 messages.
"""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from types import SimpleNamespace
from typing import Dict, List, Optional, Sequence, Tuple

from core.containers.rarc_container import RarcContainer
from core.family_projects.model import FamilyMember, FamilyPlan
from core.family_projects.store import Family as EngineFamily, fanout, links
from plugins.common.msbt import Msbt
from utils.atomic_io import atomic_write_bytes

from . import family_tags as ft
from .tags import from_editor, to_editor

GC_ARCHIVE_GLOB = "bmgres*.arc"
HD_FILE_GLOB = "*.msbt"
HD_ONLY_FOLDER = "HD only"
GC_FINGERPRINT = {"messages": 4426, "zel_00.bmg": 4411}
HD_FINGERPRINT = {"files": 68, "messages": 5040}
BASE, HD = "gc", "hd"
KEY_SEPARATOR = "\x1f"


@dataclass(frozen=True)
class Unit:
    """One message of a version. uid: stable id (archive or file, member, index). text: editor text of the version."""

    uid: str
    member_key: str
    where: str         # archive name (GameCube) or MSBT file name (HD)
    inner: str         # BMG path inside the archive, "" for HD
    index: int
    text: str
    key: str           # family match key (unique: count suffix added)


def make_rules(project_dir: Optional[Path]):
    """The GameCube rules, reading the character map of project_dir (the same path the app takes)."""
    from plugins.zelda_tww.rules import GameRules

    if project_dir is None:
        return GameRules()
    window = SimpleNamespace(project_manager=SimpleNamespace(project_dir=str(project_dir)))
    return GameRules(main_window_ref=window)


def gc_archives(folder: Path) -> List[Path]:
    return sorted(folder.glob(GC_ARCHIVE_GLOB))


def hd_files(folder: Path) -> List[Path]:
    return sorted(folder.glob(HD_FILE_GLOB))


def _gc_editor_texts(archive: Path, rules) -> List[Tuple[str, str, int, str]]:
    """(archive, inner path, index, editor text) of every BMG message of one archive."""
    container = RarcContainer(archive.read_bytes())
    out = []
    for path in container.list_files():
        if not path.endswith(".bmg"):
            continue
        data, _names = rules.load_data_from_json_obj(container.read_file(path))
        for index, text in enumerate(data[0] if data else []):
            out.append((archive.name, path, index, text))
    return out


def _hd_editor_texts(path: Path) -> List[Tuple[str, str, int, str]]:
    msbt = Msbt(path.read_bytes())
    return [(path.name, "", index, to_editor(tokens)) for index, tokens in enumerate(msbt.messages)]


def recognise(gc_count: Optional[Dict[str, int]], hd_count: Optional[Dict[str, int]]) -> Optional[str]:
    """BASE, HD, or None. Counts: GameCube message total and its zel_00 count; HD file and message totals."""
    if gc_count and gc_count.get("messages") == GC_FINGERPRINT["messages"] \
            and gc_count.get("zel_00.bmg") == GC_FINGERPRINT["zel_00.bmg"]:
        return BASE
    if hd_count and hd_count.get("files") == HD_FINGERPRINT["files"] \
            and hd_count.get("messages") == HD_FINGERPRINT["messages"]:
        return HD
    return None


class FamilyScan:
    """The scanned family: the base units, the HD units and their links. Built by ``scan_family``."""

    def __init__(self, base_folder: Path, hd_folder: Path, project_dir: Optional[Path] = None):
        self.base_folder = base_folder
        self.hd_folder = hd_folder
        self.rules = make_rules(project_dir)
        self.tags = ft.TagMap(ft.load_map())
        base_rows = [row for archive in gc_archives(base_folder) for row in _gc_editor_texts(archive, self.rules)]
        hd_rows = [row for path in hd_files(hd_folder) for row in _hd_editor_texts(path)]
        self.base_units = self._units(BASE, base_rows, "gc")
        self.hd_units = self._units(HD, hd_rows, "hd")
        self.engine = EngineFamily(
            base=BASE,
            parents={BASE: (), HD: (BASE,)},
            units={BASE: [(u.uid, u.key) for u in self.base_units], HD: [(u.uid, u.key) for u in self.hd_units]},
            exact_keys=True,
        )
        self.links = links(self.engine)[HD]          # hd uid -> (gc, gc uid)
        self._by_uid = {u.uid: u for u in self.base_units + self.hd_units}

    def _units(self, member: str, rows, side: str) -> List[Unit]:
        units = []
        for where, inner, index, text in rows:
            uid = f"{where}/{inner}#{index}" if inner else f"{where}#{index}"
            units.append(Unit(uid, member, where, inner, index, text, ft.match_key(text, side, self.tags)))
        return units

    def read(self, member: str) -> List[Tuple[str, str]]:
        """(uid, key) per unit, in file order."""
        units = self.base_units if member == BASE else self.hd_units
        return [(u.uid, u.key) for u in units]

    def unit(self, uid: str) -> Unit:
        return self._by_uid[uid]

    def hd_only(self) -> List[Unit]:
        return [u for u in self.hd_units if u.uid not in self.links]

    def plan(self) -> FamilyPlan:
        members = (
            FamilyMember(BASE, "GameCube", str(self.base_folder), base=True),
            FamilyMember(HD, "HD", str(self.hd_folder), parents=(BASE,)),
        )
        return FamilyPlan(members=members, read=self.read)


def scan_family(sources: Sequence[str], project_dir: Optional[str] = None) -> FamilyScan:
    """Recognise the two source folders by content and scan them. Raises ValueError when they do not fit."""
    rules = make_rules(Path(project_dir) if project_dir else None)
    found: Dict[str, Path] = {}
    for text in sources:
        folder = Path(text)
        gc_count = None
        if gc_archives(folder):
            rows = [row for archive in gc_archives(folder) for row in _gc_editor_texts(archive, rules)]
            gc_count = {"messages": len(rows), "zel_00.bmg": sum(1 for r in rows if r[1] == "zel_00.bmg")}
        hd_count = None
        if hd_files(folder):
            rows = [row for path in hd_files(folder) for row in _hd_editor_texts(path)]
            hd_count = {"files": len(hd_files(folder)), "messages": len(rows)}
        kind = recognise(gc_count, hd_count)
        if kind is None:
            raise ValueError(f"not a Wind Waker message folder: {folder}")
        if kind in found:
            raise ValueError(f"two sources are the same version: {found[kind]} and {folder}")
        found[kind] = folder
    if BASE not in found or HD not in found:
        raise ValueError("the Wind Waker family needs the GameCube and the HD message folders")
    return FamilyScan(found[BASE], found[HD], Path(project_dir) if project_dir else None)


def plan_for_sources(sources: Sequence[str], project_dir: Optional[str] = None) -> FamilyPlan:
    return scan_family(sources, project_dir).plan()


# -- writing ----------------------------------------------------------------------------------------

def hd_only_subset(family: FamilyScan, source: Path, out: Path) -> int:
    """Write out/<file>.msbt with the HD-only messages of one HD file. Returns the messages written (0: no file)."""
    indices = [u.index for u in family.hd_only() if u.where == source.name]
    if not indices:
        return 0
    msbt = Msbt(source.read_bytes())
    texts = [msbt.messages[i] for i in indices]
    atomic_write_bytes(out, msbt.subset(indices, texts))
    return len(indices)


def build_sources(family: FamilyScan, root: Path) -> Tuple[int, int]:
    """The project source root: the GameCube archives as they are, and the HD-only subsets. Returns (archives, messages)."""
    root.mkdir(parents=True, exist_ok=True)
    archives = 0
    for archive in gc_archives(family.base_folder):
        atomic_write_bytes(root / archive.name, archive.read_bytes())
        archives += 1
    messages = 0
    for path in hd_files(family.hd_folder):
        messages += hd_only_subset(family, path, root / HD_ONLY_FOLDER / path.name)
    return archives, messages


def _write_gc_archives(family: FamilyScan, out: Path, texts: Dict[str, str], always: bool = False) -> int:
    """Write the GameCube archives with the changed messages. Returns the BMG files rewritten."""
    out.mkdir(parents=True, exist_ok=True)
    changed_files = 0
    for archive in gc_archives(family.base_folder):
        container = RarcContainer(archive.read_bytes())
        changed_any = False
        for path in container.list_files():
            if not path.endswith(".bmg"):
                continue
            blob = container.read_file(path)
            family.rules.load_data_from_json_obj(blob)
            current = family.rules.load_data_from_json_obj(blob)[0][0]
            new = [texts.get(f"{archive.name}/{path}#{i}", text) for i, text in enumerate(current)]
            if new == current:
                continue
            container.write_file(path, family.rules.save_data_to_json_obj([new], {}))
            changed_any = True
            changed_files += 1
        if changed_any or always:
            atomic_write_bytes(out / archive.name, container.pack())
    return changed_files


def push_base(family: FamilyScan, store: dict, translation_root: Path) -> Tuple[int, List[str]]:
    """Write the shared (GameCube) translations into the translation root. Returns (BMG files, warnings)."""
    out, warnings = fanout(family.engine, store, BASE)
    changed = {uid: text for uid, text in out.items() if text is not None}
    return _write_gc_archives(family, translation_root, changed, always=True), warnings


def write_hd_output(family: FamilyScan, store: dict, translation_root: Path, out: Path) -> Tuple[int, List[str]]:
    """Write every HD MSBT file for the game: linked messages from the family text (HD tags), HD-only messages from
    the project's "HD only" subset. Unchanged files are written as they are. Returns (files written, warnings)."""
    fam_out, warnings = fanout(family.engine, store, HD)
    own: Dict[str, str] = {}
    subset_root = translation_root / HD_ONLY_FOLDER
    for path in hd_files(family.hd_folder):
        subset = subset_root / path.name
        if not subset.is_file():
            continue
        subset_msbt = Msbt(subset.read_bytes())
        for position, unit in enumerate([u for u in family.hd_only() if u.where == path.name]):
            own[unit.uid] = to_editor(subset_msbt.messages[position])
    out.mkdir(parents=True, exist_ok=True)
    written = 0
    for path in hd_files(family.hd_folder):
        msbt = Msbt(path.read_bytes())
        new_tokens = []
        changed = False
        for index, tokens in enumerate(msbt.messages):
            uid = f"{path.name}#{index}"
            text = None
            if uid in family.links:
                gc_text = fam_out.get(uid)
                text = ft.gc_to_hd(gc_text, family.tags)[0] if gc_text is not None else None
            elif uid in own:
                text = own[uid]
            if text is None or text == to_editor(tokens):
                new_tokens.append(tokens)
                continue
            new_tokens.append(from_editor(text))
            changed = True
        if changed:
            atomic_write_bytes(out / path.name, msbt.build(new_tokens))
        else:
            atomic_write_bytes(out / path.name, path.read_bytes())
        written += 1
    return written, warnings


def count_units(family: FamilyScan) -> Dict[str, int]:
    """Messages per family folder: the base (GameCube archives) and HD only."""
    return {"base": len(family.base_units), "HD only": len(family.hd_only()),
            "linked": len(family.links)}


# -- project and command line ----------------------------------------------------------------------

PROJECT_PLUGIN = "zelda_tww"


def _copy_missing_subsets(family: FamilyScan, source_root: Path, translation_root: Path) -> int:
    """The translation copy of each HD-only subset: the source copy until the translator edits it."""
    copied = 0
    for path in sorted((source_root / HD_ONLY_FOLDER).glob("*.msbt")) if (source_root / HD_ONLY_FOLDER).is_dir() else []:
        target = translation_root / HD_ONLY_FOLDER / path.name
        if not target.exists():
            atomic_write_bytes(target, path.read_bytes())
            copied += 1
    return copied


def command_project(config: dict, root: Path) -> Dict[str, int]:
    """Build the source roots, the translation roots and the family .uiproj. Returns the messages per folder."""
    from plugins.zelda_bmg.family_project import create_project, carry_project_data

    fam = config["family_project"]
    project_dir, source_root, translation_root = root / fam["dir"], root / fam["source"], root / fam["translation"]
    sources = [str((root / entry).resolve()) for entry in config["sources"]]
    family = scan_family(sources, str(project_dir) if project_dir.exists() else None)
    build_sources(family, source_root)
    _copy_missing_subsets(family, source_root, translation_root)
    store = _load_store_for(root, config)
    push_base(family, store, translation_root)
    rules = make_rules(project_dir)
    carry = root / fam["carry_from"] if fam.get("carry_from") else None
    create_project(project_dir, source_root, translation_root, fam.get("name", "Wind Waker family"), rules,
                   carry_from=carry, plugin_name=PROJECT_PLUGIN)
    if carry is not None:
        carry_project_data(carry, project_dir)
    return count_project(project_dir, rules)


def count_project(project_dir: Path, rules) -> Dict[str, int]:
    """Messages per top-level folder of the project, read through the project (the base archives sit in the ".extracted" folder)."""
    from plugins.zelda_bmg.family_project import count_messages

    return count_messages(project_dir, rules)


def _load_store_for(root: Path, config: dict) -> dict:
    from core.family_projects.store import load_store

    return load_store(root / config.get("store", "family_translations.json"), BASE)


def main(argv: Optional[Sequence[str]] = None) -> int:
    import argparse
    import json

    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("command", choices=["plan", "project", "push", "verify"])
    parser.add_argument("family", type=Path, help="path to the family file (json)")
    args = parser.parse_args(argv)
    config_path = args.family.resolve()
    config = json.loads(config_path.read_text(encoding="utf-8"))
    root = config_path.parent
    sources = [str((root / entry).resolve()) for entry in config["sources"]]
    if args.command == "plan":
        family = scan_family(sources)
        print("plan:", count_units(family))
        return 0
    if args.command == "project":
        print("project folders:", command_project(config, root))
        return 0
    fam = config["family_project"]
    project_dir, translation_root = root / fam["dir"], root / fam["translation"]
    family = scan_family(sources, str(project_dir))
    if args.command == "push":
        from core.family_projects.store import save_store
        store, pull_warnings = pull(family, _load_store_for(root, config), translation_root)
        save_store(root / config.get("store", "family_translations.json"), store)
        base_files, warnings = push_base(family, store, translation_root)
        warnings = pull_warnings + warnings
        hd_files_written, hd_warnings = write_hd_output(family, store, translation_root,
                                                        root / config.get("hd_output", "family_out/hd/Message"))
        print(f"push: {base_files} GameCube BMG files, {hd_files_written} HD MSBT files")
        for line in warnings + hd_warnings:
            print("  warning:", line)
        return 0
    print("plan:", count_units(family))
    print("project:", count_project(project_dir, make_rules(project_dir)))
    return 0



def read_base_translations(family: FamilyScan, translation_root: Path) -> Dict[str, str]:
    """Translated text per GameCube unit id, read back from the translation root archives. Untranslated: no entry."""
    translated: Dict[str, str] = {}
    for archive in gc_archives(family.base_folder):
        copy = translation_root / archive.name
        if not copy.is_file():
            continue
        for where, inner, index, text in _gc_editor_texts(copy, family.rules):
            uid = f"{where}/{inner}#{index}"
            source = family.unit(uid).text
            if text != source:
                translated[uid] = text
    return translated


def pull(family: FamilyScan, store: dict, translation_root: Path) -> Tuple[dict, List[str]]:
    """The store rebuilt from the translator's shared (GameCube) edits. Returns (store, warnings)."""
    from core.family_projects.store import seed

    translations = {BASE: read_base_translations(family, translation_root)}
    return seed(family.engine, translations)


if __name__ == "__main__":
    import sys

    sys.exit(main())
