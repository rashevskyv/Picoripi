"""3DS BCH (H3D) model files: the textures they carry, found by their PICA texture commands.

A BCH keeps its textures as PICA register writes in the commands section: ``0x82`` (dimensions: width in bits
16-26, height in bits 0-10), ``0x85`` (address of level 0 in the raw data section), ``0x8E`` (pixel format, the
same numbers as CTPK). A block with non-zero dimensions is a texture; materials repeat the registers with zeros.
Textures are named ``tex<N>`` in file order. Only level 0 is written; a mip chain, when a texture has one, is left
as it was.

Header (little endian): ``BCH\\0``, u8 backward and forward compatibility, u16 converter version, u32 addresses of
the contents, strings, commands and raw data sections (then raw-extension when compatibility > 0x20, relocation),
lengths in the same order.
"""
from __future__ import annotations

import struct
from typing import Any, Dict, List

from PIL import Image

from core.texture_formats import Texture, pixels, surface

PICA = {0: "RGBA8", 1: "RGB8", 2: "RGBA5551", 3: "RGB565", 4: "RGBA4", 5: "LA8", 6: "HILO8", 7: "L8",
        8: "A8", 9: "LA4", 10: "L4", 11: "A4", 12: "ETC1", 13: "ETC1A4"}


def detect(data: bytes) -> bool:
    return data[:4] == b"BCH\0"


def _sections(data: bytes) -> Dict[str, int]:
    if data[:4] != b"BCH\0":
        raise ValueError("Not a BCH file")
    backward = data[4]
    ext = backward > 0x20
    contents, strings, commands, raw = struct.unpack_from("<4I", data, 8)
    at = 0x18
    if ext:
        at += 4
    at += 4                                    # relocation address
    lengths = struct.unpack_from("<4I", data, at)
    return {"commands": commands, "commands_len": lengths[2], "raw": raw, "raw_len": lengths[3],
            "contents": contents, "strings": strings}


def _blocks(data: bytes) -> List[Dict[str, Any]]:
    sec = _sections(data)
    out: List[Dict[str, Any]] = []
    regs: Dict[int, int] = {}
    pos, end = sec["commands"], sec["commands"] + sec["commands_len"]
    seen = set()
    while pos + 8 <= end:
        param, header = struct.unpack_from("<II", data, pos)
        reg, mask, extra, consecutive = header & 0xFFFF, header >> 16 & 0xF, header >> 20 & 0x7FF, header >> 31
        params = [param] + list(struct.unpack_from(f"<{extra}I", data, pos + 8)) if extra else [param]
        for i, value in enumerate(params):
            target = reg + i if consecutive else reg
            if mask == 0xF:
                regs[target] = value
            if target == 0x8E and regs.get(0x82):
                dim, fmt, addr = regs[0x82], value & 0xF, regs.get(0x85, 0)
                width, height = dim >> 16 & 0x7FF, dim & 0x7FF
                if fmt in PICA and width and height and addr not in seen:
                    seen.add(addr)
                    out.append({"width": width, "height": height, "format": PICA[fmt], "address": addr})
        words = 2 + extra
        pos += (words + words % 2) * 4
    return out


def _entries(data: bytes) -> List[Dict[str, Any]]:
    raw = _sections(data)["raw"]
    entries = []
    for index, block in enumerate(_blocks(data)):
        codec = pixels.codec("pica:" + block["format"])
        entries.append({"name": f"tex{index}", "codec": codec, "format": block["format"], "width": block["width"],
                        "height": block["height"], "at": raw + block["address"]})
    return entries


def read(data: bytes, params: Dict[str, Any]) -> List[Texture]:
    return [Texture(e["name"], surface.read(data, e["at"], e["codec"], e["width"], e["height"]), e["format"], 1)
            for e in _entries(data)]


def write(data: bytes, images: Dict[int, Image.Image], params: Dict[str, Any]) -> bytes:
    out = bytearray(data)
    entries = _entries(data)
    for index, image in images.items():
        entry = entries[index]
        surface.write(out, entry["at"], entry["codec"], entry["width"], entry["height"], image)
    return bytes(out)
