"""Capcom MT Framework Mobile fonts: ``GFD`` and ``lfd`` glyph tables with an MT ``TEX`` page (3DS Monster Hunter).

The font source is the table with one page as its ``companion`` (``join_pair``); ``params.page`` is that page's
number (a font with two pages has two sources that share the table). Little endian.

``GFD`` (MH3U, Stories): u32 glyph count at 0x1C, page count at 0x18; the name (u32 length + text + NUL) ends the
header; then 16-byte records sorted by code: u32 code, u32 ``page | x << 8 | y << 20``, u32 ``? | width << 8 |
height << 20``, u32 with the advance in its low byte. Bytes after the records (a dynamic font's second table)
are kept.

``lfd`` (MH4U, Stories layouts): 0x28-byte header (u32 glyph count at 8, records at 0x1C, records end at 0x20,
tail at 0x24); 20-byte records: u32 code, u32 ``page | x << 8 | y << 20``, u32 ``width | height << 12``, u32
advance in the low byte, u32; after the records u32 0 and u32 the file offset of the page name.

``GFD`` of the Switch games (Monster Hunter Stories, version 0x21108): the same header (glyph count at 0x1C), the
name (u32 length at 0x3C, text, NUL) and 36-byte records: u32 code, six floats (width, height, left bearing, top
bearing, advance, line height), u32 ``page | x << 8 | y << 20`` and u32 flags. The page is a Switch ``TEX``
(BC7) that keeps the glyph coverage in its green channel (red and blue are constant). Records are not sorted
the same way and the file ends with the page name for icon fonts, so a font with a tail cannot grow.

The model has one cell per glyph of the page, in code order, with the glyph's box at the cell's top-left, and
spare empty cells. A typed character in a spare cell becomes a new record (``ADDS_GLYPHS``); mapping a character
to an existing cell makes a record that shares that box. An edited glyph is drawn into its own box when it fits,
else into free room of the page. Packing an unedited model gives the original bytes.
"""
from __future__ import annotations

import math
import struct
from typing import Any, Dict, List, Tuple

from PIL import Image

from core.font_formats import Metadata, Sheets, char_code, char_map, coverage, grey_sheet, map_entries
from core.font_formats.sources import join_pair, split_pair

ADDS_GLYPHS = True
SPARE = 96


NX_VERSION = 0x21108


def _parse_nx(table: bytes) -> Dict[str, Any]:
    count, nlen = struct.unpack_from("<II", table, 0x1C)[0], struct.unpack_from("<I", table, 0x3C)[0]
    start = 0x40 + nlen + 1
    end = start + count * 36
    if nlen > 0x100 or end > len(table):
        raise ValueError("font records run past the file")
    records = []
    for index in range(count):
        at = start + index * 36
        code = struct.unpack_from("<I", table, at)[0]
        fw, fh, _bx, _by, fadv, _line = struct.unpack_from("<6f", table, at + 4)
        v1 = struct.unpack_from("<I", table, at + 28)[0]
        records.append({"code": code, "raw": table[at:at + 36], "page": v1 & 0xFF, "x": (v1 >> 8) & 0xFFF,
                        "y": (v1 >> 20) & 0xFFF, "w": math.ceil(fw), "h": math.ceil(fh), "advance": round(fadv)})
    return {"kind": "gfd_nx", "start": start, "size": 36, "end": end, "records": records}


def _parse(table: bytes) -> Dict[str, Any]:
    if table[:4] == b"GFD\0" and len(table) > 0x44 and struct.unpack_from("<I", table, 4)[0] == NX_VERSION:
        return _parse_nx(table)
    if table[:4] == b"GFD\0":
        count = struct.unpack_from("<I", table, 0x1C)[0]
        start = next((p + 5 + n for p in range(0x24, 0x44, 4)
                      for n in [struct.unpack_from("<I", table, p)[0]]
                      if 0 < n < 0x100 and table[p + 4 + n:p + 5 + n] == b"\0"
                      and all(32 <= c < 127 for c in table[p + 4:p + 4 + n])), None)
        if start is None:
            raise ValueError("GFD name not found")
        size, kind = 16, "gfd"
    elif table[:4] == b"lfd\0":
        count, start = struct.unpack_from("<I", table, 8)[0], struct.unpack_from("<I", table, 0x1C)[0]
        size, kind = 20, "lfd"
    else:
        raise ValueError("Not an MT Framework font (GFD or lfd)")
    records = []
    for index in range(count):
        at = start + index * size
        code, w1, w2, w3 = struct.unpack_from("<4I", table, at)
        if kind == "gfd":
            w, h = (w2 >> 8) & 0xFFF, (w2 >> 20) & 0xFFF
        else:
            w, h = w2 & 0xFFF, (w2 >> 12) & 0xFFF
        records.append({"code": code, "raw": table[at:at + size], "page": w1 & 0xFF, "x": (w1 >> 8) & 0xFFF,
                        "y": (w1 >> 20) & 0xFFF, "w": w, "h": h, "advance": w3 & 0xFF})
    end = start + count * size
    if end > len(table):
        raise ValueError("font records run past the file")
    return {"kind": kind, "start": start, "size": size, "end": end, "records": records}


