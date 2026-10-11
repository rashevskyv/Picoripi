"""Professor Layton and the Spectre's Call (DS): ``GFSP`` pictures (``.ci``, ``.ca``) as RGBA images.

A ``GFSP`` file (Level-5 compressed inside the ``lt4_*.fa`` archives) is a small pack: a 0x24-byte header whose
word at 0x10 is the length of everything after the names in words, then a table of (size | type, hash) pairs, the
file names (``IMG.lp`` / ``IMG.lt``, or ``AS.lb``, ``AP00.lp``, ``AT00.lt`` ... of an animation) and the chunks:

- ``GSD1``: the animation script of a ``.ca`` (left as it is);
- ``GPLT``: u16 colour count, u16 8, the BGR555 colours (bit 15 set; colour 0 is the transparent key);
- ``GTXT``: u8 format (2: 4-bit indices, 3: 8-bit, 4: A5I3, 5: A3I5), u8, u8 / u8 log2 of the canvas size minus 3,
  u16 canvas width and height, u16 picture width and height, (offset, count) of three small tables (the image
  rectangle, its parts, the cell table), the offset of the tile data and u16 tile count (the word at +32). The cell table has one u16 per 8x8 cell
  of the picture: the number of the tile, or 0xFFFF for an empty cell. The tiles follow, 8x8 each, four-bit tiles
  low nibble first.

Texture ``n`` uses palette ``n`` (the last one when there are fewer palettes). Writing keeps every pixel whose
colour did not change, maps the other pixels to the nearest colour of the palette (A3I5 / A5I3 keep the alpha
steps), reuses equal tiles and appends new ones: the chunk grows and the sizes in the header are written again.
"""
from __future__ import annotations

import re
import struct
from typing import Any, Dict, List, Optional, Tuple

from PIL import Image

from core.containers import level5, lz10
from core.texture_formats import Texture

RGBA = Tuple[int, int, int, int]
FORMATS = {2: ("4-bit indices", 32), 3: ("8-bit indices", 64), 4: ("A5I3", 64), 5: ("A3I5", 64)}
EMPTY = 0xFFFF
_TAG = re.compile(rb"GPLT|GTXT|GSD1")


def _colour(value: int) -> Tuple[int, int, int]:
    r, g, b = value & 31, value >> 5 & 31, value >> 10 & 31
    return (round(r / 31 * 255), round(g / 31 * 255), round(b / 31 * 255))


def _plain(data: bytes) -> Tuple[bytes, bool]:
    """``(the GFSP bytes, whether they were Level-5 compressed)``."""
    if data[:4] == b"GFSP":
        return bytes(data), False
    plain = level5.decompress(data)
    if plain[:4] != b"GFSP":
        raise ValueError("not a GFSP picture")
    return plain, True


def _pack(original: bytes, plain: bytes) -> bytes:
    """``plain`` Level-5 compressed (LZ10, optimal parse); the original bytes when it decompresses to ``plain``."""
    if original[:4] == b"GFSP":
        return plain
    if level5.decompress(original) == plain:
        return bytes(original)
    return struct.pack("<I", len(plain) << 3 | 1) + lz10.compress(plain)[4:]


class _Chunk:
    def __init__(self, tag: bytes, at: int, end: int):
        self.tag, self.at, self.end = tag, at, end


