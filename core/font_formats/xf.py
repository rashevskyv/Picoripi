"""Level-5 XF fonts (``.xf``; Yo-kai Watch, Time Travelers and other Level-5 3DS games).

An XF file is an XPCK pack (``core.containers.level5``) of a texture (``000.xi``, IMGC) and ``FNT.bin``
(Kuriimu2 ``Xf.cs``): an ``FNTC01`` header (0x28 bytes: large and small line heights, the index of the
fallback character, then offset / 4 and count of three Level-5-compressed tables), the glyph size table
(signed x and y offset from the pen and the top of the line, width, height of the glyph's box), the large
character table and the (empty) small one. A character record, sorted by code point: u16 UTF-16 code,
u16 ``advance << 10 | size index``, u32 ``y << 18 | x << 4 | channel`` -- the glyph is the box at (x, y) of
one colour channel of the texture (R, G or B; the fonts hold three layers of glyphs in one RGBA5551 image).

The model shows one cell per character, 64 to a row, with ``SPARE_CELLS`` empty ones after them; a cell is
the glyph's channel as grey ink, drawn ``PAD`` pixels right of the pen (``kerning`` = ``PAD``). Packing an
unedited model gives the original bytes. An edited glyph that still fits its box is redrawn in place; a
bigger or new one goes into free room of the texture (any channel, searched from the bottom), and a typed
character in an empty cell becomes a new record (``ADDS_GLYPHS``).
"""
from __future__ import annotations

import struct
from typing import Any, Dict, List, Tuple

from PIL import Image

from core.containers import level5
from core.font_formats import Metadata, Sheets, char_code, char_map, coverage, grey_sheet, map_entries
from core.texture_formats import imgc

ADDS_GLYPHS = True
COLUMNS = 64
SPARE_CELLS = 64
PAD = 2              # the fonts draw some glyphs up to 2 pixels left of the pen
HEADER = 0x28


def is_xf(data: bytes) -> bool:
    """An XPCK pack that holds an ``FNTC`` table."""
    try:
        return any(blob[:4] == b"FNTC" for blob in level5.Xpck(data).files.values())
    except (ValueError, IndexError, UnicodeDecodeError):
        return False


def _members(pack: level5.Xpck) -> Tuple[str, str]:
    texture = next((n for n in pack.files if n.lower().endswith(".xi")), None)
    table = next((n for n in pack.files if n.lower().endswith(".bin")), None)
    if texture is None or table is None:
        raise ValueError("XF font without a texture or FNT.bin")
    return texture, table


def _parse(data: bytes) -> Dict[str, Any]:
    pack = level5.Xpck(data)
    texture_name, table_name = _members(pack)
    fnt = pack.files[table_name]
    if fnt[:4] != b"FNTC":
        raise ValueError("XF font table is not FNTC")
    head = struct.unpack_from("<8sihhhhq6h", fnt, 0)
    _magic, _version, large_h, _small_h, escape, _se, _z, size_off, size_n, large_off, large_n, small_off, _sn = head
    sizes_blob = fnt[size_off << 2:large_off << 2]
    large_blob = fnt[large_off << 2:small_off << 2]
    sizes_raw = level5.decompress(sizes_blob)
    large_raw = level5.decompress(large_blob)
    sizes = [struct.unpack_from("<bbBB", sizes_raw, i * 4) for i in range(size_n)]
    chars = []
    for i in range(large_n):
        code, info, image = struct.unpack_from("<HHI", large_raw, i * 8)
        chars.append({"code": code, "advance": info >> 10, "size": info & 0x3FF,
                      "x": (image >> 4) & 0x3FFF, "y": image >> 18, "channel": image & 0xF})
    return {"pack": pack, "texture": texture_name, "table": table_name, "fnt": fnt, "height": large_h,
            "escape": escape, "sizes": sizes, "chars": chars, "small": fnt[small_off << 2:],
            "methods": (level5.method_of(sizes_blob), level5.method_of(large_blob))}


def _cell_size(font: Dict[str, Any]) -> Tuple[int, int]:
    width = max(PAD + ox + w for ox, _oy, w, _h in font["sizes"])
    height = max([oy + h for _ox, oy, _w, h in font["sizes"]] + [font["height"]])
    return width, height


