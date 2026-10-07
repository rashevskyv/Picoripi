"""Policenauts (PlayStation) picture packs: the ``*.PAK`` / ``*.CPK`` members of ``PAK.DPK`` (title, menus, act
cards, staff roll, the English patch's story pages).

A pack (big-endian): u32 item count, u32 offset of each item from the end of that table. An item whose
first byte is 0x80 or 0x90 is a picture::

    u16 flags, u16 (height - 1) << 6 | mode, u16 ?, u16 (width - 1) in the low 10 bits,
    32 colours (u16, 15-bit BGR, 0 = transparent; the palette of a palette mode), then one record a row.

Mode 0x16 is 15-bit colour (a value is 4 nibbles, the row head 2 bytes), mode 3 a 16-colour palette (a
value is 1 nibble, the row head 1 byte).
A row: head = row bytes / 4 - 2, then a nibble stream of operations: ``11nnnnnn`` value = n + 1 times
the value, ``01nnnnnn`` values = n + 1 values, ``10nnnnnn`` = n + 1 transparent pixels, a 0 nibble ends
the row (the rest is transparent); a full row needs no end. Rows the data does not reach are transparent.
The row is padded to 4 bytes (a value may read into the next row's head: the game reads past it).

Modes 1, 2, 4 and 5 (minigame sprites; their values do not fit the palette above) are not read; such items are left out of the list. Writing encodes
the changed pictures again (the pack is rebuilt around them) and keeps every other item's bytes.
"""
from __future__ import annotations

import struct
from typing import Any, Dict, List, Optional, Tuple

from PIL import Image

from core.texture_formats import Texture

HEADER = 0x48
_MODES = {0x16: (4, 2, "15-bit"), 0x03: (1, 1, "4-bit")}   # value nibbles, head bytes


def _items(data: bytes) -> List[bytes]:
    if len(data) < 8:
        raise ValueError("Not a Policenauts picture pack")
    count = struct.unpack_from(">I", data, 0)[0]
    base = 4 + 4 * count
    if not 0 < count < 5000 or base > len(data):
        raise ValueError("Not a Policenauts picture pack")
    offsets = list(struct.unpack_from(f">{count}I", data, 4))
    if offsets[0] != 0 or offsets != sorted(offsets) or base + offsets[-1] > len(data):
        raise ValueError("Not a Policenauts picture pack")
    ends = offsets[1:] + [len(data) - base]
    return [data[base + a:base + b] for a, b in zip(offsets, ends)]


def _pack(items: List[bytes]) -> bytes:
    offsets, pos = [], 0
    for item in items:
        offsets.append(pos)
        pos += len(item)
    return struct.pack(f">I{len(items)}I", len(items), *offsets) + b"".join(items)


def _shape(item: bytes) -> Optional[Tuple[int, int, int]]:
    """(width, height, mode) of a picture item this module reads, else None."""
    if len(item) < HEADER or item[0] not in (0x80, 0x90):
        return None
    _flags, w1, _w2, w3 = struct.unpack_from(">4H", item, 0)
    mode = w1 & 0x3F
    return ((w3 & 0x3FF) + 1, (w1 >> 6) + 1, mode) if mode in _MODES else None


def decode(item: bytes) -> Tuple[int, int, List[int]]:
    """(width, height, values) of a picture item: colours (15-bit) or palette indices, 0 = transparent."""
    shape = _shape(item)
    if shape is None:
        raise ValueError("not a picture this module reads")
    width, height, mode = shape
    vn, hb, _name = _MODES[mode]
    nib = item.hex() + "0" * 16
    values: List[int] = []
    pos = HEADER
    for y in range(height):
        if pos + hb > len(item):
            values += [0] * (width * (height - y))
            break
        head = int.from_bytes(item[pos:pos + hb], "big")
        q = (pos + hb) * 2
        row: List[int] = []
        while len(row) < width and nib[q] != "0":
            op = int(nib[q:q + 2], 16)
            q += 2
            n = (op & 0x3F) + 1
            if op >= 0xC0:
                row += [int(nib[q:q + vn], 16)] * n
                q += vn
            elif op >= 0x80:
                row += [0] * n
            elif op >= 0x40:
                row += [int(nib[q + k * vn:q + (k + 1) * vn], 16) for k in range(n)]
                q += vn * n
            else:
                raise ValueError(f"row {y}: unknown operation {op:02X}")
        if len(row) > width:
            raise ValueError(f"row {y} is {len(row)} pixels, the picture {width}")
        values += row + [0] * (width - len(row))
        pos += (head + 2) * 4
    return width, height, values


