"""Dialogue window of Lunar: Silver Star Story Complete drawn as the game draws it (pure logic, no Qt).

Facts, measured on a native 1x capture of the USA disc (picture 320x240 at x=15 in the capture):

- the message window spans the full picture width, rows 160-223 (64 rows);
- the portrait is a 64x64 picture at (7, 152), drawn over the window's top edge;
- the text starts at x 80 when a portrait is shown and uses the 16x16 glyphs of ``SLUS_006.28`` (32 bytes a glyph,
  16 rows of big-endian u16, high bit left). Line pitch 16 is an estimate from the same capture.
- without a portrait the text start (``TEXT_X_NO_PORTRAIT``) is an estimate: the original English windows
  without a portrait are up to 272 px wide, so they cannot start at x 80.

The picture is only the box and the top edge of the portrait (rows 152-223); the scene above is not drawn.
The fit check is ``measure_page``: the box right edge less the text start, the same advances this picture uses.

A portrait is 8-bit indexed (``FACE_nnn.TIZ``: five 64x64 frames after a 32-byte header whose ID bytes name
the frame of each index). Its colours come from ``face_palettes.json`` (the owner's colour table, read from a
reference sprite sheet; see ``scripts/lunar_portrait_colours.py``). A project's own table overrides it per index;
an index that neither table has uses ``PEO.PAL``.
"""
from __future__ import annotations

import json
import re
import struct
import zlib
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Optional, Sequence, Tuple

from PIL import Image


HERE = Path(__file__).resolve().parent
WINDOW_X, WINDOW_Y, WINDOW_W, WINDOW_H = 0, 160, 320, 64
PORTRAIT_X, PORTRAIT_Y, PORTRAIT = 7, 152, 64
TEXT_X, TEXT_X_NO_PORTRAIT, TEXT_Y, LINE_PITCH = 80, 16, 168, 16
LINES_PER_PAGE = 3
# The picture: the window's rows plus the portrait's top edge above them. Nothing else of the screen.
PICTURE_X, PICTURE_Y = 0, PORTRAIT_Y
PICTURE_W, PICTURE_H = 320, WINDOW_Y + WINDOW_H - PORTRAIT_Y
BACKDROP = (96, 96, 96, 255)     # the preview has no game scene behind the band
BAND = (0, 0, 0, 128)            # the game's band: black at about half opacity (estimated, see render_page)
SPACE_WIDTH = 5
FACE_HEADER = 0x20
FRAME_BYTES = PORTRAIT * PORTRAIT
FRAMES_PER_FILE = 5

TAG_RE = re.compile(r"\{([^{}]*)\}")
PAGE_TAGS = {"page", "clear", "close", "end"}
FONT = json.loads((HERE / "font_sources.json").read_text(encoding="utf-8"))[0]
WIDTHS = json.loads((HERE / "fonts" / "lunar_font.json").read_text(encoding="utf-8"))
SPEAKERS = json.loads((HERE / "speaker_names.json").read_text(encoding="utf-8"))
FACE_COLOURS_FILE = "face_palettes.json"


def load_colour_table(path: Path) -> Dict[str, Dict[int, Tuple[int, int, int]]]:
    """A colour table {member: {index: "#rrggbb"}} as {member: {index: (r, g, b)}}; empty when the file is absent."""
    if not path.is_file():
        return {}
    raw = json.loads(path.read_text(encoding="utf-8"))
    return {name: {int(value): (int(text[1:3], 16), int(text[3:5], 16), int(text[5:7], 16))
                   for value, text in table.items()} for name, table in raw.items()}


FACE_COLOURS = load_colour_table(HERE / FACE_COLOURS_FILE)


@dataclass
class Line:
    """One printed line and the portrait number ``{FA:xx}`` set when the line ended (0 = none)."""

    text: str
    face: int = 0


@dataclass
class Layout:
    """The pages of a message and the layout problems the translator sees (empty = fits)."""

    pages: List[List[Line]]
    problems: List[str]