class _Gfsp:
    def __init__(self, plain: bytes):
        self.plain = plain
        starts = []
        for match in _TAG.finditer(plain, 0x24):
            if match.start() % 4:
                continue
            starts.append((match.start(), match.group()))
        palettes: List[_Chunk] = []
        textures: List[_Chunk] = []
        valid = []
        for position, tag in starts:
            if tag == b"GPLT":
                count = struct.unpack_from("<H", plain, position + 4)[0] if position + 8 <= len(plain) else 0
                if not 0 < count <= 256 or position + 8 + 2 * count > len(plain):
                    continue
            elif tag == b"GTXT":
                if position + 32 > len(plain) or plain[position + 4] not in FORMATS:
                    continue
                a_off, a_n, b_off, b_n, c_off, c_n, d_off = struct.unpack_from("<HHHHHHI", plain, position + 16)
                if position + c_off + 2 * c_n > len(plain) or d_off < c_off + 2 * c_n or d_off > len(plain) - position:
                    continue
            valid.append((position, tag))
        for index, (position, tag) in enumerate(valid):
            end = valid[index + 1][0] if index + 1 < len(valid) else len(plain)
            chunk = _Chunk(tag, position, end)
            if tag == b"GPLT":
                palettes.append(chunk)
            elif tag == b"GTXT":
                textures.append(chunk)
        if not textures or not palettes:
            raise ValueError("no picture in this GFSP file")
        self.palettes, self.textures = palettes, textures

    # -- one texture -----------------------------------------------------------------------------------

    def palette(self, number: int) -> List[Tuple[int, int, int]]:
        chunk = self.palettes[min(number, len(self.palettes) - 1)]
        count = struct.unpack_from("<H", self.plain, chunk.at + 4)[0]
        return [_colour(v) for v in struct.unpack_from(f"<{count}H", self.plain, chunk.at + 8)]

    def geometry(self, number: int):
        chunk = self.textures[number]
        p = self.plain
        fmt = p[chunk.at + 4]
        width, height = struct.unpack_from("<HH", p, chunk.at + 12)
        _a_off, _a_n, _b_off, _b_n, c_off, c_n, d_off = struct.unpack_from("<HHHHHHI", p, chunk.at + 16)
        size = FORMATS[fmt][1]
        tiles = (chunk.end - chunk.at - d_off) // size
        if c_n != ((width + 7) // 8) * ((height + 7) // 8):
            raise ValueError("the cell table does not match the picture size")
        return fmt, width, height, c_off, c_n, d_off, size, tiles

    def values(self, number: int) -> Tuple[List[Optional[List[int]]], int, int]:
        """Per cell the 64 stored values (a palette index, or A+I for A3I5 / A5I3), None for an empty cell."""
        fmt, width, height, c_off, c_n, d_off, size, tiles = self.geometry(number)
        chunk = self.textures[number]
        p = self.plain
        cells = struct.unpack_from(f"<{c_n}H", p, chunk.at + c_off)
        out: List[Optional[List[int]]] = []
        for value in cells:
            if value == EMPTY or value >= tiles:
                out.append(None)
                continue
            raw = p[chunk.at + d_off + value * size:chunk.at + d_off + (value + 1) * size]
            out.append(self._unpack(raw, fmt))
        return out, (width + 7) // 8, (height + 7) // 8

    @staticmethod
    def _unpack(raw: bytes, fmt: int) -> List[int]:
        if fmt == 2:
            return [v for b in raw for v in (b & 15, b >> 4)]
        return list(raw)

    @staticmethod
    def _pack_tile(values: List[int], fmt: int) -> bytes:
        if fmt == 2:
            return bytes(values[2 * i] | values[2 * i + 1] << 4 for i in range(32))
        return bytes(values)

    def image(self, number: int) -> Image.Image:
        fmt = self.textures[number].at
        fmt = self.plain[fmt + 4]
        cells, w8, h8 = self.values(number)
        palette = self.palette(number)
        width, height = struct.unpack_from("<HH", self.plain, self.textures[number].at + 12)
        image = Image.new("RGBA", (w8 * 8, h8 * 8), (0, 0, 0, 0))
        px = image.load()
        for cell, tile in enumerate(cells):
            if tile is None:
                continue
            x0, y0 = (cell % w8) * 8, (cell // w8) * 8
            for i, value in enumerate(tile):
                px[x0 + i % 8, y0 + i // 8] = self._pixel(value, fmt, palette)
        return image.crop((0, 0, width, height)) if (width, height) != image.size else image

    @staticmethod
    def _pixel(value: int, fmt: int, palette: List[Tuple[int, int, int]]) -> RGBA:
        if fmt == 4:
            index, alpha = value & 7, (value >> 3) * 255 // 31
        elif fmt == 5:
            index, alpha = value & 31, (value >> 5) * 255 // 7
        else:
            index, alpha = value, 0 if value == 0 else 255
        if index >= len(palette):
            return (0, 0, 0, 255)
        r, g, b = palette[index]
        return (r, g, b, alpha)

    # -- writing -----------------------------------------------------------------------------------------

    def with_image(self, number: int, picture: Image.Image) -> Tuple[bytes, int, int]:
        """``(GTXT chunk bytes, old chunk length, new chunk length)`` showing ``picture``."""
        fmt, width, height, c_off, c_n, d_off, size, tiles = self.geometry(number)
        chunk = self.textures[number]
        p = self.plain
        new = picture.convert("RGBA")
        if new.size != (width, height):
            raise ValueError(f"The image is {new.width}x{new.height}, the texture {width}x{height}")
        cells_old, w8, h8 = self.values(number)
        palette = self.palette(number)
        pixels = new.load()
        cache: Dict[Tuple[int, int, int], int] = {}
        first = 1 if fmt in (2, 3) and len(palette) > 1 else 0
        cell_values = list(struct.unpack_from(f"<{c_n}H", p, chunk.at + c_off))
        tile_data = [p[chunk.at + d_off + i * size:chunk.at + d_off + (i + 1) * size] for i in range(tiles)]
        known = {tile: i for i, tile in enumerate(tile_data)}
        for cell in range(c_n):
            old = cells_old[cell]
            x0, y0 = (cell % w8) * 8, (cell // w8) * 8
            block: List[int] = []
            for i in range(64):
                x, y = x0 + i % 8, y0 + i // 8
                was = old[i] if old is not None else 0
                if x >= width or y >= height:
                    block.append(was)
                    continue
                r, g, b, a = pixels[x, y]
                before = self._pixel(was, fmt, palette)
                if fmt in (2, 3):
                    same = (a < 128 and before[3] == 0) or (a >= 128 and before[3] == 255 and (r, g, b) == before[:3])
                else:
                    same = (r, g, b, a) == before
                if same:
                    block.append(was)
                    continue
                if fmt in (2, 3):
                    block.append(0 if a < 128 else self._nearest((r, g, b), palette, cache, first))
                elif fmt == 5:
                    block.append(self._nearest((r, g, b), palette, cache, 0) | (a * 7 + 127) // 255 << 5)
                else:
                    block.append(self._nearest((r, g, b), palette, cache, 0) | (a * 31 + 127) // 255 << 3)
            if old is not None and block == old:
                continue
            if old is None and all(self._pixel(v, fmt, palette)[3] == 0 for v in block):
                continue
            tile = self._pack_tile(block, fmt)
            index = known.get(tile)
            if index is None:
                index = known[tile] = len(tile_data)
                tile_data.append(tile)
                if index >= EMPTY:
                    raise ValueError("The picture needs too many different tiles")
            cell_values[cell] = index
        if cell_values == list(struct.unpack_from(f"<{c_n}H", p, chunk.at + c_off)):
            return bytes(p[chunk.at:chunk.end]), chunk.end - chunk.at, chunk.end - chunk.at
        # a tile no cell shows any more goes: the game keeps the tiles in a fixed video memory area
        used = sorted({v for v in cell_values if v != EMPTY})
        where = {old_index: new_index for new_index, old_index in enumerate(used)}
        cell_values = [where.get(v, EMPTY) if v != EMPTY else EMPTY for v in cell_values]
        tile_data = [tile_data[i] for i in used]
        body = bytearray(p[chunk.at:chunk.at + c_off])
        body += struct.pack(f"<{c_n}H", *cell_values)
        body += p[chunk.at + c_off + 2 * c_n:chunk.at + d_off]
        body += b"".join(tile_data)
        body += p[chunk.at + d_off + tiles * size:chunk.end]          # bytes after the last whole tile stay
        struct.pack_into("<H", body, 32, len(tile_data))              # the tile count (low half of the word at +32)
        return bytes(body), chunk.end - chunk.at, len(body)

    @staticmethod
    def _nearest(colour: Tuple[int, int, int], palette: List[Tuple[int, int, int]], cache: Dict[Tuple[int, int, int], int],
                 first: int) -> int:
        hit = cache.get(colour)
        if hit is None:
            hit = min(range(first, len(palette)), key=lambda i: sum((a - b) ** 2 for a, b in zip(colour, palette[i])))
            cache[colour] = hit
        return hit

    def replace(self, number: int, chunk_bytes: bytes, old_length: int) -> bytes:
        """The file with texture ``number``'s chunk replaced: the size entry and the word count are written again."""
        chunk = self.textures[number]
        p = bytearray(self.plain[:chunk.at] + chunk_bytes + self.plain[chunk.end:])
        if len(chunk_bytes) == old_length:
            return bytes(p)
        names_end = min(c.at for c in self.palettes + self.textures)
        first = names_end
        for match in re.finditer(rb"GSD1", self.plain):
            if match.start() % 4 == 0 and match.start() < first:
                first = match.start()
        struct.pack_into("<I", p, 0x10, (len(p) - first) // 4)
        # the (size | type) entry of this chunk: a word below the names whose low half is the old length
        for at in range(0x18, first, 4):
            word = struct.unpack_from("<I", p, at)[0]
            if word & 0xFFFF == old_length and word >> 16 and at % 8 == 0:
                struct.pack_into("<I", p, at, (word & 0xFFFF0000) | len(chunk_bytes))
                break
        else:
            raise ValueError("the size of the picture chunk is not in the header")
        return bytes(p)


def read(data: bytes, params: Dict[str, Any]) -> List[Texture]:
    plain, _compressed = _plain(data)
    gfsp = _Gfsp(plain)
    out = []
    for number in range(len(gfsp.textures)):
        fmt = FORMATS[plain[gfsp.textures[number].at + 4]][0]
        out.append(Texture(f"texture {number}", gfsp.image(number), fmt))
    return out


def write(data: bytes, images: Dict[int, Image.Image], params: Dict[str, Any]) -> bytes:
    plain, _compressed = _plain(data)
    result = plain
    for number in sorted(images):
        gfsp = _Gfsp(result)
        chunk, old_length, _new = gfsp.with_image(number, images[number])
        result = gfsp.replace(number, chunk, old_length)
    return _pack(data, result)
