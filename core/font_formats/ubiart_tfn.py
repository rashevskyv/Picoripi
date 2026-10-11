"""UbiArt Framework ``.tfn.ckd`` fonts of the 3DS builds (Gravity Falls: Legend of the Gnome Gemulets).

The font source is the ``.tfn.ckd`` glyph table with the ``.tga.ckd`` atlas as its ``companion`` (``join_pair``).
The table is a cooked object: a header with the atlas path, a u32 glyph count, then ``count`` records of 44 bytes
(big endian): ``0x28``, code, x, y, width, height (the glyph's box in the upright atlas), left bearing, top offset,
advance, 0, 0x0F (the u32 at offset 4 grows by 44 with every record; the game crashes if it does not); the records are sorted by code (the space first). The atlas is an ``ubiart_tex`` picture.

The model has one cell per glyph, in record order, with the glyph's box at the cell's top-left, and spare empty
cells. A typed character in a spare cell becomes a new record (``ADDS_GLYPHS``); an edited glyph is drawn into its
own box when it fits, else into free room of the atlas. Packing an unedited model gives the original bytes.
"""
from __future__ import annotations

import struct
from typing import Any, Dict, List, Tuple

from PIL import Image

from core.font_formats import Metadata, Sheets, char_code, char_map, coverage, grey_sheet, map_entries
from core.font_formats.sources import join_pair, split_pair

ADDS_GLYPHS = True
RECORD = 44
SPARE = 96
COLUMNS = 16


def _parse(table: bytes) -> Dict[str, Any]:
    """``{"count_at", "start", "records": [{code, x, y, w, h, left, top, advance, raw}]}``."""
    if len(table) < 0x60 or struct.unpack_from(">I", table, 0)[0] != 1:
        raise ValueError("Not an UbiArt font table (.tfn.ckd)")
    count_at = None
    for at in range(0x40, len(table) - 3, 4):
        count = struct.unpack_from(">I", table, at)[0]
        if 0 < count < 100000 and at + 4 + count * RECORD == len(table):
            count_at = at
            break
    if count_at is None:
        raise ValueError("The glyph records of the font table were not found")
    start, records = count_at + 4, []
    for index in range(count):
        raw = table[start + index * RECORD:start + (index + 1) * RECORD]
        marker, code, x, y, w, h, left, top, advance, zero, tail = struct.unpack(">11I", raw)
        if tail != 0x0F:
            raise ValueError("Unexpected UbiArt glyph record")
        records.append({"code": code, "x": x, "y": y, "w": w, "h": h, "left": left, "top": top,
                        "advance": advance, "raw": raw})
    return {"count_at": count_at, "start": start, "records": records}


def _record_bytes(r: Dict[str, Any]) -> bytes:
    out = bytearray(r["raw"])
    struct.pack_into(">8I", out, 4, r["code"], r["x"], r["y"], r["w"], r["h"], r["left"], r["top"], r["advance"])
    return bytes(out)


def _atlas(texture: bytes) -> Image.Image:
    from core.texture_formats import ubiart_tex
    return ubiart_tex.read(texture, {})[0].image.convert("RGBA")


