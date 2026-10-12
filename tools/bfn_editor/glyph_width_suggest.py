"""Font Editor action: suggest the advance width of selected glyphs from their drawn pixels (core/font_formats/advance.py).

The suggestion goes through the undo stack (EditMetricsCommand), so Undo returns the old width. Only the advance changes;
the glyph's pixels and kerning stay as they are.
"""
from __future__ import annotations

from typing import List

from core.font_formats import advance
from utils.logging_utils import log_info

from .bfn_commands import EditMetricsCommand
from .io_format_mixin import qimage_to_pil


def suggest_advances(viewer, glyphs: List[int]) -> int:
    """Push one undoable width change per glyph whose suggested advance differs. Returns the number of changes.

    ``glyphs`` are table glyph numbers; the width table is indexed by glyph number minus the first code.
    """
    metadata = viewer.metadata
    sheets = [qimage_to_pil(image) for image in viewer.sheet_images]
    packets = metadata["WID1"][0]["packets"]
    right = advance.latin_right_bearing(metadata, sheets)
    cell_width = int(metadata["GLY1"][0]["cell_width"])
    pushed = 0
    for glyph in sorted(set(glyphs)):
        index = glyph - viewer.first_code
        if not 0 <= index < len(packets):
            continue
        ink = advance.ink_width(metadata, sheets, index)
        if ink is None:
            continue
        old = packets[index]["width"]
        new = advance.suggested_advance(ink, packets[index]["kerning"], right, cell_width)
        if new == old:
            continue
        viewer.undo_stack.push(EditMetricsCommand(viewer, glyph, packets[index]["kerning"],
                                                 packets[index]["kerning"], old, new,
                                                 description="Suggest Advance Width"))
        pushed += 1
    log_info(f"Font editor: {pushed} advance widths suggested from the drawn pixels")
    return pushed
