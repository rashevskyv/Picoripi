"""Layout images: BFLIM (``FLIM`` -- 3DS little endian, Wii U big endian) and 3DS BCLIM (``CLIM``).

The pixels come first, then a 0x28-byte footer: the file header (magic, byte order mark...) and an
``imag`` block. FLIM: u16 width, u16 height, u16 alignment, u8 format, u8 flags, u32 image size.
CLIM: u32 block size, u16 width, u16 height, u32 format.

3DS: a PICA texture of the next power-of-two size (at least 8), stored bottom row first; FLIM flag 4
or 8 stores it turned by 90 degrees. Wii U: a GX2 surface, flags = tile mode (low 5 bits) and the
swizzle (high 3 bits, bits 8-10 of the GX2 swizzle value), top row first.
"""
from __future__ import annotations

import struct
from typing import Any, Dict, List, Tuple

from PIL import Image

from core.texture_formats import Texture, gx2, pixels, surface

PICA_FLIM = {0: "L8", 1: "A8", 2: "LA4", 3: "LA8", 4: "HILO8", 5: "RGB565", 6: "RGB8", 7: "RGBA5551",
             8: "RGBA4", 9: "RGBA8", 10: "ETC1", 11: "ETC1A4", 12: "L4", 13: "A4", 18: "L4", 19: "A4"}
CAFE_FLIM = {0: "L8", 1: "A8", 3: "LA8", 5: "RGB565", 8: "RGBA4", 9: "RGBA8", 12: "BC1", 13: "BC2", 14: "BC3",
             15: "BC4L", 16: "BC4A", 17: "BC5LA", 20: "RGBA8", 21: "BC1", 22: "BC2", 23: "BC3"}
CAFE_NAMES = {20: "RGBA8_SRGB", 21: "BC1_SRGB", 22: "BC2_SRGB", 23: "BC3_SRGB"}
_BITS = {"L8": 8, "A8": 8, "LA8": 16, "RGB565": 16, "RGBA4": 16, "RGBA8": 32}


def detect(data: bytes) -> bool:
    return len(data) >= 0x28 and data[-0x28:-0x24] in (b"FLIM", b"CLIM")


def _info(data: bytes) -> Dict[str, Any]:
    foot = len(data) - 0x28
    magic = data[foot:foot + 4]
    if magic not in (b"FLIM", b"CLIM"):
        raise ValueError("Not a BFLIM / BCLIM image")
    big = data[foot + 4:foot + 6] == b"\xfe\xff"
    e = ">" if big else "<"
    imag = foot + struct.unpack_from(e + "H", data, foot + 6)[0]
    if magic == b"CLIM":
        width, height, fmt = struct.unpack_from(e + "HHI", data, imag + 8)
        return {"cafe": False, "width": width, "height": height, "format": PICA_FLIM[fmt], "name": PICA_FLIM[fmt],
                "flags": 0}
    width, height, _align, fmt, flags = struct.unpack_from(e + "HHHBB", data, imag + 8)
    table = CAFE_FLIM if big else PICA_FLIM
    if fmt not in table:
        raise ValueError(f"BFLIM pixel format {fmt} is not supported")
    return {"cafe": big, "width": width, "height": height, "format": table[fmt],
            "name": CAFE_NAMES.get(fmt, table[fmt]) if big else table[fmt], "flags": flags}


def _pow2(value: int) -> int:
    return max(8, 1 << (value - 1).bit_length())


# -- 3DS ------------------------------------------------------------------------------------------


def _pica_geometry(info: Dict[str, Any]) -> Tuple[int, int]:
    width, height = _pow2(info["width"]), _pow2(info["height"])
    return (height, width) if info["flags"] in (4, 8) else (width, height)


def _to_display(stored: Image.Image, flags: int) -> Image.Image:
    image = stored.transpose(Image.Transpose.FLIP_TOP_BOTTOM)
    if flags == 4:
        return image.transpose(Image.Transpose.ROTATE_90).transpose(Image.Transpose.FLIP_LEFT_RIGHT)
    if flags == 8:
        return image.transpose(Image.Transpose.ROTATE_270)
    return image


def _to_stored(display: Image.Image, flags: int) -> Image.Image:
    if flags == 4:
        display = display.transpose(Image.Transpose.FLIP_LEFT_RIGHT).transpose(Image.Transpose.ROTATE_270)
    elif flags == 8:
        display = display.transpose(Image.Transpose.ROTATE_90)
    return display.transpose(Image.Transpose.FLIP_TOP_BOTTOM)


# -- Wii U ----------------------------------------------------------------------------------------


def _cafe_layout(info: Dict[str, Any], codec: pixels.Codec):
    bw, bh = codec.block
    wide, high = -(-info["width"] // bw), -(-info["height"] // bh)
    bpp = codec.size * 8
    offsets = gx2.element_offsets(wide, high, bpp, info["flags"] & 0x1F, (info["flags"] >> 5) << 8)
    return offsets


def read(data: bytes, params: Dict[str, Any]) -> List[Texture]:
    info = _info(data)
    if info["cafe"]:
        codec = pixels.codec(info["format"])
        image = surface.read(data, 0, codec, info["width"], info["height"], _cafe_layout(info, codec))
    else:
        codec = pixels.codec("pica:" + info["format"])
        width, height = _pica_geometry(info)
        full = _to_display(surface.read(data, 0, codec, width, height), info["flags"])
        image = full.crop((0, 0, info["width"], info["height"]))
    return [Texture("", image, info["name"])]


def write(data: bytes, images: Dict[int, Image.Image], params: Dict[str, Any]) -> bytes:
    image = images.get(0)
    if image is None:
        return data
    info = _info(data)
    out = bytearray(data)
    if info["cafe"]:
        codec = pixels.codec(info["format"])
        surface.write(out, 0, codec, info["width"], info["height"], image, _cafe_layout(info, codec))
        return bytes(out)
    codec = pixels.codec("pica:" + info["format"])
    width, height = _pica_geometry(info)
    full = _to_display(surface.read(data, 0, codec, width, height), info["flags"])
    full.paste(image.convert("RGBA"), (0, 0))
    surface.write(out, 0, codec, width, height, _to_stored(full, info["flags"]))
    return bytes(out)