def _record_bytes(kind: str, r: Dict[str, Any]) -> bytes:
    out = bytearray(r["raw"])
    if kind == "gfd_nx":
        fw, fh, bx, by, fadv, line = struct.unpack_from("<6f", out, 4)
        fw, fh = (fw if math.ceil(fw) == r["w"] else float(r["w"])), (fh if math.ceil(fh) == r["h"] else float(r["h"]))
        fadv = fadv if round(fadv) == r["advance"] else float(r["advance"])
        struct.pack_into("<I6f", out, 0, r["code"], fw, fh, bx, by, fadv, line)
        struct.pack_into("<I", out, 28, r["page"] | r["x"] << 8 | r["y"] << 20)
        return bytes(out)
    _code, _w1, w2, w3 = struct.unpack_from("<4I", out, 0)
    w1 = r["page"] | r["x"] << 8 | r["y"] << 20
    w2 = (w2 & 0xFF) | r["w"] << 8 | r["h"] << 20 if kind == "gfd" else (w2 & ~0xFFFFFF) | r["w"] | r["h"] << 12
    struct.pack_into("<4I", out, 0, r["code"], w1, w2 & 0xFFFFFFFF, (w3 & ~0xFF) | r["advance"])
    return bytes(out)


def _page(texture: bytes) -> Image.Image:
    from core.texture_formats import mt_tex
    return mt_tex.read(texture, {})[0].image.convert("RGBA")


def _green_page(image: Image.Image) -> bool:
    """A Switch font page keeps its coverage in green; red and blue hold one value."""
    red, _green, blue, _alpha = image.split()
    return all(hi - lo <= 8 for lo, hi in (red.getextrema(), blue.getextrema()))


def _ink(image: Image.Image, nx: bool) -> Image.Image:
    """Glyph coverage of a page: the green channel of a Switch page (red and blue constant), else alpha / luminance."""
    if nx and _green_page(image):
        return image.getchannel("G")
    return coverage(image)


