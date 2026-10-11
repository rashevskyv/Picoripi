"""PhyreEngine texture files (``RYHP`` ... ``NXGL``; Dragon Quest Builders 1, Switch).

The file is a Phyre cluster: a header (class table, asset names, texture records, fix-up tables) and, as the last
bytes, the pixels. A single-texture file: the record sits right before the class name ``PTexture2D`` that is
followed by the format name: (a marker byte), u32 highest mip level, u32 and u32 size hints, u32 width, u32
height, u32 1, ``0x00``. Formats: ``ARGB8`` (bytes B, G, R, A), ``ARGB4444`` (u16 0xARGB), ``DXT5`` (BC3), ``DXT1``
(BC1). Mip levels follow level 0, each half the size; rows are stored bottom-up (OpenGL), so images are flipped.

A pack of many textures (the UI sprite packs ``uitex`` / ``uiicon``) lists the asset names, then one 27-byte
record per texture (marker 3, u32 highest mip, u32, u32, u32 width, u32 height, u32 1, two zero bytes), then the
class name ``PTexture2D`` followed by the format names in use (``ARGB4444``, ``ARGB8``), then the fix-up tables
as LEB128 numbers: the index list 0..n-1, the header numbers 105 4 0 3 1 0 105 78 0 and groups ``kind slot ...``.
Slot 3 names the textures that use the second format name (a list ``count v...``, or with kind 6 one run
``start step count``); every other texture uses the first name. The pixels follow in record order as the last
bytes: this reading reproduces the size of all 12 packs of the game exactly.
"""
from __future__ import annotations

import re
import struct
from typing import Any, Dict, List

from PIL import Image

from core.texture_formats import Texture, pixels, surface

MAGIC = b"RYHP"
NUL = bytes(1)
FORMATS = {"ARGB8": "BGRA8", "ARGB4444": "ARGB4", "DXT5": "BC3", "DXT1": "BC1"}
PACK_RECORD = 27
_NAME = re.compile(rb"PTexture2D\x00([A-Za-z0-9]+)\x00")
_ASSET = re.compile(rb"[A-Za-z0-9_/.\-]+\.dds\x00")
_FORMAT_NAME = re.compile(rb"[A-Z][A-Za-z0-9]+")
_PACK_HEAD = [105, 4, 0, 3, 1, 0, 105, 78, 0]


def detect(data: bytes) -> bool:
    data = bytes(data)
    return data[:4] == MAGIC and b"PTexture2D\x00" in data[:0x3000] and (
        _record(data) is not None or _pack(data) is not None)


def _record(data: bytes):
    """(format name, mip count, width, height, offset of the first pixel) of a single-texture file, or None."""
    section = 84 + struct.unpack_from("<I", data, 8)[0]
    found = [m for m in _NAME.finditer(data, section, section + 0x4000)]
    if len(found) != 1:
        return None
    at = found[0].start()
    if at < 25 or data.count(b".dds" + NUL, section, at) != 1:     # a pack of textures: not one file's texture
        return None
    mip, _b, _c, width, height, depth = struct.unpack_from("<6I", data, at - 25)
    name = found[0].group(1).decode()
    if name not in FORMATS or depth != 1 or not (1 <= width <= 8192 and 1 <= height <= 8192):
        return None
    codec = pixels.codec(FORMATS[name])
    levels = mip + 1
    total = sum(surface.surface_bytes(codec, max(1, width >> n), max(1, height >> n)) for n in range(levels))
    start = len(data) - total
    if start < at:
        return None
    return name, levels, width, height, start


def _leb(data: bytes, at: int):
    value = shift = 0
    while True:
        byte = data[at]
        at += 1
        value |= (byte & 0x7F) << shift
        shift += 7
        if not byte & 0x80:
            return value, at


def _is_record(data: bytes, i: int) -> bool:
    return (i + PACK_RECORD <= len(data) and data[i] == 3 and data[i + 1:i + 5] == bytes(4)
            and data[i + 21:i + 25] == b"\x01\x00\x00\x00")


