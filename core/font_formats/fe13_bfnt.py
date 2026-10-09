"""Fire Emblem Awakening (3DS) ``.bfnt`` fonts: a glyph atlas of A4 / A8 PICA sheets with a sorted glyph table.

Header (little endian): u16 version, u16 0x20, u16 default code, u16 0, u16 line height, u16, u32 baseline, u16 sheet
width, u16 sheet height, u32 bytes per sheet, u16 format (4 = A4, 2 = A8), u16 sheet count, u32 0, u16 table
offset (0x30), u16 glyph count, u32 sheet data offset (table end aligned to 0x80), u32 bytes of all sheets.
A glyph entry (16 bytes, sorted by code): u16 Unicode code, u16 sheet, u16 x, u16 y, u8 width, u8 height,
u8 left, u8 top (rows below the line top), u8 advance, 3 pad. The sheets are tiled PICA textures.

Model: one cell per glyph (row by row), the glyph drawn at its ``top`` inside the cell. Packing writes a
redrawn glyph back into its atlas box (pixels outside the box are dropped: ponytail, grow the box when a
translation needs it). A new character gets a box on a free band of rows of a sheet; when no band is free,
the box of a Japanese glyph (code 0x3000 and above, the last ones in the table) is reused for it.
"""
from __future__ import annotations

import struct
from typing import Any, Dict, List, Tuple

from PIL import Image

from core.font_formats import Metadata, Sheets, char_code, char_map, coverage, map_entries
from core.texture_formats import pixels, surface

ADDS_GLYPHS = True
FORMATS = {4: "pica:A4", 2: "pica:A8"}
COLUMNS = 64
_ENTRY = "<4H5B3x"


def detect(data: bytes) -> bool:
    return len(data) > 0x30 and data[2:4] == b"\x20\0" and struct.unpack_from("<H", data, 0x20)[0] == 0x30


def _info(data: bytes) -> Dict[str, Any]:
    if not detect(data):
        raise ValueError("Not a Fire Emblem Awakening bfnt font")
    line, _u, baseline, width, height, per_sheet, fmt, sheets, _z, table, count, at, total = struct.unpack_from(
        "<HHIHHIHHIHHII", data, 8)
    if fmt not in FORMATS:
        raise ValueError(f"bfnt sheet format {fmt} is not supported")
    glyphs = [list(struct.unpack_from(_ENTRY, data, table + i * 16)) for i in range(count)]
    return {"line": line, "baseline": baseline, "width": width, "height": height, "per_sheet": per_sheet, "format": fmt,
            "sheets": sheets, "table": table, "count": count, "data": at, "total": total, "glyphs": glyphs,
            "cell": (max([8] + [g[4] for g in glyphs]), max([line] + [g[7] + g[5] for g in glyphs if g[7] + g[5] < 64]))}


def _model_code(code: int) -> int:
    """The model's code of a font code: C1 controls (0x80..0x9F) go to the private plane, since a code below
    256 means a cp1252 byte to the model (0x92 would collide with U+2019, which the font has too)."""
    return 0xF0000 + code if 0x80 <= code <= 0x9F else char_code(chr(code))


def _font_code(char: str) -> int:
    code = char_code(char)
    if code >= 0xF0000:
        return code - 0xF0000
    return ord(char) if 0x80 <= code <= 0x9F else code   # a cp1252 byte of the model is the Unicode character here


def _model_code(code: int) -> int:
    """The model's code of a font code: C1 controls (0x80..0x9F) go to the private plane, since a code below
    256 means a cp1252 byte to the model (0x92 would collide with U+2019, which the font has too)."""
    return 0xF0000 + code if 0x80 <= code <= 0x9F else char_code(chr(code))


def _font_code(char: str) -> int:
    code = char_code(char)
    if code >= 0xF0000:
        return code - 0xF0000
    return ord(char) if 0x80 <= code <= 0x9F else code   # a cp1252 byte of the model is the Unicode character here


