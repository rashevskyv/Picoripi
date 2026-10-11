"""Professor Layton on Nintendo DS (Curious Village, Pandora's Box, Lost Future): pictures and animation atlases as
RGBA images.

The files are BIOS compressed (a Curious Village file has the 4-byte type prefix, see
``core.containers.layton_ds``); ``write`` compresses again and gives the original bytes back when nothing changed.

``layton_bg`` (``.arc`` backgrounds of Curious Village and Pandora's Box) -- u32 colour count, that many BGR555
colours, u32 tile count, 8x8 tiles of 8-bit indices (64 bytes), u16 width / 8, u16 height / 8, then one u16 per
8x8 cell: tile index in 10 bits, vertical flip in bit 10, horizontal flip in bit 11. One opaque texture.

``layton_limg`` (Lost Future ``.cimg``) -- ``LIMG``: u32 header length (48), u16 offsets and counts of the sub-image
rectangles, the image parameters, the cell table (u16 per cell, as above), the tiles (4-bit when the palette has
16 colours or less, else 8-bit), two unknown u16, the colour count, width, height; the palette follows the
header and the tiles are the last block. One texture (the whole sheet; colour 0 is transparent).
``layton_cani`` (Lost Future ``.cani``) -- an ``LPC2`` pack of ``LIMG`` sheets and one script: every sheet is a
texture.

``layton_ani`` / ``layton_arj`` (``.arc`` / ``.arj`` animations of Curious Village and Pandora's Box) -- u16 frame
count, u16 bit depth code (``2 ** (code - 1)`` bits per pixel), (arj: u32 colour count), per frame u16 width,
u16 height, u32 tile count and per tile (arj: two u16 of ``glb``), u16 x, u16 y, u16 w, u16 h (the size is
``8 << n``) and its pixels (arc: row after row, arj: 8x8 blocks), (arc: u32 colour count) the BGR555 palette,
then the animation tables, which stay as they are. Every frame is one texture; colour 0 is transparent.

Writing maps every changed pixel to the nearest colour of the file's own palette (pixels that did not change keep
their index) and, for tiled pictures, reuses equal tiles and appends new ones; the animation layout never changes.

The formats are those of bullbin's ``madhatter`` (MIT licence, https://github.com/bullbin/madhatter).
"""
from __future__ import annotations

import struct
from typing import Any, Dict, List, Tuple

from PIL import Image

from core.containers import layton_ds
from core.texture_formats import Texture

RGBA = Tuple[int, int, int, int]
MAX_TILES = 0x3FF


def _colour(value: int) -> RGBA:
    r, g, b = value & 31, value >> 5 & 31, value >> 10 & 31
    return (round(r / 31 * 255), round(g / 31 * 255), round(b / 31 * 255), 255)


def _nearest(colour: Tuple[int, int, int], palette: List[RGBA], cache: Dict[Tuple[int, int, int], int],
             first: int = 0) -> int:
    hit = cache.get(colour)
    if hit is None:
        hit = min(range(first, len(palette)), key=lambda i: sum((a - b) ** 2 for a, b in zip(colour, palette[i][:3])))
        cache[colour] = hit
    return hit


def _plain(data: bytes) -> bytes:
    try:
        return layton_ds.decompress(data)[0]
    except (ValueError, IndexError, struct.error):
        return bytes(data)


def _compressed(data: bytes) -> bool:
    try:
        layton_ds.decompress(data)
        return True
    except (ValueError, IndexError, struct.error):
        return False


def _rewrap(original: bytes, plain: bytes) -> bytes:
    """``plain`` stored the way ``original`` was (the original bytes when nothing changed)."""
    return layton_ds.recompress(original, plain) if _compressed(original) else plain


# -- tiled pictures ----------------------------------------------------------------------------------------