def _layout(font: Dict[str, Any], page: int, spare: bool):
    mine = [i for i, r in enumerate(font["records"]) if r["page"] == page]
    cw = max([r["w"] for r in (font["records"][i] for i in mine)] + [4])
    ch = max([r["h"] for r in (font["records"][i] for i in mine)] + [4])
    cells = len(mine) + (SPARE if spare else 0)
    columns = 16 if cells <= 512 else 32
    rows = -(-cells // columns)
    return mine, cw, ch, columns, rows


def _spare(font: Dict[str, Any], table: bytes) -> bool:
    return font["kind"] == "lfd" or font["end"] == len(table)      # a GFD with a second table / tail cannot grow


def _cell(glyph: int, cw: int, ch: int, columns: int) -> Tuple[int, int, int, int]:
    x, y = (glyph % columns) * cw, (glyph // columns) * ch
    return x, y, x + cw, y + ch


def extract(data: bytes, params: Dict[str, Any]) -> Tuple[Metadata, Sheets]:
    table, texture = split_pair(data)
    font = _parse(table)
    page = int(params.get("page", 0))
    mine, cw, ch, columns, rows = _layout(font, page, _spare(font, table))
    ink = _ink(_page(texture), font["kind"] == "gfd_nx")
    sheet = Image.new("L", (columns * cw, rows * ch))
    packets, pairs, seen = [], [], set()
    for glyph, index in enumerate(mine):
        r = font["records"][index]
        if r["w"] and r["h"]:
            x, y, _x2, _y2 = _cell(glyph, cw, ch, columns)
            sheet.paste(ink.crop((r["x"], r["y"], r["x"] + r["w"], r["y"] + r["h"])), (x, y))
        packets.append({"kerning": 0, "width": r["advance"]})
        if r["code"] not in seen:
            seen.add(r["code"])
            pairs.append((char_code(chr(r["code"])), glyph))
    packets += [{"kerning": 0, "width": 0} for _ in range(columns * rows - len(packets))]
    space = next((r["advance"] for r in font["records"] if r["code"] == 0x20), cw // 2)
    metadata = {
        "header": {"signature": "lfd" if font["kind"] == "lfd" else "GFD", "num_chunks": 1},
        "INF1": [{"encoding": 1, "ascent": ch * 3 // 4, "descent": ch - ch * 3 // 4, "width": space, "leading": ch,
                  "fallback_code": 0x3F, "unk1": 0}],
        "GLY1": [{"start_glyph": 0, "end_glyph": columns * rows - 1, "cell_width": cw, "cell_height": ch,
                  "page_data_size": 0, "texture_format": 0, "glyph_horizontal_count": columns,
                  "glyph_vertical_count": rows, "texture_width": sheet.width, "texture_height": sheet.height}],
        "MAP1": [map_entries(pairs)],
        "WID1": [{"first_code_included": 0, "last_code_included": columns * rows - 1, "packets": packets}],
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
    raise ValueError(f"No free room for a {w}x{h} glyph in the font page")


def pack(metadata: Metadata, sheets: Sheets, original: bytes, params: Dict[str, Any]) -> bytes:
    from core.texture_formats import mt_tex
    table, texture = split_pair(original)
    font = _parse(table)
    page = int(params.get("page", 0))
    old_meta, old_sheets = extract(original, params)
    mine, cw, ch, columns, _rows = _layout(font, page, _spare(font, table))
    gly = metadata["GLY1"][0]
    if (gly["cell_width"], gly["cell_height"], gly["glyph_horizontal_count"]) != (cw, ch, columns):
        raise ValueError("The font's cell grid changed; it cannot be written back")
    new_ink, old_ink = coverage(sheets[0]), coverage(old_sheets[0])
    packets = metadata["WID1"][0]["packets"]
    records = font["records"]
    image = _page(texture)
    nx = font["kind"] == "gfd_nx" and _green_page(image)
    plane = _ink(image, nx)
    taken = [bytearray(plane.width) for _ in range(plane.height)]
    for r in records:
        if r["page"] == page:
            for row in range(r["y"], min(r["y"] + r["h"] + 1, plane.height)):
                taken[row][r["x"]:r["x"] + r["w"] + 1] = b"\x01" * (r["w"] + 1)
    dirty: List[Tuple[int, int, int, int]] = []

    def draw(glyph: int, r: Dict[str, Any]) -> None:
        cell = new_ink.crop(_cell(glyph, cw, ch, columns))
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
    for glyph, index in enumerate(mine):
        r = records[index]
        if new_ink.crop(_cell(glyph, cw, ch, columns)).tobytes() != old_ink.crop(_cell(glyph, cw, ch, columns)).tobytes():
            draw(glyph, r)
            changed = True
        advance = int(packets[glyph]["width"]) if glyph < len(packets) else r["advance"]
        if advance != r["advance"]:
            if not 0 <= advance < 256:
                raise ValueError(f"Advance of U+{r['code']:04X} must be 0..255")
            r["advance"], changed = advance, True
    known = {r["code"] for r in records}
    template = next((r for r in records if r["code"] == 0x41), records[0])
    added = []
    for char, glyph in char_map(metadata).items():
        code = ord(char)
        if code in known or code > 0xFFFF:
            continue
        r = dict(template, code=code, page=page, w=0, h=0, x=0, y=0, advance=0)
        if glyph < len(mine):                 # another character on an existing glyph: share its box
            shared = records[mine[glyph]]
            r.update(x=shared["x"], y=shared["y"], w=shared["w"], h=shared["h"], advance=shared["advance"])
        elif new_ink.crop(_cell(glyph, cw, ch, columns)).getbbox():
            if not _spare(font, table):
                raise ValueError("This font has a second glyph table; it cannot get new characters")
            r["h"] = template["h"]
            draw(glyph, r)
        else:
            continue
        if glyph < len(packets) and glyph >= len(mine):
            r["advance"] = max(0, min(255, int(packets[glyph]["width"]) or r["w"] + 1))
        added.append(r)
    if not changed and not added:
        return bytes(original)
    rows = sorted(records + added, key=lambda r: r["code"])
    out = bytearray(table[:font["start"]])
    out += b"".join(_record_bytes(font["kind"], r) for r in rows)
    out += table[font["end"]:]
    grow = len(added) * font["size"]
    if font["kind"] in ("gfd", "gfd_nx"):
        struct.pack_into("<I", out, 0x1C, len(rows))
    elif grow:
        struct.pack_into("<I", out, 8, len(rows))
        end, tail = struct.unpack_from("<II", out, 0x20)
        struct.pack_into("<II", out, 0x20, end + grow, tail + grow)
        name_at = struct.unpack_from("<I", out, end + grow + 4)[0]
        if font["end"] <= name_at:
            struct.pack_into("<I", out, end + grow + 4, name_at + grow)
    if dirty:                                 # only the touched boxes: the rest of the page keeps its pixels
        for box in dirty:
            ink = plane.crop(box)
            if nx:
                red, _green, blue, alpha = image.crop(box).split()
                image.paste(Image.merge("RGBA", (red, ink, blue, alpha)), box[:2])
                continue
            white = Image.new("L", ink.size, 255)
            image.paste(Image.merge("RGBA", (white, white, white, ink)), box[:2])
        texture = mt_tex.write(texture, {0: image}, {})
    return join_pair(bytes(out), texture)


def letters(data: bytes) -> set:
    """The characters a font table has (every page)."""
    return {chr(r["code"]) for r in _parse(split_pair(data)[0] if data[:4] == b"PAIR" else data)["records"]}
