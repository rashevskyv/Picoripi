"""Wii channel banner ``opening.bnr``: an IMET header, then a U8 archive whose ``meta/icon.bin`` holds TPL textures.

Layout: IMET at 0x40, U8 archive at 0x600. ``meta/icon.bin`` is an IMD5 header (32 bytes), then an LZ77 stream
of a U8 archive with ``arc/timg/*.tpl``. The largest texture of those files is the icon.
"""
from __future__ import annotations

from typing import Optional

from PIL import Image

from core.containers import lz10
from core.containers.u8_container import U8Container
from core.texture_formats import tpl

IMET_AT, U8_AT = 0x40, 0x600
U8_MAGIC = b"\x55\xaa\x38\x2d"


def is_banner(data: bytes) -> bool:
    return data[IMET_AT:IMET_AT + 4] == b"IMET" and data[U8_AT:U8_AT + 4] == U8_MAGIC


def _unwrap(stored: bytes) -> bytes:
    if stored[:4] == b"IMD5" and stored[32:36] == b"LZ77":
        return lz10.decompress(stored, 36)[0]
    return stored


def read(data: bytes) -> Optional[Image.Image]:
    if not is_banner(data):
        return None
    archive = U8Container(data[U8_AT:])
    names = [name for name in archive.list_files() if name.lower().endswith("icon.bin")]
    if not names:
        return None
    textures = U8Container(_unwrap(archive.read_file(names[0])))
    best = None
    for name in textures.list_files():
        if not name.lower().endswith(".tpl"):
            continue
        for texture in tpl.read(textures.read_file(name), {}):
            if best is None or texture.image.width * texture.image.height > best.width * best.height:
                best = texture.image
    return best
