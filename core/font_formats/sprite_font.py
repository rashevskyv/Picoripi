"""MonoGame SpriteFont (``.xnb``, uncompressed): a glyph atlas plus a sorted character map.

The game draws a character with the glyph rectangle of its entry in the character map (a binary search, so
the map stays sorted by character code). Each glyph has a cropping rectangle and a kerning triple (left, width,
right). The model is a grid sheet: cell ``i`` is the glyph of the cell's character, cells are as large as the
largest glyph, ``columns`` per row (params, default 16). ``params["spare"]`` adds that many empty cells.

Packing an unedited model gives the original bytes back: each glyph is written into its own rectangle, only
the cells that differ are encoded again, and the header, the type indices and the total size are kept.
A character typed into a free cell (``add_character``) gets a new rectangle in the atlas: a new row of slots
below the old atlas when the atlas is too short. The atlas grows only then; the glyph lists are rebuilt sorted.

ponytail: atlas slots of removed characters are not reused; a grown atlas is re-encoded whole (BC2 loses bits
in the rows that were not changed; RGBA8 does not).
"""
from __future__ import annotations

import struct
from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Tuple

from PIL import Image

from core.containers import xnb
from core.font_formats import Metadata, Sheets, map_entries
from core.texture_formats import pixels, surface

# Texture2D surface format numbers (MonoGame SurfaceFormat) this backend reads and writes.
_CODECS = {0: "RGBA8", 5: "BC2"}
# A letter typed into a free cell becomes that character (see core.font_formats.adds_glyphs).
ADDS_GLYPHS = True


def _cells(metadata: Metadata) -> Dict[str, int]:
    """``{character: cell}`` from MAP1 type 3. Codes are code points here: the shared ``char_map`` reads codes
    below 256 as cp1252, which would turn U+0080..U+009F into other characters."""
    result: Dict[str, int] = {}
    for block in metadata.get("MAP1", []):
        entries = block.get("entries", [])
        half = len(entries) // 2
        for code, cell in zip(entries[:half], entries[half:]):
            result[chr(code)] = cell
    return result


def _map(cells: Dict[str, int]) -> Dict[str, Any]:
    return map_entries([(ord(char), cell) for char, cell in cells.items()])


def is_sprite_font(data: bytes) -> bool:
    try:
        _read(bytes(data))
    except (ValueError, IndexError, struct.error, UnicodeDecodeError):
        return False
    return True


@dataclass
class _Font:
    prefix: bytes            # file bytes before the primary object's type index
    top: int                 # primary object's type index (the SpriteFont reader)
    refs: Dict[str, int]     # type indices of texture, glyph list, cropping list, character list, kerning list
    texture: xnb.Texture2D
    rects: List[Tuple[int, int, int, int]]
    crops: List[Tuple[int, int, int, int]]
    chars: List[str]
    line_spacing: int
    spacing: float
    kerning: List[Tuple[float, float, float]]
    default: Optional[str]


def _read(data: bytes) -> _Font:
    x = xnb.open_xnb(data)
    reader = x.reader
    top = reader.v7()
    if "SpriteFontReader" not in x.type_of(top):
        raise ValueError("not a SpriteFont")
    refs = {}
    refs["texture"] = reader.v7()
    if "Texture2DReader" not in x.type_of(refs["texture"]):
        raise ValueError("a SpriteFont starts with its texture")
    texture = xnb.read_texture2d(reader)
    rects_lists = []
    for name in ("glyph", "crop"):
        refs[name] = reader.v7()
        count = reader.i32()
        rects_lists.append([reader.unpack("iiii") for _ in range(count)])
    refs["charmap"] = reader.v7()
    count = reader.i32()
    chars = [reader.char() for _ in range(count)]
    line_spacing = reader.i32()
    spacing = reader.f32()
    refs["kerning"] = reader.v7()
    count = reader.i32()
    kerning = [reader.unpack("fff") for _ in range(count)]
    default = reader.char() if reader.u8() else None
    if reader.pos != len(data):
        raise ValueError(f"SpriteFont ends at {reader.pos} of {len(data)} bytes")
    if not (len(rects_lists[0]) == len(chars) == len(kerning) == len(rects_lists[1])):
        raise ValueError("SpriteFont lists differ in length")
    return _Font(prefix=x.head + xnb.write7(top), top=top, refs=refs, texture=texture,
                 rects=rects_lists[0], crops=rects_lists[1], chars=chars, line_spacing=line_spacing,
                 spacing=spacing, kerning=kerning, default=default)


