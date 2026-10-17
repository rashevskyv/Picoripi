"""A Switch FLYT message window drawn with the game's own fonts (one renderer for the Switch Pokémon plugins).

The window and the text panes come from the layout: ``plugins.manual_3ds.console_render.parse`` reads a FLYT
version 9 file (its ``txt1`` and ``wnd1`` fields). A text pane gives the rectangle, font size, line spacing,
alignment and vertical place of its lines. The font is named by the layout's font setting (``.fcpx``): that file
lists the fonts, and the first font with a glyph draws the character (fallback in list order). Each font is an
OpenType file scrambled as ``.BFOTF`` in the game's ``bin/font`` folder; ``core.font_formats.bfotf`` unscrambles it.

Coordinates: the canvas is the layout's ``lyt1`` size (1920 x 1080 for the Sword/Shield message layouts). A pane
with origin 0 is centred on its stored position (x right, y up from the canvas centre). That rule is checked on
the text panes of ``msg_00.bflyt`` and the language screen. Other origins are drawn with the same rule and are not
checked yet.
"""
from __future__ import annotations

import io
import re
from dataclasses import dataclass, replace
from typing import Dict, List, Optional, Sequence, Tuple

from PIL import Image, ImageDraw, ImageFont

from core.font_formats import bfotf
from plugins.manual_3ds import console_render as cr

RGBA = Tuple[int, int, int, int]
Rect = Tuple[float, float, float, float]          # x0, y0, x1, y1 on the canvas, y down
_FCPX_NAME = re.compile(rb"[\x20-\x7e]{3,}")


@dataclass(frozen=True)
class TextPane:
    """One ``txt1`` pane: where its lines go and how they are set."""
    name: str
    rect: Rect
    origin: int
    font_index: int
    size: Tuple[float, float]        # fontSizeX, fontSizeY in layout pixels
    char_space: float
    line_space: float
    text_pos: int                    # 0 top, 1 centre, 2 bottom: the lines' place inside the pane
    text_align: int                  # 0 left, 1 centre, 2 right
    colour: RGBA


@dataclass(frozen=True)
class MessageLayout:
    """A message window: the canvas size, its frame (the first ``wnd1``), the message panes (visible ``txt1``
    panes inside the frame, one line each, in order), the speaker-name pane and the font names."""
    canvas: Tuple[float, float]
    window: Optional[Rect]
    panes: List[TextPane]
    fonts: List[str]                 # font names of the layout's font setting, in fallback order
    name: Optional[TextPane] = None  # the speaker-name pane (hidden, or outside the frame); not drawn yet


def font_names(fcpx: bytes) -> List[str]:
    """The font file names of a ``.fcpx`` font setting, in fallback order (``*.otf``)."""
    return [m.group(0).decode("ascii") for m in _FCPX_NAME.finditer(fcpx) if m.group(0).lower().endswith(b".otf")]


def _rect(pane: cr.Pane, canvas: Tuple[float, float], offset: Tuple[float, float] = (0.0, 0.0)) -> Rect:
    cx = canvas[0] / 2 + pane.abs_x + offset[0]
    cy = canvas[1] / 2 - pane.abs_y - offset[1]
    return (cx - pane.w / 2, cy - pane.h / 2, cx + pane.w / 2, cy + pane.h / 2)


def _inside(rect: Rect, outer: Rect) -> bool:
    return rect[0] >= outer[0] - 0.5 and rect[1] >= outer[1] - 0.5 and rect[2] <= outer[2] + 0.5 and rect[3] <= outer[3] + 0.5


