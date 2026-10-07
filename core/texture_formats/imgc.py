"""Level-5 IMGC / IMGN textures (``.xi``; Yo-kai Watch, Inazuma Eleven, Layton on 3DS; IMGN on Switch), alone or
inside XPCK packs.

Header (0x48 bytes, little endian; Kuriimu2 ``Imgx.cs``): ``IMGC``, version, u8 pixel format at 0x0A, u8
mip count at 0x0C, u8 bits per pixel at 0x0D, u16 bytes per 8x8 tile at 0x0E, u16 width and height at 0x10,
u32 offset of the tables at 0x1C (0x48), u32 tile table size at 0x34, the same padded to 4 at 0x38, u32 image
data size at 0x3C. The tile table (Level-5 compressed) lists, for every 8x8 tile of the padded image, the
index of its pixels in the image data (also Level-5 compressed); identical tiles are stored once. A table that
starts with 0x0453 has an 8-byte head and 32-bit indices, else 16-bit; -1 is a blank tile.

Inside a tile the texels are those of a PICA tile transposed (x and y swapped), ETC blocks included, so a
tile is decoded with the 3DS codec and flipped over its diagonal. Pixel formats (format byte -> PICA): the
Yo-kai Watch mapping, checked on the fonts (RGBA5551 with the glyphs in R, G and B) and the menus.

IMGN (Switch; checked on Yo-kai Watch 1) has the same header and tables; a tile is 8x8 pixels row by row, or,
for a BC format, four 4x4 blocks side by side (16x4 pixels), so the blocks of the image are in plain order. Its
format bytes are ``NX_FORMATS``.

Writing keeps the size and re-encodes only the tiles whose pixels changed; the tables are compressed with
LZ10. Writing the image that was read gives the original bytes.
"""
from __future__ import annotations

import struct
from typing import Any, Dict, List, Tuple

from PIL import Image

from core.containers import level5
from core.texture_formats import Texture, pixels

FORMATS = {0x00: "RGBA8", 0x01: "RGBA4", 0x02: "RGBA5551", 0x03: "RGB8", 0x04: "RGB565", 0x0A: "LA8", 0x0B: "LA4",
           0x0C: "L8", 0x0D: "L4", 0x0E: "A8", 0x0F: "A4", 0x1B: "ETC1", 0x1C: "ETC1A4"}
NX_FORMATS = {0x00: "RGBA8", 0x01: "RGBA4", 0x03: "RGB8", 0x04: "RGB565", 0x0A: "LA8", 0x0C: "L8", 0x0E: "A8", 0x1D: "BC1",
              0x1F: "BC3"}
HEADER = 0x48
LEGACY = 0x453


def detect(data: bytes) -> bool:
    return data[:4] in (b"IMGC", b"IMGN")


