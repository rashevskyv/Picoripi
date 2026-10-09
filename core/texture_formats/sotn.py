"""Castlevania: Symphony of the Night (PlayStation) pictures: VRAM tile blocks and nibble-packed images.

``sotn_blocks`` -- the ``F_*.BIN`` files (title screen, HUD, game over, file select): blocks of
0x2000 bytes, each a 128x128 4-bit (or 64x128 8-bit) piece of VRAM. The game puts block ``i`` at
column ``(i // 4) * 2 + i % 2`` and row ``(i // 2) % 2`` of its tile page; the picture shows the
listed blocks in that arrangement. Params: ``bpp`` (4 or 8), ``blocks`` (``[first, count]``, default
all), ``clut`` (a CLUT inside the file: ``{"offset": n}``) or ``palette`` (hex of the 16-bit colours,
for a CLUT kept in another file); without either the pixels show as grey levels (index * 17 / index).

``sotn_cmp`` -- an image packed with the game's nibble coder (``DecompressData``): an 8-byte
dictionary, then 4-bit codes (literal nibbles, nibble repeats, zero runs, dictionary entries, 0xF
ends). Params: ``offset``, ``width`` / ``height`` (4-bit pixels), ``room`` (bytes the packed image
may take; default its present size), ``palette`` / ``clut`` as above. Writing packs the new picture
again and fails when it does not fit its room; an unchanged picture keeps its bytes.
"""
from __future__ import annotations

import struct
from types import SimpleNamespace
from typing import Any, Dict, List, Optional, Tuple

from PIL import Image

from core.texture_formats import Texture, pixels, surface

BLOCK = 0x2000


def _int(value: Any) -> int:
    return int(value, 0) if isinstance(value, str) else int(value)


def _palette(data: bytes, params: Dict[str, Any], bits: int) -> Optional[List[tuple]]:
    decode, _encode = pixels.psx_clut()
    count = 1 << bits
    if params.get("palette"):
        raw = bytes.fromhex(str(params["palette"]))
        return [decode(v) for v in struct.unpack_from(f"<{len(raw) // 2}H", raw)][:count]
    clut = params.get("clut")
    if clut:
        at = _int(clut["offset"])
        return [decode(v) for v in struct.unpack_from(f"<{count}H", data, at)]
    return None


def _codec(data: bytes, params: Dict[str, Any], bits: int) -> pixels.Codec:
    palette = _palette(data, params, bits)
    if palette is None:
        return pixels.codec("psx:4bpp" if bits == 4 else "psx:8bpp")
    return pixels.palette_codec(f"psx:CI{bits}", bits, palette, endian="<", low_first=True)


# ---------------------------------------------------------------- tile blocks

