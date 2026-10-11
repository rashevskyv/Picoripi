"""Next Level Games 3DS fonts (Luigi's Mansion: Dark Moon): a bundle file (``core.texture_formats.nlg_tex``) whose
table member holds, after the ``Powe`` texture entries, one or more font records.

A record is an 8-byte header (``f6bc2700`` and a slot hash), a text file ``NLG Font Description File`` that ends
in ``END`` and CR LF, spaces up to a multiple of 4, and one u32 texture id per page (the last bytes of the record).
The text lists ``PageSize``, ``PageCount``, ``RenderHeight`` and one line per glyph::

    Glyph <character or decimal code point> Width <advance> <cell width> [<offset>]

The atlas pages (256 x 256, ETC1A4) are filled in the order of the glyph lines: each glyph occupies a cell
``<cell width>`` wide and ``RenderHeight`` high, left to right, a new row when the next cell does not fit, a new page
when the rows are used up. A bundle can hold several fonts (the English one has two, the Japanese three) and the same
font twice (two slots with the same text and pages); ``params.record`` picks one of the distinct fonts.

The model has one cell per glyph in a 16-column grid (the glyph's ink at the cell's top-left); packing writes back
the cells that changed into the pages (mip levels made again) and the advance / offset numbers of the glyph lines when
the new text still fits into the old one (spaces fill what is saved). New glyphs cannot be added: the pages are full.

The Switch version (Luigi's Mansion 2 HD) has the same records in the bundle member that also holds its DXT5 pages
(1024 x 1024; ``NLGH`` bundle, see ``nlg_tex``). There the last record is followed by other data, so its end is
found by the page ids it lists, and a glyph line has its place on the page:
``Glyph <c> Width <advance> <cell width> <offset> <x0> <y0> <x1> <y1> <page>`` (the picture is drawn at four times
the size, so the rectangles are larger than the cell width). The model's cell then is the largest rectangle.
"""
from __future__ import annotations

import re
from typing import Any, Dict, List, Tuple

from PIL import Image

from core.font_formats import Metadata, Sheets, char_code, map_entries
from core.texture_formats import nlg_tex

COLUMNS = 16
_GLYPH = re.compile(r"Glyph (\S+) Width (-?\d+) (-?\d+)(?: (-?\d+))?((?: -?\d+){0,5})$")
_TITLE = b"NLG Font Description File"


def _end_by_ids(table: bytes, start: int, pages: int, known: set) -> int:
    """End of a record: just past the first run of ``pages`` u32 that are all known texture ids (-1: none found)."""
    at = table.index(b"END", start) + 3
    limit = min(len(table) - 4 * pages, at + 0x400)
    while at <= limit:
        if all(int.from_bytes(table[at + 4 * i:at + 4 * i + 4], "little") in known for i in range(pages)):
            return at + 4 * pages
        at += 1
    return -1


def _records(table: bytes) -> List[Dict[str, Any]]:
    """Every font record of the table member: text span, header values, glyphs, page ids."""
    known = {e["id"] for e in nlg_tex.entries(table)}
    found = []
    starts = []
    at = 0
    while True:
        at = table.find(_TITLE, at)
        if at < 0:
            break
        starts.append(at)
        at += len(_TITLE)
    for n, start in enumerate(starts):
        end = table.index(b"END", start) + 3
        stop = end
        while stop < len(table) and table[stop] in (0x0D, 0x0A, 0x20):
            stop += 1
        text = table[start:end].decode("latin-1").replace("\r\n", "\n")
        head, glyphs = [], []
        for line in text.split("\n"):
            match = _GLYPH.match(line)
            if match:
                token = match.group(1)
                code = int(token) if len(token) > 1 and token.isdigit() else ord(token)
                tail = [int(v) for v in match.group(5).split()]
                glyphs.append({"code": code, "token": token, "advance": int(match.group(2)),
                               "cell": int(match.group(3)), "offset": int(match.group(4) or 0),
                               "has_offset": match.group(4) is not None,
                               "rect": tuple(tail[:4]) if len(tail) == 5 else None,
                               "page": tail[4] if len(tail) == 5 else None})
            else:
                head.append(line)
        pages = int(re.search(r"PageCount (\d+)", text).group(1))
        record_end = _end_by_ids(table, start, pages, known)
        if record_end >= 0:                  # the ids are the last bytes of the record; the text ends before them
            stop = min(stop, record_end - 4 * pages)
        elif n + 1 < len(starts):
            record_end = starts[n + 1] - 8
        else:
            record_end = len(table)
        size = int(re.search(r"PageSize (\d+)", text).group(1))
        height = int(re.search(r"RenderHeight (\d+)", text).group(1))
        ascent = int(re.search(r"Ascent (\d+)", text).group(1))
        ids = [int.from_bytes(table[record_end - 4 * (pages - i):record_end - 4 * (pages - i) + 4], "little")
               for i in range(pages)]
        found.append({"start": start, "end": end, "stop": stop, "glyphs": glyphs, "page_size": size, "height": height,
                      "ascent": ascent, "ids": ids, "text": text})
    return found


