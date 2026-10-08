"""Fragile Dreams (Wii) fonts: ``FONT`` files of glyph boxes in TPL pages.

Header (big endian): ``FONT``, u32 end of the last chunk, u8, u8 code chunk count, u8 8, u8 page count, u16
cell width, u16 cell height, u32 0; then chunks of tag + u32 size (the 8 header bytes included): ``BC  `` (the
single-byte codes), ``MBC `` (Shift-JIS codes of the Japanese fonts; kept as it is) and one ``TEXD`` per page
(a TPL after the 8 header bytes). ``BC  ``: 256 u32 offsets of glyph records, counted from the chunk start
(0 = no glyph), then the 10-byte records: u8 advance, u8 line height, s8 x and s8 y of the box from the pen
and the line top, u8 width, u8 height, u8 page, u24 ``x << 12 | y`` of the box in the page.

The model shows code ``c`` as glyph ``c`` of a 16 x 16 grid; a cell holds the box drawn where the game draws
it, ``kerning`` pixels right of the cell's left edge. Codes are cp1251 characters (the game's English bytes
are cp1252 and the same for the punctuation it uses; 0xC0-0xFF and the cells of Ґ Є І Ї are where Ukrainian
letters go). Packing an unedited model gives the original bytes; an edited glyph is drawn into its own box
when it fits, else into free room of its page; widths are the advances. A code without a record in the file
stays empty (the record table has no room for new ones).
"""
from __future__ import annotations

import struct
from typing import Any, Dict, List, Tuple

from PIL import Image

from core.font_formats import Metadata, Sheets, char_code, coverage, grey_sheet, map_entries

COLUMNS = 16
CODES = 256
ENCODING = "cp1251"


def _chunks(data: bytes) -> List[Tuple[bytes, int, int]]:
    """``[(tag, start, size)]`` of the chunks after the header."""
    out, at = [], 0x14
    while at + 8 <= len(data) and data[at:at + 4] in (b"BC  ", b"MBC ", b"TEXD"):
        size = struct.unpack_from(">I", data, at + 4)[0]
        if size < 8:
            break
        out.append((data[at:at + 4], at, size))
        at += size
    return out


def _parse(data: bytes) -> Dict[str, Any]:
    if data[:4] != b"FONT" or data[0x14:0x18] != b"BC  ":
        raise ValueError("Not a Fragile Dreams font (FONT with a BC chunk)")
    chunks = _chunks(data)
    bc = chunks[0][1]
    records: Dict[int, Dict[str, int]] = {}
    for code in range(CODES):
        offset = struct.unpack_from(">I", data, bc + 8 + 4 * code)[0]
        if offset:
            at = bc + offset
            adv, line, x0, y0, w, h, page = struct.unpack_from(">BBbbBBB", data, at)
            xy = int.from_bytes(data[at + 7:at + 10], "big")
            records[code] = {"at": at, "advance": adv, "line": line, "ox": x0, "oy": y0, "w": w, "h": h,
                             "page": page, "x": xy >> 12, "y": xy & 0xFFF}
    pages = [start + 8 for tag, start, _size in chunks if tag == b"TEXD"]
    if not pages:
        raise ValueError("The font has no TEXD page")
    return {"records": records, "pages": pages, "cell": struct.unpack_from(">HH", data, 0x0C)}


def _page_images(data: bytes, font: Dict[str, Any]) -> List[Image.Image]:
    from core.texture_formats import tpl
    return [tpl.read(data[at:], {})[0].image.convert("RGBA") for at in font["pages"]]


def _geometry(font: Dict[str, Any]) -> Tuple[int, int, int, int]:
    """``(pad x, pad y, cell width, cell height)`` of the model grid."""
    recs = list(font["records"].values())
    pad_x = max([0] + [-r["ox"] for r in recs])
    pad_y = max([0] + [-r["oy"] for r in recs])
    width = max([font["cell"][0]] + [pad_x + r["ox"] + r["w"] for r in recs])
    height = max([font["cell"][1]] + [pad_y + r["oy"] + r["h"] for r in recs] + [r["line"] for r in recs])
    return pad_x, pad_y, width, height


def _char(code: int) -> str:
    try:
        return bytes([code]).decode(ENCODING)
    except UnicodeDecodeError:
        return ""


