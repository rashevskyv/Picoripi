"""Zelda BMG side of family projects: message texts of a BMG archive folder, and writing translated texts back.

A message folder holds the bmgres*.arc archives (for example res/Msgus). Texts are the editor texts of
GameRules, the same strings the project shows. Only members whose text changed are rewritten; the rest of the
archive keeps its bytes. CLI: python -m plugins.zelda_bmg.family plan|seed|fanout <family.json>
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Dict, List, Sequence

from core.containers.rarc_container import RarcContainer
from core.family_projects.align import align
from core.family_projects.store import fanout, load_store, save_store, seed
from utils.atomic_io import atomic_write_bytes

from .rules import GameRules

ARCHIVE_GLOB = "bmgres*.arc"


def editor_texts(bmg: bytes) -> List[str]:
    """The editor texts of one BMG file, in message order."""
    data, _names = GameRules().load_data_from_json_obj(bmg)
    return list(data[0]) if data else []


def write_bmg(source: bytes, texts: Sequence[str]) -> bytes:
    """The BMG of source with the given editor texts; message ids and attributes come from source."""
    rules = GameRules()
    rules.load_data_from_json_obj(source)
    return rules.save_data_to_json_obj([list(texts)], {})


def member_texts(folder: Path) -> Dict[str, List[str]]:
    """Editor texts of every BMG member of the folder's archives, keyed by file name (zel_00.bmg)."""
    texts: Dict[str, List[str]] = {}
    for archive in sorted(folder.glob(ARCHIVE_GLOB)):
        container = RarcContainer(archive.read_bytes())
        for path in container.list_files():
            if path.endswith(".bmg"):
                texts[path.rsplit("/", 1)[-1]] = editor_texts(container.read_file(path))
    return texts


def write_folder(source: Path, target: Path, texts: Dict[str, List[str]]) -> int:
    """Write target/<archive> for every archive of source that has a changed member. Returns the changed members.

    Archives without a change are not written: a translation folder holds only what changed, and the build
    takes every other archive from source.
    """
    target.mkdir(parents=True, exist_ok=True)
    rewritten = 0
    for archive in sorted(source.glob(ARCHIVE_GLOB)):
        container = RarcContainer(archive.read_bytes())
        changed = 0
        for path in container.list_files():
            name = path.rsplit("/", 1)[-1]
            if not path.endswith(".bmg") or name not in texts:
                continue
            blob = container.read_file(path)
            if editor_texts(blob) == list(texts[name]):
                continue
            container.write_file(path, write_bmg(blob, texts[name]))
            changed += 1
        if changed:
            rewritten += changed
            atomic_write_bytes(target / archive.name, container.pack())
    return rewritten


def _read_texts(spec: Path) -> Dict[str, List[str]]:
    """A translation given as an archive folder or as a json file {member: [texts]}."""
    if spec.is_dir():
        return member_texts(spec)
    if spec.is_file():
        return json.loads(spec.read_text(encoding="utf-8"))
    return {}  # no translation yet (a console slot that was never translated)


def _load_family(config_path: Path) -> dict:
    config = json.loads(config_path.read_text(encoding="utf-8"))
    base_dir = config_path.parent
    config["_dir"] = base_dir
    config["_sources"] = {}
    config["_translations"] = {}
    for key, entry in config["consoles"].items():
        config["_sources"][key] = member_texts(base_dir / entry["source"])
        if "translation" in entry:
            config["_translations"][key] = _read_texts(base_dir / entry["translation"])
    return config


def cmd_plan(config: dict) -> None:
    base = config["base"]
    for key, texts in config["_sources"].items():
        if key == base:
            continue
        shared = unique = 0
        for member, own in texts.items():
            if member not in config["_sources"][base]:
                unique += len(own)
                continue
            result = align(config["_sources"][base][member], own)
            shared += len(result.pairs)
            unique += len(result.console_only)
        print(f"{key} vs {base}: shared {shared}, own {unique}")


def cmd_seed(config: dict) -> None:
    store_path = config["_dir"] / config.get("store", "family_translations.json")
    store, warnings = seed(config["base"], config["_sources"], config["_translations"])
    save_store(store_path, store)
    print(f"wrote {store_path}: {len(store['units'])} units, {len(warnings)} warnings")
    for line in warnings:
        print("  warning:", line)


def cmd_fanout(config: dict, console: str, out: Path, dry_run: bool) -> None:
    store_path = config["_dir"] / config.get("store", "family_translations.json")
    store = load_store(store_path, config["base"])
    per_member, warnings = fanout(store, config["_sources"], console)
    filled = sum(1 for values in per_member.values() for value in values if value is not None)
    print(f"{console}: {filled} messages get a family translation")
    for line in warnings:
        print("  warning:", line)
    if dry_run:
        return
    texts = {member: [value if value is not None else current
                      for value, current in zip(values, config["_sources"][console][member])]
             for member, values in per_member.items()}
    print(f"{console}: rewrote {write_folder(config['_dir'] / config['consoles'][console]['source'], out, texts)} members")


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("command", choices=["plan", "seed", "fanout"])
    parser.add_argument("family", type=Path, help="path to family.json")
    parser.add_argument("--console", help="fanout: the console key")
    parser.add_argument("--out", type=Path, help="fanout: the translation folder to write")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args(argv)
    config = _load_family(args.family)
    if args.command == "plan":
        cmd_plan(config)
    elif args.command == "seed":
        cmd_seed(config)
    else:
        if not args.console or not args.out:
            parser.error("fanout needs --console and --out")
        cmd_fanout(config, args.console, args.out, args.dry_run)
    return 0


if __name__ == "__main__":
    sys.exit(main())