def _codec(texture: xnb.Texture2D):
    if texture.surface_format not in _CODECS:
        raise ValueError(f"surface format {texture.surface_format} is not read here")
    return pixels.codec(_CODECS[texture.surface_format])


def _atlas(font: _Font) -> Image.Image:
    codec = _codec(font.texture)
    return surface.read(font.texture.mip, 0, codec, font.texture.width, font.texture.height).convert("RGBA")


def _cell_size(font: _Font) -> Tuple[int, int]:
    return max(1, max((r[2] for r in font.rects), default=1)), max(1, max((r[3] for r in font.rects), default=1))


def extract(data: bytes, params: Dict[str, Any]) -> Tuple[Metadata, Sheets]:
    font = _read(bytes(data))
    atlas = _atlas(font)
    columns = int(params.get("columns", 16))
    count = len(font.chars) + int(params.get("spare", 0))
    cw, ch = _cell_size(font)
    rows = max(1, -(-count // columns))
    sheet = Image.new("RGBA", (columns * cw, rows * ch))
    for cell, rect in enumerate(font.rects):
        x, y, w, h = rect
        sheet.paste(atlas.crop((x, y, x + w, y + h)), ((cell % columns) * cw, (cell // columns) * ch))
    fallback = ord(font.default) if font.default is not None else 0x20
    metadata = {
        "header": {"signature": "MonoGame SpriteFont"},
        "INF1": [{"encoding": 0, "ascent": font.line_spacing, "descent": 0, "width": cw,
                  "leading": font.line_spacing, "fallback_code": fallback, "unk1": 0}],
        "GLY1": [{"start_glyph": 0, "end_glyph": count - 1, "cell_width": cw, "cell_height": ch,
                  "page_data_size": 0, "texture_format": 0, "glyph_horizontal_count": columns,
                  "glyph_vertical_count": rows, "texture_width": sheet.width, "texture_height": sheet.height}],
        "MAP1": [_map({c: i for i, c in enumerate(font.chars)})],
        "WID1": [{"first_code_included": 0, "last_code_included": count,
                  "packets": [{"kerning": font.kerning[i][0] if i < len(font.chars) else 0.0,
                               "width": font.kerning[i][1] if i < len(font.chars) else float(cw)}
                              for i in range(count)]}],
        "XNB": {"spacing": font.spacing, "line_spacing": font.line_spacing, "default_char": font.default,
                "surface_format": font.texture.surface_format},
    }
    return metadata, [sheet]


def free_cells(metadata: Metadata) -> List[int]:
    """Cells of the sheet with no character (the spare cells, or cells whose character was removed)."""
    used = set(_cells(metadata).values())
    grid = metadata["GLY1"][0]
    return [cell for cell in range(grid["glyph_horizontal_count"] * grid["glyph_vertical_count"]) if cell not in used]


def add_character(metadata: Metadata, sheets: Sheets, char: str) -> int:
    """Map ``char`` to the first free cell (a new row of cells when none is free). Draw its pixels in that cell.

    Returns the cell. ``sheets[0]`` is replaced when a row is added.
    """
    pairs = _cells(metadata)
    if char in pairs:
        raise ValueError(f"{char!r} is already in the font")
    grid = metadata["GLY1"][0]
    cw, ch = grid["cell_width"], grid["cell_height"]
    columns = grid["glyph_horizontal_count"]
    free = free_cells(metadata)
    if free:
        cell = free[0]
    else:
        cell = columns * grid["glyph_vertical_count"]
        grid["glyph_vertical_count"] += 1
        grown = Image.new("RGBA", (columns * cw, grid["glyph_vertical_count"] * ch))
        grown.paste(sheets[0].convert("RGBA"), (0, 0))
        sheets[0] = grown
        grid["texture_height"] = grown.height
    pairs[char] = cell
    metadata["MAP1"] = [_map(pairs)]
    packets = metadata["WID1"][0]["packets"]
    while len(packets) <= cell:
        packets.append({"kerning": 0.0, "width": float(cw)})
    metadata["WID1"][0]["last_code_included"] = len(packets)
    grid["end_glyph"] = len(packets) - 1
    return cell


def _slot_layout(new_sizes: List[Tuple[int, int]], atlas_w: int, atlas_h: int) -> Tuple[List[Tuple[int, int]], int]:
    """Place rectangles below the atlas, left to right, row by row. Returns the positions and the new height."""
    positions = []
    x, y, strip = 0, _up4(atlas_h), 0
    for w, h in new_sizes:
        if w > atlas_w:
            raise ValueError(f"a glyph {w} pixels wide does not fit the {atlas_w}-pixel atlas")
        if x + w > atlas_w:
            x, y, strip = 0, y + _up4(strip), 0
        positions.append((x, y))
        x += w
        strip = max(strip, h)
    return positions, _up4(y + strip)


def _up4(value: int) -> int:
    return -(-value // 4) * 4


def pack(metadata: Metadata, sheets: Sheets, original: bytes, params: Dict[str, Any]) -> bytes:
    font = _read(bytes(original))
    codec = _codec(font.texture)
    atlas = _atlas(font)
    sheet = sheets[0].convert("RGBA")
    grid = metadata["GLY1"][0]
    cw, ch, columns = grid["cell_width"], grid["cell_height"], grid["glyph_horizontal_count"]
    xnb_meta = metadata["XNB"]
    packets = metadata["WID1"][0]["packets"]
    original_index = {char: i for i, char in enumerate(font.chars)}
    cells = sorted(_cells(metadata).items(), key=lambda item: ord(item[0]))
    new = [(char, cell) for char, cell in cells if char not in original_index]
    positions, height = _slot_layout([(cw, ch) for _ in new], atlas.width, atlas.height)
    new_at = {char: pos for (char, _), pos in zip(new, positions)}

    canvas = Image.new("RGBA", (atlas.width, max(atlas.height, height)))
    canvas.paste(atlas, (0, 0))
    chars, rects, crops, kerning = [], [], [], []
    for char, cell in cells:
        packet = packets[cell] if cell < len(packets) else {"kerning": 0.0, "width": float(cw)}
        cell_x, cell_y = (cell % columns) * cw, (cell // columns) * ch
        if char in original_index:
            j = original_index[char]
            x, y, w, h = font.rects[j]
            crop, right = font.crops[j], font.kerning[j][2]
        else:
            x, y = new_at[char]
            w, h = cw, ch
            crop, right = (0, 0, 0, 0), 0.0
        if w and h:
            canvas.paste(sheet.crop((cell_x, cell_y, cell_x + w, cell_y + h)), (x, y))
        chars.append(char)
        rects.append((x, y, w, h))
        crops.append(crop)
        kerning.append((float(packet["kerning"]), float(packet["width"]), float(right)))

    if canvas.size == atlas.size:
        mip = bytearray(font.texture.mip)
        surface.write(mip, 0, codec, canvas.width, canvas.height, canvas)
    else:
        mip = bytearray(surface.surface_bytes(codec, canvas.width, canvas.height))
        surface.write(mip, 0, codec, canvas.width, canvas.height, canvas, force=True)
    texture = xnb.Texture2D(font.texture.surface_format, canvas.width, canvas.height, bytes(mip))

    out = bytearray(font.prefix)
    out += xnb.write7(font.refs["texture"]) + xnb.write_texture2d(texture)
    out += xnb.write7(font.refs["glyph"]) + struct.pack("<i", len(rects))
    out += b"".join(struct.pack("<iiii", *r) for r in rects)
    out += xnb.write7(font.refs["crop"]) + struct.pack("<i", len(crops))
    out += b"".join(struct.pack("<iiii", *c) for c in crops)
    out += xnb.write7(font.refs["charmap"]) + struct.pack("<i", len(chars))
    out += b"".join(xnb.write_char(c) for c in chars)
    out += struct.pack("<if", int(xnb_meta["line_spacing"]), float(xnb_meta["spacing"]))
    out += xnb.write7(font.refs["kerning"]) + struct.pack("<i", len(kerning))
    out += b"".join(struct.pack("<fff", *k) for k in kerning)
    default = xnb_meta.get("default_char")
    out += b"\x01" + xnb.write_char(default) if default else b"\x00"
    return xnb.finish(out)
