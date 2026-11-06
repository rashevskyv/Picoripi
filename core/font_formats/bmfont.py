"""AngelCode BMFont text fonts with DDS pages (Lunar Remastered ``FIL/CUSTOM/Font/n/test.fnt``).

The font is a text file and its texture pages (a font source with a ``companion`` glob, so the format gets
``join_pair(fnt, join_files(pages))``). ``info size``, ``common lineHeight base``, one ``page id file`` line per page
and one ``char`` line per glyph: ``id`` (Unicode), its rectangle ``x y width height`` on page ``page``, ``xoffset
yoffset`` (where the rectangle sits from the pen and the line top) and ``xadvance``. The glyph is the alpha channel
of the page (BC1 or BC3 DDS, read and written by ``core.texture_formats.dds``).

Model: one cell per glyph in file order, 32 x 32 cells a sheet, every glyph at its offsets in a cell that holds the
whole line (so all glyphs share the baseline); the cells after the last glyph are spare, for new letters (advance half the font size until it is set). Widths
are ``xadvance``. Packing an unedited model gives the original files back. A redrawn glyph whose ink stays inside its
old rectangle is written there; a glyph that grew, and a new letter, gets a new rectangle in free page space (the
ink's bounding box, one pixel apart from the others) and a changed or new ``char`` line. Only the changed pages are
written again. Kerning pairs are kept as they are.
"""
from __future__ import annotations

import re
from typing import Any, Dict, List, Optional, Tuple

import numpy as np
from PIL import Image

from core.font_formats import Metadata, Sheets, char_code, char_map, coverage, grey_sheet, map_entries
from core.font_formats.sources import join_files, join_pair, split_files, split_pair
from core.texture_formats import dds

ADDS_GLYPHS = True
COLUMNS = ROWS = 32
SPARE = 64                      # at least this many empty cells after the glyphs
GAP = 1                         # pixels between rectangles on a page
_PAIR = re.compile(r'(\w+)=("[^"]*"|\S+)')
_FIELDS = ("x", "y", "width", "height", "xoffset", "yoffset", "xadvance", "page")


