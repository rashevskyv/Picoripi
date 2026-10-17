"""Write the ``font`` entry of a Ruby or Sapphire facts file: where the ROM keeps the message font (font 3, 4bpp).

The 4bpp glyph table is rebuilt from the decompilation's font PNG (indexed, 128 x 256, tiles of 8 x 8) and searched in
the ROM. Three tile layouts are tried; exactly one must match. The width table is the decompilation's numbers
(src/data/text/font3_widths.h, the revision 1 block or the revision 0 block). Only addresses and window numbers are
written. Nothing of the game is copied into the repository.

Usage (run from the repository root):
    python tools/pokemon_ruby_font_facts.py --decomp <port\\pokeruby> --rom <unedited ROM> \\
        --facts plugins/pokemon_fr/rom_facts/ruby_usa_rev0.json --revision 0
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
from pathlib import Path
from typing import Dict, List

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from plugins.common.gba_text_font import GLYPH4_BYTES  # noqa: E402

GLYPHS = 256
TILE_COLUMNS = 16          # the PNG is 16 tiles wide (128 px)
TILE_BYTES = 32
LETTER_A = 0xBB            # the text byte of 'A' in every Generation III charmap
# The message window, from the decompilation: Contest_StartTextPrinter(window, text, tiles, left 2, top 15),
# sLineLength 26 for field messages, and the dialogue frame of text_window.c (left 0, top 14, width 26, height 4).
TEXT_LEFT_TILE = 2
TEXT_TOP_TILE = 15
LINE_TILES = 26
WINDOW_HEIGHT_TILES = 4
FRAME_TOP_TILE = 14
LINE_HEIGHT = 16           # a glyph is 16 pixels tall; the Ruby text printer steps one glyph height per line


# The PNG index to the GBA nibble: paper 0, ink 1 (nibble 15), shadow 2 (nibble 14). Checked on glyph 'A' of rev 0.
NIBBLE = {0: 0, 1: 0xF, 2: 0xE}


def _tile(image, tx: int, ty: int) -> bytes:
    out = bytearray()
    for row in range(8):
        for pair in range(4):
            lo = NIBBLE[image.pixelIndex(tx * 8 + 2 * pair, ty * 8 + row)]
            hi = NIBBLE[image.pixelIndex(tx * 8 + 2 * pair + 1, ty * 8 + row)]
            out.append(lo | (hi << 4))
    return bytes(out)


def _layouts(image) -> Dict[str, bytes]:
    """The 4bpp glyph table under each candidate tile layout (glyph = upper tile, then lower tile)."""
    tiles: Dict[int, bytes] = {}

    def tile_at(index: int) -> bytes:
        if index not in tiles:
            tiles[index] = _tile(image, index % TILE_COLUMNS, index // TILE_COLUMNS)
        return tiles[index]

    layouts = {
        # Column-major pairs: glyph g is column g % 16 of tile rows 2 * (g // 16) and the row below.
        "pairs_by_row": lambda g: (tile_at(2 * (g // 16) * TILE_COLUMNS + g % 16),
                                   tile_at((2 * (g // 16) + 1) * TILE_COLUMNS + g % 16)),
        # Linear pairs: glyph g is tiles 2g and 2g + 1 in reading order.
        "linear_pairs": lambda g: (tile_at(2 * g), tile_at(2 * g + 1)),
        # Two halves: upper tiles of all glyphs first, then the lower tiles.
        "two_halves": lambda g: (tile_at(g), tile_at(g + GLYPHS)),
    }
    out = {}
    for name, pick in layouts.items():
        out[name] = b"".join(upper + lower for upper, lower in (pick(g) for g in range(GLYPHS)))
    return out


def _widths(decomp: Path, revision: int) -> bytes:
    text = (decomp / "src" / "data" / "text" / "font3_widths.h").read_text(encoding="utf-8")
    blocks = re.findall(r"static const u8 sFont3Widths\[\] = \{(.*?)\};", text, re.S)
    if len(blocks) < 2:
        raise SystemExit("font3_widths.h must hold the English revision 1 and revision 0 blocks")
    # The first two blocks are the English ones (#if ENGLISH, then #if REVISION >= 1 and #else).
    block = blocks[0] if revision >= 1 else blocks[1]
    # The C array has 254 entries (the glyph table has 256); the game reads no width past the array.
    values = [int(x, 0) for x in re.findall(r"0[xX][0-9A-Fa-f]+|\b\d+\b", block)]
    if not 250 <= len(values) <= GLYPHS:
        raise SystemExit(f"width table has {len(values)} entries")
    return bytes(values)


def _offsets(rom: bytes, needle: bytes) -> List[int]:
    found, at = [], rom.find(needle)
    while at >= 0:
        found.append(at)
        at = rom.find(needle, at + 1)
    return found


def locate(decomp: Path, rom: bytes, revision: int, png: Path) -> Dict[str, object]:
    from PyQt6.QtGui import QImage

    image = QImage(str(png))
    if image.width() != 128 or image.height() != 256:
        raise SystemExit("the font PNG is not 128 x 256")
    widths = _widths(decomp, revision)
    # Revisions 1 and 2 keep the same width bytes in two places; the copies are equal, so the first is used.
    width_copies = _offsets(rom, widths)
    if not width_copies:
        raise SystemExit("width table is not in the ROM")
    width_at = width_copies[0]
    # The first glyphs (the ones the width table covers) must match exactly; the last glyphs may differ.
    matches = {}
    for name, table in _layouts(image).items():
        prefix = table[:len(widths) * GLYPH4_BYTES]
        if rom.find(prefix) >= 0:
            matches[name] = rom.find(prefix)
    if len(matches) != 1:
        raise SystemExit(f"glyph table matches {sorted(matches)}; expected exactly one layout")
    layout, glyph_at = next(iter(matches.items()))
    glyph_a = rom[glyph_at + LETTER_A * GLYPH4_BYTES:glyph_at + (LETTER_A + 1) * GLYPH4_BYTES]
    if not any(glyph_a):
        raise SystemExit("glyph 'A' is blank; the table is not where expected")
    return {
        "kind": "gen3_4bpp", "layout": layout, "glyph_table": glyph_at, "width_table": width_at,
        "glyph_count": GLYPHS, "width_count": len(widths), "width_copies": len(width_copies),
        "glyph_bytes": GLYPH4_BYTES,
        "window": {
            # Measured on the rev 0 Oak frame (proof): the first ink column is x 24 and the first ink rows are
            # y 114 and 130 (line step 16); the paper runs x 22..217. The box origin is (16, 104) on screen.
            # The text width is 24 tiles: the paper is 196 px wide, and the decompilation's sLineLength 26 would be
            # 208 px. A clip test in the emulator has not been done (see the status JSON).
            "text_x": 8, "text_top": 8, "text_width": 192, "lines": WINDOW_HEIGHT_TILES * 8 // LINE_HEIGHT,
            "line_height": LINE_HEIGHT, "box_width": 208, "box_height": (WINDOW_HEIGHT_TILES + 2) * 8,
            "source": ("measured on the rev 0 proof frame (text x 24, line tops 114 and 130, paper 22..217); "
                       "decomp font 3 at window tile (2,15), sLineLength 26; width estimated"),
        },
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("--decomp", required=True, type=Path)
    parser.add_argument("--rom", required=True, type=Path)
    parser.add_argument("--facts", required=True, type=Path)
    parser.add_argument("--revision", required=True, type=int, choices=(0, 1, 2))
    args = parser.parse_args()
    rom = args.rom.read_bytes()
    text = args.facts.read_text(encoding="utf-8")
    facts = json.loads(text)
    if hashlib.sha1(rom).hexdigest() != facts["rom_sha1"]:
        raise SystemExit("this ROM is not the one the facts file was made from")
    png_name = "font3_lat.png" if args.revision == 0 else "font3_lat_rev1.png"
    font = locate(args.decomp, rom, args.revision, args.decomp / "graphics" / "fonts" / png_name)
    font_line = '"font": ' + json.dumps(font, ensure_ascii=False) + ","
    lines = [line for line in text.split("\n") if not line.startswith('"font":')]
    at = next(i for i, line in enumerate(lines) if line.startswith('"rom_size"'))
    lines.insert(at + 1, font_line)
    args.facts.write_text("\n".join(lines), encoding="utf-8", newline="\n")
    print("font", font_line)


if __name__ == "__main__":
    main()
