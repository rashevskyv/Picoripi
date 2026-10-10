"""Monolith Soft layout files (``.wilay``: ``LAGP`` and ``LAHD`` of the Switch Xenoblade games) as a set of
textures: every MIBL block inside (found by its ``LBIM`` footer, written back in place at the same size) and,
in a tutorial picture layout, the one JPEG it embeds (written back as a new JPEG; the header's offset + size
pair of the picture is updated, the rest of the file moves with it).

Textures are named ``#<n>`` in file order; a JPEG is ``jpeg``.
"""
from __future__ import annotations

import io
import struct
from typing import Any, Dict, List, Tuple

from PIL import Image

from core.texture_formats import Texture, mibl

MAGICS = (b"LAGP", b"LAHD")
JPEG_START, JPEG_END = b"\xff\xd8\xff", b"\xff\xd9"


def detect(data: bytes) -> bool:
    return bytes(data[:4]) in MAGICS


def blocks(data: bytes) -> List[Tuple[str, int, int]]:
    """``(kind, start, end)`` of every texture: ``mibl`` blocks and the ``jpeg``."""
    out, pos = [], 0
    while True:
        at = data.find(mibl.MAGIC, pos)
        if at < 0:
            break
        pos = at + 4
        if struct.unpack_from("<I", data, at - 4)[0] != 10001:
            continue
        end = at + 4
        out.append(("mibl", end - mibl.block_size(mibl.footer(data[end - mibl.FOOTER.size:end])), end))
    jpeg = _jpeg(data)
    if jpeg:
        out.append(("jpeg", *jpeg))
    return sorted(out, key=lambda item: item[1])


def _jpeg(data: bytes):
    """(start, end) of the picture a LAHD header names as an (offset, size) pair, or None."""
    for at in range(8, min(len(data), 0x400) - 8, 4):
        start, size = struct.unpack_from("<II", data, at)
        if (0 < size and start + size <= len(data) and data[start:start + 3] == JPEG_START
                and data[start + size - 2:start + size] == JPEG_END):
            return start, start + size
    return None


def read(data: bytes, params: Dict[str, Any]) -> List[Texture]:
    if not detect(data):
        raise ValueError("Not a wilay layout")
    out = []
    for n, (kind, start, end) in enumerate(blocks(data)):
        if kind == "jpeg":
            image = Image.open(io.BytesIO(bytes(data[start:end])))
            out.append(Texture("jpeg", image.convert("RGBA"), "JPEG"))
        else:
            texture = mibl.read(data[start:end], params)[0]
            out.append(Texture(f"#{n}", texture.image, texture.pixel_format, texture.mipmaps))
    return out


def _patch_jpeg_size(head: bytearray, start: int, old_size: int, new_size: int) -> None:
    pair = struct.pack("<II", start, old_size)
    at = head.find(pair)
    if at < 0:
        raise ValueError("The layout header does not name the picture's offset and size")
    struct.pack_into("<I", head, at + 4, new_size)


def write(data: bytes, images: Dict[int, Image.Image], params: Dict[str, Any]) -> bytes:
    found = blocks(data)
    out = bytes(data)
    for index in sorted(images, reverse=True):          # from the end, so earlier offsets stay valid
        kind, start, end = found[index]
        image = images[index]
        if kind == "jpeg":
            old = Image.open(io.BytesIO(out[start:end]))
            if image.size != old.size:
                raise ValueError(f"The image is {image.width}x{image.height}, the picture {old.width}x{old.height}")
            if image.convert("RGBA").tobytes() == old.convert("RGBA").tobytes():
                continue
            buffer = io.BytesIO()
            image.convert("RGB").save(buffer, format="JPEG", quality=int(params.get("jpeg_quality", 92)), subsampling=0)
            new = buffer.getvalue()
            head = bytearray(out[:start])
            _patch_jpeg_size(head, start, end - start, len(new))
            out = bytes(head) + new + out[end:]
        else:
            out = out[:start] + mibl.write(out[start:end], {0: image}, params) + out[end:]
    return out
