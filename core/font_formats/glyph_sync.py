"""Copy the glyphs drawn in one copy of a font to the other copy of the same font, by character code.

A glyph is its cell pixels, its kerning and its width (the WID1 packet). The edited copy is the one saved
now. A code the edited copy changed (against its own original) is copied to the other copy, unless the other
copy changed that code too and differently: then the edited copy wins and the code is reported as a conflict.
A cell of a different size is not copied (no lossless mapping is defined for that). A pixel the other copy's
texture format cannot hold exactly is not copied either. A glyph the other copy shares with another code is
not copied either, because the copy would change that code too.

Works on the font editor's model ``(metadata, sheets)`` (see ``core.font_formats``): sheets are RGBA images.
Pure: no files, no threads. The caller reads the two copies and writes the result back.
"""
from __future__ import annotations

import copy
from collections import Counter
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple

from PIL import Image

from core.font_formats import Metadata, Sheets, char_map

Model = Tuple[Metadata, Sheets]

# GX texture formats (GLY1 ``texture_format``) the copy can check: I4 0, I8 1, IA4 2, IA8 3.
_FOUR_BIT, _EIGHT_BIT = (0, 2), (1, 3)


@dataclass
class SyncReport:
    """What one sync did: codes shared by both copies, copied, in conflict, and skipped (code -> reason)."""

    shared: int = 0
    copied: List[str] = field(default_factory=list)
    conflicts: List[str] = field(default_factory=list)
    skipped: Dict[str, str] = field(default_factory=dict)


def _cell_box(metadata: Metadata, glyph: int):
    """``(sheet, x, y, cell width, cell height, texture format)`` of a glyph in the GLY1 grid, or None."""
    for gly in metadata.get("GLY1", []):
        start, end = gly["start_glyph"], gly["end_glyph"]
        if not start <= glyph <= end:
            continue
        columns, rows = gly["glyph_horizontal_count"], gly["glyph_vertical_count"]
        sheet, cell = divmod(glyph - start, columns * rows)
        width, height = gly["cell_width"], gly["cell_height"]
        return sheet, (cell % columns) * width, (cell // columns) * height, width, height, gly["texture_format"]
    return None


def _packet(metadata: Metadata, glyph: int) -> Optional[Dict[str, int]]:
    """The WID1 packet (kerning, width) of a glyph, or None."""
    for block in metadata.get("WID1", []):
        first, packets = block["first_code_included"], block["packets"]
        if first <= glyph < first + len(packets):
            return packets[glyph - first]
    return None


def _cell(model: Model, glyph: Optional[int]) -> Optional[Image.Image]:
    """The RGBA cell of a glyph, or None when the model has none."""
    if glyph is None:
        return None
    metadata, sheets = model
    box = _cell_box(metadata, glyph)
    if box is None or box[0] >= len(sheets):
        return None
    sheet, x, y, width, height, _format = box
    return sheets[sheet].crop((x, y, x + width, y + height))


def _record(model: Model, glyph: Optional[int]):
    """What a glyph is: cell size, cell pixels, kerning and width; None when the model has no such glyph."""
    cell = _cell(model, glyph)
    packet = _packet(model[0], glyph) if glyph is not None else None
    if cell is None or packet is None:
        return None
    return cell.size, cell.tobytes(), packet["kerning"], packet["width"]


def storable(cell: Image.Image, texture_format: int) -> bool:
    """True when the texture format keeps every pixel of the cell exactly.

    The 4-bit formats store multiples of 17 only; I4 and I8 have alpha equal to intensity; IA4 and IA8 keep
    an alpha of their own (a multiple of 17 in IA4).
    """
    if texture_format not in _FOUR_BIT + _EIGHT_BIT:
        return False
    step = 17 if texture_format in _FOUR_BIT else 1
    own_alpha = texture_format in (2, 3)
    for red, green, blue, alpha in cell.getdata():
        if not red == green == blue or red % step:
            return False
        if own_alpha and alpha % (17 if texture_format == 2 else 1):
            return False
        if not own_alpha and alpha != red:
            return False
    return True


def copy_glyphs(edited: Model, edited_original: Model, other: Model, other_original: Model
                ) -> Tuple[Optional[Model], SyncReport]:
    """The other copy with the glyphs the edited copy changed, or None when nothing is copied; and the report.

    ``edited`` is the copy saved now, ``edited_original`` and ``other_original`` are the game's own fonts,
    ``other`` is the other copy as it is now.
    """
    report = SyncReport()
    edited_codes, edited_was = char_map(edited[0]), char_map(edited_original[0])
    other_codes, other_was = char_map(other[0]), char_map(other_original[0])
    shared = sorted(set(edited_codes) & set(other_codes))
    report.shared = len(shared)
    other_users = Counter(other_codes.values())             # codes that point at each glyph of the other copy
    result: Optional[Model] = None

    for char in shared:
        now = _record(edited, edited_codes[char])
        if now == _record(edited_original, edited_was.get(char)):
            continue                                        # the edited copy did not change this code
        if now is None:
            report.skipped[char] = "the edited copy has no cell or width for it"
            continue
        target = other_codes[char]
        was_other = _record(other_original, other_was.get(char))
        if _record(other, target) == now:
            continue                                        # the other copy already has this glyph
        if _record(other, target) != was_other:
            report.conflicts.append(char)                   # both changed it: the edited copy wins
        if other_users[target] > 1:
            report.skipped[char] = f"the other copy's glyph is shared by {other_users[target]} codes"
            continue
        box = _cell_box(other[0], target)
        if box is None or _packet(other[0], target) is None:
            report.skipped[char] = "the other copy has no cell or width for it"
            continue
        cell = _cell(edited, edited_codes[char])
        if cell.size != (box[3], box[4]):
            report.skipped[char] = (f"cell size {cell.width}x{cell.height} differs from the other copy's "
                                    f"{box[3]}x{box[4]}; no lossless mapping")
            continue
        if not storable(cell, box[5]):
            report.skipped[char] = "the other copy's texture format cannot hold these pixels exactly"
            continue
        if result is None:
            result = (copy.deepcopy(other[0]), [sheet.copy() for sheet in other[1]])
        sheet, x, y = box[0], box[1], box[2]
        result[1][sheet].paste(cell, (x, y))
        packet = _packet(result[0], target)
        packet["kerning"], packet["width"] = now[2], now[3]
        report.copied.append(char)
    return result, report
