"""Zelda BMG family plan: Twilight Princess GameCube, Wii and Wii U HD sources, and their message files.

A source is a folder of ``bmgres*.arc`` archives. The plugin recognises each source by its content: the message
count of its files (a fingerprint), not by the user's folder name. The two HD slots share one fingerprint; the
game's own folder name (``res/Msguk`` or ``res/Msgus``) tells them apart. The base is GameCube. The Wii links to
it, HD Msguk links to it, and HD Msgus links to HD Msguk first, then to the base.

CLI (a thin wrapper over the plan; the family file lists the sources):
    python -m plugins.zelda_bmg.family plan|seed|fanout <family.json> [--member KEY --out DIR] [--dry-run]
"""
from __future__ import annotations

import argparse
import json
import sys
from dataclasses import dataclass
from pathlib import Path
from types import SimpleNamespace
from typing import Dict, List, Optional, Sequence, Tuple

from core.containers.rarc_container import RarcContainer
from core.family_projects.model import FamilyMember, FamilyPlan
from core.family_projects.store import Family, fanout, load_store, save_store, seed
from utils.atomic_io import atomic_write_bytes

from .rules import GameRules

ARCHIVE_GLOB = "bmgres*.arc"
BASE = "gc"
# Message count of the files that tell the consoles apart (game data, not user naming).
FINGERPRINTS = {
    "gc": ("GameCube", {"zel_01.bmg": 1820, "zel_04.bmg": 1607}),
    "wii": ("Wii", {"zel_01.bmg": 1820, "zel_04.bmg": 1606}),
    "hd": ("Wii U HD", {"zel_01.bmg": 1807}),
}
# Order of the members in a plan: each one comes after its parents.
ORDER = ("gc", "wii", "hd_msguk", "hd_msgus")


@dataclass(frozen=True)
class Unit:
    """One message: its family unit id, the archive and file it lives in, its position and editor text."""

    uid: str
    archive: str
    member: str
    index: int
    text: str


def make_rules(project_dir: Optional[Path]) -> GameRules:
    """GameRules that reads the character map of project_dir (the same path the app takes)."""
    if project_dir is None:
        return GameRules()
    window = SimpleNamespace(project_manager=SimpleNamespace(project_dir=str(project_dir)))
    return GameRules(main_window_ref=window)


def editor_texts(bmg: bytes, rules: GameRules) -> List[str]:
    """The editor texts of one BMG file, in message order."""
    data, _names = rules.load_data_from_json_obj(bmg)
    return list(data[0]) if data else []


def write_bmg(source: bytes, texts: Sequence[str], rules: GameRules) -> bytes:
    """The BMG of source with the given editor texts; message ids and attributes come from source."""
    rules.load_data_from_json_obj(source)
    return rules.save_data_to_json_obj([list(texts)], {})


def scan(folder: Path, rules: GameRules) -> List[Unit]:
    """Every message of the folder's archives, in archive, file and message order."""
    units: List[Unit] = []
    for archive in sorted(folder.glob(ARCHIVE_GLOB)):
        container = RarcContainer(archive.read_bytes())
        for path in container.list_files():
            if not path.endswith(".bmg"):
                continue
            for index, text in enumerate(editor_texts(container.read_file(path), rules)):
                units.append(Unit(f"{archive.name}/{path}#{index}", archive.name, path, index, text))
    return units


def fingerprint(units: Sequence[Unit]) -> Dict[str, int]:
    """Message count per file name (the last part of the path inside the archive)."""
    counts: Dict[str, int] = {}
    for unit in units:
        name = unit.member.rsplit("/", 1)[-1]
        counts[name] = counts.get(name, 0) + 1
    return counts


def recognise(units: Sequence[Unit]) -> Optional[str]:
    """The fingerprint key these units match ("gc", "wii", "hd"), or None."""
    counts = fingerprint(units)
    for key, (_label, expected) in FINGERPRINTS.items():
        if all(counts.get(name) == number for name, number in expected.items()):
            return key
    return None


def _member_key(folder: Path, fingerprint_key: str) -> str:
    """Member key of a source. HD sources share one fingerprint: the game's folder name gives the slot."""
    if fingerprint_key != "hd":
        return fingerprint_key
    return "hd_msgus" if folder.name.lower() == "msgus" else "hd_msguk"


def _label(key: str) -> str:
    if key.startswith("hd"):
        return f"Wii U HD, slot {'Msgus' if key == 'hd_msgus' else 'Msguk'}"
    return FINGERPRINTS[key][0]


