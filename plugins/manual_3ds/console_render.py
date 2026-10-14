"""Draws a built manual page the way the console's Instruction Manual viewer draws it (Pillow, no Qt).

The page is read from the BCLYT files the viewer reads: every pane is drawn where it is stored (its own x, y
added to the groups it sits in), the window panes with their frame textures, the picture panes with their BCLIM
textures, the text panes with the console's own font. Nothing here lays text out from the translation: the
panel builds the page the way the console build does and hands the files here, the CLI hands the files of a
candidate build. The screens (top 400 x 240, bottom 320 x 240, the viewer's chrome) are composed in sim_screens.

Coordinates: a BCLYT pane is positioned by its origin (top-left for the manual's panes, centre for the root);
y grows upward. The page column image is 320 px wide; column row 0 is page y = +TOP_MARGIN (the top of the
page's white backdrop, `__BGRECT__`), so column row r = TOP_MARGIN - page_y.

Every constant that was measured against console screenshots carries the screenshot it was measured on.
"""
from __future__ import annotations

import math
import struct
from dataclasses import dataclass, field
from typing import Any, Dict, Iterator, List, Optional, Tuple

from PIL import Image

from core.texture_formats import flim

PANE_KINDS = (b"pan1", b"pic1", b"txt1", b"wnd1", b"bnd1")
TOP_MARGIN = 204.0          # the page backdrop starts 204 px above the text origin (every *_info __BGRECT__ is at y=204)
TOP_MARGIN_ROWS = 204
COLUMN_WIDTH = 320
# The column image is wider than the card: a line that runs past the card's edge is drawn over the scroll track
# on the console (shots_r8 2011-01-03_05-17-58.769: the "100" of home_menu_manual page 3, large, reaches
# canvas x 361, two columns into the track), so its overrun is kept and composed there.
OVERRUN = 16
# The console scales a glyph by fontSizeX / FONT_WIDTH across and fontSizeY / FONT_HEIGHT down (the font's FINF
# width and height; cbf_std has 25 and 30) and adds the pane's charSpace after every glyph. Measured on
# shots_r17b 2011-01-04_01-59-44.529: that gives a text difference of 0.9 where /24 or no charSpace give 13 to 25.
FONT_WIDTH = 25
FONT_HEIGHT = 30
FONT_WIDTH_FALLBACK = FONT_WIDTH
# A line's ink must stop this far before a picture's left edge, and before a box frame's inner edge (the frame
# textures of the boxes are 4 px wide); the layout check and the defect finder share these.
PICTURE_MARGIN = 1.0
FRAME_INNER = 4.0
# An overrun under this (px) is not a defect: the console rounds glyph positions to whole pixels, so a line that
# ends 0.3 px past an edge shows no ink there. The defect finder and the layout check share it.
SUB_PIXEL = 0.5
# The viewer breaks a stored line inside its pane when the line's advance comes within this of the pane width.
# Measured on shots_r17b 2011-01-04_01-58-38.378 against the round-8 health document: a 301.0 px line in a
# 301.8 px box was broken, a 316.2 px line in a 321.3 px box was not. Refined by the validation run.
WRAP_SLACK = 2.0
# Texture flip codes of a window frame (nw4r TextureFlip).
FLIP_NONE, FLIP_H, FLIP_V, FLIP_HV, FLIP_R90, FLIP_L90 = range(6)

RGBA = Tuple[int, int, int, int]


@dataclass
class Material:
    name: str
    tev: RGBA                           # the first colour slot (RGBA bytes as stored)
    textures: List[Tuple[int, int, int]]   # (texture index in txl1, wrapS, wrapT)