def parse_pages(text: str) -> Layout:
    """Split an editor text into pages.

    ``\\n`` ends a line; ``{page}``, ``{clear}``, ``{close}`` and ``{end}`` end a page; ``{FA:xx}`` sets the
    portrait (00 removes it). Other tags take no room in the window.
    """
    pages: List[List[Line]] = []
    current: List[Line] = []
    left = right = 0      # {FA:xx} is the left speaker, {FB:xx} the right one; the window shows the left first
    face = 0
    line_text = ""
    pos = 0
    for match in TAG_RE.finditer(text):
        for ch in text[pos:match.start()]:
            if ch == "\n":
                current.append(Line(line_text, face))
                line_text = ""
            else:
                line_text += ch
        pos = match.end()
        tag = match.group(1)
        if tag.startswith("FA:"):
            left = int(tag[3:], 16)
        elif tag.startswith("FB:"):
            right = int(tag[3:], 16)
        face = left or right
        if tag in PAGE_TAGS:
            if line_text:
                current.append(Line(line_text, face))
                line_text = ""
            if current:
                pages.append(current)
                current = []
            # A window with no speaker tag at its start has no portrait: the game's state is not carried over (no proof otherwise).
            left = right = face = 0
    for ch in text[pos:]:
        if ch == "\n":
            current.append(Line(line_text, face))
            line_text = ""
        else:
            line_text += ch
    if line_text:
        current.append(Line(line_text, face))
    if current:
        pages.append(current)
    problems: List[str] = []
    for number, page in enumerate(pages, 1):
        if len(page) > LINES_PER_PAGE:
            problems.append(f"page {number}: {len(page)} lines, the window shows {LINES_PER_PAGE}")
        if any(line.over for line in measure_page(page)):
            problems.append(f"page {number}: a line is wider than the window")
    return Layout(pages, problems)


def advance(ch: str) -> int:
    """Pen advance of one character in game pixels (``lunar_font.json``; a character the table lacks is a space)."""
    return WIDTHS[ch]["width"] if ch in WIDTHS else SPACE_WIDTH


def text_start(portrait: bool) -> int:
    """Where a line starts in the box: after the portrait when one is shown, else at the left text margin."""
    return TEXT_X if portrait else TEXT_X_NO_PORTRAIT


@dataclass
class MeasuredLine:
    """One line measured as the window draws it: where its text starts, its width and the room left in the box."""

    text: str
    start: int
    width: int
    limit: int                      # box right edge minus the text start: the longest line the box holds

    @property
    def over(self) -> bool:
        return self.width > self.limit

    @property
    def right(self) -> int:
        """The box x where the line's last pen position ends (the number the editor's width warning shows)."""
        return self.start + self.width


def measure_page(page: Sequence[Line]) -> List[MeasuredLine]:
    """Every line of a window measured with the same advances and start the preview draws it with.

    The window's portrait (its first line's face) moves the text start; the limit is the room from there to the
    box's right edge. Pure: no Qt, no glyph bitmaps, no picture.
    """
    portrait = bool(page and page[0].face)
    start = text_start(portrait)
    limit = WINDOW_X + WINDOW_W - start
    return [MeasuredLine(line.text, start, sum(advance(ch) for ch in line.text), limit) for line in page]


def measure(text: str) -> List[MeasuredLine]:
    """Every line of an editor text, window by window (see ``measure_page``)."""
    return [m for page in parse_pages(text).pages for m in measure_page(page)]


def text_width(text: str) -> int:
    """Pen width of a line in game pixels: the sum of the character advances the preview uses."""
    return sum(advance(ch) for ch in text)


def decode_glyphs(slus: bytes) -> Dict[str, List[int]]:
    """Character -> 16 row words (high bit left) of the text font in the program (``font_sources.json``)."""
    offset, count = int(FONT["params"]["offset"], 0), int(FONT["params"]["count"])
    chars = FONT["params"]["chars"]
    if offset < 0 or offset + count * 32 > len(slus) or len(chars) != count:
        raise ValueError("the program has no Lunar text font at the expected place")
    return {ch: list(struct.unpack_from(">16H", slus, offset + index * 32)) for index, ch in enumerate(chars)}


def index_faces(files: Dict[str, bytes]) -> Dict[int, Tuple[str, int]]:
    """Face number -> (member name, frame), from the 16 ID bytes of each FACE_nnn.TIZ member (frame = position)."""
    index: Dict[int, Tuple[str, int]] = {}
    for name in sorted(files):
        ids = files[name][0x10:0x10 + FRAMES_PER_FILE]
        for frame, value in enumerate(ids):
            if value and value not in index:
                index[value] = (name, frame)
    return index