def plan_for_sources(sources: Sequence[str], rules: GameRules) -> Tuple[FamilyPlan, Dict[str, List[Unit]]]:
    """The family plan for the given source folders, and the units read from each folder (by member key).

    Raises ValueError when a source is not a Twilight Princess message folder, or when two sources claim one
    member. The base is GameCube when present; otherwise the first member in ORDER stands in for it.
    """
    folders: Dict[str, Path] = {}
    units: Dict[str, List[Unit]] = {}
    for text in sources:
        folder = Path(text)
        read = scan(folder, rules)
        fp = recognise(read)
        if fp is None:
            raise ValueError(f"not a Twilight Princess message folder: {folder}")
        key = _member_key(folder, fp)
        if key in folders:
            raise ValueError(f"two sources are the same member {key}: {folders[key]} and {folder}")
        folders[key] = folder
        units[key] = read
    present = [key for key in ORDER if key in folders]
    if not present:
        raise ValueError("no sources")
    base = BASE if BASE in folders else present[0]
    members: List[FamilyMember] = []
    for key in present:
        if key == base:
            members.append(FamilyMember(key, _label(key), str(folders[key]), base=True))
            continue
        parents = (base,)
        if key == "hd_msgus" and "hd_msguk" in folders and base != "hd_msguk":
            parents = ("hd_msguk", base)
        members.append(FamilyMember(key, _label(key), str(folders[key]), parents=parents))
    plan = FamilyPlan(
        members=tuple(members),
        read=lambda key: [(unit.uid, unit.text) for unit in units[key]],
    )
    return plan, units


def family_of(plan: FamilyPlan) -> Family:
    """The engine's view of a plan: the units of every member, and the parents of every member."""
    return Family(
        base=plan.base,
        parents={m.key: m.parents for m in plan.members},
        units={m.key: plan.read(m.key) for m in plan.members},
    )


def write_member(source: Path, out: Path, texts: Dict[str, str], rules: GameRules) -> int:
    """Write out/<archive> for every archive of source that has a changed message. Returns the changed file count.

    texts maps a unit id to its new editor text; ids without an entry keep their text. Unchanged archives are not
    written: the build takes them from source.
    """
    out.mkdir(parents=True, exist_ok=True)
    changed_total = 0  # BMG members rewritten
    for archive in sorted(source.glob(ARCHIVE_GLOB)):
        container = RarcContainer(archive.read_bytes())
        changed = 0
        for path in container.list_files():
            if not path.endswith(".bmg"):
                continue
            blob = container.read_file(path)
            current = editor_texts(blob, rules)
            new = [texts.get(f"{archive.name}/{path}#{i}", text) for i, text in enumerate(current)]
            if new == current:
                continue
            container.write_file(path, write_bmg(blob, new, rules))
            changed += 1
        if changed:
            changed_total += changed
            atomic_write_bytes(out / archive.name, container.pack())
    return changed_total


def read_translation(folder: Path, source: Dict[str, str], rules: GameRules) -> Dict[str, str]:
    """Translated text per unit id from a translation folder. A message that still reads as its source is untranslated."""
    if not folder.is_dir():
        return {}
    return {unit.uid: ("" if source.get(unit.uid) == unit.text else unit.text) for unit in scan(folder, rules)}


def _load(config_path: Path) -> Tuple[dict, FamilyPlan, Dict[str, List[Unit]], GameRules]:
    config = json.loads(config_path.read_text(encoding="utf-8"))
    base_dir = config_path.parent
    rules = make_rules((base_dir / config["project"]) if config.get("project") else None)
    sources = [str((base_dir / entry).resolve()) for entry in config["sources"]]
    plan, units = plan_for_sources(sources, rules)
    config["_dir"] = base_dir
    return config, plan, units, rules


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("command", choices=["plan", "seed", "fanout"])
    parser.add_argument("family", type=Path, help="path to the family file (json)")
    parser.add_argument("--member", help="fanout: the member key")
    parser.add_argument("--out", type=Path, help="fanout: the folder to write the archives to")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args(argv)
    config, plan, units, rules = _load(args.family)
    store_path = config["_dir"] / config.get("store", "family_translations.json")
    if args.command == "plan":
        for member in plan.members:
            parents = ", ".join(member.parents) or "none (base)"
            print(f"{member.key} ({member.label}): {len(units[member.key])} messages, parents: {parents}")
        return 0
    if args.command == "seed":
        translations: Dict[str, Dict[str, str]] = {}
        for member in plan.members:
            folder = config.get("translations", {}).get(member.key)
            if folder:
                source = {u.uid: u.text for u in units[member.key]}
                translations[member.key] = read_translation(config["_dir"] / folder, source, rules)
        store, warnings = seed(family_of(plan), translations)
        save_store(store_path, store)
        print(f"wrote {store_path}: {sum(len(v) for v in store['texts'].values())} stored texts, "
              f"{len(warnings)} warnings")
        for line in warnings:
            print("  warning:", line)
        return 0
    if not args.member or not args.out:
        parser.error("fanout needs --member and --out")
    store = load_store(store_path, plan.base)
    per_unit, warnings = fanout(family_of(plan), store, args.member)
    print(f"{args.member}: {sum(1 for t in per_unit.values() if t is not None)} messages get a family translation")
    for line in warnings:
        print("  warning:", line)
    if not args.dry_run:
        texts = {uid: text for uid, text in per_unit.items() if text is not None}
        written = write_member(Path(plan.member(args.member).path), args.out, texts, rules)
        print(f"{args.member}: rewrote {written} message files (members)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
