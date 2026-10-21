"""Ukrainian cells for the Conker font: placeholder glyph records for the letters the 95-glyph font lacks.

Ґ Є І Ї and their lowercase forms are not in the game's font. Each cell is a placeholder copy of a Latin glyph that
looks alike (for example Є from E). The owner draws the final shapes in the Font Editor. This module only plans the
cells: it builds the placeholder records and checks that each one encodes and decodes unchanged. It does not write
the ROM. The game's glyph count (95) and glyph map (data offset 0x2E10) must be patched in code before the cells
can show in a frame.
"""
from __future__ import annotations

from dataclasses import dataclass, replace
from typing import List, Tuple

from . import font

# (Ukrainian letter, Latin base glyph used as the placeholder)
UKRAINIAN_CELLS: Tuple[Tuple[str, str], ...] = (
    ("Ґ", "F"), ("Є", "E"), ("І", "I"), ("Ї", "I"),
    ("ґ", "f"), ("є", "e"), ("і", "i"), ("ї", "i"),
)


@dataclass(frozen=True)
class Cell:
    letter: str
    base: str
    glyph: font.Glyph  # the placeholder record (index is the base glyph's index)


def plan_cells(glyphs: List[font.Glyph], glyph_map: bytes) -> List[Cell]:
    """Placeholder cells for every Ukrainian letter, copied from the base glyph of the existing font."""
    cells: List[Cell] = []
    for letter, base in UKRAINIAN_CELLS:
        index = font.glyph_index(ord(base), glyph_map)
        if index is None:
            raise ValueError(f"base glyph {base!r} is not in the glyph map")
        source = glyphs[index]
        cells.append(Cell(letter=letter, base=base, glyph=replace(source, index=index)))
    return cells


def encode_cells(cells: List[Cell]) -> bytes:
    """The placeholder records, back to back, in the record format of the font table."""
    return b"".join(font.encode_record(cell.glyph) for cell in cells)
