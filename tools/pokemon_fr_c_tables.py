"""Write the ``c_tables`` entries of a Generation III facts file: fixed-size name fields that the C code reads.

A C-built name is not a message: it sits in a fixed slot and nothing points to it. Each name field is text, the
terminator 0xFF, then padding up to the field size (padding bytes are 0x00 or 0xFF; a table can mix them after its
first terminator, as the move names do). A field inside a struct is found the same way: ``size`` is the field, and
``stride`` is the struct. The table is located by its first named entries: ``first`` lists the names of consecutive
entries, ``first_index`` gives the index of the first name. The search needs one hit whose entries after it are the
same names at the same stride, so a name that also occurs elsewhere in the ROM does not match by itself.

The length of a table is ``count`` when the table declares one, and otherwise the number of fields of the shape that
follow the start. Each count is checked against the decompilation's constant, so a wrong stride or start stops the tool.

Usage (run from the repository root):
    python tools/pokemon_fr_c_tables.py --rom <unedited ROM> --facts plugins/pokemon_fr/rom_facts/firered_usa_rev0.json
"""
from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path
from typing import Dict, List, Optional, Tuple

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from plugins.pokemon_fr import rom_text  # noqa: E402

TERMINATOR = 0xFF
SPACE = 0x00            # the charmap cell of ' '; a name never starts with it in these tables
PADS = (0x00, 0xFF)

# The tables of the Generation III facts. ``first`` names start at index ``first_index`` (the index is the
# decompilation's constant, read from its headers). ``count`` is the decompilation's count, and the table must have
# exactly that many entries; without ``count`` the table ends where the name shape ends. A missing ``stride`` is
# found from the names. Each game family has its own trainer and class anchors: their names repeat in the ROM.
SPECIES = {"name": "species", "file": "species_names.inc", "label": "gSpeciesName_", "stride": 11, "size": 11,
           "first": ["BULBASAUR", "IVYSAUR", "VENUSAUR"], "first_index": 1, "count": 412}
MOVES = {"name": "moves", "file": "move_names.inc", "label": "gMoveName_", "stride": 13, "size": 13,
         "first": ["-", "POUND", "KARATE CHOP"], "first_index": 0, "count": 355}
ABILITIES = {"name": "abilities", "file": "ability_names.inc", "label": "gAbilityName_", "stride": 13,
             "size": 13, "first": ["-------", "STENCH", "DRIZZLE"], "first_index": 0, "count": 78}
TYPES = {"name": "types", "file": "type_names.inc", "label": "gTypeName_", "stride": 7, "size": 7,
         "first": ["NORMAL", "FIGHT", "FLYING"], "first_index": 0, "count": 18}
ITEMS = {"name": "items", "file": "item_names.inc", "label": "gItemName_", "size": 14,
         "first": ["MASTER BALL", "ULTRA BALL", "GREAT BALL"], "first_index": 1}   # count per family below
BERRIES = {"name": "berries", "file": "berry_names.inc", "label": "gBerryName_", "size": 7,
           "first": ["CHERI", "CHESTO", "PECHA"], "first_index": 0, "count": 43}
COMMON = [SPECIES, MOVES, ABILITIES, TYPES, BERRIES]
FAMILY_TABLES = {
    "firered": [
        {**ITEMS, "count": 375},
        {"name": "trainer_classes", "file": "trainer_class_names.inc", "label": "gTrainerClassName_",
         "stride": 13, "size": 13, "first": ["AQUA LEADER", "TEAM AQUA"], "first_index": 2, "count": 107},
        {"name": "trainer_names", "file": "trainer_names.inc", "label": "gTrainerName_", "stride": 40,
         "size": 12, "first": ["SIDNEY", "PHOEBE", "ROXANNE"], "first_index": 25, "count": 743},
    ],
    "emerald": [
        {**ITEMS, "count": 377},
        {"name": "trainer_classes", "file": "trainer_class_names.inc", "label": "gTrainerClassName_",
         "stride": 13, "size": 13, "first": ["HIKER", "TEAM AQUA", "{PKMN} BREEDER"], "first_index": 2,
         "count": 66},
        {"name": "trainer_names", "file": "trainer_names.inc", "label": "gTrainerName_", "stride": 40,
         "size": 12, "first": ["MARCEL", "ALBERTO", "ED"], "first_index": 11, "count": 855},
    ],
    "ruby": [
        {**ITEMS, "count": 349},
        {"name": "trainer_classes", "file": "trainer_class_names.inc", "label": "gTrainerClassName_",
         "stride": 13, "size": 13, "first": ["AQUA LEADER", "TEAM AQUA", "AQUA ADMIN"], "first_index": 2,
         "count": 58},
        {"name": "trainer_names", "file": "trainer_names.inc", "label": "gTrainerName_", "stride": 40,
         "size": 12, "first": ["RANDALL", "PARKER", "GEORGE"], "first_index": 71, "count": 694},
    ],
}


