"""Write the ``font`` entry of a Generation III facts file: where the ROM keeps the normal text font.

The tables are found by their bytes, not by an address from a map: the half-row table (256 bytes) and the normal
width table (512 bytes, from the decompilation's text.c) must occur exactly where the source says they do in order.
The glyph table lies directly before the width table; the check decodes glyph 'A' and stops when it is not a letter.
Only addresses and the window numbers are written. Nothing of the game is copied into the repository.

Usage (run from the repository root):
    python tools/pokemon_fr_font_facts.py --decomp <port\\pokefirered> --rom <unedited ROM> \\
        --facts plugins/pokemon_fr/rom_facts/firered_usa_rev0.json
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
from pathlib import Path
from typing import List

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from plugins.common.gba_text_font import GLYPH_BYTES, decode_glyph  # noqa: E402

GLYPHS = 512
LETTER_A = 0xBB           # the text byte of 'A' in every Generation III charmap
WINDOW = {                 # the message box, measured from a FireRed frame (text origin x=16, two lines)
    "text_x": 16, "text_width": 216, "lines": 2, "line_height": 16, "box_width": 240, "box_height": 56,
    "source": "measured on the FireRed rev0 proof frame; the box edge is an estimate",
}


def _numbers(body: str) -> List[int]:
    return [int(x, 0) for x in re.findall(r"0[xX][0-9A-Fa-f]+|\b\d+\b", re.sub(r"//.*", "", body))]


def _array(text: str, name: str) -> List[int]:
    match = re.search(name + r"\[\] =\s*\{(.*?)\};", text, re.S)
    if match is None:
        raise SystemExit(f"{name} is not in the source")
    return _numbers(match.group(1))


def _occurrences(rom: bytes, needle: bytes) -> List[int]:
    found, at = [], rom.find(needle)
    while at >= 0:
        found.append(at)
        at = rom.find(needle, at + 1)
    return found


def _sources(decomp: Path) -> str:
    """The text of every C source of the decompilation, read once (a table may live in any of them)."""
    return "\n".join(path.read_text(encoding="utf-8", errors="replace") for path in sorted((decomp / "src").glob("*.c")))


def locate(decomp: Path, rom: bytes) -> dict:
    sources = _sources(decomp)
    text_c = (decomp / "src" / "text.c").read_text(encoding="utf-8")
    widths_name = next(name for name in re.findall(r"(?:static )?const u8 (\w*FontNormal\w*LatinGlyphWidths)\[\]", sources)
                       if "Copy" not in name)
    widths = bytes(_array(sources, widths_name))
    half_rows = bytes(_array(sources, "sFontHalfRowOffsets"))
    if len(widths) != GLYPHS or len(half_rows) != 256:
        raise SystemExit("unexpected table sizes in the source")
    hits = _occurrences(rom, widths)
    if len(hits) != 1:
        # Identical copies (a normal font and its copy): take the one at the normal font's source position.
        names = re.findall(r"(?:static )?const u8 (\w*LatinGlyphWidths)\[\]", text_c)
        same = [name for name in names if bytes(_array(text_c, name)) == widths]
        if len(hits) != len(same) or widths_name not in same:
            raise SystemExit(f"width table found {len(hits)} times; cannot tell which copy is the normal font")
        hits_index = same.index(widths_name)
    else:
        hits_index = 0
    half_hits = _occurrences(rom, half_rows)
    if len(half_hits) != 1:
        raise SystemExit(f"half-row table found {len(half_hits)} times; expected one")
    width_table = hits[hits_index]
    glyph_table = width_table - GLYPHS * GLYPH_BYTES
    glyph_a = decode_glyph(rom[glyph_table + LETTER_A * GLYPH_BYTES:glyph_table + (LETTER_A + 1) * GLYPH_BYTES],
                           rom[half_hits[0]:half_hits[0] + 256])
    ink_rows = [y for y in range(14) if any(v == 1 for v in glyph_a[y])]
    if widths[LETTER_A] != 6 or not ink_rows or ink_rows[0] < 2 or ink_rows[-1] > 13:
        raise SystemExit("glyph 'A' does not decode as a letter; the glyph table is not where expected")
    return {"half_row_table": half_hits[0], "width_table": width_table, "glyph_table": glyph_table,
            "glyph_count": GLYPHS, "window": WINDOW}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("--decomp", required=True, type=Path)
    parser.add_argument("--rom", required=True, type=Path)
    parser.add_argument("--facts", required=True, type=Path)
    args = parser.parse_args()
    rom = args.rom.read_bytes()
    text = args.facts.read_text(encoding="utf-8")
    facts = json.loads(text)
    if hashlib.sha1(rom).hexdigest() != facts["rom_sha1"]:
        raise SystemExit("this ROM is not the one the facts file was made from")
    font_line = '"font": ' + json.dumps(locate(args.decomp, rom), ensure_ascii=False) + ","
    # One line for the font entry, placed after rom_size: the rest of the file keeps its layout.
    lines = [line for line in text.split("\n") if not line.startswith('"font":')]
    at = next(i for i, line in enumerate(lines) if line.startswith('"rom_size"'))
    lines.insert(at + 1, font_line)
    args.facts.write_text("\n".join(lines), encoding="utf-8", newline="\n")
    print("font", font_line)


if __name__ == "__main__":
    main()