def _blocks(data: bytes, params: Dict[str, Any]) -> List[int]:
    first, count = params.get("blocks") or (0, len(data) // BLOCK)
    return list(range(_int(first), _int(first) + _int(count)))


def _place(index: int) -> Tuple[int, int]:
    return (index // 4) * 2 + index % 2, (index // 2) % 2


def _geometry(data: bytes, params: Dict[str, Any]):
    bits = _int(params.get("bpp", 4))
    width = 128 if bits == 4 else 64
    blocks = _blocks(data, params)
    places = [_place(i) for i in blocks]
    left, top = min(p[0] for p in places), min(p[1] for p in places)
    columns = max(p[0] for p in places) - left + 1
    rows = max(p[1] for p in places) - top + 1
    return bits, width, blocks, [(c - left, r - top) for c, r in places], columns, rows


def read_blocks(data: bytes, params: Dict[str, Any]) -> List[Texture]:
    bits, width, blocks, places, columns, rows = _geometry(data, params)
    codec = _codec(data, params, bits)
    sheet = Image.new("RGBA", (columns * width, rows * 128))
    for index, (column, row) in zip(blocks, places):
        sheet.paste(surface.read(data, index * BLOCK, codec, width, 128), (column * width, row * 128))
    return [Texture(str(params.get("name") or ""), sheet, f"psx:{bits}bpp")]


def write_blocks(data: bytes, images: Dict[int, Image.Image], params: Dict[str, Any]) -> bytes:
    out = bytearray(data)
    bits, width, blocks, places, columns, rows = _geometry(data, params)
    codec = _codec(data, params, bits)
    image = images.get(0)
    if image is None:
        return bytes(out)
    image = image.convert("RGBA")
    if image.size != (columns * width, rows * 128):
        raise ValueError(f"The image is {image.width}x{image.height}, the picture {columns * width}x{rows * 128}")
    for index, (column, row) in zip(blocks, places):
        piece = image.crop((column * width, row * 128, column * width + width, row * 128 + 128))
        surface.write(out, index * BLOCK, codec, width, 128, piece)
    return bytes(out)


# ---------------------------------------------------------------- nibble coder

def inflate(data: bytes, offset: int) -> Tuple[bytes, int]:
    """``(unpacked bytes, packed size)`` of the image at ``offset``."""
    dictionary = data[offset:offset + 8]
    pos = offset + 8
    high = True
    out: List[int] = []

    def nibble() -> int:
        nonlocal pos, high
        if pos >= len(data):
            raise ValueError("packed picture runs past the end of the file")
        if high:
            high = False
            return data[pos] >> 4
        high = True
        pos += 1
        return data[pos - 1] & 15

    while True:
        op = nibble()
        if op == 0:
            amount = (nibble() << 4) + nibble() + 0x13
            out += [0] * amount
        elif op == 1:
            out.append(nibble())
        elif op == 2:
            out += [nibble()] * 2
        elif op == 3:
            out += [nibble(), nibble()]
        elif op == 4:
            out += [nibble(), nibble(), nibble()]
        elif op == 5:
            value = nibble()
            out += [value] * (nibble() + 3)
        elif op == 6:
            out += [0] * (nibble() + 3)
        elif op == 15:
            if not high:
                pos += 1
            break
        else:
            entry = dictionary[op - 7]
            kind, amount = entry & 0xF0, entry & 0x0F
            if kind == 0x10:
                out.append(amount)
            elif kind == 0x20:
                out += [amount, amount]
            elif kind == 0x60:
                out += [0] * (amount + 3)
        if len(out) > 0x80000:
            raise ValueError("not a packed picture")
    if len(out) % 2:
        out.append(0)
    packed = bytes(out[i] | out[i + 1] << 4 for i in range(0, len(out), 2))
    return packed, pos - offset


def deflate(unpacked: bytes, dictionary: bytes) -> bytes:
    """Pack bytes with the game's coder: the shortest code stream (dynamic programming over the nibbles),
    using the dictionary entries that match."""
    nibbles: List[int] = []
    for byte in unpacked:
        nibbles += [byte & 15, byte >> 4]
    single = {e & 15: 7 + i for i, e in enumerate(dictionary) if e & 0xF0 == 0x10}
    double = {e & 15: 7 + i for i, e in enumerate(dictionary) if e & 0xF0 == 0x20}
    zeros = {(e & 15) + 3: 7 + i for i, e in enumerate(dictionary) if e & 0xF0 == 0x60}
    n = len(nibbles)
    run = [1] * (n + 1)                     # length of the run of equal nibbles starting at i
    for i in range(n - 2, -1, -1):
        if nibbles[i] == nibbles[i + 1]:
            run[i] = run[i + 1] + 1
    cost = [0] * (n + 1)
    choice: List[Tuple[int, List[int]]] = [(0, [])] * (n + 1)
    for i in range(n - 1, -1, -1):
        value = nibbles[i]
        options: List[Tuple[int, List[int]]] = [(1, [single[value]] if value in single else [1, value])]
        if i + 1 < n:
            options.append((2, [3, value, nibbles[i + 1]]))
        if i + 2 < n:
            options.append((3, [4, value, nibbles[i + 1], nibbles[i + 2]]))
        length = run[i]
        if length >= 2:
            options.append((2, [double[value]] if value in double else [2, value]))
        for take in range(3, min(length, 18) + 1):
            if value == 0:
                options.append((take, [zeros[take]] if take in zeros else [6, take - 3]))
            else:
                options.append((take, [5, value, take - 3]))
        if value == 0 and length >= 0x13:
            take = min(length, 0xFF + 0x13)
            options.append((take, [0, (take - 0x13) >> 4, (take - 0x13) & 15]))
        best = None
        for take, code in options:
            total = len(code) + cost[i + take]
            if best is None or total < best[0]:
                best = (total, take, code)
        cost[i] = best[0]
        choice[i] = (best[1], best[2])
    codes: List[int] = []
    i = 0
    while i < n:
        take, code = choice[i]
        codes += code
        i += take
    codes.append(15)
    if len(codes) % 2:
        codes.append(0)
    return bytes(dictionary) + bytes(codes[k] << 4 | codes[k + 1] for k in range(0, len(codes), 2))


def _cmp_geometry(data: bytes, params: Dict[str, Any]):
    offset = _int(params["offset"])
    width, height = _int(params.get("width", 128)), _int(params.get("height", 128))
    unpacked, size = inflate(data, offset)
    room = _int(params.get("room") or size)
    return offset, width, height, unpacked, size, room


def read_cmp(data: bytes, params: Dict[str, Any]) -> List[Texture]:
    offset, width, height, unpacked, _size, _room = _cmp_geometry(data, params)
    buffer = unpacked.ljust(width * height // 2, b"\0")
    image = surface.read(buffer, 0, _codec(data, params, 4), width, height)
    return [Texture(str(params.get("name") or ""), image, "psx:4bpp")]


def write_cmp(data: bytes, images: Dict[int, Image.Image], params: Dict[str, Any]) -> bytes:
    image = images.get(0)
    if image is None:
        return bytes(data)
    offset, width, height, unpacked, size, room = _cmp_geometry(data, params)
    buffer = bytearray(unpacked.ljust(width * height // 2, b"\0"))
    if not surface.write(buffer, 0, _codec(data, params, 4), width, height, image.convert("RGBA")):
        return bytes(data)
    packed = deflate(bytes(buffer[:max(len(unpacked), 1)]), data[offset:offset + 8])
    if len(packed) > room:
        raise ValueError(f"The packed picture takes {len(packed)} bytes, the game has room for {room}; "
                         f"use fewer colours or simpler shapes")
    out = bytearray(data)
    out[offset:offset + room] = packed + bytes(room - len(packed))
    return bytes(out)


blocks = SimpleNamespace(read=read_blocks, write=write_blocks)
packed = SimpleNamespace(read=read_cmp, write=write_cmp)