def _cells(font: Dict[str, Any], atlas: Image.Image) -> List[Image.Image]:
    cw, ch = _cell_size(font)
    planes = atlas.split()[:3]
    cells = []
    for char in font["chars"]:
        ox, oy, w, h = font["sizes"][char["size"]]
        ink = Image.new("L", (cw, ch))
        if w and h and char["channel"] < 3:
            ink.paste(planes[char["channel"]].crop((char["x"], char["y"], char["x"] + w, char["y"] + h)),
                      (PAD + ox, oy))
        cells.append(ink)
    return cells


def extract(data: bytes, params: Dict[str, Any]) -> Tuple[Metadata, Sheets]:
    font = _parse(data)
    atlas = imgc.decode(font["pack"].files[font["texture"]])
    cw, ch = _cell_size(font)
    cells = _cells(font, atlas)
    capacity = -(-(len(cells) + SPARE_CELLS) // COLUMNS) * COLUMNS
    rows = capacity // COLUMNS
    ink = Image.new("L", (COLUMNS * cw, rows * ch))
    for index, cell in enumerate(cells):
        ink.paste(cell, ((index % COLUMNS) * cw, (index // COLUMNS) * ch))
    packets = [{"kerning": PAD, "width": c["advance"]} for c in font["chars"]]
    packets += [{"kerning": PAD, "width": 0} for _ in range(capacity - len(packets))]
    space = next((c["advance"] for c in font["chars"] if c["code"] == 0x20), cw // 2)
    capital = next((c for c in font["chars"] if c["code"] == ord("H")), None)
    ascent = font["sizes"][capital["size"]][1] + font["sizes"][capital["size"]][3] if capital else ch * 3 // 4
    fallback = font["chars"][font["escape"]]["code"] if 0 <= font["escape"] < len(font["chars"]) else 0x3F
    metadata = {
        "header": {"signature": "FNTC01", "num_chunks": 3},
        "INF1": [{"encoding": 1, "ascent": ascent, "descent": ch - ascent, "width": space, "leading": font["height"],
                  "fallback_code": fallback, "unk1": 0}],
        "GLY1": [{"start_glyph": 0, "end_glyph": capacity - 1, "cell_width": cw, "cell_height": ch,
                  "page_data_size": 0, "texture_format": 0, "glyph_horizontal_count": COLUMNS,
                  "glyph_vertical_count": rows, "texture_width": ink.width, "texture_height": ink.height}],
        "MAP1": [map_entries([(char_code(chr(c["code"])), index) for index, c in enumerate(font["chars"])])],
        "WID1": [{"first_code_included": 0, "last_code_included": capacity, "packets": packets}],
    }
    return metadata, [grey_sheet(ink)]


# -- packing ----------------------------------------------------------------------------------


class _Atlas:
    """Free room in the three glyph layers of the texture: one byte per pixel, 1 where a glyph's box lies."""

    def __init__(self, size: Tuple[int, int], boxes: List[Tuple[int, int, int, int, int]]):
        self.width, self.height = size
        self.taken = [bytearray(self.width * self.height) for _ in range(3)]
        for x, y, w, h, channel in boxes:
            if w and h and channel < 3:
                self.take(channel, x, y, w, h)

    def take(self, channel: int, x: int, y: int, w: int, h: int) -> None:
        for row in range(y, min(y + h, self.height)):
            self.taken[channel][row * self.width + x:row * self.width + x + w] = b"" * w

    def grow(self, height: int) -> None:
        for taken in self.taken:
            taken.extend(bytes(self.width * (height - self.height)))
        self.height = height

    def place(self, w: int, h: int) -> Tuple[int, int, int]:
        """``(x, y, channel)`` of a free ``w`` x ``h`` box with a free column and row after it (as the game's
        own glyphs have), searched from the bottom of the layers B, G, R."""
        W = self.width
        for channel in (2, 1, 0):
            taken = self.taken[channel]
            for y in range(self.height - h, -1, -1):
                x = 0
                while x + w <= W:
                    right = min(x + w + 1, W)
                    blocker = max((taken.rfind(1, row * W + x, row * W + right) - row * W
                                   for row in range(y, min(y + h + 1, self.height))), default=-1)
                    if blocker < x:
                        self.take(channel, x, y, w, h)
                        return x, y, channel
                    x = blocker + 1
        raise ValueError(f"No free room for a {w}x{h} glyph in the font texture")


def pack(metadata: Metadata, sheets: Sheets, original: bytes, params: Dict[str, Any]) -> bytes:
    font = _parse(original)
    old_meta, old_sheets = extract(original, params)
    gly = metadata["GLY1"][0]
    cw, ch, cols = gly["cell_width"], gly["cell_height"], gly["glyph_horizontal_count"]
    if (cw, ch, cols) != (old_meta["GLY1"][0]["cell_width"], old_meta["GLY1"][0]["cell_height"], COLUMNS):
        raise ValueError("The font's cell grid changed; it cannot be written back")
    packets = metadata["WID1"][0]["packets"]
    new_ink, old_ink = coverage(sheets[0]), coverage(old_sheets[0])

    def box(glyph: int) -> Tuple[int, int, int, int]:
        x, y = (glyph % cols) * cw, (glyph // cols) * ch
        return x, y, x + cw, y + ch

    chars = font["chars"]
    new_map = char_map(metadata)
    old_map = char_map(old_meta)
    glyphs = sorted(set(new_map.values()))
    changed = {g for g in glyphs if g >= len(chars) or new_ink.crop(box(g)).tobytes() != old_ink.crop(box(g)).tobytes()}
    width_of = {g: int(packets[g]["width"]) if g < len(packets) else 0 for g in glyphs}
    if not changed and new_map == old_map and all(width_of[g] == chars[g]["advance"] for g in glyphs if g < len(chars)):
        return bytes(original)

    pack_ = font["pack"]
    xi = pack_.files[font["texture"]]
    atlas = imgc.decode(xi)
    planes = list(atlas.split())
    bits = {"RGBA8": 8, "RGB8": 8, "RGBA4": 4}.get(imgc.read(xi, {})[0].pixel_format, 5)
    sizes = list(font["sizes"])
    in_use = {g for g in glyphs if g < len(chars)}     # boxes of edited glyphs stay taken: they may be redrawn in place
    room = _Atlas(atlas.size, [(chars[g]["x"], chars[g]["y"], sizes[chars[g]["size"]][2], sizes[chars[g]["size"]][3],
                                chars[g]["channel"]) for g in in_use])
    shared: Dict[bytes, Tuple[int, int, int]] = {}     # identical glyphs share one box, as the game's own do
    kept = set()                                       # boxes an unedited glyph still draws from: never redrawn
    for g in in_use - changed:
        c = chars[g]
        _ox, _oy, w, h = sizes[c["size"]]
        if w and h and c["channel"] < 3:
            ink = planes[c["channel"]].crop((c["x"], c["y"], c["x"] + w, c["y"] + h))
            shared.setdefault(bytes((w, h)) + ink.tobytes(), (c["x"], c["y"], c["channel"]))
            kept.add((c["x"], c["y"], c["channel"]))
    placed: Dict[int, Dict[str, int]] = {}
    for g in sorted(changed):
        ink = new_ink.crop(box(g))
        found = ink.point(lambda v: 255 if v else 0).getbbox()
        if not found:
            placed[g] = {"size": _size_index(sizes, (0, 0, 0, 0)), "x": 0, "y": 0, "channel": 0}
            continue
        w, h = found[2] - found[0], found[3] - found[1]
        if w > 255 or h > 255:
            raise ValueError("A glyph is larger than 255 pixels")
        old = chars[g] if g < len(chars) else None
        old_w, old_h = (sizes[old["size"]][2], sizes[old["size"]][3]) if old else (0, 0)
        stored = _stored_ink(ink.crop(found), bits)
        key = bytes((w, h)) + stored.tobytes()
        if key in shared:
            x, y, channel = shared[key]
            placed[g] = {"size": _size_index(sizes, (found[0] - PAD, found[1], w, h)), "x": x, "y": y,
                         "channel": channel}
            continue
        if (old and old["channel"] < 3 and w <= old_w and h <= old_h
                and (old["x"], old["y"], old["channel"]) not in kept):
            x, y, channel = old["x"], old["y"], old["channel"]
            planes[channel].paste(0, (x, y, x + old_w, y + old_h))
        else:
            x, y, channel = _place(room, planes, w, h)
        planes[channel].paste(stored, (x, y))
        shared[key] = (x, y, channel)
        kept.add((x, y, channel))
        placed[g] = {"size": _size_index(sizes, (found[0] - PAD, found[1], w, h)), "x": x, "y": y, "channel": channel}

    records = []
    for char, g in new_map.items():
        code = ord(char)
        if code > 0xFFFF:
            raise ValueError("XF fonts map 16-bit characters only")
        if g in placed:
            rec = dict(placed[g])
        elif g < len(chars):
            rec = {k: chars[g][k] for k in ("size", "x", "y", "channel")}
        else:
            continue                                                  # an empty spare cell
        advance = width_of[g]
        if not 0 <= advance < 64:
            raise ValueError(f"Advance of {char!r} must be 0..63")
        records.append((code, advance << 10 | rec["size"], rec["y"] << 18 | rec["x"] << 4 | rec["channel"]))
    records.sort()
    codes = [r[0] for r in records]
    fallback = chars[font["escape"]]["code"] if 0 <= font["escape"] < len(chars) else 0x3F
    escape = codes.index(fallback) if fallback in codes else 0

    new_xi = imgc.encode(xi, Image.merge("RGBA", planes), taller=True)
    pack_.files[font["texture"]] = new_xi
    pack_.files[font["table"]] = _fnt(font, sizes, records, escape)
    return pack_.build()


def _place(room: _Atlas, planes: List[Image.Image], w: int, h: int) -> Tuple[int, int, int]:
    """A free box; when the texture is full it grows by rows, up to the power of two the GPU pads it to anyway."""
    limit = 1 << (room.height - 1).bit_length()
    while True:
        try:
            return room.place(w, h)
        except ValueError:
            if room.height >= limit:
                raise
            room.grow(min(limit, room.height + max(8, h + 1)))
            for index, plane in enumerate(planes):
                taller = Image.new("L", (plane.width, room.height), 255 if index == 3 else 0)
                taller.paste(plane, (0, 0))
                planes[index] = taller


def _stored_ink(ink: Image.Image, bits: int) -> Image.Image:
    """Ink as the texture keeps it (``bits`` per channel, widened again), so equal glyphs compare equal."""
    from core.texture_formats.pixels import _expand, _quant
    return ink.point([_expand(_quant(v, bits), bits) for v in range(256)])


def _size_index(sizes: List[Tuple[int, int, int, int]], entry: Tuple[int, int, int, int]) -> int:
    if entry not in sizes:
        if len(sizes) >= 1024:
            raise ValueError("The font's glyph size table is full (1024)")
        sizes.append(entry)
    return sizes.index(entry)


def _table(raw: bytes, method: int) -> bytes:
    blob = level5.compress(raw, level5.STORED if method == level5.STORED else level5.LZ10)
    return blob + b"\0" * (-len(blob) % 4)


def _fnt(font: Dict[str, Any], sizes, records, escape: int) -> bytes:
    sizes_blob = _table(b"".join(struct.pack("<bbBB", *s) for s in sizes), font["methods"][0])
    large_blob = _table(b"".join(struct.pack("<HHI", *r) for r in records), font["methods"][1])
    head = bytearray(font["fnt"][:HEADER])
    size_off = HEADER
    large_off = size_off + len(sizes_blob)
    small_off = large_off + len(large_blob)
    struct.pack_into("<h", head, 0x10, escape)
    struct.pack_into("<6h", head, 0x1C, size_off >> 2, len(sizes), large_off >> 2, len(records), small_off >> 2,
                     struct.unpack_from("<h", font["fnt"], 0x26)[0])
    return bytes(head) + sizes_blob + large_blob + font["small"]
