"""Next Level Games 3DS texture bundles (Luigi's Mansion: Dark Moon): a ``.data`` / ``.dict`` pair's texture table
and pixel member joined as one file.

The workspace's ``1_unpack.bat`` writes a bundle as ``<name>.data/bundle.nlgb``: ``NLGB``, u32 size of the table
member, u32 size of the pixel member, the table member, the pixel member. The table member starts with 0x38-byte
``Powe`` entries (magic ``0xE977D350``, u32 id, u32 byte length with mip levels, u32 id again, u16 width and
u16 height at 0x18, byte ``0x11 * levels`` at 0x1F, byte format at 0x34: 12 ETC1, 13 ETC1A4); what follows is the
bundle's other data (a font bundle's glyph description, see ``core.font_formats.nlg_font``). The pixel member holds
the textures one after the other, each with its mip levels, stored bottom row first. Writing changes pixels in
place; mip levels are made again from a changed picture.

The Switch version (Luigi's Mansion 2 HD) keeps the textures inside the one member that also holds the font
descriptions: ``<name>.data/bundle.nlgh`` is ``NLGH`` and that member. Each texture is a ``Powe`` entry of 0x30
bytes (same magic and fields; the byte length at 4 + 4 is the DDS file) followed by a DDS file (DXT1 or DXT5, top
row first, mip levels down to 4x4). Entries follow each other with padding; the list ends at the first place
without ``Powe`` + ``DDS ``.
"""
from __future__ import annotations

import struct
from typing import Any, Dict, List, Tuple

from PIL import Image

from core.texture_formats import Texture, pixels, surface

MAGIC = b"NLGB"
MAGIC_HD = b"NLGH"
HD_ENTRY = 0x30
_HD_FORMATS = {b"DXT1": "BC1", b"DXT5": "BC3"}
POWE = struct.pack("<I", 0xE977D350)
ENTRY = 0x38
_FORMATS = {12: "pica:ETC1", 13: "pica:ETC1A4"}


def is_bundle(data: bytes) -> bool:
    return bytes(data[:4]) in (MAGIC, MAGIC_HD)


def is_hd_table(member: bytes) -> bool:
    return member[:4] == POWE and member[HD_ENTRY:HD_ENTRY + 4] == b"DDS "


def is_hd(data: bytes) -> bool:
    return bytes(data[:4]) == MAGIC_HD


def join_hd(member: bytes) -> bytes:
    return MAGIC_HD + member


detect = is_bundle


def split(data: bytes) -> Tuple[bytes, bytes]:
    """``(table member, pixel member)`` of a bundle file."""
    if not is_bundle(data):
        raise ValueError("not a Next Level Games bundle (NLGB)")
    if is_hd(data):                          # one member holds the descriptions and the textures
        member = bytes(data[4:])
        return member, member
    size2, size3 = struct.unpack_from("<II", data, 4)
    return bytes(data[12:12 + size2]), bytes(data[12 + size2:12 + size2 + size3])


def join(table: bytes, pixels_member: bytes) -> bytes:
    return MAGIC + struct.pack("<II", len(table), len(pixels_member)) + table + pixels_member


def _hd_entries(member: bytes) -> List[Dict[str, Any]]:
    """The Powe + DDS textures of a Switch bundle member; ``offset`` is that of the DDS pixel data."""
    out, at = [], 0
    while True:
        at = member.find(POWE, at)
        if at < 0 or at + HD_ENTRY + 128 > len(member):
            break
        dds = at + HD_ENTRY
        if member[dds:dds + 4] == b"DDS " and member[dds + 84:dds + 88] in _HD_FORMATS:
            _magic, tid, length, _again = struct.unpack_from("<IIII", member, at)
            height, width, _pitch, _depth, mips = struct.unpack_from("<IIIII", member, dds + 12)
            out.append({"id": tid, "width": width, "height": height, "levels": max(1, mips), "hd": True,
                        "format": _HD_FORMATS[member[dds + 84:dds + 88]], "length": length,
                        "offset": dds + 128, "at": at})
            at = dds + length
        else:
            at += 4
    return out


