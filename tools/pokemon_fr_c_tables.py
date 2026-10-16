"""Write the ``c_tables`` entry of a Generation III facts file: fixed-size name tables that the C code reads.

A C-built table is not a message: its entries have a fixed stride. Each entry is text, the terminator 0xFF, then
one padding byte (0x00 or 0xFF, the same for the whole table) up to the stride. The table is found by its first
named entries (the search needs the charmap of the facts file). Its length is the number of entries of that shape
counted from the start; an entry whose text starts with a space (the 0x00 cell) ends the table. The stride is the
size of each entry; the editor can only write a name that fits, so the build refuses a longer one.

Usage (run from the repository root):
    python tools/pokemon_fr_c_tables.py --rom <unedited ROM> --facts plugins/pokemon_fr/rom_facts/firered_usa_rev0.json
"""
from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path
from typing import Dict, List, Optional

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from plugins.pokemon_fr import rom_text  # noqa: E402

TERMINATOR = 0xFF
SPACE = 0x00            # the charmap cell of ' '; a name never starts with it in these tables
SPECIES = {"name": "species", "file": "species_names.inc", "label": "gSpeciesName_", "stride": 11,
           "first": ["BULBASAUR", "IVYSAUR", "VENUSAUR"]}
TABLES = [SPECIES]


def _encode(charmap: rom_text.Charmap, text: str, stride: int, pad: int) -> Optional[bytes]:
    try:
        body = bytes(charmap.byte_of[ch] for ch in text)
    except KeyError:
        return None
    return body + bytes([TERMINATOR]) + bytes([pad]) * (stride - len(body) - 1)


def _shape(raw: bytes, charmap: rom_text.Charmap) -> Optional[Optional[int]]:
    """The padding byte of an entry of the table shape (None inside the result when the name fills the entry),
    or None when the entry is not one."""
    end = raw.find(TERMINATOR)
    if not 0 < end < len(raw) or raw[0] == SPACE or not all(b in charmap.char_of for b in raw[:end]):
        return None
    pad = raw[end + 1:]
    if not pad:
        return (None,)
    if len(set(pad)) != 1 or pad[0] not in (SPACE, TERMINATOR):
        return None
    return (pad[0],)


def locate(rom: bytes, charmap: rom_text.Charmap, spec: Dict[str, object]) -> Dict[str, object]:
    stride = int(spec["stride"])
    names = list(spec["first"])
    hits: List[int] = []
    for pad in (SPACE, TERMINATOR):
        needle = b"".join(_encode(charmap, name, stride, pad) for name in names)
        hits = []
        at = rom.find(needle)
        while at >= 0:
            hits.append(at)
            at = rom.find(needle, at + 1)
        if len(hits) == 1:
            break
    if len(hits) != 1:
        raise SystemExit(f"{spec['name']}: the first entries are found {len(hits)} times; expected one")
    # The table begins with the entry before the first name when that entry has the same shape (index 0, unnamed).
    start = hits[0]
    if _shape(rom[start - stride:start], charmap) is not None:
        start -= stride
    pad = _shape(rom[start + stride:start + 2 * stride], charmap)[0]
    count = 0
    while True:
        shape = _shape(rom[start + count * stride:start + (count + 1) * stride], charmap)
        if shape is None or shape[0] not in (None, pad):
            break
        count += 1
    return {"name": spec["name"], "file": spec["file"], "label": spec["label"], "offset": start,
            "stride": stride, "count": count, "pad": pad}


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
    tables = [locate(rom, charmap, spec) for spec in TABLES]
    line = '"c_tables": ' + json.dumps(tables, ensure_ascii=False) + ","
    lines = [item for item in text.split("\n") if not item.startswith('"c_tables":')]
    at = next(i for i, item in enumerate(lines) if item.startswith('"rom_size"'))
    lines.insert(at + 1, line)
    args.facts.write_text("\n".join(lines), encoding="utf-8", newline="\n")
    print("c_tables", line)


if __name__ == "__main__":
    main()
