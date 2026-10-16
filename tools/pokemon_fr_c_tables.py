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
import struct
import sys
from pathlib import Path
from typing import Dict, List, Optional, Tuple

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from plugins.pokemon_fr import rom_text  # noqa: E402

sys.path.insert(0, str(ROOT / "tools"))
from pokemon_fr_rom_facts import map_symbols  # noqa: E402

BASE = 0x08000000        # the ROM address of file offset 0 (the GBA cartridge)
MAX_TEXT = 1200          # the longest text the pointer tables are measured over

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


# Tables found through a linker-map symbol: ``symbol`` is the array, ``field`` the offset of the name or of the
# pointer inside each entry. A pointer table (``pointer``) holds one pointer per entry to a text ending in 0xFF;
# each distinct text becomes a unit that may grow (it moves, its pointers are rewritten).
FIRERED_POINTERS = [
    {"name": "move_descriptions", "file": "move_descriptions.inc", "label": "gMoveDescription_",
     "symbol": "gMoveDescriptionPointers", "stride": 4, "field": 0, "count": 354, "pointer": True},
    {"name": "ability_descriptions", "file": "ability_descriptions.inc", "label": "gAbilityDescription_",
     "symbol": "gAbilityDescriptionPointers", "stride": 4, "field": 0, "count": 78, "pointer": True},
    {"name": "nature_names", "file": "nature_names.inc", "label": "gNatureName_",
     "symbol": "gNatureNamePointers", "stride": 4, "field": 0, "count": 25, "pointer": True},
    {"name": "item_descriptions", "file": "item_descriptions.inc", "label": "gItemDescription_",
     "symbol": "gItems", "stride": 44, "field": 20, "count": 375, "pointer": True},
    {"name": "pokedex_descriptions", "file": "pokedex_descriptions.inc", "label": "gPokedexDescription_",
     "symbol": "gPokedexEntries", "stride": 36, "field": 16, "count": 387, "pointer": True},
]
FIRERED_CATEGORIES = {"name": "pokedex_categories", "file": "pokedex_categories.inc",
                      "label": "gPokedexCategory_", "symbol": "gPokedexEntries", "stride": 36, "size": 12,
                      "field": 0, "count": 387}


# Ruby and Sapphire name the same arrays differently; their Pokedex entry is FireRed's (36 bytes).
RUBY_POINTERS = [
    dict(FIRERED_POINTERS[0], symbol="gMoveDescriptions"),
    dict(FIRERED_POINTERS[1], symbol="gAbilityDescriptions"),
    dict(FIRERED_POINTERS[2], symbol="gNatureNames"),
    dict(FIRERED_POINTERS[3], count=349),
    FIRERED_POINTERS[4],
    FIRERED_CATEGORIES,
]


def family_of(game: str) -> str:
    """The game family of a facts file: its tables and trainer anchors differ between the three."""
    if "Emerald" in game:
        return "emerald"
    if "Ruby" in game or "Sapphire" in game:
        return "ruby"
    return "firered"


def tables_for(game: str) -> List[Dict[str, object]]:
    family = family_of(game)
    if family == "firered":
        return COMMON + FAMILY_TABLES[family] + FIRERED_POINTERS + [FIRERED_CATEGORIES]
    if family == "emerald":
        # Emerald's Pokedex entry is 32 bytes (FireRed's is 36): the same fields at the same offsets
        # Emerald has 377 items (FireRed 375): the item descriptions count the same entries as the item names
        changes = {"gPokedexEntries": {"stride": 32}, "gItems": {"count": 377}}
        return COMMON + FAMILY_TABLES[family] + [
            dict(spec, **changes.get(str(spec.get("symbol")), {})) for spec in FIRERED_POINTERS + [FIRERED_CATEGORIES]]
    if family == "ruby":
        return COMMON + FAMILY_TABLES[family] + RUBY_POINTERS
    return COMMON + FAMILY_TABLES[family]


def _text_at(rom: bytes, ptr: int, charmap: rom_text.Charmap) -> Optional[Tuple[int, int]]:
    """``(offset, size with the terminator)`` of the text a pointer names, or None when it names no text."""
    off = ptr - BASE
    if not 0 < off < len(rom):
        return None
    end = rom.find(bytes([TERMINATOR]), off, off + MAX_TEXT)
    if end < off:
        return None
    text = charmap.decode(rom[off:end])
    if "{0x" in text:
        return None
    plain = sum(1 for ch in text if (ch.isascii() and (ch.isalnum() or ch in " .,!?'-/&:%+()\\\"") or ch == "\u00e9"))
    if text and plain < 0.7 * len(text):
        return None
    return off, end + 1 - off


def pointer_table(rom: bytes, charmap: rom_text.Charmap, symbols: Dict[str, int], spec: Dict[str, object]) -> Dict[str, object]:
    """The texts a pointer table names: one unit per distinct text, the index of its first entry in the label."""
    base = symbols[str(spec["symbol"])] - BASE
    stride, field, count = int(spec["stride"]), int(spec["field"]), int(spec["count"])
    units: List[List[int]] = []
    seen: Dict[int, int] = {}
    for index in range(count):
        ptr = struct.unpack_from("<I", rom, base + index * stride + field)[0]
        found = _text_at(rom, ptr, charmap)
        if found is None:
            raise SystemExit(f"{spec['name']}: entry {index} does not name a text")
        off, size = found
        if off not in seen:
            seen[off] = index
            units.append([index, off, size])
    return {"name": spec["name"], "file": spec["file"], "label": spec["label"], "kind": "pointer",
            "offset": base, "stride": stride, "field": field, "count": count, "units": units}


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


def locate(rom: bytes, charmap: rom_text.Charmap, spec: Dict[str, object],
           symbols: Optional[Dict[str, int]] = None) -> Dict[str, object]:
    """The facts of one table: start, stride, field size, count and padding byte."""
    if "symbol" in spec:
        start, stride = (symbols[str(spec["symbol"])] - BASE + int(spec["field"])), int(spec["stride"])
    else:
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
    parser.add_argument("--map", type=Path, help="the link map of the decompilation build of this ROM")
    args = parser.parse_args()
    rom = args.rom.read_bytes()
    text = args.facts.read_text(encoding="utf-8")
    facts = json.loads(text)
    if hashlib.sha1(rom).hexdigest() != facts["rom_sha1"]:
        raise SystemExit("this ROM is not the one the facts file was made from")
    charmap = rom_text.Charmap.load(rom_text.FACTS_DIR / facts["charmap"])
    symbols = map_symbols(args.map)[0] if args.map else {}
    tables = []
    for spec in tables_for(facts["game"]):
        if "symbol" in spec and not symbols:
            print(f"skipped {spec['name']}: no --map")
            continue
        if spec.get("pointer"):
            tables.append(pointer_table(rom, charmap, symbols, spec))
        else:
            tables.append(locate(rom, charmap, spec, symbols))
    line = '"c_tables": ' + json.dumps(tables, ensure_ascii=False) + ","
    lines = [item for item in text.split("\n") if not item.startswith('"c_tables":')]
    at = next(i for i, item in enumerate(lines) if item.startswith('"rom_size"'))
    lines.insert(at + 1, line)
    args.facts.write_text("\n".join(lines), encoding="utf-8", newline="\n")
    print("c_tables", line)


if __name__ == "__main__":
    main()