def _atlas(data: bytes, info: Dict[str, Any]) -> List[Image.Image]:
    codec = pixels.codec(FORMATS[info["format"]])
    return [surface.read(data, info["data"] + s * info["per_sheet"], codec, info["width"], info["height"])
            for s in range(info["sheets"])]


def _cell_box(info: Dict[str, Any], glyph: int) -> Tuple[int, int, int, int]:
    cw, ch = info["cell"]
    column, row = glyph % COLUMNS, glyph // COLUMNS
    return column * cw, row * ch, (column + 1) * cw, (row + 1) * ch


def _model(info: Dict[str, Any], atlas: List[Image.Image], count: int) -> Image.Image:
    cw, ch = info["cell"]
    sheet = Image.new("RGBA", (COLUMNS * cw, -(-count // COLUMNS) * ch))
    for index, (_code, page, x, y, w, h, _left, top, _adv) in enumerate(info["glyphs"]):
        left, cell_top = _cell_box(info, index)[:2]
        sheet.paste(atlas[page].crop((x, y, x + w, y + h)), (left, cell_top + top))
    return sheet


def extract(data: bytes, params: Dict[str, Any]) -> Tuple[Metadata, Sheets]:
    info = _info(data)
    count = -(-info["count"] // COLUMNS) * COLUMNS + COLUMNS   # one spare row of cells for new characters
    sheet = _model(info, _atlas(data, info), count)
    cw, ch = info["cell"]
    glyphs = info["glyphs"]
    packets = [{"kerning": -g[6], "width": g[8]} for g in glyphs] + [{"kerning": 0, "width": cw}] * (count - len(glyphs))
    top = max([info["line"]] + [g[7] for g in glyphs])
    metadata = {
        "header": {"signature": "FE13 bfnt", "num_chunks": 4, "texture_format": FORMATS[info["format"]][5:]},
        "INF1": [{"encoding": 1, "ascent": top, "descent": ch - top, "width": cw, "leading": info["line"],
                  "fallback_code": 0x3F, "unk1": 0}],
        "GLY1": [{"start_glyph": 0, "end_glyph": count - 1, "cell_width": cw, "cell_height": ch,
                  "page_data_size": info["per_sheet"], "texture_format": info["format"],
                  "glyph_horizontal_count": COLUMNS, "glyph_vertical_count": sheet.height // ch,
                  "texture_width": sheet.width, "texture_height": sheet.height}],
        "MAP1": [map_entries([(_model_code(g[0]), i) for i, g in enumerate(glyphs)])],
        "WID1": [{"first_code_included": 0, "last_code_included": count, "packets": packets,
                  "glyph_widths": [g[4] for g in glyphs] + [cw] * (count - len(glyphs))}],
    }
    return metadata, [sheet]


def free_bands(info: Dict[str, Any], page: int, height: int) -> List[Tuple[int, int]]:
    """``(y, rows)`` bands of sheet ``page`` no glyph box touches, at least ``height`` rows tall."""
    used = bytearray(info["height"])
    for _code, p, _x, y, _w, h, *_rest in info["glyphs"]:
        if p == page:
            used[y:y + h + 1] = b"\1" * (min(info["height"], y + h + 1) - y)
    bands, start = [], None
    for y, busy in enumerate(list(used) + [1]):
        if not busy and start is None:
            start = y
        elif busy and start is not None:
            if y - start >= height:
                bands.append((start, y - start))
            start = None
    return bands


def _place(info: Dict[str, Any], w: int, h: int, shelves: Dict[Any, List[int]], taken: List[int]) -> Tuple[int, int, int]:
    """``(sheet, x, y)`` for a new ``w`` x ``h`` box: on a free band (``shelves``: (page, y) -> [y, next x, rows]),
    else the box of the last Japanese glyph that fits (its index goes to ``taken``)."""
    for page in range(info["sheets"]):
        for band in free_bands(info, page, h + 1):
            shelf = shelves.setdefault((page, band[0]), [band[0], 0, band[1]])
            if shelf[1] + w + 1 <= info["width"] and shelf[2] >= h + 1:
                x = shelf[1]
                shelf[1] += w + 1
                return page, x, shelf[0]
    for index in range(len(info["glyphs"]) - 1, -1, -1):
        g = info["glyphs"][index]
        if g[0] >= 0x3000 and index not in taken and g[4] >= w and g[5] >= h:
            taken.append(index)
            return g[1], g[2], g[3]
    raise ValueError("No room in the font for a new character")


def pack(metadata: Metadata, sheets: Sheets, original: bytes, params: Dict[str, Any]) -> bytes:
    info = _info(original)
    atlas = _atlas(original, info)
    cw, ch = info["cell"]
    glyphs = info["glyphs"]
    old = _model(info, atlas, -(-info["count"] // COLUMNS) * COLUMNS + COLUMNS)
    new = sheets[0].convert("RGBA")
    if new.size != old.size:
        raise ValueError(f"The sheet is {new.size[0]}x{new.size[1]}, the font's {old.size[0]}x{old.size[1]}")
    packets = metadata["WID1"][0]["packets"]
    for index, g in enumerate(glyphs):
        box = _cell_box(info, index)
        if new.crop(box).tobytes() != old.crop(box).tobytes():
            _code, page, x, y, w, h, _left, top, _adv = g
            atlas[page].paste(new.crop((box[0], box[1] + top, box[0] + w, box[1] + top + h)), (x, y))
        if index < len(packets):
            g[6], g[8] = max(0, min(255, -int(packets[index]["kerning"]))), max(0, min(255, int(packets[index]["width"])))
    existing = {g[0]: i for i, g in enumerate(glyphs)}
    wanted = {_font_code(char): glyph for char, glyph in char_map(metadata).items()}
    changed = [code for code, glyph in existing.items() if wanted.get(code) != glyph]
    if changed:
        raise ValueError("This font keeps the characters it has; changed or removed: "
                         + " ".join(f"U+{code:04X}" for code in sorted(changed)[:10]))
    shelves: Dict[Any, List[int]] = {}
    taken: List[int] = []
    added = []
    for code, glyph in sorted((c, g) for c, g in wanted.items() if c not in existing):
        if code > 0xFFFF:
            raise ValueError("The font maps 16-bit character codes only")
        box = _cell_box(info, glyph)
        cell = new.crop(box)
        ink = coverage(cell).getbbox()
        if ink is None:
            continue
        top = ink[1]
        w, h = min(ink[2], cw), ink[3] - top
        page, x, y = _place(info, w, h, shelves, taken)
        atlas[page].paste(Image.new("RGBA", (w, h)), (x, y))
        atlas[page].paste(cell.crop((0, top, w, top + h)), (x, y))
        packet = packets[glyph] if glyph < len(packets) else {"kerning": 0, "width": w}
        added.append([code, page, x, y, w, h, max(0, -int(packet["kerning"])), top, int(packet["width"])])
    glyphs = [g for i, g in enumerate(glyphs) if i not in taken] + added
    glyphs.sort(key=lambda g: g[0])
    table = b"".join(struct.pack(_ENTRY, *g) for g in glyphs)
    data_at = (info["table"] + len(table) + 0x7F) & ~0x7F
    head = bytearray(original[:info["table"]])
    struct.pack_into("<HI", head, 0x22, len(glyphs), data_at)
    out = bytearray(head) + table + bytes(data_at - info["table"] - len(table))
    codec = pixels.codec(FORMATS[info["format"]])
    for page, image in enumerate(atlas):
        start = info["data"] + page * info["per_sheet"]
        raw = bytearray(original[start:start + info["per_sheet"]])
        if image.tobytes() != surface.read(original, start, codec, info["width"], info["height"]).tobytes():
            surface.write(raw, 0, codec, info["width"], info["height"], image)
        out += raw
    return bytes(out)