def _layout(font: Dict[str, Any]):
    records = font["records"]
    cw = max([r["w"] for r in records] + [4])
    ch = max([r["h"] for r in records] + [4])
    cells = len(records) + SPARE
    rows = -(-cells // COLUMNS)
    return cw, ch, rows


def _cell(glyph: int, cw: int, ch: int) -> Tuple[int, int, int, int]:
    x, y = (glyph % COLUMNS) * cw, (glyph // COLUMNS) * ch
    return x, y, x + cw, y + ch


def extract(data: bytes, params: Dict[str, Any]) -> Tuple[Metadata, Sheets]:
    table, texture = split_pair(data)
    font = _parse(table)
    records = font["records"]
    cw, ch, rows = _layout(font)
    ink = coverage(_atlas(texture))
    sheet = Image.new("L", (COLUMNS * cw, rows * ch))
    packets, pairs, seen = [], [], set()
    for glyph, r in enumerate(records):
        if r["w"] and r["h"]:
            x, y, _x2, _y2 = _cell(glyph, cw, ch)
            sheet.paste(ink.crop((r["x"], r["y"], r["x"] + r["w"], r["y"] + r["h"])), (x, y))
        packets.append({"kerning": r["left"], "width": r["advance"]})
        if r["code"] not in seen and r["code"] < 0x110000:
            seen.add(r["code"])
            pairs.append((char_code(chr(r["code"])), glyph))
    packets += [{"kerning": 0, "width": 0} for _ in range(COLUMNS * rows - len(packets))]
    space = next((r["advance"] for r in records if r["code"] == 0x20), cw // 2)
    metadata = {
        "header": {"signature": "TFN", "num_chunks": 1},
        "INF1": [{"encoding": 1, "ascent": ch * 3 // 4, "descent": ch - ch * 3 // 4, "width": space, "leading": ch,
                  "fallback_code": 0x3F, "unk1": 0}],
        "GLY1": [{"start_glyph": 0, "end_glyph": COLUMNS * rows - 1, "cell_width": cw, "cell_height": ch,
                  "page_data_size": 0, "texture_format": 0, "glyph_horizontal_count": COLUMNS,
                  "glyph_vertical_count": rows, "texture_width": sheet.width, "texture_height": sheet.height}],
        "MAP1": [map_entries(pairs)],
        "WID1": [{"first_code_included": 0, "last_code_included": COLUMNS * rows - 1, "packets": packets}],
    }
    return metadata, [grey_sheet(sheet)]


def _free_box(taken: List[bytearray], width: int, height: int, w: int, h: int) -> Tuple[int, int]:
    """Top-left of a free ``w`` x ``h`` box with a free pixel after it, searched row by row."""
    for y in range(1, height - h):
        x = 1
        while x + w < width:
            blocker = max((taken[row].rfind(1, x, x + w + 1) for row in range(y, y + h + 1)), default=-1)
            if blocker < 0:
                return x, y
            x = blocker + 1
    raise ValueError(f"No free room for a {w}x{h} glyph in the font atlas")


def pack(metadata: Metadata, sheets: Sheets, original: bytes, params: Dict[str, Any]) -> bytes:
    from core.texture_formats import ubiart_tex
    table, texture = split_pair(original)
    font = _parse(table)
    records = font["records"]
    old_meta, old_sheets = extract(original, params)
    cw, ch, _rows = _layout(font)
    gly = metadata["GLY1"][0]
    if (gly["cell_width"], gly["cell_height"], gly["glyph_horizontal_count"]) != (cw, ch, COLUMNS):
        raise ValueError("The font's cell grid changed; it cannot be written back")
    new_ink, old_ink = coverage(sheets[0]), coverage(old_sheets[0])
    packets = metadata["WID1"][0]["packets"]
    image = _atlas(texture)
    plane = coverage(image)
    taken = [bytearray(plane.width) for _ in range(plane.height)]
    for r in records:
        for row in range(r["y"], min(r["y"] + r["h"] + 1, plane.height)):
            taken[row][r["x"]:r["x"] + r["w"] + 1] = b"\x01" * (r["w"] + 1)
    dirty: List[Tuple[int, int, int, int]] = []

    def draw(glyph: int, r: Dict[str, Any]) -> None:
        cell = new_ink.crop(_cell(glyph, cw, ch))
        box = cell.getbbox()
        right, bottom = (box[2], box[3]) if box else (0, 0)
        if r["w"] and r["h"]:
            plane.paste(0, (r["x"], r["y"], r["x"] + r["w"], r["y"] + r["h"]))
            dirty.append((r["x"], r["y"], r["x"] + r["w"], r["y"] + r["h"]))
        if right > r["w"] or bottom > r["h"] or not (r["w"] and r["h"]):
            r["w"], r["h"] = max(right, 1), max(bottom, r["h"], 1)
            r["x"], r["y"] = _free_box(taken, plane.width, plane.height, r["w"], r["h"])
            for row in range(r["y"], r["y"] + r["h"] + 1):
                taken[row][r["x"]:r["x"] + r["w"] + 1] = b"\x01" * (r["w"] + 1)
        plane.paste(cell.crop((0, 0, r["w"], r["h"])), (r["x"], r["y"]))
        dirty.append((r["x"], r["y"], r["x"] + r["w"], r["y"] + r["h"]))

    changed = False
    for glyph, r in enumerate(records):
        if new_ink.crop(_cell(glyph, cw, ch)).tobytes() != old_ink.crop(_cell(glyph, cw, ch)).tobytes():
            draw(glyph, r)
            changed = True
        if glyph < len(packets):
            advance, left = int(packets[glyph]["width"]), int(packets[glyph]["kerning"])
            if (advance, left) != (r["advance"], r["left"]):
                r["advance"], r["left"], changed = max(advance, 0), max(left, 0), True
    known = {r["code"] for r in records}
    template = next((r for r in records if r["code"] == 0x41), records[0])
    added = []
    for char, glyph in char_map(metadata).items():
        code = ord(char)
        if code in known or code > 0xFFFF:
            continue
        r = dict(template, code=code, w=0, h=0, x=0, y=0, advance=0, left=0)
        if glyph < len(records):                 # another character on an existing glyph: share its box
            shared = records[glyph]
            r.update(x=shared["x"], y=shared["y"], w=shared["w"], h=shared["h"], advance=shared["advance"],
                     left=shared["left"], top=shared["top"])
        elif new_ink.crop(_cell(glyph, cw, ch)).getbbox():
            r["h"] = template["h"]
            draw(glyph, r)
            width = int(packets[glyph]["width"]) if glyph < len(packets) else 0
            r["advance"] = width or r["w"] + 2
            r["left"] = int(packets[glyph]["kerning"]) if glyph < len(packets) else 0
        else:
            continue
        added.append(r)
    if not changed and not added:
        return bytes(original)
    rows = sorted(records + added, key=lambda r: r["code"])
    out = bytearray(table[:font["count_at"]])
    if added:                                 # u32 at 4 is the size of the glyph data: +44 per record (the game crashes else)
        struct.pack_into(">I", out, 4, struct.unpack_from(">I", out, 4)[0] + len(added) * RECORD)
    out += struct.pack(">I", len(rows))
    out += b"".join(_record_bytes(r) for r in rows)
    if dirty:                                 # only the touched boxes: the rest of the atlas keeps its pixels
        for box in dirty:
            ink = plane.crop(box)
            white = Image.new("L", ink.size, 255)
            image.paste(Image.merge("RGBA", (white, white, white, ink)), box[:2])
        texture = ubiart_tex.write(texture, {0: image}, {})
    return join_pair(bytes(out), texture)


def letters(data: bytes) -> set:
    """The characters a font table has."""
    return {chr(r["code"]) for r in _parse(split_pair(data)[0] if data[:4] == b"PAIR" else data)["records"]
            if r["code"] < 0x110000}
