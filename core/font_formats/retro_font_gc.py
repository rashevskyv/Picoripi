"""Retro Studios FONT of the GameCube Metroid Prime (USA 1.00: versions 0 to 2) with its TXTR.

A ``.font`` file (the workspace's ``1_unpack.bat`` writes it) is the FONT resource followed by its TXTR, both
decompressed. FONT (big endian), as the game's ``CRasterFont`` reads it: ``FONT``, u32 version, u32 mono width,
u32 mono height, [u32 baseline from version 1] [u32 line margin from version 2], two flag bytes, u32, u32 font
size, the font name\\0, u32 texture id, u32 mode (0 one layer, 1 outline), u32 glyph count, 46 bytes per glyph
-- u16 character, f32 left, top, right, bottom texture coordinates, s32 left padding, advance, right padding,
cell width, cell height, baseline, kerning index -- then u32 kerning count and 8 bytes per pair.

The texture is any GX format (``core.texture_formats.txtr_gx``); the model copies each glyph's rectangle as it
is decoded (RGBA) into a cell of a grid (16 columns, 256 cells per sheet). Packing writes back only the cells
the editor changed (in a palette format a new colour becomes the nearest colour of the palette, so the palette and
the other glyphs keep their bytes), and the paddings of a glyph whose width or kerning changed; an unedited model packs to the original bytes. New glyphs cannot be added here (no entry in
the glyph table). PAL discs (version 4) are the Trilogy layout and go to ``retro_font_gx``.

The layout is from the game's reader only: no GameCube disc has been available to check it on real files.
"""
from __future__ import annotations

import struct
from typing import Any, Dict, Tuple

from PIL import Image

from core.font_formats import Metadata, Sheets, char_code, map_entries
from core.texture_formats import txtr_gx

GLYPH = struct.Struct(">H4f7i")
LEFT, ADVANCE, RIGHT, WIDTH, HEIGHT = 5, 6, 7, 8, 9      # fields of a glyph record (index in the unpacked tuple)
COLUMNS, PER_SHEET = 16, 256


def _font(form: bytes) -> Dict[str, Any]:
    """Offsets and fields of a FONT resource of version 0 to 2."""
    if form[:4] != b"FONT":
        raise ValueError("Not a Retro FONT")
    version, _mono_w, mono_h = struct.unpack_from(">III", form, 4)
    if version > 2:
        raise ValueError(f"FONT version {version} is not a GameCube USA font")
    at = 16 + 4 * (version >= 1) + 4 * (version >= 2) + 10       # past the baseline, margin, flags, u32, size
    end = form.index(b"\0", at) + 1
    texture_id, mode, count = struct.unpack_from(">III", form, end)
    first = end + 12
    glyphs = [list(GLYPH.unpack_from(form, first + GLYPH.size * i)) for i in range(count)]
    kerning = first + GLYPH.size * count
    size = kerning + 4 + 8 * struct.unpack_from(">I", form, kerning)[0]
    return {"version": version, "size": size, "mode": mode, "first": first, "glyphs": glyphs,
            "texture_id": texture_id, "line_height": mono_h}


def parts(form: bytes) -> Tuple[int, int]:
    """``(FONT size, texture id)`` of a FONT resource."""
    info = _font(form)
    return info["size"], info["texture_id"]


def _split(bundle: bytes) -> Tuple[bytes, bytes]:
    size = _font(bundle)["size"]
    return bytes(bundle[:size]), bytes(bundle[size:])


def _is_gc(bundle: bytes) -> bool:
    return struct.unpack_from(">I", bundle, 4)[0] <= 2


def _boxes(info: Dict[str, Any], width: int, height: int):
    boxes = []
    for glyph in info["glyphs"]:
        left, top = round(glyph[1] * width), round(glyph[2] * height)
        right, bottom = left + max(0, glyph[WIDTH]), top + max(0, glyph[HEIGHT])
        boxes.append((left, top, min(right, width), min(bottom, height)))
    cell_w = max([g[WIDTH] for g in info["glyphs"]] + [1])
    cell_h = max([g[HEIGHT] for g in info["glyphs"]] + [1])
    return boxes, cell_w, cell_h


def _snap(cell: Image.Image, colours) -> Image.Image:
    """``cell`` with every colour replaced by the nearest of the texture's palette: a colour the palette lacks would
    make the texture writer build a new palette and re-index every glyph."""
    known, near = set(colours), {}
    out = cell.copy()
    pixels_ = out.load()
    for y in range(out.height):
        for x in range(out.width):
            colour = pixels_[x, y]
            if colour not in known:
                if colour not in near:
                    near[colour] = min(colours, key=lambda c: sum((a - b) ** 2 for a, b in zip(c, colour)))
                pixels_[x, y] = near[colour]
    return out


def _image(tex: bytes) -> Image.Image:
    return txtr_gx.read(tex, {})[0].image.convert("RGBA")


def extract(data: bytes, params: Dict[str, Any]) -> Tuple[Metadata, Sheets]:
    if not _is_gc(data):
        from core.font_formats import retro_font_gx
        return retro_font_gx.extract(data, params)
    form, tex = _split(data)
    info = _font(form)
    image = _image(tex)
    boxes, cell_w, cell_h = _boxes(info, *image.size)
    rows = PER_SHEET // COLUMNS
    count = len(info["glyphs"])
    sheets = [Image.new("RGBA", (COLUMNS * cell_w, rows * cell_h)) for _ in range(max(1, -(-count // PER_SHEET)))]
    for cell, box in enumerate(boxes):
        if box[2] <= box[0] or box[3] <= box[1]:
            continue
        slot = cell % PER_SHEET
        sheets[cell // PER_SHEET].paste(image.crop(box), ((slot % COLUMNS) * cell_w, (slot // COLUMNS) * cell_h))
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
    if not _is_gc(original):
        from core.font_formats import retro_font_gx
        return retro_font_gx.pack(metadata, sheets, original, params)
    form, tex = _split(original)
    info = _font(form)
    image = _image(tex)
    boxes, cell_w, cell_h = _boxes(info, *image.size)
    edited = image.copy()
    colours = txtr_gx.palette(tex)
    changed = False
    for cell, box in enumerate(boxes):
        if box[2] <= box[0] or box[3] <= box[1] or cell // PER_SHEET >= len(sheets):
            continue
        slot = cell % PER_SHEET
        x, y = (slot % COLUMNS) * cell_w, (slot // COLUMNS) * cell_h
        model = sheets[cell // PER_SHEET].convert("RGBA").crop((x, y, x + box[2] - box[0], y + box[3] - box[1]))
        if model.tobytes() != image.crop(box).tobytes():
            edited.paste(_snap(model, colours) if colours else model, box[:2])
            changed = True
    if changed:
        tex = txtr_gx.write(tex, {0: edited}, {})
    new_form = bytearray(form)
    packets = (metadata.get("WID1") or [{}])[0].get("packets", [])
    for i, glyph in enumerate(info["glyphs"]):
        if i >= len(packets):
            break
        left = -int(packets[i]["kerning"])
        advance = int(packets[i]["width"]) - left - glyph[RIGHT]
        if (left, advance) != (glyph[LEFT], glyph[ADVANCE]):
            struct.pack_into(">ii", new_form, info["first"] + GLYPH.size * i + 18, left, advance)
    return bytes(new_form) + tex
