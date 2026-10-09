"""TIM2 pictures (``TIM2``, PlayStation 2 and PSP), alone or embedded in another file.

A TIM2 file: ``"TIM2"``, u8 version, u8 alignment (0: pictures follow the 16-byte header, 1: from 128), u16
picture count, 8 reserved bytes. Each picture: u32 total size, u32 CLUT size, u32 image size, u16 header size,
u16 CLUT colours, u8 picture format, u8 mip levels, u8 CLUT type (low bits: 1 16-bit, 2 24-bit, 3 32-bit
colours; bit 0x80 set: the entries are in plain order, else an 8-bit CLUT has the PS2 "CSM1" order, blocks of
8 entries swapped), u8 image type (1 16-bit, 2 24-bit, 3 32-bit, 4 4-bit index, 5 8-bit index), u16 width,
u16 height, then GS registers. The pixels follow the header (4-bit: low nibble first), the CLUT follows them.
A CLUT whose alpha never passes 0x80 uses the PS2 range (0x80 = opaque).

The textures of a file are the pictures of every TIM2 found in it (a TIM2 file, several back to back, or TIM2s
inside a program or a subtitle file), named by their order. Only the first mip level is read and written.
Writing keeps the CLUT: a new colour takes the nearest CLUT entry, unchanged pixels keep their bytes.
"""
from __future__ import annotations

import struct
from typing import Any, Dict, List

from PIL import Image

from core.texture_formats import Texture, pixels, surface

MAGIC = b"TIM2"
_INDEX_BITS = {4: 4, 5: 8}
_DIRECT = {1: "16-bit", 2: "24-bit", 3: "32-bit"}


def detect(data: bytes) -> bool:
    return bool(_pictures(data))


def _file_pictures(data: bytes, start: int) -> List[Dict[str, Any]]:
    version, align, count = struct.unpack_from("<BBH", data, start + 4)
    if version not in (3, 4) or align not in (0, 1) or not 0 < count <= 256:
        return []
    out, at = [], start + (128 if align else 16)
    for _ in range(count):
        if at + 48 > len(data):
            return []
        total, clut, image, head, colours = struct.unpack_from("<IIIHH", data, at)
        _fmt, levels, clut_type, image_type, width, height = struct.unpack_from("<BBBBHH", data, at + 16)
        bits = _INDEX_BITS.get(image_type) or {1: 16, 2: 24, 3: 32}.get(image_type)
        if (bits is None or not width or not height or head < 48 or at + total > len(data)
                or head + image + clut > total or width * height * bits // 8 > image):
            return []
        out.append({"at": at, "pixels": at + head, "clut": at + head + image, "colours": colours,
                    "clut_type": clut_type, "image_type": image_type, "bits": bits, "width": width,
                    "height": height, "levels": max(1, levels)})
        at += total
    return out


def _pictures(data: bytes) -> List[Dict[str, Any]]:
    out, at = [], data.find(MAGIC)
    while at >= 0:
        found = _file_pictures(data, at) if at + 16 <= len(data) else []
        out += found
        at = data.find(MAGIC, at + 4)
    return out


def _colour(raw: bytes, size: int) -> tuple:
    if size == 2:
        v = raw[0] | raw[1] << 8
        return (pixels._expand(v & 31, 5), pixels._expand(v >> 5 & 31, 5), pixels._expand(v >> 10 & 31, 5),
                255 if v & 0x8000 else 0)
    return (raw[0], raw[1], raw[2], raw[3] if size == 4 else 255)


def _palette(data: bytes, pic: Dict[str, Any]) -> List[tuple]:
    size = {1: 2, 2: 3, 3: 4}.get(pic["clut_type"] & 0x3F, 4)
    count = pic["colours"] or (1 << pic["bits"])
    colours = [_colour(data[pic["clut"] + i * size:pic["clut"] + (i + 1) * size], size) for i in range(count)]
    if size == 4 and max(c[3] for c in colours) <= 0x80:
        colours = [(r, g, b, min(255, a * 255 // 0x80)) for r, g, b, a in colours]
    if pic["bits"] == 8 and not pic["clut_type"] & 0x80 and len(colours) >= 32:
        colours = [colours[(i & ~0x18) | (i & 0x08) << 1 | (i & 0x10) >> 1] for i in range(len(colours))]
    return colours


def _codec(data: bytes, pic: Dict[str, Any]) -> pixels.Codec:
    if pic["bits"] in (4, 8):
        return pixels.palette_codec(f"TIM2 {pic['bits']}-bit", pic["bits"], _palette(data, pic), endian="<",
                                    low_first=True)
    if pic["bits"] == 16:
        return pixels.codec("psx:RGB555")
    raise ValueError(f"TIM2 {_DIRECT[pic['image_type']]} pictures are not supported")


def read(data: bytes, params: Dict[str, Any]) -> List[Texture]:
    pics = _pictures(data)
    if not pics:
        raise ValueError("No TIM2 picture in the file")
    return [Texture(str(i), surface.read(data, p["pixels"], _codec(data, p), p["width"], p["height"]),
                    f"TIM2 {p['bits']}-bit", p["levels"]) for i, p in enumerate(pics)]


def write(data: bytes, images: Dict[int, Image.Image], params: Dict[str, Any]) -> bytes:
    pics = _pictures(data)
    out = bytearray(data)
    for index, image in images.items():
        p = pics[index]
        if image.size != (p["width"], p["height"]):
            raise ValueError(f"TIM2 picture {index} is {p['width']}x{p['height']}, the new image is "
                             f"{image.size[0]}x{image.size[1]}")
        surface.write(out, p["pixels"], _codec(data, p), p["width"], p["height"], image)
    return bytes(out)
