"""Atlus 3DS ``STEX`` textures (Shin Megami Tensei IV / Apocalypse): one PICA texture per file.

Header (little endian): ``STEX``, u32, u32 0xDE1 (GL_TEXTURE_2D), u32 width, u32 height, u32 GL type, u32 GL
format, u32 data size, u32 data offset (0x80), then a name. The GL (type, format) pair names the PICA format.
"""
from __future__ import annotations

import struct
from typing import Any, Dict, List

from PIL import Image

from core.texture_formats import Texture, pixels, surface

# (GL type, GL format) -> PICA format
GL = {(0x1401, 0x6752): "RGBA8", (0x1401, 0x6754): "RGB8", (0x1401, 0x6756): "A8", (0x1401, 0x6757): "L8",
      (0x1401, 0x6758): "LA8", (0x1401, 0x6759): "HILO8", (0x8034, 0x6752): "RGBA4", (0x8033, 0x6752): "RGBA5551",
      (0x8363, 0x6754): "RGB565", (0x6760, 0x6758): "LA4", (0x6761, 0x6756): "A4", (0x6761, 0x6757): "L4",
      (0x1401, 0x675A): "ETC1", (0x1401, 0x675B): "ETC1A4"}


def detect(data: bytes) -> bool:
    return data[:4] == b"STEX"


def _entry(data: bytes) -> Dict[str, Any]:
    if data[:4] != b"STEX":
        raise ValueError("Not an STEX texture")
    width, height, gl_type, gl_format, size, at = struct.unpack_from("<6I", data, 0x0C)
    fmt = GL.get((gl_type, gl_format))
    if fmt is None:
        raise ValueError(f"STEX GL type {gl_type:#x} / format {gl_format:#x} is not supported")
    codec = pixels.codec("pica:" + fmt)
    if surface.surface_bytes(codec, width, height) > len(data) - at:
        raise ValueError("STEX data is cut short")
    name = data[0x24:data.index(b"\0", 0x24)].decode("ascii", "replace") if data[0x24:0x25] not in (b"", b"\0") else ""
    return {"name": name, "codec": codec, "format": fmt, "at": at, "width": width, "height": height}


def read(data: bytes, params: Dict[str, Any]) -> List[Texture]:
    e = _entry(data)
    return [Texture(e["name"], surface.read(data, e["at"], e["codec"], e["width"], e["height"]), e["format"])]


def write(data: bytes, images: Dict[int, Image.Image], params: Dict[str, Any]) -> bytes:
    out = bytearray(data)
    e = _entry(data)
    for index, image in images.items():
        if index != 0:
            raise ValueError("An STEX file holds one texture")
        surface.write(out, e["at"], e["codec"], e["width"], e["height"], image)
    return bytes(out)
