"""Nintendo DS bitmap fonts: NFTR (``RTFN``, NitroSDK ``NNSG2dFont``), e.g. Four Swords Anniversary Edition.

Layout (little endian): a 16-byte header (``RTFN``, BOM ``FF FE``, version, file size, header size, block
count) and the blocks ``FNIF`` (metrics, encoding and the +8 pointers to the first ``PLGC``, ``HDWC`` and
``PAMC``), ``PLGC`` (cell width and height, bytes per glyph, baseline, bits per pixel, then one bitmap per
glyph: rows of ``cell width`` pixels, the bits run on from row to row, most significant bit first), chains of
``HDWC`` (left, glyph width, advance per glyph, from a first to a last glyph) and ``PAMC`` (code -> glyph:
direct range, table or scan list; the same layout as the 3DS ``CWDH`` / ``CMAP`` of ``bcfnt``).

The model puts glyph ``i`` in cell ``i`` of one sheet (``params``: ``columns``, default 16, and ``spare``
empty cells after the glyphs for new characters, default 32). Packing an unedited model returns the original
bytes. Editing re-encodes the redrawn bitmaps and writes the widths; a character typed into a spare cell
adds a glyph: its bitmap goes at the end of ``PLGC``, its widths at the end of the ``HDWC`` that ends with the
last glyph, its code into the ``PAMC`` table or scan list that covers it (else a new scan list at the end of
the chain). The blocks behind a grown one move and every pointer follows. Changing or removing a code the file
already has is refused, as for the other fonts with a character map.
"""
from __future__ import annotations

import struct
from typing import Any, Dict, List, Tuple

from PIL import Image

from core.font_formats import Metadata, Sheets, char_map, char_code, coverage, grey_sheet, map_entries

ADDS_GLYPHS = True  # a character typed into a spare cell gets a new glyph, its widths and its PAMC code
_NO_GLYPH = 0xFFFF


def is_nftr(data: bytes) -> bool:
    return bytes(data[:6]) == b"RTFN\xff\xfe"


