"""Agatsuma ``RTEX`` textures of Code of Princess: the 3DS ``.rtx`` and the Switch EX ``.rtex``.

A 0x20-byte header (little endian): ``RTEX``, u32 0, u16 width, height (the picture), u16 stored width, height (the
texture: powers of two on the 3DS), u32 data offset (0x20), u32 data size, u16 pixel format, u16 flags (0x10 on the
3DS), u32 row pitch, u32 average colour. The data is the pixels, or ``RZ``, the big-endian u32 size of the plain
pixels and a zlib stream (the Switch). Pixel formats (the u16):

- 13 RGBA4 and 0x1002 / 0x4002 ETC1A4: PICA textures in 8x8 tiles, stored bottom row first (the picture is the
  top-left ``width`` x ``height`` of the flipped texture);
- 2 RGBA8, 20 RGB8 and 0x33 LA8 (the Switch): plain rows from the top.

An edited zlib texture is compressed again (the file changes size and the data size field follows); an unedited
one is written back byte for byte. Other formats (0x34, one byte per pixel on the Switch) are not read.
"""
from __future__ import annotations

import struct
import zlib
from typing import Any, Dict, List

from PIL import Image

from core.texture_formats import Texture, pixels, surface

PICA = {13: "RGBA4", 0x1002: "ETC1A4", 0x4002: "ETC1A4"}
LINEAR = {2: ("RGBA8", "RGBA", 4), 20: ("RGB8", "RGB", 3), 0x33: ("LA8", "LA", 2)}


def detect(data: bytes) -> bool:
    return len(data) >= 0x20 and data[:4] == b"RTEX" and struct.unpack_from("<H", data, 0x18)[0] in {*PICA, *LINEAR}


def _info(data: bytes) -> Dict[str, Any]:
    if not detect(data):
        raise ValueError("Not an RTEX texture of a known pixel format")
    width, height, stored_w, stored_h, at, _size, fmt = struct.unpack_from("<HHHHIIH", data, 8)
    info = {"width": width, "height": height, "stored_w": stored_w, "stored_h": stored_h, "at": at,
            "zlib": data[at:at + 2] == b"RZ", "fmt": fmt}
    if fmt in PICA:
        info.update(kind="pica", format=PICA[fmt], codec=pixels.codec("pica:" + PICA[fmt]))
    else:
        name, mode, bpp = LINEAR[fmt]
        info.update(kind="linear", format=name, mode=mode, bpp=bpp)
    return info


def _plain(data: bytes, info: Dict[str, Any]) -> bytes:
    """The pixel bytes of the stored size."""
    if info["zlib"]:
        return zlib.decompressobj().decompress(data[info["at"] + 6:])
    return data[info["at"]:]


def _full(data: bytes, info: Dict[str, Any]) -> Image.Image:
    plain = _plain(data, info)
    if info["kind"] == "linear":
        need = info["stored_w"] * info["stored_h"] * info["bpp"]
        if len(plain) < need:
            raise ValueError("The RTEX pixel data does not match its size")
        return Image.frombytes(info["mode"], (info["stored_w"], info["stored_h"]), plain[:need]).convert("RGBA")
    return surface.read(plain, 0, info["codec"], info["stored_w"], info["stored_h"]).transpose(
        Image.Transpose.FLIP_TOP_BOTTOM)


def read(data: bytes, params: Dict[str, Any]) -> List[Texture]:
    info = _info(data)
    full = _full(data, info)
    return [Texture("", full.crop((0, 0, info["width"], info["height"])), info["format"])]


def write(data: bytes, images: Dict[int, Image.Image], params: Dict[str, Any]) -> bytes:
    image = images.get(0)
    if image is None:
        return data
    info = _info(data)
    image = image.convert("RGBA")
    if image.size != (info["width"], info["height"]):
        raise ValueError(f"The image is {image.width}x{image.height}, the texture {info['width']}x{info['height']}")
    full = _full(data, info)
    before = full.tobytes()
    full.paste(image, (0, 0))
    if full.tobytes() == before:
        return data
    plain = bytearray(_plain(data, info))
    if info["kind"] == "linear":
        raw = full.convert(info["mode"]).tobytes()
        plain[:len(raw)] = raw
    else:
        surface.write(plain, 0, info["codec"], info["stored_w"], info["stored_h"],
                      full.transpose(Image.Transpose.FLIP_TOP_BOTTOM))
    if not info["zlib"]:
        return bytes(data[:info["at"]]) + bytes(plain) + bytes(data[info["at"] + len(plain):])
    packed = b"RZ" + struct.pack(">I", len(plain)) + zlib.compress(bytes(plain), 9)
    out = bytearray(data[:info["at"]]) + packed
    struct.pack_into("<I", out, 0x14, len(packed))
    return bytes(out)
