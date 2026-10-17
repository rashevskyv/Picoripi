"""The budget box of a 3DS system string: the text drawn with the console's system font, in the owner's budget.

The box is as wide as the string's width budget (budgets.json, font pixels) and as many lines high as its line budget.
Each line is drawn with the font's glyphs at the font's advances, so the ink is the width the console paints. A line
wider than the budget keeps its ink, and a red edge marks the budget; lines past the line budget sit under a red band.
The status the panel shows comes from the numbers here, not from a second measure.

Scale tags ({t:1.0:XXXX}, {t:1.1:XXXX}) draw their text larger, as the owner's validate.py measures them; other tags
draw nothing. The width of each line is the one rules.line_widths measures, so the box and the budget check agree.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any, List, Optional

from PIL import Image, ImageDraw

from plugins.manual_3ds import sim_screens as ss

# The owner's MSBT tag (tools/msbt.py TOKEN_RE): {t:group.type:args} and {/t:group.type}. Same as rules._TAG.
_TAG = re.compile(r"\{(/?)t:(\d+)\.(\d+)(?::([0-9a-fA-F]*))?\}")
_SCALE_100 = 0x6400
MARGIN = 6
PAPER = (255, 255, 255, 255)
INK = (0, 0, 0, 255)
EDGE = (120, 120, 120, 255)
RED = (220, 30, 30, 255)
RED_FILL = (220, 30, 30, 40)
BACKDROP = (236, 236, 236, 255)


def runs(text: str) -> List[List[Any]]:
    """The text as per-line runs: [[segment, scale], ...] for each line. Tags are removed, scales are the product of
    the open {t:1.0} and {t:1.1} scales, as rules.line_widths reads them."""
    lines: List[List[Any]] = [[]]
    scales = {"0": 1.0, "1": 1.0}
    index = 0
    while index < len(text):
        tag = _TAG.match(text, index)
        if tag:
            if tag.group(2) == "1" and tag.group(3) in scales:
                value = tag.group(4)
                scales[tag.group(3)] = int(value, 16) / _SCALE_100 if value and not tag.group(1) else 1.0
            index = tag.end()
            continue
        char = text[index]
        index += 1
        if char == "\n":
            lines.append([])
            continue
        scale = scales["0"] * scales["1"]
        if lines[-1] and lines[-1][-1][1] == scale:
            lines[-1][-1][0] += char
        else:
            lines[-1].append([char, scale])
    return lines


def is_wide(width: float, budget: Optional[int]) -> bool:
    """The owner's check (validate.py): the width rounded to whole pixels is past the budget."""
    return budget is not None and round(width) > budget


@dataclass
class BoxResult:
    """What the box shows: the picture and the numbers the status line states."""

    image: Image.Image
    line_widths: List[float]                   # painted width of each line, font pixels
    width_budget: Optional[int]
    line_budget: Optional[int]
    missing: List[str] = field(default_factory=list)   # characters the font has no glyph for

    @property
    def widest(self) -> float:
        return max(self.line_widths, default=0.0)

    @property
    def wide_lines(self) -> List[int]:
        """1-based numbers of the lines wider than the width budget."""
        if self.width_budget is None:
            return []
        return [number + 1 for number, width in enumerate(self.line_widths) if is_wide(width, self.width_budget)]

    @property
    def extra_lines(self) -> int:
        """Lines past the line budget (0 when the budget is unknown or kept)."""
        if self.line_budget is None:
            return 0
        return max(0, len(self.line_widths) - self.line_budget)


def draw_box(text: str, line_widths: List[float], width_budget: Optional[int], line_budget: Optional[int],
             glyphs: Any) -> BoxResult:
    """Draw ``text`` (one line per "\\n") in its budget box with ``glyphs`` (console_render.Glyphs).

    ``line_widths`` are the widths of the lines as rules.line_widths measured them. The box is a little wider than
    the widest line when there is no width budget.
    """
    line_list = runs(text) or [[]]
    feed = glyphs.line_feed or glyphs.height
    count = max(len(line_list), line_budget or 0, 1)
    # The box is the budget, or wider when a line is: the ink past the budget stays visible, with the edge drawn.
    inner = max(width_budget or 0, round(max(line_widths, default=0.0)))
    box_w = inner + 2 * MARGIN
    box_h = int(round(count * feed)) + 2 * MARGIN
    canvas = Image.new("RGBA", (box_w, box_h), PAPER)
    draw = ImageDraw.Draw(canvas)
    if line_budget and len(line_list) > line_budget:
        band_top = MARGIN + line_budget * feed
        draw.rectangle([0, band_top, box_w - 1, MARGIN + len(line_list) * feed - 1], fill=RED_FILL)
    if width_budget:
        edge = MARGIN + width_budget
        draw.line([(edge, 0), (edge, box_h - 1)], fill=EDGE)
    for number, segments in enumerate(line_list):
        top = MARGIN + number * feed
        baseline = top + glyphs.ascent
        pen = float(MARGIN)
        for segment, scale in segments:
            ss._draw_text(canvas, glyphs, segment, pen, baseline, glyphs.width * scale, glyphs.height * scale, INK)
            pen += ss._text_width(glyphs, segment, scale, 0.0)
        if width_budget and number < len(line_widths) and is_wide(line_widths[number], width_budget):
            draw.line([(MARGIN, top), (MARGIN + width_budget, top)], fill=RED)
    missing = sorted({ch for ch in text if not ch.isspace() and not glyphs.has(ord(ch))})
    return BoxResult(canvas, list(line_widths), width_budget, line_budget, missing)