def read_layout(layout: bytes, fcpx: bytes, offset: Tuple[float, float] = (0.0, 0.0),
                names: Optional[Sequence[str]] = None) -> MessageLayout:
    """The message window of a FLYT layout: the message panes, the frame that holds them, the name pane, the fonts.

    ``offset`` moves the whole layout on the canvas (x right, y up): a parts pane of the window's outer layout places it
    (Z-A: msg_body_00.bflyt puts msg_00.bflyt at y -370). ``names`` picks the message panes by name (visible ones).
    Without it, the message panes are the visible ``txt1`` panes with the largest string buffer (a message line's is
    about 4006 bytes; a speaker name's is small). The frame is the first ``wnd1`` that holds all of them; none (Arceus,
    Scarlet / Violet) means the box is drawn around the panes. The name pane is the first other ``txt1``.
    """
    parsed = cr.parse(layout)
    canvas = (parsed.width, parsed.height)
    frames = [_rect(pane, canvas, offset) for pane in parsed.panes if pane.kind == "wnd1"]
    texts = [(pane, TextPane(pane.name, _rect(pane, canvas, offset), pane.origin, pane.font_index,
                             (pane.font_size[0], pane.font_size[1]), pane.char_space, pane.line_space,
                             pane.text_pos, pane.text_align, _colour(pane.colours[0])))
             for pane in parsed.panes if pane.kind == "txt1"]
    top = max((raw.buffer for raw, _text in texts if raw.visible), default=0)
    if names is not None:
        message = [index for index, (raw, _text) in enumerate(texts) if raw.visible and raw.name in names]
        message.sort(key=lambda index: list(names).index(texts[index][0].name))
    else:
        message = [index for index, (raw, _text) in enumerate(texts) if raw.visible and top > 0 and raw.buffer == top]
    panes = [texts[index][1] for index in message]
    window = next((frame for frame in frames if all(_inside(text.rect, frame) for text in panes)), None)
    others = [text for index, (_raw, text) in enumerate(texts) if index not in message]
    name = others[0] if others else None
    return MessageLayout(canvas, window, panes, font_names(fcpx), name)


def _colour(value: Tuple[int, int, int, int]) -> RGBA:
    return (value[0], value[1], value[2], value[3])


class Face:
    """One OpenType font: its character map, advances and the PIL font that draws it at ``px`` pixels per em."""

    def __init__(self, otf: bytes):
        self.table = bfotf.OpenType(otf)
        self.cmap: Dict[int, int] = self.table.cmap()
        self._otf = otf
        self._pil: Dict[int, ImageFont.FreeTypeFont] = {}

    @classmethod
    def from_bfotf(cls, data: bytes) -> "Face":
        return cls(bfotf.decrypt(data)[0])

    def has(self, ch: str) -> bool:
        return ord(ch) in self.cmap

    def advance(self, ch: str, px: float) -> float:
        return self.table.advance(self.cmap[ord(ch)]) * px / self.table.units_per_em

    def ascent(self, px: float) -> float:
        return self.table.ascender * px / self.table.units_per_em

    def pil(self, px: float) -> ImageFont.FreeTypeFont:
        key = round(px * 4)
        if key not in self._pil:
            self._pil[key] = ImageFont.truetype(io.BytesIO(self._otf), size=max(1, round(px)))
        return self._pil[key]

    def draw(self, image: Image.Image, ch: str, pen: float, baseline: float, px: float, colour: RGBA) -> None:
        """One glyph: its pen position (left) and baseline, drawn with the outline font."""
        ImageDraw.Draw(image).text((pen, baseline), ch, font=self.pil(px), fill=colour, anchor="ls")


# The alpha of a TMP distance-field atlas: the edge is at 128; the ramp is 56 levels wide (a soft edge, not measured).
_SDF_EDGE, _SDF_RAMP = 128.0, 56.0