def _encode_row(row: List[int], vn: int, hb: int) -> bytes:
    out: List[str] = []
    width = len(row)
    i = 0
    while i < width:
        value = row[i]
        if not any(row[i:]):
            out.append("0" if vn < 4 else "00")
            break
        run = 1
        while i + run < width and row[i + run] == value and run < 64:
            run += 1
        if value == 0:
            out.append(f"{0x80 | run - 1:02x}")
        elif run >= 2:
            out.append(f"{0xC0 | run - 1:02x}{value:0{vn}x}")
        else:
            start = i
            while i < width and i - start < 64 and row[i] and not (i + 1 < width and row[i + 1] == row[i]):
                i += 1
            if i == start:
                i += 1
            out.append(f"{0x40 | i - start - 1:02x}" + "".join(f"{v:0{vn}x}" for v in row[start:i]))
            continue
        i += run
    stream = "".join(out)
    stream += "0" * (len(stream) % 2)
    body = bytes.fromhex(stream)
    size = max(8, (hb + len(body) + 3) // 4 * 4)
    head = size // 4 - 2
    if head >= 1 << (8 * hb):
        raise ValueError("a row is too long for its head")
    return head.to_bytes(hb, "big") + body + bytes(size - hb - len(body))


def encode(item: bytes, values: List[int]) -> bytes:
    """The item with its rows written from ``values`` (the header and palette are kept)."""
    width, height, mode = _shape(item)  # type: ignore[misc]
    vn, hb, _name = _MODES[mode]
    rows = [_encode_row(values[y * width:(y + 1) * width], vn, hb) for y in range(height)]
    return item[:HEADER] + b"".join(rows)


def _rgba(value: int) -> Tuple[int, int, int, int]:
    if value == 0:
        return 0, 0, 0, 0
    r, g, b = value & 31, (value >> 5) & 31, (value >> 10) & 31
    return r << 3 | r >> 2, g << 3 | g >> 2, b << 3 | b >> 2, 255


def _colour(pixel: Tuple[int, int, int, int]) -> int:
    r, g, b, a = pixel
    if a < 128:
        return 0
    return ((r >> 3) | (g >> 3) << 5 | (b >> 3) << 10) or 0x8000


def _palette(item: bytes) -> List[int]:
    return list(struct.unpack_from(">32H", item, 8))


def _image(item: bytes) -> Image.Image:
    width, height, values = decode(item)
    if _shape(item)[2] == 0x16:  # type: ignore[index]
        colours = [_rgba(v) for v in values]
    else:
        palette = _palette(item)
        colours = [_rgba(palette[v]) if v < len(palette) else (0, 0, 0, 0) for v in values]
    image = Image.new("RGBA", (width, height))
    image.putdata(colours)
    return image


def _pictures(items: List[bytes]) -> List[int]:
    """Item numbers of the pictures this module reads (decoding checked)."""
    out = []
    for number, item in enumerate(items):
        if _shape(item) is None:
            continue
        try:
            decode(item)
        except (ValueError, IndexError):
            continue
        out.append(number)
    return out


def read(data: bytes, params: Dict[str, Any]) -> List[Texture]:
    items = _items(data)
    return [Texture(f"{number:03d}", _image(items[number]), f"Policenauts {_MODES[_shape(items[number])[2]][2]}")
            for number in _pictures(items)]


def write(data: bytes, images: Dict[int, Image.Image], params: Dict[str, Any]) -> bytes:
    items = _items(data)
    pictures = _pictures(items)
    changed = False
    for index, image in images.items():
        number = pictures[index]
        item = items[number]
        width, height, old = decode(item)
        image = image.convert("RGBA")
        if image.size != (width, height):
            raise ValueError(f"picture {number} is {width}x{height}, the new image {image.size[0]}x{image.size[1]}")
        new_pixels = list(image.getdata())
        direct = _shape(item)[2] == 0x16  # type: ignore[index]
        palette = _palette(item)
        limit = 16
        colours = [_rgba(c) for c in palette[:limit]]
        cache: Dict[Tuple[int, int, int, int], int] = {}
        values = []
        for value, pixel in zip(old, new_pixels):
            if direct:
                values.append(value if _rgba(value) == pixel else _colour(pixel))
                continue
            if value < len(colours) and colours[value] == pixel:
                values.append(value)
                continue
            found = cache.get(pixel)
            if found is None:
                if pixel[3] < 128:
                    found = 0
                else:
                    found = min(range(1, limit), key=lambda i: (colours[i][3] == 0) * 10 ** 6 + sum(
                        (colours[i][k] - pixel[k]) ** 2 for k in range(3)))
                cache[pixel] = found
            values.append(found)
        if values != old:
            items[number] = encode(item, values)
            changed = True
    return _pack(items) if changed else bytes(data)
