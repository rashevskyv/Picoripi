"""Level-5 G4 fonts (Switch: Yo-kai Watch 4++, Yo-kai Academy Y): a ``font.cfg.bin`` table + a ``font.g4tx`` texture.

The two files come as one blob (``sources.join_pair``; the plugin's font source names the texture as its
``companion``). The table is a Level-5 cfg.bin (``t2b``: entry name CRC32, parameter count, two type bits per
parameter, then one i32 per parameter; no strings here). Per font of the file: ``INF`` (font, ascent, glyph box
height, descent, character count, texture width, height, 0), ``CHR`` per character (font, Shift-JIS code or 63,
the UTF-8 bytes as one big-endian number, x, y, width, x offset from the pen, advance, channel), ``KERNINF``
(font, pair count) and its ``KERN`` pairs; ``END`` closes the table. ``CHR`` entries of a font are sorted by the
UTF-8 number (unsigned). The glyph is the box (x, y, width, box height) of one channel (R, G, B, A) of the
RGBA8 texture. A file holds a main font (0), a small furigana font (1) and sometimes a second style of both
(2, 3); ``params.font`` picks one (default 0).

The model is one cell per character, 64 to a row, with ``SPARE_CELLS`` empty ones after them; the ink is drawn
``PAD`` pixels right of the pen. Packing an unedited model gives the original bytes. An edited glyph that fits
its box is redrawn in place, a bigger or new one goes into free room of the texture (any channel), and a
character typed into an empty cell becomes a new ``CHR`` (``ADDS_GLYPHS``).
"""
from __future__ import annotations

import struct
from typing import Any, Dict, List, Tuple

from PIL import Image

from core.font_formats import Metadata, Sheets, char_code, char_map, coverage, grey_sheet, map_entries
from core.font_formats.sources import join_pair, split_pair
from core.font_formats.xf import _Atlas as Atlas      # free-room search over glyph layers, shared with XF
from core.texture_formats import g4tx

ADDS_GLYPHS = True
COLUMNS = 64
SPARE_CELLS = 64
INT, NO_SJIS = 1, 63


