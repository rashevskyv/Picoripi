"""3DS ``BCH`` (Nintendo H3D / "Ctr Binary") graphics files: the textures their GPU commands point at.

A BCH holds models, materials and textures; a Capcom file of pictures (Ace Attorney Trilogy 3DS: ``pack.dat``)
holds one texture and nothing else. The texture's size, pixel format and place are not in a table of their own: they
are PICA200 register writes in the GPU command block (``TEXUNIT0_DIM`` 0x82 = width << 16 | height, ``TEXUNIT0_ADDR1``
0x85 = byte offset into the data block, ``TEXUNIT0_TYPE`` 0x8e = pixel format). Header (little endian): ``BCH\\0``,
u8 backward / forward compatibility, u16 version, then u32 offsets of the contents, the string table, the GPU
commands and the data, the relocation table, and the five lengths. A command is a parameter word, a header word
(register, byte mask, extra-parameter count, consecutive flag) and the extra parameters, padded to 8 bytes.

Every distinct (size, format, offset) of texture unit 0 is one texture, in order of its data offset; writing
changes pixels in place (same size). A material that points at the same data shares the texture.
"""
from __future__ import annotations

import struct
from typing import Any, Dict, List, Tuple

from PIL import Image

from core.texture_formats import Texture, pixels, surface

PICA = {0: "RGBA8", 1: "RGB8", 2: "RGBA5551", 3: "RGB565", 4: "RGBA4", 5: "LA8", 6: "HILO8", 7: "L8",
        8: "A8", 9: "LA4", 10: "L4", 11: "A4", 12: "ETC1", 13: "ETC1A4"}
_DIM, _ADDR, _TYPE = 0x82, 0x85, 0x8E


def detect(data: bytes) -> bool:
    return len(data) > 0x38 and data[:4] == b"BCH\0"


def _commands(data: bytes, start: int, size: int):
    """``(register, value)`` of every GPU command in the block."""
    words = struct.unpack_from(f"<{size // 4}I", data, start)
    at = 0
    while at + 1 < len(words):
        value, head = words[at], words[at + 1]
        register, extra, consecutive = head & 0xFFFF, (head >> 20) & 0x7FF, head >> 31
        yield register, value
        for i in range(extra):
            nxt = words[at + 2 + i] if at + 2 + i < len(words) else 0
            yield register + (i + 1 if consecutive else 0), nxt
        at += 2 + extra + (extra & 1)


def _entries(data: bytes) -> List[Dict[str, Any]]:
    if not detect(data):
        raise ValueError("Not a BCH file")
    forward = data[5]
    if forward >= 0x21:
        raise ValueError(f"BCH version {forward:#x} (a separate data extension block) is not supported")
    _contents, _strings, gpu, base, _reloc, _clen, _slen, glen, dlen = struct.unpack_from("<IIIIIIIII", data, 8)
    found: Dict[Tuple[int, int, int], None] = {}
    state: Dict[str, int] = {}
    for register, value in _commands(data, gpu, glen):
        if register == _DIM:
            state["dim"] = value
        elif register == _ADDR:
            state["addr"] = value
        elif register == _TYPE and "dim" in state and "addr" in state and value in PICA:
            found[(state["dim"], state["addr"], value)] = None
    out = []
    for dim, addr, fmt in found:
        width, height = (dim >> 16) & 0x7FF, dim & 0x7FF
        codec = pixels.codec("pica:" + PICA[fmt])
        if not width or not height or addr + surface.surface_bytes(codec, width, height) > dlen:
            continue
        out.append({"at": base + addr, "width": width, "height": height, "format": PICA[fmt], "codec": codec})
    return sorted(out, key=lambda e: e["at"])


def read(data: bytes, params: Dict[str, Any]) -> List[Texture]:
    return [Texture("", surface.read(data, e["at"], e["codec"], e["width"], e["height"]), e["format"])
            for e in _entries(data)]


def write(data: bytes, images: Dict[int, Image.Image], params: Dict[str, Any]) -> bytes:
    out = bytearray(data)
    entries = _entries(data)
    for index, image in images.items():
        e = entries[index]
        surface.write(out, e["at"], e["codec"], e["width"], e["height"], image)
    return bytes(out)
