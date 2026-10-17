"""Find the text font of a Game Boy Pokemon ROM by its bytes and write the ``font`` entry of its facts file.

Usage: python tools/pokemon_gb_font_facts.py <decomp dir> <unedited ROM> <facts json>

The decomp's gfx/font/font.png (1 bit per tile row, 128 tiles) and font_extra.png (2 bits, 32 tiles) are
packed the way the decomp's INCBIN files are. The ROM is searched for each block: the file offset of the first
match is the fact. Shade mappings are tried until the block is found, so the tool does not assume a palette.
Only addresses, counts and the text box geometry are written; no glyph is copied into the facts.

The text codes: the main font starts at byte 0x80 (``A`` is 0x80) and the extra font at 0x60. The tool checks
both against the facts' charmap before it writes.
"""
from __future__ import annotations

import itertools
import json
import sys
from pathlib import Path
from typing import Dict, List, Optional, Sequence, Tuple

from PIL import Image

FONT_CODE = 0x80
EXTRA_CODE = 0x60
MAIN_TILES = 128
EXTRA_TILES = 32
# The text box of the game (pret): TextBoxBorder at (0, 12) with 4 rows and 18 columns inside, text on rows 14
# and 16 from column 1. Pixels: 8 x 8 cells.
WINDOW = {"text_x": 8, "text_width": 144, "lines": 2, "line_height": 16, "box_width": 160, "box_height": 48,
          "text_top": 16}


def _levels(image: Image.Image) -> Tuple[List[List[int]], List[int]]:
    """The image as rows of grey levels, and the sorted distinct levels."""
    width, height = image.size
    pixels = image.convert("L").load()
    rows = [[pixels[x, y] for x in range(width)] for y in range(height)]
    return rows, sorted({value for row in rows for value in row})


def _tiles_1bpp(rows: List[List[int]], dark: Sequence[int]) -> bytes:
    """8 bytes a tile, 16 tiles a row of tiles. A pixel whose level is in ``dark`` is a 1 bit."""
    out = bytearray()
    for ty in range(len(rows) // 8):
        for tx in range(len(rows[0]) // 8):
            for y in range(8):
                byte = 0
                for x in range(8):
                    byte = (byte << 1) | (1 if rows[ty * 8 + y][tx * 8 + x] in dark else 0)
                out.append(byte)
    return bytes(out)


def _tiles_2bpp(rows: List[List[int]], shade: Dict[int, int]) -> bytes:
    """16 bytes a tile: the low plane of a row, then the high plane. ``shade`` maps a level to 0..3."""
    out = bytearray()
    for ty in range(len(rows) // 8):
        for tx in range(len(rows[0]) // 8):
            for y in range(8):
                low = high = 0
                for x in range(8):
                    value = shade[rows[ty * 8 + y][tx * 8 + x]]
                    low = (low << 1) | (value & 1)
                    high = (high << 1) | ((value >> 1) & 1)
                out += bytes([low, high])
    return bytes(out)


def find_1bpp(rom: bytes, rows: List[List[int]], levels: List[int]) -> Optional[int]:
    """The offset of the 1bpp font: every subset of the levels as the dark set, the first one that is in the ROM."""
    for size in range(1, len(levels)):
        for dark in itertools.combinations(levels, size):
            at = rom.find(_tiles_1bpp(rows, dark))
            if at >= 0:
                return at
    return None


def find_2bpp(rom: bytes, rows: List[List[int]], levels: List[int]) -> Optional[int]:
    """The offset of the 2bpp extra font: every choice of distinct shades 0..3 for the levels, in level order."""
    for shades in itertools.permutations(range(4), len(levels)):
        shade = dict(zip(levels, shades))
        at = rom.find(_tiles_2bpp(rows, shade))
        if at >= 0:
            return at
    return None


def charmap_codes(facts: Dict[str, object]) -> Dict[str, int]:
    return {str(char): int(code) for char, code in facts["charmap"]}


def main(argv: Sequence[str]) -> int:
    if len(argv) != 3:
        print(__doc__)
        return 2
    decomp, rom_path, facts_path = Path(argv[0]), Path(argv[1]), Path(argv[2])
    gfx = decomp / "gfx" / "font"
    rom = rom_path.read_bytes()
    facts = json.loads(facts_path.read_text(encoding="utf-8"))
    codes = charmap_codes(facts)
    if codes.get("A") != FONT_CODE:
        raise SystemExit(f"the charmap puts A at {codes.get('A')}, not {FONT_CODE:#x}")

    rows, levels = _levels(Image.open(gfx / "font.png"))
    if len(rows) != 64 or len(rows[0]) != 128:
        raise SystemExit("font.png is not 128 x 64")
    main_at = find_1bpp(rom, rows, levels)
    if main_at is None:
        raise SystemExit("the main font tiles are not in the ROM")

    extra_rows, extra_levels = _levels(Image.open(gfx / "font_extra.png"))
    if len(extra_rows) != 16 or len(extra_rows[0]) != 128 or len(extra_levels) > 4:
        raise SystemExit("font_extra.png is not 128 x 16 with up to four levels")
    extra_at = find_2bpp(rom, extra_rows, extra_levels)
    if extra_at is None:
        raise SystemExit("the extra font tiles are not in the ROM")

    facts["font"] = {
        "kind": "gb",
        "tiles_1bpp": {"at": main_at, "count": MAIN_TILES, "code": FONT_CODE},
        "tiles_2bpp": {"at": extra_at, "count": EXTRA_TILES, "code": EXTRA_CODE},
        "window": WINDOW,
    }
    facts_path.write_text(json.dumps(facts, ensure_ascii=False, indent=1), encoding="utf-8", newline="\n")
    print(f"font {main_at:#x}, extra {extra_at:#x}: written to {facts_path.name}")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