def inflate_member(member: bytes) -> bytes:
    """The frames of a TIZ member: its payload after the 32-byte header is raw deflate (``lunar.py`` notes)."""
    return zlib.decompressobj(-15).decompress(member[FACE_HEADER:])


def decode_frame(frames: bytes, frame: int) -> bytes:
    """The 64x64 indices of one frame of inflated TIZ frames."""
    start = frame * FRAME_BYTES
    chunk = frames[start:start + FRAME_BYTES]
    if len(chunk) != FRAME_BYTES:
        raise ValueError("the face member is shorter than its frames")
    return chunk


def palette_from_file(data: bytes) -> List[Tuple[int, int, int]]:
    """256 RGB entries from a PS1 palette file of u16 colours (5-5-5 bits; the STP bit is ignored)."""
    if len(data) < 512:
        raise ValueError("palette file shorter than 256 colours")
    out = []
    for value in struct.unpack_from("<256H", data, 0):
        out.append(((value & 31) * 255 // 31, ((value >> 5) & 31) * 255 // 31, ((value >> 10) & 31) * 255 // 31))
    return out


def face_picture(files: Dict[str, bytes], index: Dict[int, Tuple[str, int]], face: int,
                 palette: Sequence[Tuple[int, int, int]],
                 colours: Optional[Dict[str, Dict[int, Tuple[int, int, int]]]] = None) -> Optional[Image.Image]:
    """RGBA 64x64 portrait of a face number, or None when no member holds it. Index 0 is transparent.

    The colour of an index comes from ``colours`` (a project's table, optional), else from ``FACE_COLOURS`` (the
    plugin's table), else from ``palette``.
    """
    entry = index.get(face)
    if entry is None:
        return None
    name, frame = entry
    indices = decode_frame(inflate_member(files[name]), frame)
    own = dict(FACE_COLOURS.get(name, {}))
    own.update((colours or {}).get(name, {}))
    image = Image.new("RGBA", (PORTRAIT, PORTRAIT), (0, 0, 0, 0))
    pixels = image.load()
    for i, value in enumerate(indices):
        if value:
            red, green, blue = own.get(value) or palette[value]
            pixels[i % PORTRAIT, i // PORTRAIT] = (red, green, blue, 255)
    return image


def render_page(page: Sequence[Line], glyphs: Dict[str, List[int]], portrait: Optional[Image.Image]) -> Image.Image:
    """The PICTURE_W x PICTURE_H picture of one page: the window, the portrait and the text, at the measured places.

    The game's band is a translucent dark strip over the scene: about half the scene's brightness (row means of
    the native capture: about 155 above the band, about 75 inside). The preview has no scene, so the band is
    black at alpha 128 over a neutral grey backdrop, and only inside the window. Everything else stays transparent.
    """
    canvas = Image.new("RGBA", (PICTURE_W, PICTURE_H), (0, 0, 0, 0))
    box = (WINDOW_X - PICTURE_X, WINDOW_Y - PICTURE_Y)
    canvas.alpha_composite(Image.new("RGBA", (WINDOW_W, WINDOW_H), BACKDROP), box)
    canvas.alpha_composite(Image.new("RGBA", (WINDOW_W, WINDOW_H), BAND), box)
    if portrait is not None:
        canvas.alpha_composite(portrait, (PORTRAIT_X - PICTURE_X, PORTRAIT_Y - PICTURE_Y))
    text_x = TEXT_X if portrait is not None else TEXT_X_NO_PORTRAIT
    for row, line in enumerate(page[:LINES_PER_PAGE]):
        x = text_x
        top = TEXT_Y - PICTURE_Y + row * LINE_PITCH
        for ch in line.text:
            if ch in glyphs:
                _blit(canvas, glyphs[ch], x, top)
            x += advance(ch)
    return canvas


def _blit(canvas: Image.Image, rows: List[int], x: int, y: int) -> None:
    pixels = canvas.load()
    for ry, word in enumerate(rows):
        for rx in range(16):
            if word >> (15 - rx) & 1:
                px, py = x + rx, y + ry
                if 0 <= px < PICTURE_W and 0 <= py < PICTURE_H:
                    pixels[px, py] = (255, 255, 255, 255)


def speaker_name(face: int) -> Optional[str]:
    """The character name of a face number, from ``speaker_names.json`` (only the numbers checked on screen)."""
    return SPEAKERS.get(f"{face:02X}")