def _distinct(records: List[Dict[str, Any]]) -> List[List[int]]:
    """Record numbers grouped by (text, pages): the slots that are the same font."""
    groups: Dict[Tuple[str, Tuple[int, ...]], List[int]] = {}
    for i, r in enumerate(records):
        groups.setdefault((r["text"], tuple(r["ids"])), []).append(i)
    return list(groups.values())


def _cells(record: Dict[str, Any]) -> List[Tuple[int, int, int]]:
    """``(page, x, y)`` of every glyph cell, by the packing order of the description."""
    size, height = record["page_size"], record["height"]
    page = x = y = 0
    out = []
    for glyph in record["glyphs"]:
        if glyph["rect"]:
            out.append((glyph["page"], glyph["rect"][0], glyph["rect"][1]))
            continue
        if x + glyph["cell"] > size:
            x, y = 0, y + height
        if y + height > size:
            page, x, y = page + 1, 0, 0
        out.append((page, x, y))
        x += glyph["cell"]
    return out


def _context(data: bytes, params: Dict[str, Any]):
    table, pixel_member = nlg_tex.split(data)
    records = _records(table)
    if not records:
        raise ValueError("No font description in this bundle")
    groups = _distinct(records)
    index = int(params.get("record", 0))
    if index >= len(groups):
        raise ValueError(f"The bundle has {len(groups)} fonts; record {index} was asked")
    textures = {e["id"]: e for e in nlg_tex.entries(table)}
    return table, pixel_member, records, groups[index], textures


def _page_images(record: Dict[str, Any], textures: Dict[int, Dict[str, Any]], pixel_member: bytes):
    return [nlg_tex.read_texture(textures[tid], pixel_member) for tid in record["ids"]]


def _cell_box(cell: Tuple[int, int, int], glyph: Dict[str, Any], height: int) -> Tuple[int, int, int, int]:
    _page, x, y = cell
    if glyph["rect"]:
        return glyph["rect"]
    return (x, y, x + glyph["cell"], y + height)


def _cell_size(record: Dict[str, Any]) -> Tuple[int, int]:
    """Width and height of one cell of the model: the largest glyph box."""
    glyphs, height = record["glyphs"], record["height"]
    boxes = [(g["rect"][2] - g["rect"][0], g["rect"][3] - g["rect"][1]) if g["rect"] else (g["cell"], height)
             for g in glyphs]
    return max([b[0] for b in boxes] + [1]), max([b[1] for b in boxes] + [1])