def family_of(game: str) -> str:
    """The game family of a facts file: its tables and trainer anchors differ between the three."""
    if "Emerald" in game:
        return "emerald"
    if "Ruby" in game or "Sapphire" in game:
        return "ruby"
    return "firered"


def tables_for(game: str) -> List[Dict[str, object]]:
    return COMMON + FAMILY_TABLES[family_of(game)]


def _field(charmap: rom_text.Charmap, text: str) -> Optional[bytes]:
    """The bytes of a name with its terminator, or None when a character has no cell."""
    try:
        return charmap.encode(text)
    except rom_text.CodecError:
        return None


def _shape(raw: bytes, charmap: rom_text.Charmap) -> Tuple[bool, Optional[int]]:
    """``(is a name field, its padding byte)``. The padding byte is None when the name fills the field."""
    if not raw or raw[0] == SPACE:
        return False, None
    end = raw.find(TERMINATOR)
    body = raw if end < 0 else raw[:end]
    if body and "{0x" in charmap.decode(body):
        return False, None
    if end < 0:
        return True, None
    rest = raw[end + 1:]
    if any(b not in PADS for b in rest):
        return False, None
    return True, (rest[0] if rest else None)


def _find_start(rom: bytes, charmap: rom_text.Charmap, spec: Dict[str, object]) -> Tuple[int, int]:
    """``(start of entry 0, stride)`` of the table, with one hit only."""
    names = list(spec["first"])
    needles = [_field(charmap, name) for name in names]
    if any(needle is None for needle in needles):
        raise SystemExit(f"{spec['name']}: a first name has no cell in the charmap")
    index = int(spec.get("first_index", 0))
    stride = spec.get("stride")
    stride = int(stride) if stride else None
    size = int(spec["size"])
    occurrences = []
    for needle in needles:
        found, at = [], rom.find(needle)
        while at >= 0:
            found.append(at)
            at = rom.find(needle, at + 1)
        occurrences.append(found)
    hits: List[Tuple[int, int]] = []
    if stride is not None:
        for at in occurrences[0]:
            if all(rom.startswith(needles[k], at + k * stride) for k in range(len(names))):
                hits.append((at - index * stride, stride))
    else:
        for at in occurrences[0]:
            for later in occurrences[1]:
                step = later - at
                if step < size:
                    continue
                if all(rom.startswith(needles[k], at + k * step) for k in range(len(names))):
                    hits.append((at - index * step, step))
    hits = sorted(set(hits))
    if len(hits) != 1:
        raise SystemExit(f"{spec['name']}: the first names give {len(hits)} tables; expected one")
    return hits[0]


def locate(rom: bytes, charmap: rom_text.Charmap, spec: Dict[str, object]) -> Dict[str, object]:
    """The facts of one table: start, stride, field size, count and padding byte."""
    start, stride = _find_start(rom, charmap, spec)
    size = int(spec["size"])
    expected = spec.get("count")
    count = 0
    limit = int(expected) if expected is not None else 1 << 20
    while count < limit:
        at = start + count * stride
        if at + size > len(rom):
            break
        ok, _ = _shape(rom[at:at + size], charmap)
        if not ok:
            break
        count += 1
    if expected is not None and count != int(expected):
        raise SystemExit(f"{spec['name']}: {count} entries of the table shape; the decompilation has {expected}")
    if count == 0:
        raise SystemExit(f"{spec['name']}: no entries")
    # The padding byte is the one most fields carry after their terminator (a move name table mixes both).
    trailing: Dict[int, int] = {}
    for item in range(count):
        at = start + item * stride
        raw = rom[at:at + size]
        end = raw.find(TERMINATOR)
        for byte in raw[end + 1:] if end >= 0 else b"":
            trailing[byte] = trailing.get(byte, 0) + 1
    pad = max(trailing, key=trailing.get) if trailing else 0
    return {"name": spec["name"], "file": spec["file"], "label": spec["label"], "offset": start,
            "stride": stride, "size": size, "count": count, "pad": pad}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("--rom", required=True, type=Path)
    parser.add_argument("--facts", required=True, type=Path)
    args = parser.parse_args()
    rom = args.rom.read_bytes()
    text = args.facts.read_text(encoding="utf-8")
    facts = json.loads(text)
    if hashlib.sha1(rom).hexdigest() != facts["rom_sha1"]:
        raise SystemExit("this ROM is not the one the facts file was made from")
    charmap = rom_text.Charmap.load(rom_text.FACTS_DIR / facts["charmap"])
    tables = [locate(rom, charmap, spec) for spec in tables_for(facts["game"])]
    line = '"c_tables": ' + json.dumps(tables, ensure_ascii=False) + ","
    lines = [item for item in text.split("\n") if not item.startswith('"c_tables":')]
    at = next(i for i, item in enumerate(lines) if item.startswith('"rom_size"'))
    lines.insert(at + 1, line)
    args.facts.write_text("\n".join(lines), encoding="utf-8", newline="\n")
    print("c_tables", line)


if __name__ == "__main__":
    main()
