"""EA SHPG shape files of the Wii (Spore Hero ``.gsh``, ``.lsi``, the page of an ``FntG`` font): GX textures.

Header: ``SHPG``, u32 LE file size, u32 BE image count, 4-character directory id, then per image a
4-character name and a u32 BE offset. An image is a chain of records: u8 code, u24 BE distance to the next
record (0: the last), u16 BE width and height, four u16 (the high nibble of the fourth: extra mip levels),
then the record's data. The first record holds the GX texels (``IMAGE_CODES``: every mip level, each padded
to whole tiles); a palette record follows a C4 / C8 image (``PALETTES``: IA8 / RGB565 / RGB5A3 entries as
u16, or 32-bit colours as two planes: the A,R pairs of every entry, then the G,B pairs); a ``0x70`` record holds the
full name. A palette image keeps its palette when every colour of the new image is in it; otherwise a
palette of the same size is made for the new image and written in place.
"""
from __future__ import annotations

import struct
from typing import Any, Dict, List

from PIL import Image

from core.texture_formats import Texture, pixels, surface

MAGIC = b"SHPG"
IMAGE_CODES = {0x15: "RGB5A3", 0x16: "RGBA8", 0x18: "C4", 0x19: "C8", 0x1E: "CMPR"}
_INDEXED = {0x18: (4, (8, 8)), 0x19: (8, (8, 4))}
PALETTES = {0x30: 0, 0x31: 1, 0x32: 2, 0x33: "RGBA8"}      # record code -> GX palette format (u16) or RGBA8
NAME = 0x70


def detect(data: bytes) -> bool:
    return data[:4] == MAGIC


def _records(data: bytes, at: int) -> List[Dict[str, int]]:
    out = []
    while True:
        code, nxt = data[at], int.from_bytes(data[at + 1:at + 4], "big")
        width, height = struct.unpack_from(">HH", data, at + 4)
        out.append({"code": code, "at": at, "width": width, "height": height,
                    "mips": 1 + (struct.unpack_from(">H", data, at + 14)[0] >> 12)})
        if not nxt or at + nxt >= len(data):
            return out
        at += nxt


def images(data: bytes, base: int = 0) -> List[Dict[str, Any]]:
    """``[{name, code, width, height, mips, data, palette}]`` of an SHPG at ``base`` in ``data``."""
    if data[base:base + 4] != MAGIC:
        raise ValueError("Not an SHPG shape file")
    return [image_at(data, base + struct.unpack_from(">I", data, base + 0x14 + 8 * index)[0],
                     data[base + 0x10 + 8 * index:base + 0x14 + 8 * index].rstrip(b"\0").decode("latin-1"))
            for index in range(struct.unpack_from(">I", data, base + 8)[0])]


def image_at(data: bytes, at: int, name: str = "") -> Dict[str, Any]:
    """The image whose record chain starts at ``at`` (also used without the SHPG header: an FntG font page)."""
    records = _records(data, at)
    image = records[0]
    if image["code"] not in IMAGE_CODES:
        raise ValueError(f"SHPG image {name}: record code {image['code']:#x} is not supported")
    palette = next((r for r in records[1:] if r["code"] in PALETTES), None)
    if image["code"] in _INDEXED and palette is None:
        raise ValueError(f"SHPG image {name}: no palette")
    full = next((r for r in records[1:] if r["code"] == NAME), None)
    if full is not None:
        name = data[full["at"] + 4:data.index(b"\0", full["at"] + 4)].decode("latin-1") or name
    return {"name": name, "code": image["code"], "width": image["width"], "height": image["height"],
            "mips": image["mips"], "data": image["at"] + 16, "palette": palette}


def _palette_codec(head: Dict[str, Any]):
    """``(read(data) -> colours, write(out, colours))`` of the image's palette record."""
    record = head["palette"]
    at, count, fmt = record["at"] + 16, record["width"] * record["height"], PALETTES[record["code"]]
    if fmt == "RGBA8":
        plane = -(-count // 16) * 32         # the A,R pairs of every entry, then the G,B pairs

        def read(data):
            return [(data[at + 2 * i + 1], data[at + plane + 2 * i], data[at + plane + 2 * i + 1], data[at + 2 * i])
                    for i in range(count)]

        def write(out, colours):
            for i, (r, g, b, a) in enumerate(colours):
                out[at + 2 * i:at + 2 * i + 2] = bytes((a, r))
                out[at + plane + 2 * i:at + plane + 2 * i + 2] = bytes((g, b))
        return read, write, count
    decode, encode = pixels.gx_palette_format(fmt)

    def read(data):
        return [decode(v) for v in struct.unpack_from(f">{count}H", data, at)]

    def write(out, colours):
        struct.pack_into(f">{count}H", out, at, *[encode(*c) for c in colours])
    return read, write, count


def palette(data: bytes, head: Dict[str, Any]) -> List[tuple]:
    """The colours of a C4 / C8 image's palette."""
    return _palette_codec(head)[0](data)


def _codec(head: Dict[str, Any], palette=None) -> pixels.Codec:
    code = head["code"]
    if code in _INDEXED:
        bits, tile = _INDEXED[code]
        return pixels.palette_codec(f"gx:{IMAGE_CODES[code]}", bits, palette, tile=tile)
    return pixels.codec(f"gx:{IMAGE_CODES[code]}")


def read_image(data: bytes, head: Dict[str, Any]) -> Image.Image:
    palette = _palette_codec(head)[0](data) if head["code"] in _INDEXED else None
    return surface.read(data, head["data"], _codec(head, palette), head["width"], head["height"])


def write_image(out: bytearray, head: Dict[str, Any], image: Image.Image) -> bool:
    """Store ``image`` and its mip levels; False when nothing changes."""
    image = image.convert("RGBA")
    if read_image(bytes(out), head).tobytes() == image.tobytes():
        return False
    mips = surface.mip_levels(image, head["mips"])
    palette, force = None, False
    if head["code"] in _INDEXED:
        read, write, count = _palette_codec(head)
        palette = read(out)
        used = {colour for level in mips for _n, colour in level.getcolors(maxcolors=1 << 20)}
        if not used <= set(palette):
            capacity = min(count, 1 << _INDEXED[head["code"]][0])
            colours = pixels.nearest_palette(mips[0], capacity)
            write(out, colours + [(0, 0, 0, 0)] * (count - len(colours)))
            palette, force = read(out), True
    codec = _codec(head, palette)
    at = head["data"]
    for level, level_image in enumerate(mips):
        width, height = max(1, head["width"] >> level), max(1, head["height"] >> level)
        surface.write(out, at, codec, width, height, level_image, force=force)
        at += surface.surface_bytes(codec, width, height)
    return True


def read(data: bytes, params: Dict[str, Any]) -> List[Texture]:
    return [Texture(head["name"], read_image(data, head), IMAGE_CODES[head["code"]], head["mips"])
            for head in images(data)]


def write(data: bytes, images_: Dict[int, Image.Image], params: Dict[str, Any]) -> bytes:
    out = bytearray(data)
    heads = images(data)
    changed = False
    for index, image in images_.items():
        changed = write_image(out, heads[index], image) or changed
    return bytes(out) if changed else data
