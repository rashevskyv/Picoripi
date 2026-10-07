"""GBA 4bpp tiles inside an LZ77-packed multiboot program (The Wind Waker's Tingle Tuner client).

The program is the one ``core.font_formats.gba_tiles`` reads (``program_offset``, ``program_address``,
``tail_pointers``). Each texture is a run of 8x8 tiles (32 bytes, rows of 4 bytes, low nibble first) inside an
LZ77 block of the unpacked program, shown ``columns`` tiles wide in the colours of one 16-colour bank of a BGR555
palette that lies unpacked in the program; colour 0 is transparent.

Params: the program keys and ``textures``: a list of ``{name, block, room, offset, tiles, columns, palette,
bank}`` -- ``block`` the address of the LZ77 block, ``room`` the bytes the packed block may take, ``offset``
the first tile's byte offset in the unpacked block, ``palette`` the palette address. Writing keeps the
nibble of every pixel whose colour did not change (banks may repeat a colour), maps the other pixels to the
nearest colour of the bank, packs the block again (Vram-safe) and refuses a block that outgrows its room.
"""
from __future__ import annotations

import struct
from typing import Any, Dict, List

from PIL import Image

from core.containers import lz10
from core.font_formats import gba_tiles
from core.texture_formats import Texture

TILE = 8


def _int(value: Any) -> int:
    return int(value, 0) if isinstance(value, str) else int(value)


def _bank(program: bytes, entry: Dict[str, Any], base: int) -> List[tuple]:
    at = _int(entry["palette"]) - base + 32 * _int(entry.get("bank", 0))
    colours = []
    for value in struct.unpack_from("<16H", program, at):
        r, g, b = value & 31, value >> 5 & 31, value >> 10 & 31
        colours.append((r * 255 // 31, g * 255 // 31, b * 255 // 31, 255))
    colours[0] = (0, 0, 0, 0)
    return colours


def _geometry(entry: Dict[str, Any]):
    tiles, columns = _int(entry["tiles"]), _int(entry.get("columns", 32))
    return tiles, columns, (columns * TILE, -(-tiles // columns) * TILE)


def _decode(block: bytes, entry: Dict[str, Any], colours: List[tuple]) -> Image.Image:
    tiles, columns, size = _geometry(entry)
    image = Image.new("RGBA", size, (0, 0, 0, 0))
    px = image.load()
    start = _int(entry.get("offset", 0))
    for tile in range(tiles):
        x0, y0 = (tile % columns) * TILE, (tile // columns) * TILE
        for y in range(TILE):
            for x in range(TILE):
                byte = block[start + tile * 32 + y * 4 + x // 2]
                px[x0 + x, y0 + y] = colours[byte >> 4 if x & 1 else byte & 15]
    return image


def _encode(block: bytearray, entry: Dict[str, Any], colours: List[tuple], old: Image.Image,
            new: Image.Image) -> None:
    tiles, columns, size = _geometry(entry)
    if new.size != size:
        raise ValueError(f"The image is {new.width}x{new.height}, the tiles {size[0]}x{size[1]}")
    before, after = old.load(), new.convert("RGBA").load()
    nearest: Dict[tuple, int] = {}

    def index(colour: tuple) -> int:
        if colour[3] < 128:
            return 0
        if colour not in nearest:
            nearest[colour] = min(range(1, 16), key=lambda i: sum((p - q) ** 2 for p, q in zip(colours[i][:3], colour[:3])))
        return nearest[colour]

    start = _int(entry.get("offset", 0))
    for tile in range(tiles):
        x0, y0 = (tile % columns) * TILE, (tile // columns) * TILE
        for y in range(TILE):
            for x in range(TILE):
                colour = after[x0 + x, y0 + y]
                if colour == before[x0 + x, y0 + y]:
                    continue
                at = start + tile * 32 + y * 4 + x // 2
                shift = 4 if x & 1 else 0
                block[at] = block[at] & ~(15 << shift) & 0xFF | index(colour) << shift


def read(data: bytes, params: Dict[str, Any]) -> List[Texture]:
    program = gba_tiles.read_program(data, params)
    base = _int(params["program_address"])
    out = []
    for entry in params.get("textures") or []:
        block = lz10.decompress(program, _int(entry["block"]) - base)[0]
        out.append(Texture(str(entry.get("name") or ""), _decode(block, entry, _bank(program, entry, base)), "GBA 4bpp"))
    return out


def write(data: bytes, images: Dict[int, Image.Image], params: Dict[str, Any]) -> bytes:
    program = bytearray(gba_tiles.read_program(data, params))
    base = _int(params["program_address"])
    entries = params.get("textures") or []
    blocks: Dict[int, bytearray] = {}
    for index, image in images.items():
        entry = entries[index]
        at = _int(entry["block"]) - base
        if at not in blocks:
            blocks[at] = bytearray(lz10.decompress(program, at)[0])
        colours = _bank(program, entry, base)
        _encode(blocks[at], entry, colours, _decode(blocks[at], entry, colours), image)
    changed = False
    for at, block in blocks.items():
        if bytes(block) == lz10.decompress(program, at)[0]:
            continue
        room = next(_int(e["room"]) for e in entries if _int(e["block"]) - base == at)
        packed = lz10.compress(bytes(block), vram=True)
        if len(packed) > room:
            raise ValueError(f"The tiles pack into {len(packed)} bytes; the program has room for {room}. "
                             "Use fewer colours or simpler shapes.")
        program[at:at + room] = packed + bytes(room - len(packed))
        changed = True
    return gba_tiles.replace_program(data, bytes(program), params) if changed else data
