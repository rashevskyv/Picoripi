"""GameCube / Wii TPL texture palettes (``00 20 AF 30``): several GX images, each with an optional palette.

Header: magic, u32 image count, u32 offset of the image table (u32 image header offset, u32 palette
header offset per image). Image header: u16 height, u16 width, u32 format, u32 data offset, ..., u8
max LOD at 0x22 (mip levels = max LOD + 1). Palette header: u16 entries, u8, u8, u32 format, u32 data
offset. Offsets count from the start of the TPL. The pixels and palettes are the BTI ones (``bti``).
"""
from __future__ import annotations

import struct
from typing import Any, Dict, List

from PIL import Image

from core.texture_formats import Texture, bti

MAGIC = b"\x00\x20\xaf\x30"


def detect(data: bytes) -> bool:
    return data[:4] == MAGIC


def _heads(data: bytes) -> List[Dict[str, int]]:
    if data[:4] != MAGIC:
        raise ValueError("Not a TPL texture palette")
    count, table = struct.unpack_from(">II", data, 4)
    out = []
    for index in range(count):
        image_at, palette_at = struct.unpack_from(">II", data, table + 8 * index)
        height, width, fmt, data_at = struct.unpack_from(">HHII", data, image_at)
        if fmt not in bti.FORMATS:
            raise ValueError(f"TPL image {index}: GX format {fmt} is not supported")
        head = {"format": fmt, "width": width, "height": height, "data": data_at, "mips": 1,
                "pal_format": 0, "pal_count": 0, "pal_offset": 0}
        if len(data) > image_at + 0x22 and data[image_at + 0x22] < 12:
            head["mips"] = data[image_at + 0x22] + 1
        if palette_at:
            count_entries, _unpacked, _pad, pal_format, pal_at = struct.unpack_from(">HBBII", data, palette_at)
            head.update(pal_format=pal_format, pal_count=count_entries, pal_offset=pal_at)
        out.append(head)
    return out


def read(data: bytes, params: Dict[str, Any]) -> List[Texture]:
    return [Texture(str(index), bti.read_image(data, head), bti.FORMATS[head["format"]], head["mips"])
            for index, head in enumerate(_heads(data))]


def write(data: bytes, images: Dict[int, Image.Image], params: Dict[str, Any]) -> bytes:
    out = bytearray(data)
    heads = _heads(data)
    changed = False
    for index, image in images.items():
        changed = bti.write_image(out, heads[index], image) or changed
    return bytes(out) if changed else data