def extract(data: bytes, params: Dict[str, Any]) -> Tuple[Metadata, Sheets]:
    table, pixel_member, records, group, textures = _context(data, params)
    record = records[group[0]]
    pages = _page_images(record, textures, pixel_member)
    cells = _cells(record)
    glyphs = record["glyphs"]
    cell_w, height = _cell_size(record)
    rows = max(1, -(-len(glyphs) // COLUMNS))
    sheet = Image.new("RGBA", (COLUMNS * cell_w, rows * height))
    packets = []
    for i, (glyph, cell) in enumerate(zip(glyphs, cells)):
        if cell[0] < len(pages):
            piece = pages[cell[0]].crop(_cell_box(cell, glyph, record["height"]))
            sheet.paste(piece, ((i % COLUMNS) * cell_w, (i // COLUMNS) * height))
        packets.append({"kerning": -glyph["offset"], "width": glyph["advance"]})
    space = next((p["width"] for g, p in zip(glyphs, packets) if g["code"] == 32), cell_w // 2)
    metadata = {
        "header": {"signature": "NLGF", "num_chunks": 4},
        "INF1": [{"encoding": 1, "ascent": record["ascent"], "descent": max(0, height - record["ascent"]),
                  "width": space, "leading": height, "fallback_code": 0x3F, "unk1": 0}],
        "GLY1": [{"start_glyph": 0, "end_glyph": rows * COLUMNS - 1, "cell_width": cell_w, "cell_height": height,
                  "glyph_horizontal_count": COLUMNS, "glyph_vertical_count": rows,
                  "texture_width": sheet.width, "texture_height": sheet.height}],
        "MAP1": [map_entries([(char_code(chr(g["code"])), i) for i, g in enumerate(glyphs)])],
        "WID1": [{"first_code_included": 0, "last_code_included": len(glyphs), "packets": packets}],
    }
    return metadata, [sheet]


def _description(record: Dict[str, Any], widths: List[Dict[str, int]]) -> str:
    """The text of the record with the glyph lines' advance and offset numbers replaced."""
    lines, n = [], 0
    for line in record["text"].split("\n"):
        match = _GLYPH.match(line)
        if match and n < len(widths):
            glyph = record["glyphs"][n]
            advance, offset = int(widths[n]["width"]), -int(widths[n]["kerning"])
            tail = f" {offset}" if glyph["has_offset"] or offset else ""
            if glyph["rect"]:
                tail += " " + " ".join(str(v) for v in (*glyph["rect"], glyph["page"]))
            line = f"Glyph {glyph['token']} Width {advance} {glyph['cell']}{tail}"
            n += 1
        lines.append(line)
    return "\r\n".join(lines)


def pack(metadata: Metadata, sheets: Sheets, original: bytes, params: Dict[str, Any]) -> bytes:
    table, pixel_member, records, group, textures = _context(original, params)
    record = records[group[0]]
    pages = _page_images(record, textures, pixel_member)
    cells = _cells(record)
    glyphs = record["glyphs"]
    cell_w, height = _cell_size(record)
    out = bytearray(pixel_member)
    edited = [p.copy() for p in pages]
    touched = set()
    if sheets:
        sheet = sheets[0].convert("RGBA")
        for i, (glyph, cell) in enumerate(zip(glyphs, cells)):
            if cell[0] >= len(pages):
                continue
            x, y = (i % COLUMNS) * cell_w, (i // COLUMNS) * height
            box = _cell_box(cell, glyph, record["height"])
            gw, gh = box[2] - box[0], box[3] - box[1]
            if y + height > sheet.height or x + cell_w > sheet.width:
                continue
            piece = sheet.crop((x, y, x + gw, y + gh))
            if piece.tobytes() != pages[cell[0]].crop(box).tobytes():
                edited[cell[0]].paste(piece, box[:2])
                touched.add(cell[0])
    for page in touched:
        nlg_tex.write_texture(out, textures[record["ids"][page]], edited[page])
    new_table = bytearray(table)
    packets = (metadata.get("WID1") or [{}])[0].get("packets") or []
    if len(packets) >= len(glyphs):
        current = [{"kerning": -g["offset"], "width": g["advance"]} for g in glyphs]
        wanted = [{"kerning": int(p["kerning"]), "width": int(p["width"])} for p in packets[:len(glyphs)]]
        if wanted != current:
            for number in group:
                r = records[number]
                text = _description(r, wanted).encode("latin-1")
                span = r["stop"] - r["start"]
                body = text + b"\r\n"
                if len(body) > span:
                    raise ValueError("the new glyph widths do not fit into the font description of the game "
                                     f"({len(body)} bytes against {span})")
                new_table[r["start"]:r["stop"]] = body + b" " * (span - len(body))
    if nlg_tex.is_hd(original):          # the descriptions and the pixels are one member
        merged = bytearray(out)
        for r in {records[number]["start"]: records[number] for number in group}.values():
            merged[r["start"]:r["stop"]] = new_table[r["start"]:r["stop"]]
        if bytes(merged) == pixel_member:
            return bytes(original)
        return nlg_tex.join_hd(bytes(merged))
    if not touched and bytes(new_table) == table:
        return bytes(original)
    return nlg_tex.join(bytes(new_table), bytes(out))
