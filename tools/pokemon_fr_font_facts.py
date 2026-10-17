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
FRAME_LEFT_TILES = 2      # WindowFunc_DrawDialogueFrame draws two tile columns left of the window
FRAME_RIGHT_TILES = 2     # and two to the right (left - 2 .. left + width + 1)
FRAME_TOP_TILES = 1       # and one tile row above the window
FRAME_BOTTOM_TILES = 1    # and one below it (top - 1 .. top + height)
TILE = 8
INK_ROWS = 14             # the rows that carry ink in a glyph (plugins/common/gba_text_font.GLYPH_ROWS)


def _template(sources: str) -> dict:
    """tilemapLeft, tilemapTop, width and height of the field text window (the first one of the standard template)."""
    match = re.search(r"sStandardTextBox_WindowTemplates\[\][^{]*\{(.*?)\n\s*\}", sources, re.S)
    if match is None:
        raise SystemExit("sStandardTextBox_WindowTemplates is not in the source")
    values = {}
    for key in ("tilemapLeft", "tilemapTop", "width", "height"):
        found = re.search(r"\." + key + r"\s*=\s*(\d+)", match.group(1))
        if found is None:
            raise SystemExit(f"{key} is not in sStandardTextBox_WindowTemplates")
        values[key] = int(found.group(1))
    return values


def window_from_decomp(decomp: Path) -> dict:
    """The field message window in its own pixels, from the decompilation's numbers (text.c and the window template).

    The printer starts at window (x 0, y 1) and moves down by the font's max letter height plus the line spacing.
    Lines fit while their ink (INK_ROWS) ends inside the window's height.
    """
    sources = _sources(decomp)
    template = _template(sources)
    printer = re.search(r"\bAddTextPrinterParameterized2\(u8 windowId[^;{]*\)\s*\{(.*?)AddTextPrinter\(", sources, re.S)
    if printer is None:
        raise SystemExit("AddTextPrinterParameterized2 is not in the source")
    origin_y = int(re.search(r"printer\.y = (\d+);", printer.group(1)).group(1))
    spacing = int(re.search(r"printer\.lineSpacing = (\d+);", printer.group(1)).group(1))
    font_info = re.search(r"\[FONT_NORMAL\]\s*=\s*\{[^}]*?maxLetterHeight\s*=\s*(\d+)", sources, re.S)
    if font_info is None:
        raise SystemExit("FONT_NORMAL maxLetterHeight is not in the source")
    step = int(font_info.group(1)) + spacing
    width_px = template["width"] * TILE
    height_px = template["height"] * TILE
    lines = 1
    while origin_y + lines * step + INK_ROWS <= height_px:
        lines += 1
    return {
        "text_x": FRAME_LEFT_TILES * TILE, "text_top": FRAME_TOP_TILES * TILE + origin_y,
        "text_width": width_px, "lines": lines, "line_height": step,
        "box_width": width_px + (FRAME_LEFT_TILES + FRAME_RIGHT_TILES) * TILE,
        "box_height": height_px + (FRAME_TOP_TILES + FRAME_BOTTOM_TILES) * TILE,
        "source": (f"decomp window {template['width']}x{template['height']} tiles at ({template['tilemapLeft']},"
                   f"{template['tilemapTop']}); printer y {origin_y}, line spacing {spacing}, "
                   f"font max letter height {font_info.group(1)}"),
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
            "glyph_count": GLYPHS, "window": window_from_decomp(decomp)}


def _write_font_line(facts_path: Path, text: str, font: dict) -> None:
    font_line = '"font": ' + json.dumps(font, ensure_ascii=False) + ","
    # One line for the font entry, placed after rom_size: the rest of the file keeps its layout.
    lines = [line for line in text.split("\n") if not line.startswith('"font":')]
    at = next(i for i, line in enumerate(lines) if line.startswith('"rom_size"'))
    lines.insert(at + 1, font_line)
    facts_path.write_text("\n".join(lines), encoding="utf-8", newline="\n")
    print("font", font_line)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("--decomp", required=True, type=Path)
    parser.add_argument("--rom", type=Path, help="the unedited ROM (not needed with --window-only)")
    parser.add_argument("--facts", required=True, type=Path)
    parser.add_argument("--window-only", action="store_true",
                        help="rewrite only the window of an existing font entry, from the decompilation")
    args = parser.parse_args()
    text = args.facts.read_text(encoding="utf-8")
    facts = json.loads(text)
    if args.window_only:
        font = dict(facts["font"])
        font["window"] = window_from_decomp(args.decomp)
        _write_font_line(args.facts, text, font)
        return
    if args.rom is None:
        raise SystemExit("--rom is needed unless --window-only is given")
    rom = args.rom.read_bytes()
    if hashlib.sha1(rom).hexdigest() != facts["rom_sha1"]:
        raise SystemExit("this ROM is not the one the facts file was made from")
    _write_font_line(args.facts, text, locate(args.decomp, rom))


if __name__ == "__main__":
    main()
