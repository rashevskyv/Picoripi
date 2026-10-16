"""Write the ``places`` of a Generation III facts file: the other places in the image that hold a text a unit already has.

A text the image holds twice is one text. The unit keeps its first place; every other place with the same bytes (the
terminator included) is listed under the unit's label, so one edit writes all of them. A copy counts only when it is a
text: at least three letters, and it starts after a terminator or a byte that is not a character. Nothing is written
into the ROM; the facts file gets one key, ``places``: label -> offsets.

Usage (run from the repository root):
    python tools/pokemon_fr_copies.py --rom <unedited ROM> --facts plugins/pokemon_fr/rom_facts/firered_usa_rev0.json
"""
from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path
from typing import Dict, List

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "tools"))

from plugins.pokemon_fr import rom_text  # noqa: E402
from pokemon_fr_braille_facts import write_keys  # noqa: E402

BASE = 0x08000000
TERMINATOR = 0xFF
MIN_LETTERS = 3


def find_copies(rom: bytes, units: List[rom_text.Unit], charmap: rom_text.Charmap) -> Dict[str, List[int]]:
    """Per unit label: the offsets of its uncovered copies in the ROM."""
    covered = bytearray(len(rom))
    for unit in units:
        for start in (unit.offset, *unit.places):
            end = min(len(rom), start + unit.size)
            covered[start:end] = b"\x01" * (end - start)
    copies: Dict[str, List[int]] = {}
    seen = set()
    for unit in units:
        if unit.braille or unit.size < 4:
            continue
        body = rom[unit.offset:unit.offset + unit.size]
        if body[-1] != TERMINATOR or body in seen:
            continue
        if sum(ch.isalpha() for ch in charmap.decode(body[:-1])) < MIN_LETTERS:
            continue
        seen.add(body)
        spot = rom.find(body)
        while spot >= 0:
            starts_text = spot == 0 or rom[spot - 1] == TERMINATOR or rom[spot - 1] not in charmap.char_of
            if starts_text and spot != unit.offset and covered.find(b"\x01", spot, spot + len(body)) < 0:
                copies.setdefault(unit.label, []).append(spot)
            spot = rom.find(body, spot + 1)
    return copies


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("--rom", required=True, type=Path)
    parser.add_argument("--facts", required=True, type=Path)
    args = parser.parse_args()
    rom = args.rom.read_bytes()
    facts = json.loads(args.facts.read_text(encoding="utf-8"))
    if hashlib.sha1(rom).hexdigest() != facts["rom_sha1"]:
        raise SystemExit("this ROM is not the one the facts file was made from")
    if "places" in facts:
        raise SystemExit("the facts already hold places; rebuild the facts from their committed version first")
    charmap = rom_text.Charmap.load(rom_text.FACTS_DIR / facts["charmap"])
    units = list(rom_text.load_units(args.facts)[0]) + rom_text.load_tables(args.facts)
    copies = find_copies(rom, units, charmap)
    places = {label: sorted(spots) for label, spots in sorted(copies.items())}
    write_keys(args.facts, {"places": places})
    print("places", sum(len(spots) for spots in places.values()), "in", len(places), "texts", flush=True)


if __name__ == "__main__":
    main()