class Font:
    """The blocks of an NFTR file in file order, with the glyphs, widths and character maps decoded."""

    def __init__(self, data: bytes):
        data = bytes(data)
        if not is_nftr(data):
            raise ValueError("Not an NFTR font (RTFN)")
        self.version, _size, header_size, _count = struct.unpack_from("<HIHH", data, 6)
        self.header = data[:header_size]
        self.order: List[Tuple[str, int]] = []      # (kind, index in its list) in file order
        self.raw: List[bytes] = []                   # blocks of other kinds, kept as they are
        self.finf = b""
        self.widths: List[List[Any]] = []            # [first glyph, [(left, glyph width, advance), ...]]
        self.maps: List[List[Any]] = []              # [begin, end, method, payload]
        at, starts = header_size, {}
        while at + 8 <= len(data):
            magic, size = struct.unpack_from("<4sI", data, at)
            if size < 8 or at + size > len(data):
                raise ValueError(f"Broken NFTR block {magic!r} at 0x{at:X}")
            block = data[at:at + size]
            starts[at] = (magic, len(self.widths), len(self.maps))
            if magic == b"FNIF":
                self.finf = block
                self.order.append(("finf", 0))
            elif magic == b"PLGC":
                self._read_glyphs(block)
                self.order.append(("cglp", 0))
            elif magic == b"HDWC":
                first, last = struct.unpack_from("<HH", block, 8)
                entries = [struct.unpack_from("bBB", block, 16 + 3 * i) for i in range(last - first + 1)]
                self.widths.append([first, entries])
                self.order.append(("cwdh", len(self.widths) - 1))
            elif magic == b"PAMC":
                self.maps.append(self._read_map(block))
                self.order.append(("cmap", len(self.maps) - 1))
            else:
                self.raw.append(block)
                self.order.append(("raw", len(self.raw) - 1))
            at += size
        if not self.finf or not hasattr(self, "glyphs"):
            raise ValueError("NFTR font without FNIF or PLGC")
        # The chains as the pointers link them (the file order is kept when writing).
        self.width_chain = self._chain(data, 0x14, 12, b"HDWC", starts, 1)
        self.map_chain = self._chain(data, 0x18, 16, b"PAMC", starts, 2)

    def _chain(self, data: bytes, finf_field: int, next_field: int, magic: bytes, starts, slot: int) -> List[int]:
        finf_at = next(at for at, (m, _w, _c) in starts.items() if m == b"FNIF")
        pointer, chain = struct.unpack_from("<I", data, finf_at + finf_field)[0], []
        while pointer and (pointer - 8) in starts and starts[pointer - 8][0] == magic and len(chain) < 4096:
            chain.append(starts[pointer - 8][slot])
            pointer = struct.unpack_from("<I", data, pointer - 8 + next_field)[0]
        return chain

    def _read_glyphs(self, block: bytes) -> None:
        (self.cell_width, self.cell_height, self.glyph_size, self.baseline, self.max_width, self.bpp,
         self.flags) = struct.unpack_from("<BBHbBBB", block, 8)
        if self.bpp not in (1, 2, 4, 8) or not self.glyph_size:
            raise ValueError(f"NFTR glyphs of {self.bpp} bits per pixel are not supported")
        count = (len(block) - 16) // self.glyph_size
        while count and 16 + (count - 1) * self.glyph_size + 3 >= len(block):   # the block's padding, not a glyph
            count -= 1
        self.glyphs = [block[16 + i * self.glyph_size:16 + (i + 1) * self.glyph_size] for i in range(count)]

    @staticmethod
    def _read_map(block: bytes) -> List[Any]:
        begin, end, method = struct.unpack_from("<HHI", block, 8)
        if method == 0:
            payload: Any = struct.unpack_from("<H", block, 20)[0]
        elif method == 1:
            payload = list(struct.unpack_from(f"<{end - begin + 1}H", block, 20))
        elif method == 2:
            count = struct.unpack_from("<H", block, 20)[0]
            payload = [struct.unpack_from("<HH", block, 22 + 4 * i) for i in range(count)]
        else:
            raise ValueError(f"Unknown NFTR PAMC method {method}")
        return [begin, end, method, payload]

    # -- reading ---------------------------------------------------------------------------------

    def codes(self) -> Dict[int, int]:
        """``{code: glyph}`` of every PAMC block (the first block that maps a code wins)."""
        result: Dict[int, int] = {}
        for index in self.map_chain or range(len(self.maps)):
            begin, end, method, payload = self.maps[index]
            if method == 0:
                pairs = [(code, code - begin + payload) for code in range(begin, end + 1)]
            elif method == 1:
                pairs = [(begin + i, glyph) for i, glyph in enumerate(payload)]
            else:
                pairs = list(payload)
            for code, glyph in pairs:
                if glyph != _NO_GLYPH:
                    result.setdefault(code, glyph)
        return result

    def width_entries(self) -> Dict[int, Tuple[int, int, int]]:
        result: Dict[int, Tuple[int, int, int]] = {}
        for first, entries in self.widths:
            for offset, entry in enumerate(entries):
                result.setdefault(first + offset, entry)
        return result

    @property
    def cp1252(self) -> bool:
        """FNIF encoding 3: the codes are Windows-1252 bytes (0x80-0x9F are typographic marks, not C1 controls)."""
        return len(self.finf) > 15 and self.finf[15] == 3

    def to_char(self, code: int) -> str:
        if self.cp1252 and code < 256:
            try:
                return bytes([code]).decode("cp1252")
            except UnicodeDecodeError:
                pass
        return chr(code)

    def to_code(self, char: str) -> int:
        if self.cp1252:
            try:
                encoded = char.encode("cp1252")
                if len(encoded) == 1:
                    return encoded[0]
            except UnicodeEncodeError:
                pass
        return ord(char)

    def defaults(self) -> Tuple[int, int, int]:
        """FNIF's ``(left, glyph width, advance)`` for glyphs without an HDWC entry."""
        return struct.unpack_from("bBB", self.finf, 12)

    def decode(self, glyph: bytes) -> Image.Image:
        """The ink of one glyph bitmap (grey levels scaled to 0..255)."""
        bits, width, height = self.bpp, self.cell_width, self.cell_height
        top = (1 << bits) - 1
        number = int.from_bytes(glyph, "big")
        total = len(glyph) * 8
        pixels = bytearray(width * height)
        for index in range(width * height):
            shift = total - (index + 1) * bits
            if shift < 0:
                break
            pixels[index] = ((number >> shift) & top) * 255 // top
        return Image.frombytes("L", (width, height), bytes(pixels))

    def encode(self, ink: Image.Image) -> bytes:
        """A glyph bitmap of a cell of ink (the inverse of ``decode``)."""
        bits, top = self.bpp, (1 << self.bpp) - 1
        number = 0
        for value in ink.tobytes():
            number = number << bits | (value * top + 127) // 255
        total = self.glyph_size * 8
        used = self.cell_width * self.cell_height * bits
        return (number << (total - used)).to_bytes(self.glyph_size, "big")

    # -- writing ---------------------------------------------------------------------------------

    def build(self) -> bytes:
        """The file of the blocks as they are now, in file order, with every offset and pointer computed."""
        pieces: List[bytes] = []
        at = len(self.header)
        starts: Dict[Tuple[str, int], int] = {}
        for kind, index in self.order:
            block = self._block(kind, index)
            starts[(kind, index)] = at
            pieces.append(block)
            at += len(block)
        out = bytearray(self.header + b"".join(pieces))
        finf = starts[("finf", 0)]
        struct.pack_into("<I", out, finf + 0x10, starts[("cglp", 0)] + 8)
        for chain, kind, field, next_field in ((self.width_chain, "cwdh", 0x14, 12),
                                               (self.map_chain, "cmap", 0x18, 16)):
            struct.pack_into("<I", out, finf + field, starts[(kind, chain[0])] + 8 if chain else 0)
            for current, following in zip(chain, chain[1:] + [None]):
                pointer = starts[(kind, following)] + 8 if following is not None else 0
                struct.pack_into("<I", out, starts[(kind, current)] + next_field, pointer)
        struct.pack_into("<IHH", out, 8, len(out), len(self.header), len(self.order))
        return bytes(out)

    def _block(self, kind: str, index: int) -> bytes:
        if kind == "finf":
            return self.finf
        if kind == "raw":
            return self.raw[index]
        if kind == "cglp":
            body = struct.pack("<BBHbBBB", self.cell_width, self.cell_height, self.glyph_size, self.baseline,
                               self.max_width, self.bpp, self.flags) + b"".join(self.glyphs)
            return _block(b"PLGC", body)
        if kind == "cwdh":
            first, entries = self.widths[index]
            body = struct.pack("<HHI", first, first + len(entries) - 1, 0)
            return _block(b"HDWC", body + b"".join(struct.pack("bBB", *entry) for entry in entries))
        begin, end, method, payload = self.maps[index]
        body = struct.pack("<HHII", begin, end, method, 0)
        if method == 0:
            body += struct.pack("<H", payload)
        elif method == 1:
            body += struct.pack(f"<{len(payload)}H", *payload)
        else:
            body += struct.pack("<H", len(payload)) + b"".join(struct.pack("<HH", *pair) for pair in payload)
        return _block(b"PAMC", body)


