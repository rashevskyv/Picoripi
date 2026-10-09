"""Eternal Darkness (GameCube) fonts: a 16 x 16 grid of glyph cells in one TPL image, widths in another file.

``EFonts.tpl`` (two 512 x 512 CMPR images: the text font and the second font) and ``FontBack.tpl`` (image 1:
32 button icons) hold the glyphs; the game draws them upside down (the images are stored flipped) and fills
the grid column by column: character code ``c`` is cell column ``c // rows``, row ``c % rows``. The widths
are a table in the companion file ``EBootPak.bin``: entry ``width_table`` of its top pack is u32 count, u8 line
height, then one advance per code. The model shows the grid row by row (glyph ``i`` is code ``i``) the right
way up; packing turns it back, writes the image only when a pixel changed and the widths only when one did.

Codes are single bytes. The game's text is ASCII; the plugin writes cp1251, so the model maps 0x80-0xFF to
cp1251 characters (Ukrainian letters land in the free cells there).

Params: ``image`` (index in the TPL), ``grid`` ([columns, rows], default [16, 16]), ``width_table`` (entry of the
companion's pack), optional ``flip`` (default true) and ``encoding`` (default cp1251).
"""
from __future__ import annotations

import struct
from typing import Any, Dict, Tuple

from PIL import Image

from core.font_formats import Metadata, Sheets, char_code, map_entries
from core.font_formats.sources import join_pair, split_pair


def _int(value: Any) -> int:
    return int(value, 0) if isinstance(value, str) else int(value)


def _widths_span(pack: bytes, entry: int) -> Tuple[int, int, int]:
    """(offset of the width bytes, count, line height) of entry ``entry`` of the companion pack."""
    count, magic = struct.unpack_from(">II", pack, 0)
    if magic != 0x6B5 or not 0 <= entry < count:
        raise ValueError("The companion file is not an Eternal Darkness pack with that entry")
    offset = struct.unpack_from(">I", pack, 8 + 8 * entry)[0]
    widths, height = struct.unpack_from(">IB", pack, offset)
    return offset + 5, widths, height


def _layout(params: Dict[str, Any], image: Image.Image) -> Tuple[int, int, int, int]:
    columns, rows = (_int(v) for v in params.get("grid", (16, 16)))
    return columns, rows, image.width // columns, image.height // rows


def _image(tpl: bytes, params: Dict[str, Any]) -> Image.Image:
    from core.texture_formats import tpl as tpl_format
    return tpl_format.read(tpl, {})[_int(params.get("image", 0))].image.convert("RGBA")


def _to_model(image: Image.Image, params: Dict[str, Any]) -> Image.Image:
    if params.get("flip", True):
        image = image.transpose(Image.Transpose.FLIP_TOP_BOTTOM)
    columns, rows, width, height = _layout(params, image)
    sheet = Image.new("RGBA", image.size)
    for code in range(columns * rows):
        src = ((code // rows) * width, (code % rows) * height)
        dst = ((code % columns) * width, (code // columns) * height)
        sheet.paste(image.crop((*src, src[0] + width, src[1] + height)), dst)
    return sheet


def _from_model(sheet: Image.Image, params: Dict[str, Any]) -> Image.Image:
    columns, rows, width, height = _layout(params, sheet)
    image = Image.new("RGBA", sheet.size)
    for code in range(columns * rows):
        src = ((code % columns) * width, (code // columns) * height)
        dst = ((code // rows) * width, (code % rows) * height)
        image.paste(sheet.crop((*src, src[0] + width, src[1] + height)), dst)
    if params.get("flip", True):
        image = image.transpose(Image.Transpose.FLIP_TOP_BOTTOM)
    return image


def extract(data: bytes, params: Dict[str, Any]) -> Tuple[Metadata, Sheets]:
    tpl, pack = split_pair(data)
    sheet = _to_model(_image(tpl, params), params)
    columns, rows, width, height = _layout(params, sheet)
    at, count, line = _widths_span(pack, _int(params["width_table"]))
    widths = list(pack[at:at + count])
    encoding = str(params.get("encoding") or "cp1251")
    glyphs = columns * rows
    pairs = []
    for code in range(glyphs):
        char = bytes([code]).decode(encoding, "replace")
        if code >= 0x20 and char != "�":
            pairs.append((char_code(char), code))
    metadata = {
        "header": {"signature": "Eternal Darkness font", "num_chunks": 4},
        "INF1": [{"encoding": 0, "ascent": line, "descent": 0, "width": width, "leading": line,
                  "fallback_code": 0x3F, "unk1": 0}],
        "GLY1": [{"start_glyph": 0, "end_glyph": glyphs - 1, "cell_width": width, "cell_height": height,
                  "page_data_size": 0, "texture_format": 0, "glyph_horizontal_count": columns,
                  "glyph_vertical_count": rows, "texture_width": sheet.width, "texture_height": sheet.height}],
        "MAP1": [map_entries(pairs)],
        "WID1": [{"first_code_included": 0, "last_code_included": glyphs - 1,
                  "packets": [{"kerning": 0, "width": widths[i] if i < count else width} for i in range(glyphs)]}],
    }
    return metadata, [sheet]


def pack(metadata: Metadata, sheets: Sheets, original: bytes, params: Dict[str, Any]) -> bytes:
    """``original`` (the TPL + companion pair) with the edited glyphs and widths; unchanged parts keep their bytes."""
    from core.texture_formats import tpl as tpl_format
    tpl, companion = split_pair(original)
    index = _int(params.get("image", 0))
    current = _image(tpl, params)
    image = _from_model(sheets[0].convert("RGBA"), params)
    if image.size != current.size:
        raise ValueError(f"The sheet is {image.width}x{image.height}, the font {current.width}x{current.height}")
    if image.tobytes() != current.tobytes():
        tpl = tpl_format.write(tpl, {index: image}, {})
    pack_bytes = bytearray(companion)
    at, count, _line = _widths_span(companion, _int(params["width_table"]))
    packets = (metadata.get("WID1") or [{}])[0].get("packets", [])
    for code in range(min(count, len(packets))):
        pack_bytes[at + code] = max(0, min(255, int(packets[code].get("width", pack_bytes[at + code]))))
    return join_pair(tpl, bytes(pack_bytes))