class TmpFace:
    """A TextMesh Pro font asset: its glyph table, character map and atlas (the ``font/<bundle>/<name>.json`` and
    ``.png`` of the workspace). Metrics are in the font's point size; a glyph at ``px`` pixels per em is scaled by
    ``px / pointSize``. The atlas is a signed distance field: the glyph is where the value is above the edge."""

    def __init__(self, asset: dict, atlas: Image.Image):
        info = asset.get("m_FaceInfo") or {}
        self.point = float(info.get("m_PointSize") or 0.0)
        self.face_scale = float(info.get("m_Scale") or 1.0)
        self.line_height = float(info.get("m_LineHeight") or 0.0)
        self.ascent_line = float(info.get("m_AscentLine") or 0.0)
        if self.point <= 0:
            raise ValueError("the TMP font asset has no point size")
        self.glyphs = {int(g["m_Index"]): g for g in asset.get("m_GlyphTable") or []}
        self.cmap = {int(c["m_Unicode"]): (int(c["m_GlyphIndex"]), float(c.get("m_Scale") or 1.0))
                     for c in asset.get("m_CharacterTable") or []}
        self.padding = float(asset.get("m_AtlasPadding") or 0)
        self.atlas = atlas.convert("L")

    def _k(self, px: float) -> float:
        return px / self.point * self.face_scale

    def has(self, ch: str) -> bool:
        entry = self.cmap.get(ord(ch))
        return entry is not None and entry[0] in self.glyphs

    def advance(self, ch: str, px: float) -> float:
        index, char_scale = self.cmap[ord(ch)]
        return self.glyphs[index]["m_Metrics"]["m_HorizontalAdvance"] * self._k(px) * char_scale

    def ascent(self, px: float) -> float:
        return self.ascent_line * self._k(px)

    def draw(self, image: Image.Image, ch: str, pen: float, baseline: float, px: float, colour: RGBA) -> None:
        """One glyph: its atlas rectangle (padding included) scaled to the glyph's metrics, thresholded as an SDF."""
        index, char_scale = self.cmap[ord(ch)]
        glyph = self.glyphs[index]
        metrics, rect = glyph["m_Metrics"], glyph["m_GlyphRect"]
        k = self._k(px) * char_scale
        p = self.padding
        width, height = float(rect["m_Width"]) + 2 * p, float(rect["m_Height"]) + 2 * p
        if width <= 0 or height <= 0 or metrics["m_Width"] <= 0:
            return
        # The atlas origin is the bottom-left corner (Unity); the picture's origin is the top-left.
        left_px = float(rect["m_X"]) - p
        top_px = self.atlas.height - (float(rect["m_Y"]) + float(rect["m_Height"]) + p)
        crop = self.atlas.crop((round(left_px), round(top_px), round(left_px + width), round(top_px + height)))
        sx = float(metrics["m_Width"]) * k / float(rect["m_Width"]) if rect["m_Width"] else k
        sy = float(metrics["m_Height"]) * k / float(rect["m_Height"]) if rect["m_Height"] else k
        dest_w, dest_h = max(1, round(width * sx)), max(1, round(height * sy))
        mask = crop.resize((dest_w, dest_h), Image.BILINEAR)
        alpha = mask.point(lambda v: int(max(0.0, min(1.0, (v - _SDF_EDGE) / _SDF_RAMP + 0.5)) * 255))
        alpha = alpha.point(lambda v: v * colour[3] // 255)
        x = pen + float(metrics["m_HorizontalBearingX"]) * k - p * sx
        y = baseline - float(metrics["m_HorizontalBearingY"]) * k - p * sy
        layer = Image.new("RGBA", (dest_w, dest_h), colour[:3] + (0,))
        layer.putalpha(alpha)
        _composite(image, layer, round(x), round(y))


def _composite(image: Image.Image, layer: Image.Image, x: int, y: int) -> None:
    """Alpha-composites ``layer`` onto ``image`` at (x, y), clipped to the image."""
    x0, y0 = max(0, -x), max(0, -y)
    x1, y1 = min(layer.width, image.width - x), min(layer.height, image.height - y)
    if x1 <= x0 or y1 <= y0:
        return
    image.alpha_composite(layer.crop((x0, y0, x1, y1)), (x + x0, y + y0))


class FontChain:
    """The faces of one layout's font setting, in fallback order."""

    def __init__(self, faces: Sequence[Face]):
        self.faces = list(faces)

    def face_of(self, ch: str) -> Optional[Face]:
        return next((face for face in self.faces if face.has(ch)), None)

    def width(self, text: str, px: float, char_space: float = 0.0) -> float:
        total = 0.0
        for ch in text:
            face = self.face_of(ch)
            if face is not None:
                total += face.advance(ch, px) + char_space
        return total


def line_pitch(pane: TextPane) -> float:
    """The distance from one line to the next: the font's height plus the pane's line spacing."""
    return pane.size[1] + pane.line_space


def wrap_text(text: str, width: float, chain: FontChain, px: float, char_space: float = 0.0) -> Tuple[List[str], bool]:
    """``text`` as lines no wider than ``width`` (word wrap at spaces). Returns the lines and whether a word is wider
    than ``width`` (that word then stands on its own line, wider than the pane)."""
    lines: List[str] = []
    current = ""
    too_long = False
    for word in text.split(" "):
        candidate = word if not current else current + " " + word
        if current and chain.width(candidate, px, char_space) > width:
            lines.append(current)
            current = word
        else:
            current = candidate
        if chain.width(current, px, char_space) > width:
            too_long = True
    lines.append(current)
    return lines, too_long


def draw_pane(image: Image.Image, pane: TextPane, chain: FontChain, lines: List[str]) -> List[int]:
    """Draws the lines of one pane onto ``image`` (canvas size). Returns the indexes of lines wider than the pane."""
    x0, y0, x1, y1 = pane.rect
    px = pane.size[0]
    pitch = line_pitch(pane)
    block = len(lines) * pitch
    if pane.text_pos == 0:
        top = y0
    elif pane.text_pos == 2:
        top = y1 - block
    else:
        top = y0 + (y1 - y0 - block) / 2
    too_wide: List[int] = []
    for index, line in enumerate(lines):
        width = chain.width(line, px, pane.char_space)
        if width > x1 - x0 + 0.5:
            too_wide.append(index)
        if pane.text_align == 1:
            pen = x0 + (x1 - x0 - width) / 2
        elif pane.text_align == 2:
            pen = x1 - width
        else:
            pen = x0
        baseline = top + index * pitch + (chain.faces[0].ascent(px) if chain.faces else 0.0)
        for ch in line:
            face = chain.face_of(ch)
            if face is None:
                continue
            face.draw(image, ch, pen, baseline, px, pane.colour)
            pen += face.advance(ch, px) + pane.char_space
    return too_wide


def draw_pane_x_stretched(image: Image.Image, pane: TextPane, chain: FontChain, lines: List[str], em_y: float) -> None:
    """Draws one pane with glyphs ``em_y`` px tall and stretched in X to the pane's ``size[0]``.

    Measured on the Sword/Shield field box (layout X 54, the Eden frame's glyph height 42): the text is drawn at
    ``em_y`` and every glyph and advance is scaled by ``size[0] / em_y`` from the pane's left edge. Left-aligned panes
    only; the stretch is applied to the whole strip right of the pane origin.
    """
    k = pane.size[0] / em_y
    layer = Image.new("RGBA", image.size, (0, 0, 0, 0))
    draw_pane(layer, replace(pane, size=(em_y, em_y)), chain, lines)
    x0, y0, x1, y1 = (int(round(v)) for v in pane.rect)
    strip = layer.crop((x0, y0, image.size[0], y1))
    wide = strip.resize((max(1, round(strip.width * k)), strip.height), Image.LANCZOS)
    overlay = Image.new("RGBA", image.size, (0, 0, 0, 0))
    overlay.paste(wide, (x0, y0))
    image.alpha_composite(overlay)


def render_window(layout: MessageLayout, chain: FontChain, lines_by_pane: Sequence[List[str]],
                  background: RGBA = (0, 0, 0, 0), em_y: Optional[float] = None) -> Image.Image:
    """The window with its text: pane i gets ``lines_by_pane[i]``. Cropped to the window frame when there is one.
    ``em_y`` (optional) draws the glyphs at that height and stretches them to the pane's X size (see
    ``draw_pane_x_stretched``). A line wider than its pane is drawn anyway; the caller reports it with ``overflow``."""
    width, height = (int(v) for v in layout.canvas)
    image = Image.new("RGBA", (width, height), background)
    for pane, lines in zip(layout.panes, lines_by_pane):
        if em_y is None:
            draw_pane(image, pane, chain, lines)
        else:
            draw_pane_x_stretched(image, pane, chain, lines, em_y)
    box = layout.window or _panes_box(layout.panes)
    if box is None:
        return image
    x0, y0, x1, y1 = (int(round(v)) for v in box)
    return image.crop((max(0, x0), max(0, y0), min(width, x1), min(height, y1)))


_MARGIN = 16.0


def _panes_box(panes: Sequence[TextPane]) -> Optional[Rect]:
    """The rectangle around the message panes, with a margin (the crop when the layout has no frame)."""
    if not panes:
        return None
    return (min(p.rect[0] for p in panes) - _MARGIN, min(p.rect[1] for p in panes) - _MARGIN,
            max(p.rect[2] for p in panes) + _MARGIN, max(p.rect[3] for p in panes) + _MARGIN)


__all__ = ["Face", "FontChain", "MessageLayout", "TextPane", "draw_pane", "draw_pane_x_stretched", "font_names",
           "line_pitch", "read_layout", "render_window", "wrap_text"]
