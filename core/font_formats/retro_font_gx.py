"""Retro Studios FONT of the Wii Metroid Prime games (Trilogy: versions 4 and 5) with its C4 texture.

A ``.font`` file (``1_unpack`` writes it) is the FONT resource followed by its TXTR (``core.texture_formats.
txtr_gx``), both decompressed. FONT (big endian): ``FONT``, u32 version, u32, u32 line height, 0x12 more header
bytes, the font name\\0, the texture id (u32 in version 4, u64 in 5), u32 mode, u32 glyph count, 27 bytes per
glyph -- u16 character, f32 left, top, right, bottom texture coordinates, u8 layer, s8 left padding, s8 advance,
s8 right padding, u8 width, u8 height, u8 base offset, u16 kerning index -- then u32 kerning count and 8 bytes
per pair.

The texture is C4: each glyph is a field of bits of the 4-bit index -- one bit per layer in mode 2 (4 layers),
two bits in the other modes (2 layers: 1 fill, 2 outline, 3 both). The model copies every glyph's field into a
cell of a grid (16 columns, 256 cells per sheet): fill white, outline dark grey, both light grey. A glyph's
model width is left padding + advance + right padding, its kerning minus the left padding. Packing writes the
cells back into their texture rectangles and the paddings of a glyph whose width or kerning changed; an
unedited model packs to the original bytes. New glyphs cannot be added (no room in the texture).
"""
from __future__ import annotations

import struct
from typing import Any, Dict, Tuple

from PIL import Image

from core.font_formats import Metadata, Sheets, char_code, map_entries
from core.texture_formats import pixels, surface

GLYPH = struct.Struct(">H4fBbbbBBBH")
LAYER, LEFT, ADVANCE, RIGHT, WIDTH, HEIGHT = 5, 6, 7, 8, 9, 10      # fields of a glyph record
COLUMNS, PER_SHEET = 16, 256
COLOURS = [(0, 0, 0, 0), (255, 255, 255, 255), (96, 96, 96, 255), (176, 176, 176, 255)]   # field value -> RGBA
_INDEX = pixels.palette_codec("gx:C4", 4, [(i * 17, i * 17, i * 17, 255) for i in range(16)], tile=(8, 8))


def _font(form: bytes) -> Dict[str, Any]:
    """Offsets and fields of a FONT resource."""
    if form[:4] != b"FONT":
        raise ValueError("Not a Retro FONT")
    version, _unk, line_height = struct.unpack_from(">III", form, 4)
    end = form.index(b"\0", 0x22) + 1
    width = 4 if version <= 4 else 8
    mode, count = struct.unpack_from(">II", form, end + width)
    first = end + width + 8
    glyphs = [list(GLYPH.unpack_from(form, first + GLYPH.size * i)) for i in range(count)]
    kerning = first + GLYPH.size * count
    size = kerning + 4 + 8 * struct.unpack_from(">I", form, kerning)[0]
    return {"version": version, "size": size, "mode": mode, "first": first, "glyphs": glyphs,
            "texture_id": int.from_bytes(form[end:end + width], "big"), "line_height": line_height}


def split(bundle: bytes) -> Tuple[bytes, bytes]:
    """``(FONT, TXTR)`` of a ``.font`` file."""
    size = _font(bundle)["size"]
    return bytes(bundle[:size]), bytes(bundle[size:])


def _texture(tex: bytes) -> Tuple[int, int, int]:
    """``(width, height, texel offset)`` of the font's C4 TXTR."""
    fmt, width, height = struct.unpack_from(">IHH", tex)
    if fmt != 4:
        raise ValueError(f"Font texture format {fmt}, expected 4 (C4)")
    pal_w, pal_h = struct.unpack_from(">HH", tex, 16)
    return width, height, 20 + 2 * pal_w * pal_h


def _layout(info: Dict[str, Any], width: int, height: int):
    """Per glyph its texture box and bit shift; the field mask; the cell size."""
    bits = 1 if info["mode"] == 2 else 2
    boxes = []
    for glyph in info["glyphs"]:
        left, top = round(glyph[1] * width), round(glyph[2] * height)
        boxes.append(((left, top, left + glyph[WIDTH], top + glyph[HEIGHT]), glyph[LAYER] * bits))
    cell_w = max([g[WIDTH] for g in info["glyphs"]] + [1])
    cell_h = max([g[HEIGHT] for g in info["glyphs"]] + [1])
    return boxes, (1 << bits) - 1, cell_w, cell_h