def extract(data: bytes, params: Dict[str, Any]) -> Tuple[Metadata, Sheets]:
    font = _parse(data)
    pages = [coverage(p) for p in _page_images(data, font)]
    pad_x, pad_y, cw, ch = _geometry(font)
    rows = CODES // COLUMNS
    ink = Image.new("L", (COLUMNS * cw, rows * ch))
    for code, r in font["records"].items():
        if r["w"] and r["h"] and r["page"] < len(pages):
            box = pages[r["page"]].crop((r["x"], r["y"], r["x"] + r["w"], r["y"] + r["h"]))
            ink.paste(box, ((code % COLUMNS) * cw + pad_x + r["ox"], (code // COLUMNS) * ch + pad_y + r["oy"]))
    line = max([font["cell"][1]] + [r["line"] for r in font["records"].values()])
    space = font["records"].get(0x20, {}).get("advance") or font["records"].get(ord("i"), {}).get("advance", cw // 3)
    packets = [{"kerning": pad_x, "width": font["records"][c]["advance"] if c in font["records"] else 0}
               for c in range(CODES)]
    pairs = [(char_code(_char(c)), c) for c in range(0x20, CODES) if _char(c)]
    metadata = {
        "header": {"signature": "FONT", "num_chunks": len(_chunks(data))},
        "INF1": [{"encoding": 0, "ascent": line, "descent": 0, "width": space, "leading": line,
                  "fallback_code": 0x3F, "unk1": 0}],
        "GLY1": [{"start_glyph": 0, "end_glyph": CODES - 1, "cell_width": cw, "cell_height": ch,
                  "page_data_size": 0, "texture_format": 0, "glyph_horizontal_count": COLUMNS,
                  "glyph_vertical_count": rows, "texture_width": ink.width, "texture_height": ink.height}],
        "MAP1": [map_entries(pairs)],
        "WID1": [{"first_code_included": 0, "last_code_included": CODES - 1, "packets": packets}],
    }
    return metadata, [grey_sheet(ink)]


# -- packing ----------------------------------------------------------------------------------


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
    from core.texture_formats import tpl
    font = _parse(original)
    old_meta, old_sheets = extract(original, params)
    pad_x, pad_y, cw, ch = _geometry(font)
    gly = metadata["GLY1"][0]
    if (gly["cell_width"], gly["cell_height"], gly["glyph_horizontal_count"]) != (cw, ch, COLUMNS):
        raise ValueError("The font's cell grid changed; it cannot be written back")
    new_ink, old_ink = coverage(sheets[0]), coverage(old_sheets[0])
    packets = metadata["WID1"][0]["packets"]

    def cell(code: int) -> Tuple[int, int, int, int]:
        x, y = (code % COLUMNS) * cw, (code // COLUMNS) * ch
        return x, y, x + cw, y + ch

    changed = [c for c in range(CODES) if new_ink.crop(cell(c)).tobytes() != old_ink.crop(cell(c)).tobytes()]
    widths = {c: int(packets[c]["width"]) for c in range(min(CODES, len(packets)))}
    records = font["records"]
    if not changed and all(widths.get(c, r["advance"]) == r["advance"] for c, r in records.items()):
        return bytes(original)

    out = bytearray(original)
    images = _page_images(original, font)
    planes = [coverage(p) for p in images]
    dirty = set()
    taken = []
    for plane in planes:
        rows = [bytearray(plane.width) for _ in range(plane.height)]
        taken.append(rows)
    for r in records.values():
        if r["page"] < len(taken):
            for row in range(r["y"], min(r["y"] + r["h"] + 1, len(taken[r["page"]]))):
                taken[r["page"]][row][r["x"]:r["x"] + r["w"] + 1] = b"\x01" * (r["w"] + 1)
    for code in changed:
        if code not in records:
            if new_ink.crop(cell(code)).getbbox():
                raise ValueError(f"Code {code:#04x} has no glyph record in this font; draw it in a cell that has one")
            continue
        r = records[code]
        glyph = new_ink.crop(cell(code))
        found = glyph.getbbox()
        page = r["page"]
        planes[page].paste(0, (r["x"], r["y"], r["x"] + r["w"], r["y"] + r["h"]))
        dirty.add(page)
        if not found:
            r.update(w=0, h=0)
            continue
        w, h = found[2] - found[0], found[3] - found[1]
        if w > 255 or h > 255:
            raise ValueError("A glyph is larger than 255 pixels")
        if w > r["w"] or h > r["h"]:
            x, y = _free_box(taken[page], planes[page].width, planes[page].height, w, h)
            for row in range(y, y + h + 1):
                taken[page][row][x:x + w + 1] = b"\x01" * (w + 1)
            r.update(x=x, y=y)
        planes[page].paste(glyph.crop(found), (r["x"], r["y"]))
        r.update(w=w, h=h, ox=found[0] - pad_x, oy=found[1] - pad_y)
        if not (-128 <= r["ox"] < 128 and -128 <= r["oy"] < 128):
            raise ValueError("A glyph box lies too far from the pen")
    for code, r in records.items():
        advance = widths.get(code, r["advance"])
        if not 0 <= advance < 256:
            raise ValueError(f"Advance of code {code:#04x} must be 0..255")
        struct.pack_into(">BBbbBBB", out, r["at"], advance, r["line"], r["ox"], r["oy"], r["w"], r["h"], r["page"])
        out[r["at"] + 7:r["at"] + 10] = (r["x"] << 12 | r["y"]).to_bytes(3, "big")
    for page in sorted(dirty):
        at = font["pages"][page]
        rgba = images[page].copy()
        rgba.paste(grey_sheet(planes[page]), (0, 0))
        blob = tpl.write(bytes(out[at:]), {0: rgba}, {})
        out[at:at + len(blob)] = blob
    return bytes(out)
