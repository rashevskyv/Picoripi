"""Peace Walker (HD / Master Collection) texture packs ``*.txp``: DDS textures behind a small index.

Header (little-endian): ``u32 version, u32 id, u32 count, u32 count, u32, u32, u32 first table, u32 0,
u32 second table, ...``; the second table has 0x30-byte records whose fifth u32 is the file offset of a DDS file.
A DDS keeps its 0x80-byte header; its pixels start where the space left before the next texture (or the end of
the pack) is exactly the pixel data (Switch packs pad the header to 0x1000 bytes). Pixels are linear (DXT1 / DXT5,
or 32-bit BGRA), mip levels follow level 0 when the header says so.

Writing replaces the pixel data of a changed texture in place (mip levels made again from the new image); the
pack keeps its size and every other byte.
"""
from __future__ import annotations

import struct
from typing import Any, Dict, List, Tuple

from PIL import Image

from core.texture_formats import Texture, pixels

_FORMATS = {b"DXT1": ("BC1", 8), b"DXT5": ("BC3", 16), b"DXT3": ("BC2", 16)}


def detect(data: bytes) -> bool:
    if len(data) < 0x40:
        return False
    count, second = struct.unpack_from("<I", data, 8)[0], struct.unpack_from("<I", data, 32)[0]
    if not 0 < count < 4096 or not 0x20 <= second < len(data) - 0x30:
        return False
    at = struct.unpack_from("<I", data, second + 16)[0]
    return bytes(data[at:at + 4]) == b"DDS "


def _level_size(fmt: str, block: int, width: int, height: int) -> int:
    if fmt == "BGRA8":
        return width * height * 4
    return max(1, (width + 3) // 4) * max(1, (height + 3) // 4) * block


def _entries(data: bytes) -> List[Tuple[int, int, int, int, str, int, int]]:
    """``(DDS offset, pixel offset, width, height, pixel format, block bytes, mip count)`` of every texture."""
    count, second = struct.unpack_from("<I", data, 8)[0], struct.unpack_from("<I", data, 32)[0]
    starts = [struct.unpack_from("<I", data, second + 0x30 * i + 16)[0] for i in range(count)]
    following = sorted(set(starts)) + [len(data)]
    out = []
    for at in starts:
        if bytes(data[at:at + 4]) != b"DDS ":
            raise ValueError(f"No DDS at 0x{at:X} in the texture pack")
        height, width = struct.unpack_from("<II", data, at + 12)
        mips = max(1, struct.unpack_from("<I", data, at + 28)[0])
        fourcc = bytes(data[at + 0x54:at + 0x58])
        if fourcc in _FORMATS:
            fmt, block = _FORMATS[fourcc]
        elif struct.unpack_from("<I", data, at + 0x58)[0] == 32:
            fmt, block = "BGRA8", 4
        else:
            raise ValueError(f"DDS pixel format {fourcc!r} is not supported")
        total = sum(_level_size(fmt, block, max(1, width >> m), max(1, height >> m)) for m in range(mips))
        end = next(n for n in following if n > at)
        pixels_at = end - total if end - total >= at + 0x80 else at + 0x80
        out.append((at, pixels_at, width, height, fmt, block, mips))
    return out


def read(data: bytes, params: Dict[str, Any]) -> List[Texture]:
    out = []
    for index, (_at, start, width, height, fmt, block, mips) in enumerate(_entries(data)):
        size = _level_size(fmt, block, width, height)
        image = pixels.codec(fmt).decode(bytes(data[start:start + size]), width, height)
        out.append(Texture(f"{index:03d}", image.convert("RGBA"), fmt, mips))
    return out


def write(data: bytes, images: Dict[int, Image.Image], params: Dict[str, Any]) -> bytes:
    out = bytearray(data)
    for index, (_at, start, width, height, fmt, block, mips) in enumerate(_entries(data)):
        image = images.get(index)
        if image is None:
            continue
        image = image.convert("RGBA")
        if image.size != (width, height):
            raise ValueError(f"Texture {index}: the image is {image.width}x{image.height}, not {width}x{height}")
        codec = pixels.codec(fmt)
        old = codec.decode(bytes(data[start:start + _level_size(fmt, block, width, height)]), width, height)
        if old.convert("RGBA").tobytes() == image.tobytes():
            continue
        pos = start
        for level in range(mips):
            w, h = max(1, width >> level), max(1, height >> level)
            level_image = image if level == 0 else image.resize((w, h), Image.Resampling.BOX)
            if fmt != "BGRA8" and (w % 4 or h % 4):      # a block format: whole 4x4 blocks
                padded = Image.new("RGBA", (-(-w // 4) * 4, -(-h // 4) * 4))
                padded.paste(level_image, (0, 0))
                level_image = padded
            raw = codec.encode(level_image)
            out[pos:pos + len(raw)] = raw
            pos += _level_size(fmt, block, w, h)
    return bytes(out)