def _indices(tex: bytes) -> Image.Image:
    width, height, at = _texture(tex)
    return surface.read(tex, at, _INDEX, width, height).getchannel("R").point(lambda v: v // 17)


def _cell(sheets: Sheets, cell: int, cell_w: int, cell_h: int, size: Tuple[int, int]) -> Image.Image:
    slot = cell % PER_SHEET
    x, y = (slot % COLUMNS) * cell_w, (slot // COLUMNS) * cell_h
    return sheets[cell // PER_SHEET].convert("RGBA").crop((x, y, x + size[0], y + size[1]))


def _value(colour, mask: int) -> int:
    """The field value of a model pixel: transparent 0, else the nearest of the model's colours."""
    if colour[3] < 128:
        return 0
    if mask == 1:
        return 1 if max(colour[:3]) >= 128 else 0
    grey = max(colour[:3])
    return min((1, 2, 3), key=lambda v: abs(COLOURS[v][0] - grey))


def extract(data: bytes, params: Dict[str, Any]) -> Tuple[Metadata, Sheets]:
    form, tex = split(data)
    info = _font(form)
    index = _indices(tex)
    boxes, mask, cell_w, cell_h = _layout(info, *index.size)
    rows = PER_SHEET // COLUMNS
    count = len(info["glyphs"])
    sheets = [Image.new("RGBA", (COLUMNS * cell_w, rows * cell_h)) for _ in range(max(1, -(-count // PER_SHEET)))]
    for cell, (box, shift) in enumerate(boxes):
        if box[2] <= box[0] or box[3] <= box[1]:
            continue
        glyph = Image.new("RGBA", (box[2] - box[0], box[3] - box[1]))
        glyph.putdata([COLOURS[(v >> shift) & mask] for v in index.crop(box).get_flattened_data()])
        slot = cell % PER_SHEET
        sheets[cell // PER_SHEET].paste(glyph, ((slot % COLUMNS) * cell_w, (slot // COLUMNS) * cell_h))
    entries = [(char_code(chr(g[0])), i) for i, g in enumerate(info["glyphs"])]
    packets = [{"kerning": -g[LEFT], "width": g[LEFT] + g[ADVANCE] + g[RIGHT]} for g in info["glyphs"]]
    space = next((p["width"] for g, p in zip(info["glyphs"], packets) if g[0] == 0x20), cell_w // 2)
    metadata = {
        "header": {"signature": "FONT", "num_chunks": 4},
        "INF1": [{"encoding": 1, "ascent": info["line_height"], "descent": max(1, cell_h - info["line_height"]),
                  "width": space, "leading": cell_h, "fallback_code": 0x3F, "unk1": 0}],
        "GLY1": [{"start_glyph": 0, "end_glyph": len(sheets) * PER_SHEET - 1, "cell_width": cell_w,
                  "cell_height": cell_h, "glyph_horizontal_count": COLUMNS, "glyph_vertical_count": rows,
                  "texture_width": COLUMNS * cell_w, "texture_height": rows * cell_h}],
        "MAP1": [map_entries(entries)],
        "WID1": [{"first_code_included": 0, "last_code_included": len(sheets) * PER_SHEET, "packets": packets}],
    }
    return metadata, sheets


def pack(metadata: Metadata, sheets: Sheets, original: bytes, params: Dict[str, Any]) -> bytes:
    form, tex = split(original)
    info = _font(form)
    index = _indices(tex)
    boxes, mask, cell_w, cell_h = _layout(info, *index.size)
    pixels_ = index.load()
    changed = False
    for cell, (box, shift) in enumerate(boxes):
        if box[2] <= box[0] or box[3] <= box[1] or cell // PER_SHEET >= len(sheets):
            continue
        model = _cell(sheets, cell, cell_w, cell_h, (box[2] - box[0], box[3] - box[1]))
        for (dx, dy), colour in zip(((x, y) for y in range(model.height) for x in range(model.width)),
                                    model.get_flattened_data()):
            old = pixels_[box[0] + dx, box[1] + dy]
            new = (old & ~(mask << shift)) | (_value(colour, mask) << shift)
            if new != old:
                pixels_[box[0] + dx, box[1] + dy] = new
                changed = True
    if changed:
        width, height, at = _texture(tex)
        grey = index.point(lambda v: v * 17)
        out = bytearray(tex)
        surface.write(out, at, _INDEX, width, height, Image.merge("RGBA", (grey, grey, grey, Image.new("L", grey.size, 255))))
        tex = bytes(out)
    new_form = bytearray(form)
    packets = (metadata.get("WID1") or [{}])[0].get("packets", [])
    for i, glyph in enumerate(info["glyphs"]):
        if i >= len(packets):
            break
        left = -int(packets[i]["kerning"])
        advance = int(packets[i]["width"]) - left - glyph[RIGHT]
        if (left, advance) != (glyph[LEFT], glyph[ADVANCE]):
            struct.pack_into(">bb", new_form, info["first"] + GLYPH.size * i + 19, max(-128, min(127, left)),
                             max(-128, min(127, advance)))
    return bytes(new_form) + tex