def entries(table: bytes) -> List[Dict[str, Any]]:
    """The textures of a table member: id, width, height, mip levels, format code, offset in the pixel member."""
    if is_hd_table(table):
        return _hd_entries(table)
    out, at, offset = [], 0, 0
    while table[at:at + 4] == POWE and at + ENTRY <= len(table):
        _magic, tid, length, _again = struct.unpack_from("<IIII", table, at)
        width, height = struct.unpack_from("<HH", table, at + 0x18)
        out.append({"id": tid, "width": width, "height": height, "levels": max(1, table[at + 0x1F] // 0x11),
                    "format": table[at + 0x34], "length": length, "offset": offset, "at": at})
        offset += length
        at += ENTRY
    return out


def table_end(table: bytes) -> int:
    """Offset in the table member just past the ``Powe`` entries."""
    return len(entries(table)) * ENTRY


def _codec(entry: Dict[str, Any]) -> pixels.Codec:
    if entry.get("hd"):
        return pixels.codec(entry["format"])
    try:
        return pixels.codec(_FORMATS[entry["format"]])
    except KeyError:
        raise ValueError(f"unsupported Next Level Games texture format {entry['format']}") from None


def _levels(entry: Dict[str, Any]) -> List[Tuple[int, int, int, int]]:
    """``(offset in the pixel member, width, height, bytes)`` per mip level."""
    codec, at, out = _codec(entry), entry["offset"], []
    for level in range(entry["levels"]):
        floor = 1 if entry.get("hd") else 8
        w, h = max(floor, entry["width"] >> level), max(floor, entry["height"] >> level)
        size = surface.surface_bytes(codec, w, h)
        out.append((at, w, h, size))
        at += size
    return out


def read_texture(entry: Dict[str, Any], pixel_member: bytes) -> Image.Image:
    at, w, h, _size = _levels(entry)[0]
    image = surface.read(pixel_member, at, _codec(entry), w, h)
    return image if entry.get("hd") else image.transpose(Image.Transpose.FLIP_TOP_BOTTOM)


def write_texture(out: bytearray, entry: Dict[str, Any], image: Image.Image) -> bool:
    """Draw ``image`` (upright) into the pixel member ``out``; the lower mip levels are made again. True if changed."""
    codec = _codec(entry)
    levels = _levels(entry)
    flipped = image.convert("RGBA")
    if not entry.get("hd"):
        flipped = flipped.transpose(Image.Transpose.FLIP_TOP_BOTTOM)
    at, w, h, _size = levels[0]
    if flipped.size != (w, h):
        raise ValueError(f"The image is {flipped.size[0]}x{flipped.size[1]}, the texture {w}x{h}")
    changed = surface.write(out, at, codec, w, h, flipped)
    if changed:
        for (lat, lw, lh, _s), level_image in zip(levels[1:], surface.mip_levels(flipped, len(levels))[1:]):
            surface.write(out, lat, codec, lw, lh, level_image.resize((lw, lh)), force=True)
    return bool(changed)


def read(data: bytes, params: Dict[str, Any]) -> List[Texture]:
    table, pixel_member = split(data)
    return [Texture(f"{e['id']:08x}", read_texture(e, pixel_member),
                    e["format"] if e.get("hd") else _FORMATS[e["format"]].split(":")[-1], e["levels"])
            for e in entries(table)]


def write(data: bytes, images: Dict[int, Image.Image], params: Dict[str, Any]) -> bytes:
    table, pixel_member = split(data)
    listed = entries(table)
    out = bytearray(pixel_member)
    changed = False
    for index, image in images.items():
        changed |= write_texture(out, listed[index], image)
    if not changed:
        return bytes(data)
    return join_hd(bytes(out)) if is_hd(data) else join(table, bytes(out))