def _entries(raw: bytes) -> Tuple[List[Tuple[int, List[int], List[int]]], int]:
    """``[(name crc, types, values)]`` and where the entries end."""
    count = struct.unpack_from("<I", raw)[0]
    pos, out = 0x10, []
    for _ in range(count):
        crc, n = struct.unpack_from("<IB", raw, pos)
        types = [(raw[pos + 5 + i // 4] >> 2 * (i % 4)) & 3 for i in range(n)]
        at = (pos + 5 + (n + 3) // 4 + 3) & ~3
        out.append((crc, types, list(struct.unpack_from(f"<{n}i", raw, at))))
        pos = at + 4 * n
    return out, pos


def _entry_bytes(crc: int, types: List[int], values: List[int]) -> bytes:
    n = len(types)
    bits = bytearray((n + 3) // 4)
    for i, kind in enumerate(types):
        bits[i // 4] |= kind << 2 * (i % 4)
    head = struct.pack("<IB", crc, n) + bytes(bits)
    return head + b"\xff" * (-len(head) % 4) + struct.pack(f"<{n}i", *values)


def _names(raw: bytes) -> Dict[int, str]:
    """Entry name CRC32 -> name, from the key table after the (empty) string table."""
    s_off, s_len = struct.unpack_from("<II", raw, 4)
    at = (s_off + s_len + 15) & ~15
    _size, count, names_at, _names_len = struct.unpack_from("<4I", raw, at)
    out = {}
    for index in range(count):
        crc, name_at = struct.unpack_from("<Ii", raw, at + 16 + 8 * index)
        start = at + names_at + name_at
        out[crc] = raw[start:raw.index(b"\0", start)].decode("utf-8", "replace")
    return out


def _parse(data: bytes, params: Dict[str, Any]) -> Dict[str, Any]:
    table, texture = split_pair(data)
    entries, _end = _entries(table)
    names = _names(table)
    font = int(params.get("font", 0))
    kinds = [names.get(crc, "") for crc, _t, _v in entries]
    info = next((i for i, k in enumerate(kinds) if k == "INF" and entries[i][2][0] == font), None)
    if info is None:
        raise ValueError(f"G4 font table has no font {font}")
    chars = [i for i, k in enumerate(kinds) if k == "CHR" and entries[i][2][0] == font]
    if not chars or chars != list(range(chars[0], chars[0] + len(chars))):
        raise ValueError("G4 font characters are missing or not in one run")
    heights = {v[0]: v[2] for i, (_c, _t, v) in enumerate(entries) if kinds[i] == "INF"}
    textures = g4tx._textures(texture)
    if len(textures) != 1 or textures[0]["format"] != 0x25:
        raise ValueError("G4 font texture is not one RGBA8 image")
    _f, ascent, height, _descent, _count, _w, _h, _z = entries[info][2]
    records = [dict(zip(("font", "sjis", "utf8", "x", "y", "w", "ox", "advance", "channel"), entries[i][2]))
               for i in chars]
    return {"table": table, "texture": texture, "entries": entries, "info": info, "chars": chars,
            "records": records, "ascent": ascent, "height": height, "font": font, "heights": heights,
            "kinds": kinds}


def _char(record: Dict[str, int]) -> str:
    value = record["utf8"] & 0xFFFFFFFF
    raw = value.to_bytes(max(1, (value.bit_length() + 7) // 8), "big")
    try:
        return raw.decode("utf-8")
    except UnicodeDecodeError:
        return ""


def _pad(font: Dict[str, Any]) -> int:
    return max([0] + [-r["ox"] for r in font["records"]])


def _cell_size(font: Dict[str, Any]) -> Tuple[int, int]:
    pad = _pad(font)
    return max([1] + [pad + r["ox"] + r["w"] for r in font["records"]]), font["height"]


def _planes(texture: bytes) -> List[Image.Image]:
    return list(g4tx.read(texture, {})[0].image.split())


def extract(data: bytes, params: Dict[str, Any]) -> Tuple[Metadata, Sheets]:
    font = _parse(data, params)
    planes = _planes(font["texture"])
    pad = _pad(font)
    cw, ch = _cell_size(font)
    records = font["records"]
    capacity = -(-(len(records) + SPARE_CELLS) // COLUMNS) * COLUMNS
    rows = capacity // COLUMNS
    ink = Image.new("L", (COLUMNS * cw, rows * ch))
    for index, r in enumerate(records):
        if r["w"] > 0 and 0 <= r["channel"] < len(planes):
            glyph = planes[r["channel"]].crop((r["x"], r["y"], r["x"] + r["w"], r["y"] + ch))
            ink.paste(glyph, ((index % COLUMNS) * cw + pad + r["ox"], (index // COLUMNS) * ch))
    packets = [{"kerning": pad, "width": r["advance"]} for r in records]
    packets += [{"kerning": pad, "width": 0} for _ in range(capacity - len(packets))]
    space = next((r["advance"] for r in records if r["utf8"] == 0x20), cw // 2)
    codes = [(char_code(c), index) for index, c in ((i, _char(r)) for i, r in enumerate(records)) if c]
    metadata = {
        "header": {"signature": "G4FONT", "num_chunks": 1},
        "INF1": [{"encoding": 1, "ascent": font["ascent"], "descent": ch - font["ascent"], "width": space,
                  "leading": ch, "fallback_code": 0x3F, "unk1": 0}],
        "GLY1": [{"start_glyph": 0, "end_glyph": capacity - 1, "cell_width": cw, "cell_height": ch,
                  "page_data_size": 0, "texture_format": 0, "glyph_horizontal_count": COLUMNS,
                  "glyph_vertical_count": rows, "texture_width": ink.width, "texture_height": ink.height}],
        "MAP1": [map_entries(codes)],
        "WID1": [{"first_code_included": 0, "last_code_included": capacity, "packets": packets}],
    }
    return metadata, [grey_sheet(ink)]


def _sjis(char: str) -> int:
    try:
        raw = char.encode("shift-jis")
    except UnicodeEncodeError:
        return NO_SJIS
    return int.from_bytes(raw, "big")


def pack(metadata: Metadata, sheets: Sheets, original: bytes, params: Dict[str, Any]) -> bytes:
    font = _parse(original, params)
    old_meta, old_sheets = extract(original, params)
    gly = metadata["GLY1"][0]
    cw, ch, cols = gly["cell_width"], gly["cell_height"], gly["glyph_horizontal_count"]
    if (cw, ch, cols) != (old_meta["GLY1"][0]["cell_width"], old_meta["GLY1"][0]["cell_height"], COLUMNS):
        raise ValueError("The font's cell grid changed; it cannot be written back")
    pad = _pad(font)
    packets = metadata["WID1"][0]["packets"]
    new_ink, old_ink = coverage(sheets[0]), coverage(old_sheets[0])
    records = font["records"]

    def box(glyph: int) -> Tuple[int, int, int, int]:
        x, y = (glyph % cols) * cw, (glyph // cols) * ch
        return x, y, x + cw, y + ch

    new_map, old_map = char_map(metadata), char_map(old_meta)
    glyphs = sorted(set(new_map.values()))
    changed = {g for g in glyphs
               if g >= len(records) or new_ink.crop(box(g)).tobytes() != old_ink.crop(box(g)).tobytes()}
    width_of = {g: int(packets[g]["width"]) if g < len(packets) else 0 for g in glyphs}
    if not changed and new_map == old_map and all(width_of[g] == records[g]["advance"]
                                                  for g in glyphs if g < len(records)):
        return bytes(original)

    planes = _planes(font["texture"])
    layers = len(planes)
    every = [dict(zip(("font", "sjis", "utf8", "x", "y", "w", "ox", "advance", "channel"), v))
             for kind, (_crc, _t, v) in zip(font["kinds"], font["entries"]) if kind == "CHR"]
    keep = [r for r in every if r["font"] != font["font"]] + [records[g] for g in glyphs if g < len(records)]
    room = Atlas(planes[0].size, [(r["x"], r["y"], r["w"], font["heights"].get(r["font"], ch), r["channel"])
                                  for r in keep], layers)
    placed: Dict[int, Dict[str, int]] = {}
    for g in sorted(changed):
        ink = new_ink.crop(box(g))
        found = ink.point(lambda v: 255 if v else 0).getbbox()
        if not found:
            placed[g] = {"x": 0, "y": 0, "w": 1, "ox": 0, "channel": 0}
            continue
        left, right = found[0], found[2]
        w = right - left
        glyph = ink.crop((left, 0, right, ch))
        old = records[g] if g < len(records) else None
        if old and 0 <= old["channel"] < layers and w <= old["w"]:
            x, y, channel = old["x"], old["y"], old["channel"]
            planes[channel].paste(0, (x, y, x + old["w"], y + ch))
        else:
            x, y, channel = room.place(w, ch)
        planes[channel].paste(glyph, (x, y))
        placed[g] = {"x": x, "y": y, "w": w, "ox": left - pad, "channel": channel}

    rows = []
    for char, g in new_map.items():
        utf8 = int.from_bytes(char.encode("utf-8"), "big")
        if utf8 > 0xFFFFFFFF:
            raise ValueError(f"{char!r} is longer than 4 UTF-8 bytes")
        if g in placed:
            rec = placed[g]
        elif g < len(records):
            rec = records[g]
        else:
            continue                                               # an empty spare cell
        old = records[g] if g < len(records) else None
        sjis = old["sjis"] if old and old["utf8"] & 0xFFFFFFFF == utf8 else _sjis(char)
        rows.append([font["font"], sjis, struct.unpack("<i", struct.pack("<I", utf8))[0], rec["x"], rec["y"],
                     rec["w"], rec["ox"], width_of[g], rec["channel"]])
    rows.sort(key=lambda v: v[2] & 0xFFFFFFFF)

    entries = list(font["entries"])
    chr_crc, chr_types = entries[font["chars"][0]][0], entries[font["chars"][0]][1]
    first, last = font["chars"][0], font["chars"][-1] + 1
    entries[first:last] = [(chr_crc, chr_types, values) for values in rows]
    info = list(entries[font["info"]][2])
    info[4] += len(rows) - len(records)
    entries[font["info"]] = (entries[font["info"]][0], entries[font["info"]][1], info)
    table = font["table"]
    s_off, s_len = struct.unpack_from("<II", table, 4)
    body = bytearray(16) + b"".join(_entry_bytes(*e) for e in entries)
    start = (len(body) + 15) & ~15
    out = body + b"\xff" * (start - len(body))
    out += table[(s_off + s_len + 15) & ~15:]
    struct.pack_into("<4I", out, 0, len(entries), start, 0, 0)
    atlas = Image.merge("RGBA", planes)
    return join_pair(bytes(out), g4tx.write(font["texture"], {0: atlas}, {}))