class _Tiled:
    """Palette, 8x8 tiles (64 palette indices each), the cell table: what ``bg`` and ``LIMG`` files share."""

    def __init__(self, palette: List[RGBA], tiles: List[bytes], cells: List[int], w8: int, h8: int,
                 zero_transparent: bool):
        self.palette, self.tiles, self.cells, self.w8, self.h8 = palette, tiles, cells, w8, h8
        self.zero_transparent = zero_transparent

    def cell_indices(self, cell: int) -> bytes:
        value = self.cells[cell]
        index = value & 0x3FF
        if index >= len(self.tiles):
            return bytes(64)
        rows = [self.tiles[index][8 * y:8 * y + 8] for y in range(8)]
        if value & 0x800:
            rows = [row[::-1] for row in rows]
        if value & 0x400:
            rows = rows[::-1]
        return b"".join(rows)

    def indices(self) -> bytearray:
        width = self.w8 * 8
        out = bytearray(width * self.h8 * 8)
        for cell in range(self.w8 * self.h8):
            x0, y0 = (cell % self.w8) * 8, (cell // self.w8) * 8
            block = self.cell_indices(cell)
            for y in range(8):
                out[(y0 + y) * width + x0:(y0 + y) * width + x0 + 8] = block[8 * y:8 * y + 8]
        return out

    def colour(self, index: int) -> RGBA:
        if index >= len(self.palette):
            return (0, 0, 0, 255)
        if index == 0 and self.zero_transparent:
            return (0, 0, 0, 0)
        return self.palette[index]

    def image(self) -> Image.Image:
        image = Image.new("RGBA", (self.w8 * 8, self.h8 * 8))
        image.putdata([self.colour(i) for i in self.indices()])
        return image

    def with_image(self, picture: Image.Image) -> Tuple[List[bytes], List[int]]:
        """``(tiles, cells)`` that show ``picture``: unchanged cells keep their tile, new pictures get new tiles."""
        new = picture.convert("RGBA")
        if new.size != (self.w8 * 8, self.h8 * 8):
            raise ValueError(f"The image is {new.width}x{new.height}, the texture {self.w8 * 8}x{self.h8 * 8}")
        width = self.w8 * 8
        old = self.indices()
        pixels = new.load()
        cache: Dict[Tuple[int, int, int], int] = {}
        tiles = list(self.tiles)
        known = {tile: i for i, tile in enumerate(tiles)}
        cells = list(self.cells)
        first = 1 if self.zero_transparent and len(self.palette) > 1 else 0
        for cell in range(self.w8 * self.h8):
            x0, y0 = (cell % self.w8) * 8, (cell // self.w8) * 8
            block = bytearray(64)
            for y in range(8):
                for x in range(8):
                    was = old[(y0 + y) * width + x0 + x]
                    r, g, b, a = pixels[x0 + x, y0 + y]
                    before = self.colour(was)
                    if (a < 128 and before[3] == 0) or (a >= 128 and before[3] == 255 and (r, g, b) == before[:3]):
                        block[8 * y + x] = was
                    elif a < 128 and self.zero_transparent:
                        block[8 * y + x] = 0
                    else:
                        block[8 * y + x] = _nearest((r, g, b), self.palette, cache, first)
            if bytes(block) == self.cell_indices(cell):
                continue
            tile = bytes(block)
            index = known.get(tile)
            if index is None:
                if len(tiles) >= MAX_TILES:
                    raise ValueError("The picture needs more than 1022 different 8x8 tiles")
                index = known[tile] = len(tiles)
                tiles.append(tile)
            cells[cell] = index
        return tiles, cells


def _parse_bg(plain: bytes) -> Tuple[_Tiled, int]:
    count = struct.unpack_from("<I", plain, 0)[0]
    if not 0 < count <= 256:
        raise ValueError("not a Layton background")
    palette = [_colour(v) for v in struct.unpack_from(f"<{count}H", plain, 4)]
    at = 4 + 2 * count
    tile_count = struct.unpack_from("<I", plain, at)[0]
    tiles_at = at + 4
    at = tiles_at + 64 * tile_count
    w8, h8 = struct.unpack_from("<HH", plain, at)
    if not w8 or not h8 or at + 4 + 2 * w8 * h8 != len(plain):
        raise ValueError("not a Layton background")
    cells = list(struct.unpack_from(f"<{w8 * h8}H", plain, at + 4))
    tiles = [plain[tiles_at + 64 * i:tiles_at + 64 * (i + 1)] for i in range(tile_count)]
    return _Tiled(palette, tiles, cells, w8, h8, False), 4 + 2 * count


def _bg_read(data: bytes, params: Dict[str, Any]) -> List[Texture]:
    return [Texture("", _parse_bg(_plain(data))[0].image(), "BGR555 8bpp tiles")]


def _bg_write(data: bytes, images: Dict[int, Image.Image], params: Dict[str, Any]) -> bytes:
    if 0 not in images:
        return bytes(data)
    plain = _plain(data)
    sheet, head = _parse_bg(plain)
    tiles, cells = sheet.with_image(images[0])
    out = bytearray(plain[:head])
    out += struct.pack("<I", len(tiles)) + b"".join(tiles)
    out += struct.pack("<HH", sheet.w8, sheet.h8) + struct.pack(f"<{len(cells)}H", *cells)
    return _rewrap(data, bytes(out))


class _Limg:
    """``LIMG``: the header names where the palette, the sub-image rectangles, the cell table and the tiles lie."""

    def __init__(self, plain: bytes):
        if plain[:4] != b"LIMG" or len(plain) < 32:
            raise ValueError("not a LIMG sheet")
        self.plain = plain
        self.header = struct.unpack_from("<I", plain, 4)[0]
        (self.sub_at, self.sub_count, self.param_at, self.unk1, self.table_at, self.table_len, self.tiles_at,
         self.tile_count, self.unk2, colours, self.width, self.height) = struct.unpack_from("<12H", plain, 8)
        self.bpp = 4 if colours <= 16 else 8
        self.tile_size = 32 if self.bpp == 4 else 64
        self.w8, self.h8 = (self.width + 7) // 8, (self.height + 7) // 8
        if not colours or self.table_len != self.w8 * self.h8 or \
                self.tiles_at + self.tile_count * self.tile_size != len(plain) or \
                self.header + 2 * colours > min(self.sub_at, self.table_at, self.tiles_at, self.param_at):
            raise ValueError("not a LIMG sheet this version can read")
        palette = [_colour(v) for v in struct.unpack_from(f"<{colours}H", plain, self.header)]
        cells = list(struct.unpack_from(f"<{self.table_len}H", plain, self.table_at))
        tiles = [self._unpack(plain[self.tiles_at + i * self.tile_size:self.tiles_at + (i + 1) * self.tile_size])
                 for i in range(self.tile_count)]
        self.sheet = _Tiled(palette, tiles, cells, self.w8, self.h8, True)

    def _unpack(self, raw: bytes) -> bytes:
        if self.bpp == 8:
            return bytes(raw)
        return bytes(v for b in raw for v in (b & 15, b >> 4))

    def _pack(self, tile: bytes) -> bytes:
        if self.bpp == 8:
            return tile
        return bytes(tile[2 * i] | tile[2 * i + 1] << 4 for i in range(32))

    def with_image(self, picture: Image.Image) -> bytes:
        tiles, cells = self.sheet.with_image(picture)
        out = bytearray(self.plain[:self.tiles_at])
        out[self.table_at:self.table_at + 2 * len(cells)] = struct.pack(f"<{len(cells)}H", *cells)
        struct.pack_into("<H", out, 8 + 14, len(tiles))          # tile count
        return bytes(out) + b"".join(self._pack(tile) for tile in tiles)


def _limg_read(data: bytes, params: Dict[str, Any]) -> List[Texture]:
    return [Texture("", _Limg(_plain(data)).sheet.image(), "BGR555 tiles")]


def _limg_write(data: bytes, images: Dict[int, Image.Image], params: Dict[str, Any]) -> bytes:
    if 0 not in images:
        return bytes(data)
    plain = _plain(data)
    return _rewrap(data, _Limg(plain).with_image(images[0]))


def _cani_members(plain: bytes) -> Tuple[layton_ds.Pack, List[int]]:
    pack = layton_ds.Pack.parse(plain)
    return pack, [i for i, m in enumerate(pack.members) if m.data[:4] == b"LIMG"]


def _cani_read(data: bytes, params: Dict[str, Any]) -> List[Texture]:
    pack, sheets = _cani_members(_plain(data))
    return [Texture(pack.members[i].name, _Limg(pack.members[i].data).sheet.image(), "BGR555 tiles") for i in sheets]


def _cani_write(data: bytes, images: Dict[int, Image.Image], params: Dict[str, Any]) -> bytes:
    plain = _plain(data)
    pack, sheets = _cani_members(plain)
    for number, picture in images.items():
        member = pack.members[sheets[number]]
        member.data = _Limg(member.data).with_image(picture)
    return _rewrap(data, pack.build())


# -- animation atlases ------------------------------------------------------------------------------------

class _Ani:
    def __init__(self, plain: bytes, arj: bool):
        self.plain, self.arj = plain, arj
        count, code = struct.unpack_from("<HH", plain, 0)
        if count == 0 or code not in (3, 4):
            raise ValueError("not a Layton animation file")
        self.bpp = 2 ** (code - 1)
        pos = 4
        colours = 0
        if arj:
            colours = struct.unpack_from("<I", plain, pos)[0]
            pos += 4
        self.frames: List[Tuple[int, int, List[Tuple[int, int, int, int, int]]]] = []
        for _ in range(count):
            width, height, tiles = struct.unpack_from("<HHI", plain, pos)
            pos += 8
            parts = []
            for _t in range(tiles):
                if arj:
                    pos += 4
                x, y, ew, eh = struct.unpack_from("<4H", plain, pos)
                pos += 8
                tw, th = 8 << ew, 8 << eh
                parts.append((x, y, tw, th, pos))
                pos += tw * th * self.bpp // 8
                if pos > len(plain):
                    raise ValueError("not a Layton animation file")
            self.frames.append((width, height, parts))
        if not arj:
            colours = struct.unpack_from("<I", plain, pos)[0]
            pos += 4
        if not 0 < colours <= 256 or pos + 2 * colours > len(plain):
            raise ValueError("not a Layton animation file")
        self.palette = [_colour(v) for v in struct.unpack_from(f"<{colours}H", plain, pos)]
        self.colours = [(0, 0, 0, 0)] + self.palette[1:]

    def _unpack(self, raw: bytes, tw: int, th: int) -> List[int]:
        n = tw * th
        if self.bpp == 8:
            values = list(raw[:n])
        else:
            values = []
            for byte in raw[:n // 2]:
                values += [byte & 15, byte >> 4]
        if not self.arj:
            return values
        out = [0] * n
        i = 0
        for by in range(th // 8):
            for bx in range(tw // 8):
                for y in range(8):
                    for x in range(8):
                        out[(by * 8 + y) * tw + bx * 8 + x] = values[i]
                        i += 1
        return out

    def _pack(self, values: List[int], tw: int, th: int) -> bytes:
        if self.arj:
            ordered = []
            for by in range(th // 8):
                for bx in range(tw // 8):
                    for y in range(8):
                        base = (by * 8 + y) * tw + bx * 8
                        ordered += values[base:base + 8]
            values = ordered
        if self.bpp == 8:
            return bytes(values)
        return bytes(values[2 * i] | values[2 * i + 1] << 4 for i in range(len(values) // 2))

    def frame_indices(self, number: int) -> List[int]:
        width, height, parts = self.frames[number]
        canvas = [0] * (width * height)
        for x, y, tw, th, at in parts:
            values = self._unpack(self.plain[at:at + tw * th * self.bpp // 8], tw, th)
            for row in range(th):
                if y + row >= height:
                    break
                for col in range(tw):
                    if x + col < width:
                        canvas[(y + row) * width + x + col] = values[row * tw + col]
        return canvas

    def image(self, number: int) -> Image.Image:
        width, height, _parts = self.frames[number]
        image = Image.new("RGBA", (width, height))
        image.putdata([self.colours[i] if i < len(self.colours) else (0, 0, 0, 255)
                       for i in self.frame_indices(number)])
        return image


def _ani_read(data: bytes, params: Dict[str, Any], arj: bool) -> List[Texture]:
    ani = _Ani(_plain(data), arj)
    return [Texture(f"frame {i}", ani.image(i), f"BGR555 {ani.bpp}bpp") for i in range(len(ani.frames))]


def _ani_write(data: bytes, images: Dict[int, Image.Image], params: Dict[str, Any], arj: bool) -> bytes:
    plain = _plain(data)
    ani = _Ani(plain, arj)
    out = bytearray(plain)
    cache: Dict[Tuple[int, int, int], int] = {}
    first = 1 if len(ani.palette) > 1 else 0
    for number, picture in images.items():
        width, height, parts = ani.frames[number]
        new = picture.convert("RGBA")
        if new.size != (width, height):
            raise ValueError(f"The image is {new.width}x{new.height}, the texture {width}x{height}")
        pixels = new.load()
        old = ani.frame_indices(number)
        mapped = list(old)
        for y in range(height):
            for x in range(width):
                r, g, b, a = pixels[x, y]
                was = ani.colours[old[y * width + x]] if old[y * width + x] < len(ani.colours) else (0, 0, 0, 255)
                if (a < 128 and was[3] == 0) or (a >= 128 and was[3] == 255 and (r, g, b) == was[:3]):
                    continue
                mapped[y * width + x] = 0 if a < 128 else _nearest((r, g, b), ani.palette, cache, first)
        for x, y, tw, th, at in parts:
            values = ani._unpack(plain[at:at + tw * th * ani.bpp // 8], tw, th)
            for row in range(th):
                for col in range(tw):
                    if y + row < height and x + col < width:
                        place = (y + row) * width + x + col
                        if mapped[place] != old[place]:          # only what changed: other tiles may overlap
                            values[row * tw + col] = mapped[place]
            raw = ani._pack(values, tw, th)
            out[at:at + len(raw)] = raw
    return _rewrap(data, bytes(out))


# -- the backends ------------------------------------------------------------------------------------------

class bg:
    """Module-like backends: ``core.texture_formats`` calls ``read`` and ``write`` on them."""

    read = staticmethod(_bg_read)
    write = staticmethod(_bg_write)


class limg:
    read = staticmethod(_limg_read)
    write = staticmethod(_limg_write)


class cani:
    read = staticmethod(_cani_read)
    write = staticmethod(_cani_write)


class ani:
    @staticmethod
    def read(data: bytes, params: Dict[str, Any]) -> List[Texture]:
        return _ani_read(data, params, False)

    @staticmethod
    def write(data: bytes, images: Dict[int, Image.Image], params: Dict[str, Any]) -> bytes:
        return _ani_write(data, images, params, False)


class arj:
    @staticmethod
    def read(data: bytes, params: Dict[str, Any]) -> List[Texture]:
        return _ani_read(data, params, True)

    @staticmethod
    def write(data: bytes, images: Dict[int, Image.Image], params: Dict[str, Any]) -> bytes:
        return _ani_write(data, images, params, True)
