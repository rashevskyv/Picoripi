"""Agatsuma / Studio Saizensen ``FD`` bitmap fonts (Code of Princess, 3DS): ``sys.fnt``, ``script12.fnt``.

Layout (little endian): ``FD`` + a version byte + ``0x8A``, u32 size after the header, u32 0, u32 size of the code
table, u32 0, then u16 glyph count, glyph width, cell width, cell height, glyphs per row and 0 at 0x14. The u16
character codes (Unicode) of every glyph follow at 0x20, then one record per glyph: two floats ``v`` and ``u`` (the
glyph's place in the atlas as fractions of its height and 1024-pixel width) and, in the 12-byte form, the glyph's
advance as an int. The atlas is the rest of the file: an ETC1A4 PICA texture (one byte per pixel) of 1024 x H pixels
stored turned by 90 degrees (as ``H`` x 1024); a glyph is a (cell height x cell width) box of the turned atlas that
is turned back to (cell width x cell height).

The model lays glyph ``i`` in cell ``i`` of a sheet of ``glyphs per row`` columns. Character codes are fixed (the
code table is not extended); pixels, the advance and the glyph width are written back, an unedited font byte for byte.
"""
from __future__ import annotations

import struct
from typing import Any, Dict, List, Tuple

from PIL import Image

from core.font_formats import Metadata, Sheets, char_code, coverage, grey_sheet, map_entries
from core.texture_formats import pixels, surface

ADDS_GLYPHS = False
WIDTH = 1024


class Font:
    def __init__(self, data: bytes) -> None:
        if data[:2] != b"FD" or len(data) < 0x40 or data[3] != 0x8A:
            raise ValueError("Not a Code of Princess FD font with its own atlas")
        self.data = bytes(data)
        self.count, self.glyph_w, self.cell_w, self.cell_h, self.per_row = struct.unpack_from("<5H", data, 0x14)
        codes_len = struct.unpack_from("<I", data, 0xC)[0]
        self.codes = list(struct.unpack_from(f"<{self.count}H", data, 0x20))
        self.rec_at = 0x20 + codes_len
        remaining = len(data) - self.rec_at
        for size in (12, 8):
            tex = remaining - size * self.count
            if tex >= 1024 and tex & (tex - 1) == 0:
                self.rec_size, self.tex_size = size, tex
                break
        else:
            raise ValueError("The FD font's atlas is not part of the file")
        self.tex_at = self.rec_at + self.rec_size * self.count
        self.height = self.tex_size // WIDTH
        self.codec = pixels.codec("pica:ETC1A4")
        self.records: List[List[Any]] = []
        for i in range(self.count):
            v, u = struct.unpack_from("<2f", data, self.rec_at + i * self.rec_size)
            adv = struct.unpack_from("<I", data, self.rec_at + i * self.rec_size + 8)[0] if self.rec_size == 12 else None
            self.records.append([v, u, adv])

    def atlas(self) -> Image.Image:
        """The upright reading order atlas: 1024 x height RGBA."""
        stored = surface.read(self.data, self.tex_at, self.codec, self.height, WIDTH)
        return stored.transpose(Image.Transpose.ROTATE_270)

    def box(self, index: int) -> Tuple[int, int]:
        v, u, _a = self.records[index]
        return round(u * WIDTH), round(v * self.height)


def _model_code(code: int) -> int:
    return char_code(chr(code)) if code >= 0x100 or code < 0x80 or code > 0x9F else 0xF700 + code


def extract(data: bytes, params: Dict[str, Any]) -> Tuple[Metadata, Sheets]:
    font = Font(data)
    atlas = font.atlas()
    cols = max(1, min(font.per_row, font.count))
    rows = (font.count + cols - 1) // cols
    sheet = Image.new("RGBA", (cols * font.cell_w, rows * font.cell_h))
    packets = []
    for i in range(font.count):
        x, y = font.box(i)
        cell = atlas.crop((x, y, x + font.cell_h, y + font.cell_w)).transpose(Image.Transpose.TRANSPOSE)
        sheet.paste(cell, ((i % cols) * font.cell_w, (i // cols) * font.cell_h))
        adv = font.records[i][2]
        packets.append({"kerning": 0, "width": font.glyph_w if adv is None else adv})
    sheet = grey_sheet(sheet.split()[3])
    for _ in range(font.count, cols * rows):
        packets.append({"kerning": 0, "width": font.glyph_w})
    pairs = [(_model_code(code), i) for i, code in enumerate(font.codes)]
    metadata = {
        "header": {"signature": "FD", "num_chunks": 4, "texture_format": "ETC1A4"},
        "INF1": [{"encoding": 1, "ascent": font.cell_h, "descent": 0, "width": font.glyph_w, "leading": font.cell_h,
                  "fallback_code": 0x3F, "unk1": 0}],
        "GLY1": [{"start_glyph": 0, "end_glyph": cols * rows - 1, "cell_width": font.cell_w, "cell_height": font.cell_h,
                  "page_data_size": font.tex_size, "texture_format": 0, "glyph_horizontal_count": cols,
                  "glyph_vertical_count": rows, "texture_width": sheet.width, "texture_height": sheet.height}],
        "MAP1": [map_entries(pairs)],
        "WID1": [{"first_code_included": 0, "last_code_included": cols * rows, "packets": packets}],
    }
    return metadata, [sheet]


def pack(metadata: Metadata, sheets: Sheets, original: bytes, params: Dict[str, Any]) -> bytes:
    font = Font(original)
    cols = max(1, min(font.per_row, font.count))
    rows = (font.count + cols - 1) // cols
    new = sheets[0].convert("RGBA")
    if new.size != (cols * font.cell_w, rows * font.cell_h):
        raise ValueError(f"The sheet is {new.width}x{new.height}, the font's {cols * font.cell_w}x{rows * font.cell_h}")
    old_meta, old_sheets = extract(original, params)
    old = old_sheets[0]
    out = bytearray(original)
    atlas = font.atlas()
    changed = False
    packets = metadata["WID1"][0]["packets"]
    coverage_new = coverage(new)
    for i in range(font.count):
        cx, cy = (i % cols) * font.cell_w, (i // cols) * font.cell_h
        box = (cx, cy, cx + font.cell_w, cy + font.cell_h)
        if new.crop(box).tobytes() != old.crop(box).tobytes():
            alpha = coverage_new.crop(box)
            cell = Image.new("RGBA", (font.cell_w, font.cell_h), (255, 255, 255, 0))
            cell.putalpha(alpha)
            x, y = font.box(i)
            atlas.paste(cell.transpose(Image.Transpose.TRANSPOSE), (x, y))
            changed = True
        if font.rec_size == 12:
            adv = max(0, min(0xFFFFFFFF, int(packets[i]["width"]))) if i < len(packets) else font.records[i][2]
            if adv != font.records[i][2]:
                struct.pack_into("<I", out, font.rec_at + i * 12 + 8, adv)
    if changed:
        stored = atlas.transpose(Image.Transpose.ROTATE_90)
        surface.write(out, font.tex_at, font.codec, font.height, WIDTH, stored)
    return bytes(out)
