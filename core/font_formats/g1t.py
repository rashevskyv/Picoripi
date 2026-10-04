"""Koei Tecmo G1T texture used as a bitmap font (Hyrule Warriors DE ``font_eu.g1t``): a BC3 atlas cut into a grid.

The file has no character table and no widths: the character -> cell rule and the cell size are
the game's constants. Only 4x4 blocks whose pixels were edited are encoded again, so untouched glyphs
keep their bytes.

Widths: when the game keeps them in its executable, ``widths`` describes that table -- ``values``
(the game's ``f32`` advance per code, ``first_code`` on), ``scale`` (game units per atlas pixel:
Hyrule Warriors draws a 64-pixel cell at font size 48, so 0.75) and ``patches`` (``{exefs patch file
relative to the translation folder: address of the table in that build's decompressed executable}``;
the file is named by the build id, so each build of the game takes its own). A glyph is then drawn at
the pen (kerning 0) and advances by ``value / scale`` pixels; edited widths are written as an IPS32
patch of the executable (``widths_patch``) and read back from it (``apply_widths_patch``). Without
``widths`` the advance is measured from the ink of the cell.

Parameters: ``cell_width``, ``cell_height``, ``columns``, ``first_cell`` (cell of ``first_code``),
``first_code`` and ``last_code`` (byte codes, one cell each, in order), ``codepage`` (cp1252),
``spacing`` (pixels added to the ink width), ``space_width``, ``ink_threshold`` (alpha), ``ascent``,
``widths``.
"""
from __future__ import annotations

import struct
from typing import Any, Dict, List, Tuple

from PIL import Image

from core.font_formats import Metadata, Sheets, char_code, map_entries

BC3 = 0x5B
NSO_HEADER = 0x100   # IPS offsets of an exefs patch count from the start of the NSO file, header included


def _texture(data: bytes) -> Tuple[int, int, int]:
    """``(data offset, width, height)`` of the first texture; only linear BC3 is supported."""
    if data[:4] != b"GT1G":
        raise ValueError("Not a G1T texture")
    table, count = struct.unpack_from("<II", data, 0x0C)
    if count < 1:
        raise ValueError("G1T without textures")
    entry = table + struct.unpack_from("<I", data, table)[0]
    fmt, dims, flags = data[entry + 1], data[entry + 2], data[entry + 4:entry + 8]
    header = 8 + (struct.unpack_from("<I", data, entry + 8)[0] if flags[3] & 0x11 else 0)
    if fmt != BC3:
        raise ValueError(f"G1T texture format {fmt:#04x} is not supported (only BC3, {BC3:#04x})")
    width, height = 1 << (dims & 0xF), 1 << (dims >> 4)
    start = entry + header
    if start + width * height > len(data):
        raise ValueError("G1T texture data is cut short")
    return start, width, height


def _decode(data: bytes) -> Image.Image:
    start, width, height = _texture(data)
    return Image.frombytes("RGBA", (width, height), data[start:start + width * height], "bcn", 3)


def _measure(sheet: Image.Image, box: Tuple[int, int, int, int], threshold: int) -> Tuple[int, int]:
    """``(left, ink width)`` of a cell; ``(0, 0)`` when it is empty."""
    alpha = sheet.crop(box).getchannel("A").point(lambda value: 255 if value > threshold else 0)
    bounds = alpha.getbbox()
    return (bounds[0], bounds[2] - bounds[0]) if bounds else (0, 0)