@dataclass
class Pane:
    kind: str
    name: str
    visible: bool
    origin: int
    alpha: int
    x: float
    y: float
    w: float
    h: float
    abs_x: float = 0.0       # page position of the pane's origin point (groups added)
    abs_y: float = 0.0
    parent_alpha: int = 255
    # pic1
    colours: Tuple[RGBA, RGBA, RGBA, RGBA] = ((255,) * 4,) * 4
    material: int = 0
    texcoords: Tuple[float, ...] = (0.0, 0.0, 1.0, 0.0, 0.0, 1.0, 1.0, 1.0)
    # txt1
    text: str = ""
    font_index: int = 0
    text_pos: int = 0
    text_align: int = 0
    font_size: Tuple[float, float] = (0.0, 0.0)
    char_space: float = 0.0
    line_space: float = 0.0
    # wnd1
    inflation: Tuple[float, float, float, float] = (0.0, 0.0, 0.0, 0.0)
    frames: List[Tuple[int, int]] = field(default_factory=list)   # (material, flip)

    @property
    def top_left(self) -> Tuple[float, float]:
        """Page position of the pane's top-left corner, from its origin point (0..8: a 3 x 3 grid, row-major)."""
        ox = (self.origin % 3) * 0.5
        oy = (self.origin // 3) * 0.5
        return self.abs_x - ox * self.w, self.abs_y + oy * self.h


@dataclass
class Layout:
    width: float
    height: float
    textures: List[str]
    fonts: List[str]
    materials: List[Material]
    panes: List[Pane]


def _sections(data: bytes) -> Iterator[Tuple[bytes, int, int]]:
    header = struct.unpack_from("<H", data, 0x06)[0]
    count = struct.unpack_from("<H", data, 0x10)[0]
    pos = header
    for _ in range(count):
        size = struct.unpack_from("<I", data, pos + 4)[0]
        yield data[pos:pos + 4], pos, size
        pos += size


def _names(data: bytes, pos: int) -> List[str]:
    count = struct.unpack_from("<I", data, pos + 8)[0]
    out = []
    for index in range(count):
        start = pos + 12 + struct.unpack_from("<I", data, pos + 12 + 4 * index)[0]
        out.append(data[start:].split(b"\0")[0].decode("ascii", "replace"))
    return out


def _materials(data: bytes, pos: int, size: int) -> List[Material]:
    count = struct.unpack_from("<I", data, pos + 8)[0]
    starts = [pos + struct.unpack_from("<I", data, pos + 12 + 4 * index)[0] for index in range(count)]
    out = []
    for start in starts:
        name = data[start:start + 0x14].split(b"\0")[0].decode("ascii", "replace")
        tev = struct.unpack_from("<4B", data, start + 0x14)
        flags = struct.unpack_from("<I", data, start + 0x30)[0]
        textures = [struct.unpack_from("<HBB", data, start + 0x34 + 4 * t) for t in range(flags & 3)]
        out.append(Material(name, tev, textures))
    return out


def parse(data: bytes) -> Layout:
    """Every pane of a BCLYT with its page position, plus the texture, font and material tables."""
    if data[:4] != b"CLYT":
        raise ValueError(f"not a BCLYT: {data[:4]!r}")
    width = height = 0.0
    textures: List[str] = []
    fonts: List[str] = []
    materials: List[Material] = []
    panes: List[Pane] = []
    groups: List[Tuple[float, float, int]] = [(0.0, 0.0, 255)]
    last: Tuple[float, float, int] = (0.0, 0.0, 255)
    for magic, pos, size in _sections(data):
        if magic == b"lyt1":
            _origin, width, height = struct.unpack_from("<Iff", data, pos + 8)
        elif magic == b"txl1":
            textures = _names(data, pos)
        elif magic == b"fnl1":
            fonts = _names(data, pos)
        elif magic == b"mat1":
            materials = _materials(data, pos, size)
        elif magic == b"pas1":
            groups.append(last)
        elif magic == b"pae1":
            if len(groups) > 1:
                groups.pop()
        elif magic in PANE_KINDS:
            pane = _pane(data, pos, magic)
            ox, oy, parent_alpha = groups[-1]
            pane.abs_x = ox + pane.x
            pane.abs_y = oy + pane.y
            pane.parent_alpha = parent_alpha
            panes.append(pane)
            # A child's alpha is scaled by its parents' when its "influenced alpha" flag (bit 1) is set.
            own = pane.alpha * parent_alpha // 255 if pane.visible else 0
            last = (pane.abs_x, pane.abs_y, own)
    return Layout(width, height, textures, fonts, materials, panes)


def _pane(data: bytes, pos: int, magic: bytes) -> Pane:
    flags, origin, alpha = struct.unpack_from("<BBB", data, pos + 8)
    name = data[pos + 0x0C:pos + 0x1C].split(b"\0")[0].decode("ascii", "replace")
    x, y = struct.unpack_from("<ff", data, pos + 0x24)
    w, h = struct.unpack_from("<ff", data, pos + 0x44)
    pane = Pane(magic.decode("ascii"), name, bool(flags & 1), origin, alpha, x, y, w, h)
    if magic == b"pic1":
        pane.colours = tuple(struct.unpack_from("<4B", data, pos + 0x4C + 4 * index) for index in range(4))  # type: ignore[assignment]
        pane.material, count = struct.unpack_from("<HB", data, pos + 0x5C)
        if count:
            pane.texcoords = struct.unpack_from("<8f", data, pos + 0x60)
    elif magic == b"txt1":
        _buf, str_bytes, pane.material, pane.font_index = struct.unpack_from("<HHHH", data, pos + 0x4C)
        pane.text_pos, pane.text_align = struct.unpack_from("<BB", data, pos + 0x54)
        offset = struct.unpack_from("<I", data, pos + 0x58)[0]
        top = struct.unpack_from("<4B", data, pos + 0x5C)
        bottom = struct.unpack_from("<4B", data, pos + 0x60)
        pane.colours = (top, top, bottom, bottom)
        sx, sy, pane.char_space, pane.line_space = struct.unpack_from("<ffff", data, pos + 0x64)
        pane.font_size = (sx, sy)
        pane.text = data[pos + offset:pos + offset + str_bytes].decode("utf-16-le", "replace").rstrip("\0")
    elif magic == b"wnd1":
        pane.inflation = struct.unpack_from("<ffff", data, pos + 0x4C)
        count = data[pos + 0x5C]
        content, frames = struct.unpack_from("<II", data, pos + 0x60)
        pane.colours = tuple(struct.unpack_from("<4B", data, pos + content + 4 * index) for index in range(4))  # type: ignore[assignment]
        pane.material = struct.unpack_from("<H", data, pos + content + 16)[0]
        for index in range(count):
            at = pos + struct.unpack_from("<I", data, pos + frames + 4 * index)[0]
            pane.frames.append(struct.unpack_from("<HB", data, at))
    return pane


# -- textures and glyphs ----------------------------------------------------------------------------


def decode_bclim(data: bytes) -> Image.Image:
    """A manual's BCLIM as the viewer draws it: the stored rows top first, the image in the top-left corner.

    flim.read gives exactly that for a 3DS CLIM (checked on the console: the icon row of cap_menu_manual_6 is at
    the top on shots_r17b 2011-01-04_01-59-44.529, and num_01, 18 x 18 in a 32 x 32 texture, shows its boxed digit).
    """
    return flim.read(data, {})[0].image.convert("RGBA")


class Textures:
    """BCLIM textures by name, decoded once (decode_bclim)."""

    def __init__(self, files: Dict[str, bytes]):
        self._files = files
        self._images: Dict[str, Optional[Image.Image]] = {}

    def get(self, name: str) -> Optional[Image.Image]:
        if name not in self._images:
            data = self._files.get(name)
            image = None
            if data is not None:
                try:
                    image = decode_bclim(data)
                except Exception:
                    image = None
            self._images[name] = image
        return self._images[name]


class Glyphs:
    """Glyph cells of the console's system font (a bcfnt.Font from the owner's tools), as Pillow alpha masks."""

    def __init__(self, font: Any, bcfnt: Any):
        self.font = font
        self._bcfnt = bcfnt
        self._cells: Dict[int, Optional[Image.Image]] = {}
        finf = font.finf
        self.line_feed = finf[1]
        self.height = finf[20] if len(finf) > 22 else font.sheets.cell_height
        self.width = finf[21] if len(finf) > 22 else FONT_WIDTH_FALLBACK
        self.ascent = finf[22] if len(finf) > 22 else font.sheets.baseline

    def has(self, code: int) -> bool:
        return code in self.font.cmap

    def metrics(self, code: int) -> Tuple[int, int, int]:
        """(left, glyph width, char width) of a code point; the font's default widths when it has no glyph."""
        index = self.font.cmap.get(code)
        if index is None or index >= len(self.font.widths):
            return 0, 0, self.font.finf[5]
        return self.font.widths[index]

    def cell(self, code: int) -> Optional[Image.Image]:
        """The glyph's cell as an "L" image (0..255 coverage), cell_width x cell_height."""
        if code not in self._cells:
            image = None
            if code in self.font.cmap:
                rows = self._bcfnt.glyph_rows(self.font, code)
                height = len(rows)
                width = len(rows[0]) if height else 0
                if width and height:
                    raw = bytes(min(255, (v[1] if isinstance(v, tuple) else v) * 17) for row in rows for v in row)
                    image = Image.frombytes("L", (width, height), raw)
            self._cells[code] = image
        return self._cells[code]


# -- drawing ----------------------------------------------------------------------------------------


@dataclass
class TextRun:
    """One drawn line of a text pane: where it starts, its advance, and the text (for the defect finder)."""

    pane: str
    text: str
    x: float          # page x where the first glyph's pen starts
    top: float        # page y of the line's top
    width: float      # advance of the whole line
    wrapped: bool     # the viewer broke this line inside the pane (the text did not fit the box)
    ink_right: float = 0.0   # page x where the last glyph's ink ends (its left bearing plus glyph width)


def _blend(colour: RGBA, alpha: int) -> RGBA:
    return colour[0], colour[1], colour[2], colour[3] * alpha // 255


def _frame_image(texture: Image.Image, flip: int) -> Image.Image:
    if flip == FLIP_H:
        return texture.transpose(Image.Transpose.FLIP_LEFT_RIGHT)
    if flip == FLIP_V:
        return texture.transpose(Image.Transpose.FLIP_TOP_BOTTOM)
    if flip == FLIP_HV:
        return texture.transpose(Image.Transpose.ROTATE_180)
    if flip == FLIP_R90:
        return texture.transpose(Image.Transpose.ROTATE_270)
    if flip == FLIP_L90:
        return texture.transpose(Image.Transpose.ROTATE_90)
    return texture


def _stretch_edge(texture: Image.Image, width: int, height: int, anchor: str) -> Image.Image:
    """The texture drawn in a width x height box with clamp-to-edge sampling past its own size.

    `anchor` names the corner the texture sits in ("lt", "rt", "lb", "rb"); the rows and columns past it repeat
    the texture's last row or column, which is how the console stretches a frame texture along an edge.
    """
    out = Image.new("RGBA", (max(width, 1), max(height, 1)))
    tw, th = texture.size
    cw, ch = min(tw, width), min(th, height)
    left = 0 if anchor[0] == "l" else width - cw
    top = 0 if anchor[1] == "t" else height - ch
    src_x = 0 if anchor[0] == "l" else tw - cw
    src_y = 0 if anchor[1] == "t" else th - ch
    corner = texture.crop((src_x, src_y, src_x + cw, src_y + ch))
    out.paste(corner, (left, top))
    if width > cw:
        column = texture.crop((tw - 1, src_y, tw, src_y + ch)) if anchor[0] == "l" else texture.crop((0, src_y, 1, src_y + ch))
        strip = column.resize((width - cw, ch), Image.Resampling.NEAREST)
        out.paste(strip, (cw if anchor[0] == "l" else 0, top))
    if height > ch:
        row = out.crop((0, top + ch - 1, width, top + ch)) if anchor[1] == "t" else out.crop((0, top, width, top + 1))
        strip = row.resize((width, height - ch), Image.Resampling.NEAREST)
        out.paste(strip, (0, ch if anchor[1] == "t" else 0))
    return out


class PageRenderer:
    """Draws the panes of a page's BCLYT files onto a column image."""

    def __init__(self, textures: Textures, glyphs: Glyphs, scale_x_divisor: float = 0.0, char_space: bool = True):
        self.textures = textures
        self.glyphs = glyphs
        # Calibration knobs (see sim_calibration in the docs): the x scale divisor (FINF width, 25) and whether
        # the pane's charSpace is added between glyphs.
        self.scale_x_divisor = scale_x_divisor or glyphs.width
        self.use_char_space = char_space
        self.wrap_slack = WRAP_SLACK
        self.runs: List[TextRun] = []
        self.missing: set = set()

    # -- page -------------------------------------------------------------------------------------

    def render(self, files: List[bytes], height: Optional[float] = None) -> Image.Image:
        """The column of a page: `files` in draw order (the *_bg file first, then the K sub-pages)."""
        layouts = [parse(data) for data in files]
        page_height = height or max((lay.height for lay in layouts), default=0.0)
        rows = int(math.ceil(page_height + 2 * TOP_MARGIN))
        canvas = Image.new("RGBA", (COLUMN_WIDTH + OVERRUN, max(rows, 1)), (0, 0, 0, 0))
        for layout in layouts:
            for pane in layout.panes:
                if not pane.visible:
                    continue
                if pane.kind == "wnd1":
                    self._draw_window(canvas, layout, pane)
                elif pane.kind == "pic1":
                    self._draw_picture(canvas, layout, pane)
                elif pane.kind == "txt1":
                    self._draw_text(canvas, layout, pane)
        return canvas

    @staticmethod
    def to_column(page_x: float, page_y: float) -> Tuple[float, float]:
        return page_x, TOP_MARGIN - page_y

    # -- windows ----------------------------------------------------------------------------------

    def _texture_of(self, layout: Layout, material: int) -> Optional[Image.Image]:
        if material >= len(layout.materials) or not layout.materials[material].textures:
            return None
        index = layout.materials[material].textures[0][0]
        if index >= len(layout.textures):
            return None
        return self.textures.get(layout.textures[index])

    def _draw_window(self, canvas: Image.Image, layout: Layout, pane: Pane) -> None:
        left, top = pane.top_left
        cx, cy = self.to_column(left, top)
        x0, y0 = int(round(cx)), int(round(cy))
        width, height = int(round(pane.w)), int(round(pane.h))
        if width <= 0 or height <= 0:
            return
        alpha = pane.alpha * pane.parent_alpha // 255
        frames: List[Tuple[Optional[Image.Image], int]] = [(self._texture_of(layout, m), flip) for m, flip in pane.frames]
        # Frame thickness comes from the frame textures (nw4r Window::GetFrameSize); none without a texture.
        if len(frames) == 1 and frames[0][0] is not None:
            tex = frames[0][0]
            fl = fr = tex.width
            ft = fb = tex.height
        elif len(frames) >= 4 and all(f[0] is not None for f in frames[:4]):
            lt, rt, lb, _rb = (_frame_image(f[0], f[1]) for f in frames[:4])  # type: ignore[arg-type]
            fl, ft, fr, fb = lt.width, lt.height, rt.width, lb.height
        else:
            fl = fr = ft = fb = 0
        il, ir, it, ib = pane.inflation
        # Content: the inner rectangle in the vertex colours (a gradient is drawn as its average: flat here).
        content = tuple(sum(c[i] for c in pane.colours) // 4 for i in range(4))
        cl = int(round(fl - il))
        ct = int(round(ft - it))
        cw = int(round(pane.w - fl - fr + il + ir))
        ch = int(round(pane.h - ft - fb + it + ib))
        if content[3] and cw > 0 and ch > 0:
            fill = Image.new("RGBA", (cw, ch), _blend(content, alpha))
            canvas.alpha_composite(fill, (x0 + cl, y0 + ct))
        if fl == 0 and ft == 0:
            return
        # Frames: four L-shaped quads, each a corner plus the edge that follows it clockwise (nw4r DrawFrame).
        if len(frames) == 1:
            base = frames[0][0]
            assert base is not None
            quads = [
                ("lt", base, 0, 0, width - fr, ft),
                ("rt", base.transpose(Image.Transpose.FLIP_LEFT_RIGHT), width - fr, 0, fr, height - fb),
                ("rb", base.transpose(Image.Transpose.ROTATE_180), fl, height - fb, width - fl, fb),
                ("lb", base.transpose(Image.Transpose.FLIP_TOP_BOTTOM), 0, ft, fl, height - ft),
            ]
        else:
            lt, rt, lb, rb = (_frame_image(f[0], f[1]) for f in frames[:4])  # type: ignore[arg-type]
            quads = [
                ("lt", lt, 0, 0, width - fr, ft),
                ("rt", rt, width - fr, 0, fr, height - fb),
                ("rb", rb, fl, height - fb, width - fl, fb),
                ("lb", lb, 0, ft, fl, height - ft),
            ]
        for anchor, tex, qx, qy, qw, qh in quads:
            if qw <= 0 or qh <= 0:
                continue
            piece = _stretch_edge(tex, qw, qh, anchor)
            if alpha != 255:
                piece = _with_alpha(piece, alpha)
            canvas.alpha_composite(piece, (x0 + qx, y0 + qy))

    # -- pictures ---------------------------------------------------------------------------------

    def _draw_picture(self, canvas: Image.Image, layout: Layout, pane: Pane) -> None:
        left, top = pane.top_left
        cx, cy = self.to_column(left, top)
        x0, y0 = int(round(cx)), int(round(cy))
        width, height = int(round(pane.w)), int(round(pane.h))
        if width <= 0 or height <= 0:
            return
        alpha = pane.alpha * pane.parent_alpha // 255
        texture = self._texture_of(layout, pane.material)
        if texture is None:
            colour = tuple(sum(c[i] for c in pane.colours) // 4 for i in range(4))
            if colour[3]:
                canvas.alpha_composite(Image.new("RGBA", (width, height), _blend(colour, alpha)), (x0, y0))
            return
        u0, v0, u1, _v1, _u2, v2, _u3, _v3 = pane.texcoords
        tw, th = texture.size
        # Texture coordinates of the top-left, top-right and bottom-left corners; reversed ones mirror the picture.
        box = (min(u0, u1) * tw, min(v0, v2) * th, max(u0, u1) * tw, max(v0, v2) * th)
        if 0.0 <= min(box) and box[2] <= tw and box[3] <= th and box[2] > box[0] and box[3] > box[1]:
            piece = texture.crop(tuple(int(round(v)) for v in box))
        else:
            piece = texture  # a repeating texture (viewer chrome); the pages do not use one
        if u1 < u0:
            piece = piece.transpose(Image.Transpose.FLIP_LEFT_RIGHT)
        if v2 < v0:
            piece = piece.transpose(Image.Transpose.FLIP_TOP_BOTTOM)
        if piece.size != (width, height):
            piece = piece.resize((width, height), Image.Resampling.BILINEAR)
        tint = tuple(sum(c[i] for c in pane.colours) // 4 for i in range(4))
        if tint != (255, 255, 255, 255) or alpha != 255:
            piece = _tinted(piece, tint, alpha)
        canvas.alpha_composite(piece, (x0, y0))

    # -- text -------------------------------------------------------------------------------------

    def _advance(self, code: int, scale_x: float) -> float:
        return self.glyphs.metrics(code)[2] * scale_x

    def _line_width(self, text: str, scale_x: float, char_space: float) -> float:
        if not text:
            return 0.0
        return sum(self._advance(ord(ch), scale_x) for ch in text) + char_space * (len(text) - 1)

    def _wrap(self, text: str, limit: float, scale_x: float, char_space: float) -> List[Tuple[str, bool]]:
        """The lines the viewer draws for one stored line: greedy at the pane width, broken at a space.

        The stored line is drawn whole when it fits. When it does not, the viewer breaks it at the last space
        that fits and continues one line step below, inside the same pane (the defect the model missed).
        """
        out: List[Tuple[str, bool]] = []
        for stored in text.split("\n"):
            wrapped = False
            rest = stored
            while rest:
                if self._line_width(rest, scale_x, char_space) <= limit + 1e-6:
                    out.append((rest, wrapped))
                    break
                cut = -1
                for index, ch in enumerate(rest):
                    if ch == " " and self._line_width(rest[:index], scale_x, char_space) <= limit + 1e-6:
                        cut = index
                if cut <= 0:
                    # No space fits: the viewer breaks inside the word, after the last glyph that fits.
                    cut = 1
                    while cut < len(rest) and self._line_width(rest[:cut + 1], scale_x, char_space) <= limit + 1e-6:
                        cut += 1
                    out.append((rest[:cut], wrapped))
                    rest = rest[cut:]
                else:
                    out.append((rest[:cut], wrapped))
                    rest = rest[cut + 1:]
                wrapped = True
        return out or [("", False)]

    def _draw_text(self, canvas: Image.Image, layout: Layout, pane: Pane) -> None:
        if not pane.text:
            return
        sx, sy = pane.font_size
        scale_x = sx / self.scale_x_divisor
        scale_y = sy / self.glyphs.height
        char_space = pane.char_space if self.use_char_space else 0.0
        line_height = sy + pane.line_space
        lines = self._wrap(pane.text, pane.w - self.wrap_slack, scale_x, char_space)
        left, top = pane.top_left
        alpha = pane.alpha * pane.parent_alpha // 255
        # The text block sits in the pane by text_pos (a 3 x 3 grid); each line by text_align.
        block_h = line_height * len(lines)
        row = pane.text_pos // 3
        block_top = top - (pane.h - block_h) * row * 0.5
        column_align = pane.text_pos % 3 if pane.text_align == 0 else pane.text_align - 1
        colour_top, colour_bottom = pane.colours[0], pane.colours[2]
        for index, (line, wrapped) in enumerate(lines):
            width = self._line_width(line, scale_x, char_space)
            start = left + (pane.w - width) * column_align * 0.5
            line_top = block_top - index * line_height
            self.runs.append(TextRun(pane.name, line, start, line_top, width, wrapped, self._ink_right(line, start, scale_x, char_space)))
            self._draw_line(canvas, line, start, line_top, scale_x, scale_y, char_space, colour_top, colour_bottom, alpha)

    def _ink_right(self, line: str, x: float, scale_x: float, char_space: float) -> float:
        pen = x
        right = x
        for ch in line:
            code = ord(ch)
            if not ch.isspace():
                left, glyph_w, _char_w = self.glyphs.metrics(code)
                right = max(right, pen + (left + glyph_w) * scale_x)
            pen += self._advance(code, scale_x) + char_space
        return right

    def _draw_line(self, canvas: Image.Image, line: str, x: float, top: float, scale_x: float, scale_y: float,
                   char_space: float, colour_top: RGBA, colour_bottom: RGBA, alpha: int) -> None:
        pen = x
        cell_w = self.glyphs.font.sheets.cell_width
        cell_h = self.glyphs.font.sheets.cell_height
        cx, cy = self.to_column(0.0, top)
        for ch in line:
            code = ord(ch)
            if not ch.isspace():
                cell = self.glyphs.cell(code)
                if cell is None:
                    self.missing.add(ch)
                else:
                    left, _glyph_w, _char_w = self.glyphs.metrics(code)
                    gx = pen + left * scale_x
                    self._blit_glyph(canvas, cell, gx, cy, cell_w * scale_x, cell_h * scale_y, colour_top, colour_bottom, alpha)
            pen += self._advance(code, scale_x) + char_space

    @staticmethod
    def _blit_glyph(canvas: Image.Image, cell: Image.Image, x: float, y: float, width: float, height: float,
                    colour_top: RGBA, colour_bottom: RGBA, alpha: int) -> None:
        """Draw a glyph cell scaled to width x height at the fractional position (x, y), bilinear like the GPU."""
        x0, y0 = int(math.floor(x)), int(math.floor(y))
        fx, fy = x - x0, y - y0
        out_w, out_h = int(math.ceil(width + fx)) + 1, int(math.ceil(height + fy)) + 1
        # Affine: output pixel (u, v) samples the cell at ((u - fx) * cw / width, (v - fy) * ch / height).
        sx, sy = cell.width / width, cell.height / height
        mask = cell.transform((out_w, out_h), Image.Transform.AFFINE, (sx, 0.0, -fx * sx, 0.0, sy, -fy * sy),
                              Image.Resampling.BILINEAR, fillcolor=0)
        if alpha != 255:
            mask = mask.point(lambda v: v * alpha // 255)
        if colour_top == colour_bottom:
            ink = Image.new("RGBA", (out_w, out_h), colour_top)
        else:
            ink = Image.new("RGBA", (out_w, out_h), colour_top)
            bottom = Image.new("RGBA", (out_w, out_h), colour_bottom)
            ramp = Image.linear_gradient("L").resize((out_w, out_h))
            ink = Image.composite(bottom, ink, ramp)
        ink.putalpha(Image.eval(mask, lambda v: v) if colour_top[3] == 255 else mask.point(lambda v: v * colour_top[3] // 255))
        canvas.alpha_composite(ink, (x0, y0))


def _with_alpha(image: Image.Image, alpha: int) -> Image.Image:
    out = image.copy()
    out.putalpha(out.getchannel("A").point(lambda v: v * alpha // 255))
    return out


def _tinted(image: Image.Image, tint: RGBA, alpha: int) -> Image.Image:
    r, g, b, a = image.split()
    channels = [c.point(lambda v, t=t: v * t // 255) for c, t in zip((r, g, b), tint[:3])]
    a = a.point(lambda v: v * tint[3] * alpha // (255 * 255))
    return Image.merge("RGBA", channels + [a])


# -- the contents (Index.bclyt) ---------------------------------------------------------------------


@dataclass
class Category:
    name: str
    valid: bool
    pages: List[int]            # page file numbers (Page_NNN)


@dataclass
class Index:
    """What Index.bclyt says about a manual: the page titles, the categories and the sub-page counts."""

    titles: List[str]           # PageTitle_NNN in order: the console's page number is NNN + 1
    categories: List[Category]  # Category_NNN in order (the first one has no heading on the console)
    splits_large: List[int]     # __AREA__ blocks (480 px) per page, large text (MetaData SplitNumL)
    splits_small: List[int]

    def number_of(self, page: int) -> int:
        return page + 1

    def category_of(self, page: int) -> int:
        for index, category in enumerate(self.categories):
            if page in category.pages:
                return index
        return 0

    def title_of(self, page: int) -> str:
        return self.titles[page] if 0 <= page < len(self.titles) else ""


def _user_data(data: bytes, pos: int, size: int) -> Dict[str, Any]:
    body = data[pos + 8:pos + size]
    count = struct.unpack_from("<I", body, 0)[0]
    out: Dict[str, Any] = {}
    for index in range(count):
        base = 4 + index * 12
        name_off, data_off, length, kind = struct.unpack_from("<IIHB", body, base)
        name = body[base + name_off:].split(b"\0")[0].decode("ascii", "replace")
        if kind == 0:
            out[name] = body[base + data_off:base + data_off + length].decode("utf-8", "replace")
        elif kind == 1:
            out[name] = list(struct.unpack_from(f"<{length}i", body, base + data_off))
        else:
            out[name] = list(struct.unpack_from(f"<{length}f", body, base + data_off))
    return out


def read_index(data: bytes) -> Index:
    """The contents of a manual from its Index.bclyt (text panes plus their usd1 user data)."""
    texts: Dict[str, str] = {}
    user: Dict[str, Dict[str, Any]] = {}
    last = ""
    for magic, pos, size in _sections(data):
        if magic in PANE_KINDS:
            pane = _pane(data, pos, magic)
            last = pane.name
            if magic == b"txt1":
                texts[last] = pane.text
        elif magic == b"usd1":
            user[last] = _user_data(data, pos, size)
    titles = [texts[name] for name in sorted(texts) if name.startswith("PageTitle_")]
    categories = []
    for name in sorted(texts):
        if not name.startswith("Category_"):
            continue
        facts = user.get(name, {})
        pages = [facts[key][0] for key in sorted(facts) if key.startswith("PageID_")]
        categories.append(Category(texts[name], bool(facts.get("IsValid", [1])[0]), pages))
    meta = user.get("MetaData", {})
    return Index(titles, categories, list(meta.get("SplitNumL", [])), list(meta.get("SplitNumS", [])))


# -- page files -------------------------------------------------------------------------------------


def page_files(archive_files: Dict[str, bytes], page: int, part: str) -> List[bytes]:
    """The BCLYT files of one page in draw order: the backdrop, then the sub-pages K = 0, 1, ...; [] if none."""
    prefix = f"Page_{page:03d}_{part}_"
    subs = sorted(
        (name for name in archive_files if name.startswith(prefix) and name[len(prefix):-6].isdigit()),
        key=lambda name: int(name[len(prefix):-6]),
    )
    if not subs:
        return []
    out = []
    backdrop = archive_files.get(f"{prefix}bg.bclyt")
    if backdrop is not None:
        out.append(backdrop)
    out.extend(archive_files[name] for name in subs)
    return out


def page_numbers(archive_files: Dict[str, bytes], part: str) -> List[int]:
    out = set()
    for name in archive_files:
        if name.startswith("Page_") and name.endswith("_0.bclyt") and f"_{part}_" in name:
            out.add(int(name[5:8]))
    return sorted(out)