class _Font:
    def __init__(self, data: bytes) -> None:
        fnt, pages = split_pair(bytes(data))
        self.lines = fnt.decode("utf-8").splitlines(keepends=True)
        self.files = split_files(pages)
        self.size = self.line_height = self.base = 0
        self.page_files: Dict[int, str] = {}
        self.chars: Dict[int, Dict[str, int]] = {}
        self.line_of: Dict[int, int] = {}
        for index, line in enumerate(self.lines):
            kind = line.split(" ", 1)[0]
            fields = {key: value.strip('"') for key, value in _PAIR.findall(line)}
            if kind == "info":
                self.size = int(fields.get("size", 0))
            elif kind == "common":
                self.line_height, self.base = int(fields.get("lineHeight", 0)), int(fields.get("base", 0))
            elif kind == "page":
                self.page_files[int(fields["id"])] = fields["file"]
            elif kind == "char":
                self.chars[int(fields["id"])] = {key: int(value) for key, value in fields.items()}
                self.line_of[int(fields["id"])] = index
        if not self.chars or not self.page_files:
            raise ValueError("Not a BMFont text font with pages")
        self.codes = list(self.chars)
        boxes = list(self.chars.values())
        self.min_x = min([0] + [c["xoffset"] for c in boxes])
        self.min_y = min([0] + [c["yoffset"] for c in boxes])
        self.cell_w = max([self.size] + [c["xoffset"] + c["width"] for c in boxes]) - self.min_x
        self.cell_h = max([self.line_height] + [c["yoffset"] + c["height"] for c in boxes]) - self.min_y
        self.sheet_count = -(-(len(self.codes) + SPARE) // (COLUMNS * ROWS))
        self._pages: Dict[int, Image.Image] = {}

    def page_bytes(self, page: int) -> bytes:
        name = self.page_files[page]
        found = next((data for file, data in self.files if file == name), None)
        if found is None:
            raise ValueError(f"The font page {name} is missing")
        return found

    def page(self, page: int) -> Image.Image:
        if page not in self._pages:
            self._pages[page] = dds.read(self.page_bytes(page), {})[0].image.convert("RGBA")
        return self._pages[page]

    def cell(self, index: int) -> Tuple[int, int, int]:
        """(sheet, left, top) of cell ``index``."""
        sheet, rest = divmod(index, COLUMNS * ROWS)
        row, column = divmod(rest, COLUMNS)
        return sheet, column * self.cell_w, row * self.cell_h

    def place(self, char: Dict[str, int]) -> Tuple[int, int, int, int]:
        """The glyph's rectangle inside its cell."""
        left, top = char["xoffset"] - self.min_x, char["yoffset"] - self.min_y
        return left, top, left + char["width"], top + char["height"]


def extract(data: bytes, params: Dict[str, Any]) -> Tuple[Metadata, Sheets]:
    font = _Font(data)
    inks = [Image.new("L", (COLUMNS * font.cell_w, ROWS * font.cell_h), 0) for _ in range(font.sheet_count)]
    for index, code in enumerate(font.codes):
        char = font.chars[code]
        if char["width"] <= 0 or char["height"] <= 0:
            continue
        sheet, left, top = font.cell(index)
        x, y = char["x"], char["y"]
        rect = font.page(char["page"]).getchannel("A").crop((x, y, x + char["width"], y + char["height"]))
        inks[sheet].paste(rect, (left + char["xoffset"] - font.min_x, top + char["yoffset"] - font.min_y))
    pairs = [(char_code(chr(code)), index) for index, code in enumerate(font.codes)]
    cells = font.sheet_count * COLUMNS * ROWS
    packets = [{"kerning": -font.min_x, "width": font.chars[code]["xadvance"]} for code in font.codes]
    packets += [{"kerning": -font.min_x, "width": font.size // 2}] * (cells - len(packets))   # spare cells
    metadata = {
        "header": {"signature": "BMFont", "textures_editable": True},
        "INF1": [{"encoding": 1, "ascent": font.base - font.min_y, "descent": font.cell_h - font.base + font.min_y,
                  "width": font.size, "leading": font.line_height, "fallback_code": 0x3F, "unk1": 0}],
        "GLY1": [{"start_glyph": 0, "end_glyph": cells - 1, "cell_width": font.cell_w,
                  "cell_height": font.cell_h, "glyph_horizontal_count": COLUMNS, "glyph_vertical_count": ROWS,
                  "texture_width": COLUMNS * font.cell_w, "texture_height": ROWS * font.cell_h}],
        "MAP1": [map_entries(pairs)],
        "WID1": [{"first_code_included": 0, "last_code_included": cells, "packets": [dict(p) for p in packets]}],
    }
    return metadata, [grey_sheet(ink) for ink in inks]


class _Space:
    """Free page space: every rectangle of the font (and the ones placed now) is taken."""

    def __init__(self, font: _Font) -> None:
        self.font = font
        self.taken: Dict[int, np.ndarray] = {}
        for char in font.chars.values():
            self.take(char["page"], char["x"], char["y"], char["width"], char["height"])

    def _grid(self, page: int) -> np.ndarray:
        if page not in self.taken:
            width, height = self.font.page(page).size
            self.taken[page] = np.zeros((height, width), dtype=bool)
        return self.taken[page]

    def take(self, page: int, x: int, y: int, width: int, height: int) -> None:
        if width > 0 and height > 0:
            self._grid(page)[max(0, y - GAP):y + height + GAP, max(0, x - GAP):x + width + GAP] = True

    def find(self, width: int, height: int) -> Tuple[int, int, int]:
        """(page, x, y) of the first free rectangle of this size, page by page, row by row."""
        for page in sorted(self.font.page_files):
            grid = self._grid(page)
            rows, columns = grid.shape
            if width > columns or height > rows:
                continue
            table = np.zeros((rows + 1, columns + 1), dtype=np.int32)
            table[1:, 1:] = grid.cumsum(0).cumsum(1)
            used = table[height:, width:] - table[:-height, width:] - table[height:, :-width] + table[:-height, :-width]
            free = np.argwhere(used == 0)
            if len(free):
                y, x = (int(v) for v in free[0])
                self.take(page, x, y, width, height)
                return page, x, y
        raise ValueError(f"The font pages have no free {width}x{height} place for a new glyph")


def _char_line(line: str, fields: Dict[str, int]) -> str:
    for key in _FIELDS:
        line = re.sub(rf"\b{key}=-?\d+", f"{key}={fields[key]}", line)
    return line


def pack(metadata: Metadata, sheets: Sheets, original: bytes, params: Dict[str, Any]) -> bytes:
    font = _Font(original)
    _, old_sheets = extract(original, params)
    count = len(font.codes)
    wanted = {char: glyph for char, glyph in char_map(metadata).items() if len(char) == 1}
    moved = [code for index, code in enumerate(font.codes) if wanted.get(chr(code), index) != index]
    if moved:
        raise ValueError("This font keeps the characters it has; changed: "
                         + " ".join(f"U+{code:04X}" for code in moved[:10]))
    new = {ord(char): glyph for char, glyph in wanted.items() if ord(char) not in font.chars}
    if any(glyph < count for glyph in new.values()):
        raise ValueError(f"A new character must stand in a spare cell (glyph {count} on)")
    packets = metadata["WID1"][0]["packets"]
    space: Optional[_Space] = None
    touched: set = set()
    changed: Dict[int, Dict[str, int]] = {}

    def ink_of(index: int) -> Image.Image:
        sheet, left, top = font.cell(index)
        if sheet >= len(sheets):
            return Image.new("L", (font.cell_w, font.cell_h), 0)
        return coverage(sheets[sheet].crop((left, top, left + font.cell_w, top + font.cell_h)))

    def write(char: Dict[str, int], ink: Image.Image, place: Tuple[int, int, int, int]) -> None:
        part = ink.crop(place)
        white = Image.new("L", part.size, 255)
        font.page(char["page"]).paste(Image.merge("RGBA", (white, white, white, part)), (char["x"], char["y"]))
        touched.add(char["page"])

    def relocate(char: Dict[str, int], ink: Image.Image, box: Tuple[int, int, int, int]) -> None:
        nonlocal space
        space = space or _Space(font)
        width, height = box[2] - box[0], box[3] - box[1]
        char["page"], char["x"], char["y"] = space.find(width, height)
        char.update(width=width, height=height, xoffset=box[0] + font.min_x, yoffset=box[1] + font.min_y)
        write(char, ink, box)

    for index, code in enumerate(font.codes):
        char = dict(font.chars[code])
        if index < len(packets) and int(packets[index]["width"]) != char["xadvance"]:
            char["xadvance"] = int(packets[index]["width"])
        sheet, left, top = font.cell(index)
        box = (left, top, left + font.cell_w, top + font.cell_h)
        if sheet < len(sheets) and sheets[sheet].crop(box).tobytes() != old_sheets[sheet].crop(box).tobytes():
            ink = coverage(sheets[sheet].crop(box))
            bbox = ink.getbbox()
            place = font.place(char)
            if bbox is None or (bbox[0] >= place[0] and bbox[1] >= place[1]
                                and bbox[2] <= place[2] and bbox[3] <= place[3]):
                if char["width"] > 0 and char["height"] > 0:
                    write(char, ink, place)
            else:
                relocate(char, ink, bbox)
        if char != font.chars[code]:
            changed[code] = char
    added: List[str] = []
    for code, glyph in sorted(new.items(), key=lambda item: item[1]):
        ink = ink_of(glyph)
        char = {"id": code, "x": 0, "y": 0, "width": 0, "height": 0, "xoffset": 0, "yoffset": 0, "page": 0,
                "chnl": 15, "xadvance": int(packets[glyph]["width"]) if glyph < len(packets) else font.size}
        bbox = ink.getbbox()
        if bbox:
            relocate(char, ink, bbox)
        added.append(" ".join(f"{key}={char[key]}" for key in ("id",) + _FIELDS + ("chnl",)))
    if not changed and not added and not touched:
        return bytes(original)
    lines = list(font.lines)
    ending = "\r\n" if lines[0].endswith("\r\n") else "\n"
    for code, char in changed.items():
        lines[font.line_of[code]] = _char_line(lines[font.line_of[code]], char)
    if added:
        last = max(font.line_of.values())
        lines[last + 1:last + 1] = ["char " + line + ending for line in added]
        lines = [re.sub(r"^chars count=\d+", f"chars count={count + len(added)}", line) for line in lines]
    names = {font.page_files[page]: page for page in touched}
    files = [(name, dds.write(data, {0: font.page(names[name])}, {}) if name in names else data)
             for name, data in font.files]
    return join_pair("".join(lines).encode("utf-8"), join_files(files))
