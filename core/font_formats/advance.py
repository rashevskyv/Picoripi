"""Advance widths of a bitmap font's glyphs from their drawn pixels, with the rule the font's own Latin letters follow.

A glyph has three numbers in the width table: kerning (its left offset), glyph width (the ink it draws) and advance
(the step to the next glyph). The ink width is the drawn columns of the glyph's cell. The left bearing is the
kerning as it stands (drawn glyph start = -kerning); the right bearing is the median of the font's Latin letters and
digits, so the advance = ink - kerning + right bearing. A Cyrillic block that carries one flat advance for every glyph
(35 in the Wind Waker HD message font) is re-measured with it.

Pixels and kerning are never changed here; only the glyph width and the advance.
"""
from __future__ import annotations

import statistics
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Tuple

from core.font_formats import char_map

INK_THRESHOLD = 40          # alpha at or above this counts as ink
LATIN = "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789"


def _cell_box(metadata: Dict[str, Any], glyph: int) -> Optional[Tuple[int, int, int, int]]:
    """(sheet, x, y, cell width, cell height) of a glyph in the GLY1 grid, or None when the grid is missing."""
    gly = metadata.get("GLY1") or []
    if not gly:
        return None
    cell = gly[0]
    cw, ch = int(cell["cell_width"]), int(cell["cell_height"])
    cols, rows = int(cell["glyph_horizontal_count"]), int(cell["glyph_vertical_count"])
    per_sheet = cols * rows
    if per_sheet <= 0:
        return None
    sheet, index = divmod(glyph, per_sheet)
    return sheet, (index % cols) * cw, (index // cols) * ch, cw, ch


def ink_width(metadata: Dict[str, Any], sheets: List[Any], glyph: int) -> Optional[int]:
    """Drawn width of a glyph: the columns from its first to its last inked column. None when the cell is empty."""
    box = _cell_box(metadata, glyph)
    if box is None:
        return None
    sheet, x0, y0, cw, ch = box
    if sheet >= len(sheets):
        return None
    alpha = sheets[sheet].convert("RGBA").getchannel("A").crop((x0, y0, x0 + cw, y0 + ch))
    columns = [x for x in range(cw) if any(alpha.getpixel((x, y)) >= INK_THRESHOLD for y in range(ch))]
    if not columns:
        return None
    return columns[-1] - columns[0] + 1


def _packets(metadata: Dict[str, Any]) -> List[Dict[str, int]]:
    return metadata["WID1"][0]["packets"]


def _glyph_widths(metadata: Dict[str, Any]) -> List[int]:
    wid = metadata["WID1"][0]
    if "glyph_widths" not in wid:
        wid["glyph_widths"] = [0] * len(wid["packets"])
    return wid["glyph_widths"]


def latin_right_bearing(metadata: Dict[str, Any], sheets: List[Any]) -> float:
    """Median right side bearing of the font's Latin letters and digits: advance - (left bearing + ink width).

    The left bearing of a glyph is -kerning; the right bearing is what the advance adds after the ink.
    """
    cmap = char_map(metadata)
    packets = _packets(metadata)
    bearings = []
    for char in LATIN:
        glyph = cmap.get(char)
        if glyph is None or glyph >= len(packets):
            continue
        ink = ink_width(metadata, sheets, glyph)
        if ink is None:
            continue
        bearings.append(packets[glyph]["width"] + packets[glyph]["kerning"] - ink)
    if len(bearings) < 2:
        raise ValueError("the font has too few Latin glyphs to take the side bearings from")
    return statistics.median(bearings)


def suggested_advance(ink: int, kerning: int, right_bearing: float, cell_width: int) -> int:
    """Advance of a glyph with ink ``ink`` and left bearing -kerning, followed by the Latin right bearing."""
    return max(0, min(cell_width, round(ink - kerning + right_bearing)))


def remeasure(metadata: Dict[str, Any], sheets: List[Any], glyphs: Iterable[int]) -> List[Tuple[int, int, int]]:
    """Set glyph width (ink) and advance (rule) for each glyph that has ink. Returns (glyph, old advance, new advance)."""
    packets = _packets(metadata)
    widths = _glyph_widths(metadata)
    right = latin_right_bearing(metadata, sheets)
    cell_width = int(metadata["GLY1"][0]["cell_width"])
    changes = []
    for glyph in sorted(set(glyphs)):
        if glyph >= len(packets):
            continue
        ink = ink_width(metadata, sheets, glyph)
        if ink is None:
            continue
        old = packets[glyph]["width"]
        packets[glyph]["width"] = suggested_advance(ink, packets[glyph]["kerning"], right, cell_width)
        widths[glyph] = ink
        if packets[glyph]["width"] != old:
            changes.append((glyph, old, packets[glyph]["width"]))
    return changes


def cyrillic_glyphs(metadata: Dict[str, Any]) -> List[int]:
    """Glyphs mapped from the Cyrillic block (U+0400..U+04FF) and from no other code.

    A glyph that a Latin code also uses (the Ukrainian I is the Latin I in this font) keeps its width.
    """
    mapping = char_map(metadata)
    cyrillic = {glyph for code, glyph in mapping.items() if 0x0400 <= ord(code) <= 0x04FF}
    other = {glyph for code, glyph in mapping.items() if not 0x0400 <= ord(code) <= 0x04FF}
    return sorted(cyrillic - other)


def flat_block(metadata: Dict[str, Any]) -> bool:
    """True when every Cyrillic glyph has the same advance: the default of a cell width, not a measured one."""
    glyphs = cyrillic_glyphs(metadata)
    packets = _packets(metadata)
    return bool(glyphs) and len({packets[g]["width"] for g in glyphs}) == 1


def fix_file(path: Path, font_format: str = "bffnt_wiiu", params: Optional[Dict[str, Any]] = None) -> List[Tuple[int, int, int]]:
    """Re-measure the Cyrillic glyphs of a font file in place (pixels and kerning are written back as they are).

    Only a flat Cyrillic block is re-measured (``flat_block``): a font whose Cyrillic advances were measured already is
    left as it is. Returns the changed advances as (glyph, old, new). Writes atomically; a file with no change is not rewritten.
    """
    from core import font_formats
    from utils.atomic_io import atomic_write_bytes

    data = Path(path).read_bytes()
    fmt = font_formats.detect(data) or font_format
    metadata, sheets = font_formats.extract(fmt, data, params or {})
    if not flat_block(metadata):
        return []
    changes = remeasure(metadata, sheets, cyrillic_glyphs(metadata))
    if changes:
        atomic_write_bytes(Path(path), font_formats.pack(fmt, metadata, sheets, data, params or {}))
    return changes