def _fixup_groups(data: bytes, start: int, count: int):
    """(set of texture indices of slot 3, offset after the numbers read) or None."""
    pos = start
    try:
        for _ in range(count):
            _value, pos = _leb(data, pos)
        tokens = []
        for _ in range(len(_PACK_HEAD) + 6 + count + 8):
            value, pos = _leb(data, pos)
            tokens.append(value)
    except IndexError:
        return None
    if tokens[:len(_PACK_HEAD)] != _PACK_HEAD:
        return None
    second: set = set()
    at = len(_PACK_HEAD)
    while at + 3 < len(tokens) and tokens[at + 1] in (2, 3):
        kind, slot = tokens[at], tokens[at + 1]
        at += 2
        if kind == 6:                                              # a run: start, step, count
            first, step, number = tokens[at:at + 3]
            items = [first + step * k for k in range(number)]
            at += 3
        else:                                                      # a list: count, values
            number = tokens[at]
            items = tokens[at + 1:at + 1 + number]
            at += 1 + number
        if slot == 3:
            second = set(items)
    return second


def _pack(data: bytes):
    """[(asset name, format name, mip count, width, height, offset of level 0)] of a pack file, or None."""
    section = 84 + struct.unpack_from("<I", data, 8)[0]
    names = list(_ASSET.finditer(data, section, section + 0x40000))
    if len(names) < 2:
        return None
    first = next((i for i in range(names[-1].end(), names[-1].end() + 8)
                  if all(_is_record(data, i + PACK_RECORD * k) for k in range(3))), None)
    if first is None:
        return None
    records, at = [], first
    while _is_record(data, at):
        mip, _b, _c, width, height, _d = struct.unpack_from("<6I", data, at + 1)
        records.append((mip + 1, width, height))
        at += PACK_RECORD
    count = len(records)
    if count < 2 or len(names) < count or not all(1 <= w <= 8192 and 1 <= h <= 8192 for _m, w, h in records):
        return None
    pool = data.find(b"PTexture2D" + NUL, at - 3, at + 24)
    if pool < 0:
        return None
    text, cursor = [], pool + 11
    while True:
        end = data.find(NUL, cursor)
        word = data[cursor:end]
        if not _FORMAT_NAME.fullmatch(word) or word.decode() not in FORMATS:
            break
        text.append(word.decode())
        cursor = end + 1
    start = data.find(bytes(range(1, min(count, 16))), cursor, cursor + 200)
    if not text or start < 0:
        return None
    found = _fixup_groups(data, start - 1, count)
    if found is None or (found and (max(found) >= count or len(text) < 2)):
        return None
    sizes = []
    for index, (mips, width, height) in enumerate(records):
        codec = pixels.codec(FORMATS[text[1] if index in found else text[0]])
        sizes.append(sum(surface.surface_bytes(codec, max(1, width >> n), max(1, height >> n)) for n in range(mips)))
    offset = len(data) - sum(sizes)
    if offset < cursor:
        return None
    out = []
    for index, (mips, width, height) in enumerate(records):
        asset = names[len(names) - count + index].group()[:-1].decode()
        out.append((asset, text[1] if index in found else text[0], mips, width, height, offset))
        offset += sizes[index]
    return out


def _levels(width: int, height: int, count: int, start: int, codec):
    at, out = start, []
    for n in range(count):
        w, h = max(1, width >> n), max(1, height >> n)
        out.append((at, w, h))
        at += surface.surface_bytes(codec, w, h)
    return out


def _items(data: bytes):
    record = _record(data)
    if record is not None:
        name, mips, width, height, start = record
        return [("", name, mips, width, height, start)]
    items = _pack(data)
    if items is None:
        raise ValueError("Not a Phyre texture file")
    return items


def read(data: bytes, params: Dict[str, Any]) -> List[Texture]:
    data = bytes(data)
    out = []
    for asset, name, mips, width, height, start in _items(data):
        codec = pixels.codec(FORMATS[name])
        image = surface.read(data, start, codec, width, height).transpose(Image.Transpose.FLIP_TOP_BOTTOM)
        out.append(Texture(asset, image, name, mips))
    return out


def write(data: bytes, images: Dict[int, Image.Image], params: Dict[str, Any]) -> bytes:
    data = bytes(data)
    items = _items(data)
    out = bytearray(data)
    changed = False
    for index, new in images.items():
        _asset, name, mips, width, height, start = items[index]
        codec = pixels.codec(FORMATS[name])
        flipped = new.convert("RGBA").transpose(Image.Transpose.FLIP_TOP_BOTTOM)
        levels = _levels(width, height, mips, start, codec)
        at, w, h = levels[0]
        if surface.write(out, at, codec, w, h, flipped) == 0:
            continue                                  # nothing redrawn: the stored mip levels stay
        changed = True
        for (at, w, h), level in zip(levels[1:], surface.mip_levels(flipped, len(levels))[1:]):
            surface.write(out, at, codec, w, h, level)
    return bytes(out) if changed else data