def extract(data: bytes, params: Dict[str, Any]) -> Tuple[Metadata, Sheets]:
    sheet = _decode(data)
    cell_w, cell_h = int(params["cell_width"]), int(params["cell_height"])
    columns = int(params.get("columns", sheet.width // cell_w))
    rows = sheet.height // cell_h
    first_cell, first_code = int(params.get("first_cell", 0)), int(params.get("first_code", 0x20))
    last_code = int(params.get("last_code", 0xFF))
    codepage = params.get("codepage", "cp1252")
    spacing, threshold = int(params.get("spacing", 0)), int(params.get("ink_threshold", 64))

    packets = []
    for cell in range(columns * rows):
        x, y = (cell % columns) * cell_w, (cell // columns) * cell_h
        left, ink = _measure(sheet, (x, y, x + cell_w, y + cell_h), threshold)
        packets.append({"kerning": left if ink else 0, "width": ink + spacing if ink else 0})
    pairs = []
    for code in range(first_code, last_code + 1):
        try:
            char = bytes([code]).decode(codepage)
        except UnicodeDecodeError:
            char = chr(code)
        pairs.append((char_code(char), first_cell + code - first_code))
    space = first_cell + 0x20 - first_code
    if "space_width" in params and 0 <= space < len(packets):
        packets[space] = {"kerning": 0, "width": int(params["space_width"])}
    table = params.get("widths")
    if table:
        scale = float(table.get("scale", 1))
        for index, value in enumerate(table["values"]):
            packets[first_cell + index] = {"kerning": 0, "width": round(float(value) / scale)}

    ascent = int(params.get("ascent", cell_h * 3 // 4))
    metadata = {
        "header": {"signature": "G1T font", "num_chunks": 4},
        "INF1": [{"encoding": 0, "ascent": ascent, "descent": cell_h - ascent,
                  "width": int(params.get("space_width", cell_w // 2)), "leading": cell_h,
                  "fallback_code": 0x3F, "unk1": 0}],
        "GLY1": [{"start_glyph": 0, "end_glyph": columns * rows - 1, "cell_width": cell_w, "cell_height": cell_h,
                  "page_data_size": sheet.width * sheet.height, "texture_format": BC3,
                  "glyph_horizontal_count": columns, "glyph_vertical_count": rows,
                  "texture_width": sheet.width, "texture_height": sheet.height}],
        "MAP1": [map_entries(pairs)],
        "WID1": [{"first_code_included": 0, "last_code_included": columns * rows, "packets": packets}],
    }
    return metadata, [sheet]


def pack(metadata: Metadata, sheets: Sheets, original: bytes, params: Dict[str, Any]) -> bytes:
    """``original`` with every edited 4x4 block encoded again (widths are not stored in a G1T)."""
    start, width, height = _texture(original)
    old = _decode(original).tobytes()
    new_image = sheets[0].convert("RGBA")
    if new_image.size != (width, height):
        raise ValueError(f"The sheet is {new_image.size}, the texture {width}x{height}")
    new = new_image.tobytes()
    out = bytearray(original)
    row_bytes = width * 4
    blocks_per_row = width // 4
    for by in range(height // 4):
        band = slice(by * 4 * row_bytes, (by * 4 + 4) * row_bytes)
        if old[band] == new[band]:
            continue
        for bx in range(blocks_per_row):
            changed = any(
                old[(by * 4 + y) * row_bytes + bx * 16:(by * 4 + y) * row_bytes + bx * 16 + 16]
                != new[(by * 4 + y) * row_bytes + bx * 16:(by * 4 + y) * row_bytes + bx * 16 + 16]
                for y in range(4))
            if changed:
                block = new_image.crop((bx * 4, by * 4, bx * 4 + 4, by * 4 + 4)).tobytes("bcn", 3)
                at = start + (by * blocks_per_row + bx) * 16
                out[at:at + 16] = block
    return bytes(out)


# -- the game's width table, patched in its executable -----------------------------------


def _read_ips(data: bytes) -> Dict[int, bytes]:
    """``{offset: bytes}`` of an IPS32 patch; empty for no patch."""
    if not data:
        return {}
    if data[:5] != b"IPS32":
        raise ValueError("Not an IPS32 patch")
    records, at = {}, 5
    while data[at:at + 4] != b"EEOF":
        if at + 6 > len(data):
            raise ValueError("The IPS32 patch is cut short")
        offset, size = struct.unpack_from(">IH", data, at)
        at += 6
        if size == 0:   # run-length record
            count, value = struct.unpack_from(">HB", data, at)
            records[offset], at = bytes([value]) * count, at + 3
        else:
            records[offset], at = data[at:at + size], at + size
    return records


def _write_ips(records: Dict[int, bytes]) -> bytes:
    out = bytearray(b"IPS32")
    for offset in sorted(records):
        out += struct.pack(">IH", offset, len(records[offset])) + records[offset]
    return bytes(out + b"EEOF")


def _table_span(params: Dict[str, Any], address: Any) -> Tuple[int, int, float, List[float]]:
    """``(patch offset, size in bytes, scale, the game's values)`` of the width table at ``address``."""
    table = params["widths"]
    values = [float(value) for value in table["values"]]
    return int(str(address), 0) + NSO_HEADER, 4 * len(values), float(table.get("scale", 1)), values


def apply_widths_patch(metadata: Metadata, params: Dict[str, Any], address: Any, patch: bytes) -> None:
    """Widths of ``patch`` (an exefs patch ``widths_patch`` wrote for the table at ``address``) over
    the game's in ``metadata``."""
    if not params.get("widths") or not patch:
        return
    start, size, scale, _values = _table_span(params, address)
    packets, first_cell = metadata["WID1"][0]["packets"], int(params.get("first_cell", 0))
    for offset, data in _read_ips(patch).items():
        for index in range(size // 4):
            at = start + 4 * index - offset
            if 0 <= at and at + 4 <= len(data):
                packets[first_cell + index]["width"] = round(struct.unpack_from("<f", data, at)[0] / scale)


def widths_patch(metadata: Metadata, params: Dict[str, Any], address: Any, existing: bytes = b"") -> bytes:
    """The exefs patch with this font's widths for the table at ``address``, keeping the records of
    ``existing`` for other tables.

    A width left at the game's (in pixels) keeps the game's exact value; the table gets a record only
    when some width differs, so an unedited font adds nothing to the patch.
    """
    start, size, scale, game = _table_span(params, address)
    packets, first_cell = metadata["WID1"][0]["packets"], int(params.get("first_cell", 0))
    records = {offset: data for offset, data in _read_ips(existing).items()
               if offset >= start + size or offset + len(data) <= start}
    values = []
    for index, value in enumerate(game):
        pixels = int(packets[first_cell + index]["width"])
        values.append(value if round(value / scale) == pixels else pixels * scale)
    if values != game:
        records[start] = struct.pack(f"<{len(values)}f", *values)
    return _write_ips(records)