def _info(data: bytes) -> Dict[str, Any]:
    if not detect(data):
        raise ValueError("Not a Level-5 IMGC texture")
    nx = data[:4] == b"IMGN"
    fmt, bpp = data[0x0A], data[0x0D]
    width, height = struct.unpack_from("<HH", data, 0x10)
    table_at = struct.unpack_from("<I", data, 0x1C)[0]
    tile_size, tile_padded, image_size = struct.unpack_from("<III", data, 0x34)
    names = NX_FORMATS if nx else FORMATS
    if fmt not in names:
        raise ValueError(f"{data[:4].decode()} pixel format {fmt:#04x} is not supported")
    codec = pixels.codec(names[fmt] if nx else "pica:" + names[fmt])
    tw, th = (16, 4) if nx and codec.block != (1, 1) else (8, 8)
    return {"format": names[fmt], "codec": codec, "nx": nx, "bpp": bpp, "width": width, "height": height,
            "tile": (tw, th), "padded": (-(-width // tw) * tw, -(-height // th) * th), "tile_bytes": 64 * bpp // 8,
            "table_at": table_at, "table": data[table_at:table_at + tile_size],
            "image": data[table_at + tile_padded:table_at + tile_padded + image_size]}


def _tiles(info: Dict[str, Any]) -> Tuple[bytes, List[int]]:
    """``(tile table head, index per tile)`` of the padded image."""
    table = level5.decompress(info["table"])
    if len(table) >= 2 and struct.unpack_from("<H", table)[0] == LEGACY:
        return table[:8], list(struct.unpack_from(f"<{(len(table) - 8) // 4}i", table, 8))
    return b"", list(struct.unpack_from(f"<{len(table) // 2}h", table))


def _flip_tiles(image: Image.Image) -> Image.Image:
    """Every 8x8 tile mirrored over its diagonal (its own inverse)."""
    out = Image.new(image.mode, image.size)
    for y in range(0, image.height, 8):
        for x in range(0, image.width, 8):
            out.paste(image.crop((x, y, x + 8, y + 8)).transpose(Image.Transpose.TRANSPOSE), (x, y))
    return out


def _decode_tiles(info: Dict[str, Any], tiles: List[bytes]) -> Image.Image:
    """The padded image of the level-0 ``tiles``."""
    codec = info["codec"]
    width, height = info["padded"]
    if not info["nx"]:
        return _flip_tiles(codec.decode(b"".join(tiles), width, height))
    if codec.block != (1, 1):                       # 16x4 tiles of blocks: the blocks are in plain order
        return codec.decode(b"".join(tiles), width, height)
    line = 8 * codec.size                           # one row of a tile
    per_row, row_bytes = width // 8, width * codec.size
    out = bytearray(row_bytes * height)
    for n, tile in enumerate(tiles):
        base = n // per_row * 8 * row_bytes + n % per_row * line
        for row in range(8):
            out[base + row * row_bytes:base + row * row_bytes + line] = tile[row * line:(row + 1) * line]
    return codec.decode(bytes(out), width, height)


def _encode_tile(info: Dict[str, Any], tile: Image.Image) -> bytes:
    codec = info["codec"]
    if not info["nx"]:
        return codec.encode(tile.transpose(Image.Transpose.TRANSPOSE))
    return codec.encode(tile)


def _stored_tiles(info: Dict[str, Any]) -> Tuple[bytes, List[bytes]]:
    head, indices = _tiles(info)
    store = level5.decompress(info["image"])
    size = info["tile_bytes"]
    count = _count(info)
    tiles = [store[i * size:(i + 1) * size] if i >= 0 else bytes(size) for i in indices]
    if len(tiles) < count or any(len(t) != size for t in tiles):
        raise ValueError("IMGC tile table is shorter than the image")
    return head, tiles


def _count(info: Dict[str, Any], height: int = 0) -> int:
    """Tiles of level 0 (of the padded ``height`` when given)."""
    (tw, th), (width, padded) = info["tile"], info["padded"]
    return width // tw * ((height or padded) // th)


def decode(data: bytes) -> Image.Image:
    """The texture (level 0) as an RGBA image of its own size."""
    info = _info(data)
    _head, tiles = _stored_tiles(info)
    image = _decode_tiles(info, tiles[:_count(info)])
    return image if image.size == (info["width"], info["height"]) else image.crop((0, 0, info["width"], info["height"]))


def encode(data: bytes, image: Image.Image, taller: bool = False) -> bytes:
    """``data`` with its level 0 replaced by ``image`` (same size); the original bytes when nothing changed.

    ``taller``: the image may have more rows than the texture (a font that needs room for new glyphs); the
    texture grows to that height. Only for a texture without mip levels.
    """
    info = _info(data)
    grow = taller and image.width == info["width"] and image.height > info["height"] and data[0x0C] <= 1
    if image.size != (info["width"], info["height"]) and not grow:
        raise ValueError(f"The image is {image.size[0]}x{image.size[1]}, the texture {info['width']}x{info['height']}")
    head, tiles = _stored_tiles(info)
    width, height = info["padded"]
    tw, th = info["tile"]
    count = _count(info)                        # level 0; the mip levels' tiles follow and are kept
    old = _decode_tiles(info, tiles[:count])
    if grow:
        height = -(-image.height // th) * th
        tiles = tiles[:count] + [bytes(info["tile_bytes"])] * (_count(info, height) - count)
        count = len(tiles)
        taller_old = Image.new("RGBA", (width, height))
        taller_old.paste(old, (0, 0))
        old = taller_old
    new = old.copy()
    new.paste(image.convert("RGBA"), (0, 0))
    changed = False
    per_row = width // tw
    for index in range(count):
        x, y = index % per_row * tw, index // per_row * th
        box = (x, y, x + tw, y + th)
        tile = new.crop(box)
        if tile.tobytes() != old.crop(box).tobytes():
            tiles[index] = _encode_tile(info, tile)
            changed = True
    if not changed:
        return bytes(data)
    _old_head, old_indices = _tiles(info)
    blank = -1 if -1 in old_indices else None
    order: Dict[bytes, int] = {}
    indices: List[int] = []
    zero = bytes(info["tile_bytes"])
    for tile in tiles:
        if blank is not None and tile == zero:
            indices.append(-1)
            continue
        indices.append(order.setdefault(tile, len(order)))
    table = head + (struct.pack(f"<{len(indices)}i", *indices) if head else struct.pack(f"<{len(indices)}h", *indices))
    store = b"".join(order)
    table_c = level5.compress(table)
    store_c = level5.compress(store)
    store_c += b"\0" * (-len(store_c) % 4)
    out = bytearray(data[:info["table_at"]])
    if grow:
        struct.pack_into("<H", out, 0x12, image.height)
    struct.pack_into("<III", out, 0x34, len(table_c), (len(table_c) + 3) & ~3, len(store_c))
    out += table_c + b"\0" * (-len(table_c) % 4) + store_c
    return bytes(out)


def pixel_format(data: bytes) -> str:
    return _info(data)["format"]


def read(data: bytes, params: Dict[str, Any]) -> List[Texture]:
    return [Texture("", decode(data), pixel_format(data), max(1, data[0x0C]))]


def write(data: bytes, images: Dict[int, Image.Image], params: Dict[str, Any]) -> bytes:
    return encode(data, images[0]) if 0 in images else bytes(data)