def _block(magic: bytes, body: bytes) -> bytes:
    body += bytes(-(len(body) + 8) % 4)
    return magic + struct.pack("<I", len(body) + 8) + body


# -- model ------------------------------------------------------------------------------------------


def _grid(font: Font, params: Dict[str, Any]) -> Tuple[int, int]:
    columns = max(1, int(params.get("columns", 16)))
    cells = len(font.glyphs) + max(0, int(params.get("spare", 32)))
    return columns, (cells + columns - 1) // columns


def _box(font: Font, columns: int, glyph: int) -> Tuple[int, int, int, int]:
    x, y = (glyph % columns) * font.cell_width, (glyph // columns) * font.cell_height
    return x, y, x + font.cell_width, y + font.cell_height


def extract(data: bytes, params: Dict[str, Any]) -> Tuple[Metadata, Sheets]:
    font = Font(data)
    columns, rows = _grid(font, params)
    ink = Image.new("L", (columns * font.cell_width, rows * font.cell_height))
    for index, glyph in enumerate(font.glyphs):
        ink.paste(font.decode(glyph), _box(font, columns, index)[:2])
    left, glyph_width, advance = font.defaults()
    widths = font.width_entries()
    packets, glyph_widths = [], []
    for index in range(columns * rows):
        entry = widths.get(index, (left, glyph_width, advance))
        packets.append({"kerning": -entry[0], "width": entry[2]})
        glyph_widths.append(entry[1])
    pairs = [(char_code(font.to_char(code)), glyph) for code, glyph in font.codes().items() if glyph < columns * rows]
    line_feed = font.finf[9]
    metadata = {
        "header": {"signature": "RTFN", "num_chunks": len(font.order), "texture_format": f"{font.bpp} bpp"},
        "INF1": [{"encoding": 1, "ascent": font.baseline, "descent": max(0, font.cell_height - font.baseline),
                  "width": advance, "leading": line_feed, "fallback_code": 0x3F, "unk1": 0}],
        "GLY1": [{"start_glyph": 0, "end_glyph": columns * rows - 1, "cell_width": font.cell_width,
                  "cell_height": font.cell_height, "page_data_size": font.glyph_size, "texture_format": font.bpp,
                  "glyph_horizontal_count": columns, "glyph_vertical_count": rows,
                  "texture_width": ink.width, "texture_height": ink.height}],
        "MAP1": [map_entries(pairs)],
        "WID1": [{"first_code_included": 0, "last_code_included": columns * rows, "packets": packets,
                  "glyph_widths": glyph_widths}],
    }
    return metadata, [grey_sheet(ink)]


def _clamp(value: int, low: int, high: int) -> int:
    return max(low, min(high, int(value)))


def pack(metadata: Metadata, sheets: Sheets, original: bytes, params: Dict[str, Any]) -> bytes:
    font = Font(original)
    columns, rows = _grid(font, params)
    new_ink = coverage(sheets[0])
    old_metadata, old_sheets = extract(original, params)
    if new_ink.size != old_sheets[0].size:
        raise ValueError(f"The sheet is {new_ink.size[0]}x{new_ink.size[1]}, the font grid "
                         f"{old_sheets[0].width}x{old_sheets[0].height}")
    old_ink = coverage(old_sheets[0])
    packets = metadata["WID1"][0]["packets"]
    count = len(font.glyphs)

    existing = font.codes()
    wanted = {font.to_code(char): glyph for char, glyph in char_map(metadata).items()}
    changed = [code for code, glyph in existing.items() if wanted.get(code) != glyph]
    if changed:
        raise ValueError("This font keeps the characters it has; changed or removed: "
                         + " ".join(f"U+{code:04X}" for code in sorted(changed)[:10]))
    new = {code: glyph for code, glyph in wanted.items() if code not in existing}
    if new and max(new) > 0xFFFF:
        raise ValueError("NFTR fonts map 16-bit character codes only")
    last = max([count - 1, *new.values()])
    if last >= columns * rows:
        raise ValueError(f"Glyph {last} is beyond the font's {columns * rows} cells")
    if (not new and new_ink.tobytes() == old_ink.tobytes()
            and packets[:count] == old_metadata["WID1"][0]["packets"][:count]):
        return bytes(original)

    widths = font.width_entries()
    default = font.defaults()
    entries: Dict[int, Tuple[int, int, int]] = {}
    for index in range(last + 1):
        box = _box(font, columns, index)
        cell = new_ink.crop(box)
        redrawn = index >= count or cell.tobytes() != old_ink.crop(box).tobytes()
        if index >= count:
            font.glyphs.append(font.encode(cell))
        elif redrawn:
            font.glyphs[index] = font.encode(cell)
        old = widths.get(index, default)
        bounds = cell.point(lambda value: 255 if value >= 128 else 0).getbbox()
        glyph_width = (bounds[2] if bounds else 0) if redrawn else old[1]
        packet = packets[index] if index < len(packets) else {"kerning": -default[0], "width": default[2]}
        entries[index] = (_clamp(-int(packet["kerning"]), -128, 127), _clamp(glyph_width, 0, 255),
                          _clamp(packet["width"], 0, 255))

    # Widths of the glyphs the file describes, then the new glyphs at the end of the range that ends the font.
    for block in font.widths:
        first, block_entries = block
        block[1] = [entries.get(first + offset, entry) for offset, entry in enumerate(block_entries)]
    if last >= count:
        tail = next((block for block in font.widths if block[0] + len(block[1]) == count), None)
        added = [entries[index] for index in range(count, last + 1)]
        if tail is not None:
            tail[1].extend(added)
        else:
            font.widths.append([count, added])
            font.order.insert(_after(font, "cwdh"), ("cwdh", len(font.widths) - 1))
            font.width_chain.append(len(font.widths) - 1)

    # New codes: a table slot, else the scan list that covers them, else a new scan list.
    loose: List[Tuple[int, int]] = []
    for code, glyph in sorted(new.items()):
        for index in font.map_chain:
            begin, end, method, payload = font.maps[index]
            if begin <= code <= end and method == 1:
                payload[code - begin] = glyph
                break
            if begin <= code <= end and method == 2:
                payload.append((code, glyph))
                payload.sort()
                break
        else:
            loose.append((code, glyph))
    if loose:
        font.maps.append([loose[0][0], loose[-1][0], 2, loose])
        font.order.insert(_after(font, "cmap"), ("cmap", len(font.maps) - 1))
        font.map_chain.append(len(font.maps) - 1)
    return font.build()


def _after(font: Font, kind: str) -> int:
    """Where a new block of ``kind`` goes in file order: after the last of its kind."""
    positions = [position for position, (other, _index) in enumerate(font.order) if other == kind]
    return positions[-1] + 1 if positions else len(font.order)
