"""PSP GIM pictures (``MIG.00.1PSP``) and the FCHN packs of them some PSP games use.

GIM: a 16-byte signature, then blocks of ``u16 id, u16 -, u32 size, u32 child offset, u32 data offset``:
root (2) > picture (3) > image (4) + palette (5), file info (0xFF). The data of an image or palette
block starts with a header: u16 header size, u16 -, u16 format, u16 order (1 = PSP swizzle: 16-byte
by 8-row blocks), u16 width, u16 height, u16 bits per pixel, u16 pitch align, u16 height align, ...,
u32 offset of the level table (from that header), u32 pixels start, u32 pixels end, ..., u16 level
count at 0x2A, u16 frame count at 0x2E. The pixels of a level fill ``align(width * bpp / 8, 16)``
bytes by ``align(height, 8)`` rows. Formats: 0 RGBA5650, 1 RGBA5551, 2 RGBA4444, 3 RGBA8888 (red in
the low bits), 4 index4 (low nibble first), 5 index8; a palette uses formats 0-3, one entry per pixel
of its width.

FCHN (a pack, as in Lunar: Silver Star Harmony): ``"FCHN", u16 data start, u16 count``, then count
entries ``u32 size, u32 offset`` (offsets count from the data start); members that are GIMs are its
textures, named by their entry number.

Writing keeps the bytes of every unchanged pixel. A palette picture keeps its palette when it holds
every new colour, else a palette of the same size is made for the new image and written in place.
Only the first level of the first frame is read and written.
"""
from __future__ import annotations

import struct
from typing import Any, Dict, List, Tuple

import numpy as np
from PIL import Image

from core.texture_formats import Texture, pixels

MAGIC = b"MIG.00.1PSP\x00"
PACK = b"FCHN"
FORMATS = {0: "RGBA5650", 1: "RGBA5551", 2: "RGBA4444", 3: "RGBA8888", 4: "I4", 5: "I8"}
_BITS = {0: 16, 1: 16, 2: 16, 3: 32, 4: 4, 5: 8}
# (bits of r, g, b, a) of the 16-bit formats, red in the lowest bits
_LAYOUT = {0: (5, 6, 5, 0), 1: (5, 5, 5, 1), 2: (4, 4, 4, 4)}


def detect(data: bytes) -> bool:
    return data[:12] == MAGIC or (data[:4] == PACK and _members(data) != [])


def _members(data: bytes) -> List[Tuple[str, int, int]]:
    """``(name, offset, size)`` of every GIM in ``data`` (a GIM, or an FCHN pack)."""
    if data[:12] == MAGIC:
        return [("", 0, len(data))]
    if data[:4] != PACK or len(data) < 8:
        return []
    start, count = struct.unpack_from("<HH", data, 4)
    if 8 + 8 * count > len(data):
        return []
    out = []
    for index in range(count):
        size, offset = struct.unpack_from("<II", data, 8 + 8 * index)
        at = start + offset
        if size and at + size <= len(data) and data[at:at + 12] == MAGIC:
            out.append((str(index), at, size))
    return out


def _blocks(data: bytes, at: int, end: int):
    """``(id, block start)`` of the blocks between ``at`` and ``end``, children first."""
    while at + 16 <= end:
        kind, _unused, size, child = struct.unpack_from("<HHII", data, at)
        if size < 16 or at + size > end:
            raise ValueError(f"GIM block at 0x{at:X} is broken")
        yield kind, at
        if kind in (2, 3) and child:
            yield from _blocks(data, at + child, at + size)
        at += size


def _head(data: bytes, block: int) -> Dict[str, int]:
    base = block + struct.unpack_from("<I", data, block + 12)[0]
    (fmt, order, width, height, bpp, pitch_align, height_align) = struct.unpack_from("<HHHHHHH", data, base + 4)
    table, start = struct.unpack_from("<II", data, base + 0x18)
    first = struct.unpack_from("<I", data, base + table)[0] if table else start
    if fmt not in FORMATS:
        raise ValueError(f"GIM pixel format {fmt} is not supported")
    if order == 1:                     # the swizzle works on 16-byte by 8-row blocks
        pitch_align, height_align = max(pitch_align, 16), max(height_align, 8)
    pitch = -(-max(1, width * _BITS[fmt] // 8) // max(pitch_align, 1)) * max(pitch_align, 1)
    rows = -(-height // max(height_align, 1)) * max(height_align, 1)
    return {"format": fmt, "order": order, "width": width, "height": height, "pitch": pitch, "rows": rows,
            "data": base + first, "levels": struct.unpack_from("<H", data, base + 0x2A)[0]}


def _pictures(data: bytes) -> List[Tuple[str, Dict[str, int], Dict[str, int]]]:
    """``(name, image head, palette head or {})`` of every picture."""
    out = []
    for name, at, size in _members(data):
        image = palette = None
        for kind, block in _blocks(data, at + 16, at + size):
            if kind == 4 and image is None:
                image = _head(data, block)
            elif kind == 5 and palette is None:
                palette = _head(data, block)
        if image is None:
            continue
        if image["format"] in (4, 5) and palette is None:
            raise ValueError(f"GIM {name or 'picture'}: an index image without a palette")
        out.append((name, image, palette or {}))
    return out


def _plane(data: bytes, head: Dict[str, int]) -> np.ndarray:
    """The stored bytes of a level as ``rows x pitch``, unswizzled."""
    raw = np.frombuffer(data, np.uint8, head["pitch"] * head["rows"], head["data"])
    if head["order"] == 1:
        raw = raw.reshape(head["rows"] // 8, head["pitch"] // 16, 8, 16).transpose(0, 2, 1, 3)
    return raw.reshape(head["rows"], head["pitch"]).copy()


def _store(out: bytearray, head: Dict[str, int], plane: np.ndarray) -> None:
    if head["order"] == 1:
        plane = plane.reshape(head["rows"] // 8, 8, head["pitch"] // 16, 16).transpose(0, 2, 1, 3)
    raw = np.ascontiguousarray(plane).tobytes()
    out[head["data"]:head["data"] + len(raw)] = raw


def _values(plane: np.ndarray, head: Dict[str, int]) -> np.ndarray:
    """One number per pixel, ``height x width``."""
    fmt, width, height = head["format"], head["width"], head["height"]
    if fmt == 4:
        both = np.stack([plane & 0x0F, plane >> 4], axis=-1).reshape(plane.shape[0], -1)
        return both[:height, :width].astype(np.uint32)
    if fmt == 5:
        return plane[:height, :width].astype(np.uint32)
    if fmt == 3:
        return plane.view("<u4")[:height, :width].astype(np.uint32)
    return plane.view("<u2")[:height, :width].astype(np.uint32)


def _put_values(plane: np.ndarray, head: Dict[str, int], values: np.ndarray) -> None:
    fmt, width, height = head["format"], head["width"], head["height"]
    if fmt == 4:
        both = np.stack([plane & 0x0F, plane >> 4], axis=-1).reshape(plane.shape[0], -1)
        both[:height, :width] = values
        plane[:] = (both[:, 0::2] | (both[:, 1::2] << 4)).astype(np.uint8)
    elif fmt == 5:
        plane[:height, :width] = values
    elif fmt == 3:
        plane.view("<u4")[:height, :width] = values
    else:
        plane.view("<u2")[:height, :width] = values


def _to_rgba(values: np.ndarray, fmt: int) -> np.ndarray:
    if fmt == 3:
        return values.astype("<u4").view(np.uint8).reshape(values.shape + (4,)).copy()
    out = np.empty(values.shape + (4,), np.uint8)
    shift = 0
    for channel, bits in enumerate(_LAYOUT[fmt]):
        if not bits:
            out[..., channel] = 255
            continue
        v = (values >> shift) & ((1 << bits) - 1)
        out[..., channel] = np.array([pixels._expand(x, bits) for x in range(1 << bits)], np.uint8)[v]
        shift += bits
    return out


def _from_rgba(rgba: np.ndarray, fmt: int) -> np.ndarray:
    if fmt == 3:
        return np.ascontiguousarray(rgba.astype(np.uint8)).view("<u4")[..., 0].astype(np.uint32)
    out = np.zeros(rgba.shape[:-1], np.uint32)
    shift = 0
    for channel, bits in enumerate(_LAYOUT[fmt]):
        if bits:
            out |= ((rgba[..., channel].astype(np.uint32) * ((1 << bits) - 1) + 127) // 255) << shift
            shift += bits
    return out


def _palette(data: bytes, head: Dict[str, int]) -> np.ndarray:
    entries = _values(_plane(data, head), head)[0]
    return _to_rgba(entries, head["format"])


def _decode(data: bytes, image: Dict[str, int], palette: Dict[str, int]) -> np.ndarray:
    values = _values(_plane(data, image), image)
    if image["format"] in (4, 5):
        colours = _palette(data, palette)
        values = np.minimum(values, len(colours) - 1)
        return colours[values]
    return _to_rgba(values, image["format"])


def read(data: bytes, params: Dict[str, Any]) -> List[Texture]:
    return [Texture(name, Image.fromarray(_decode(data, image, palette), "RGBA"), FORMATS[image["format"]],
                    max(1, image["levels"]))
            for name, image, palette in _pictures(data)]


def _write_picture(out: bytearray, image: Dict[str, int], palette: Dict[str, int], new: Image.Image) -> bool:
    if new.size != (image["width"], image["height"]):
        raise ValueError(f"GIM picture is {image['width']}x{image['height']}, the new image is "
                         f"{new.size[0]}x{new.size[1]}")
    want = np.asarray(new.convert("RGBA"), np.uint8)
    old = _decode(bytes(out), image, palette)
    changed = np.any(want != old, axis=-1)
    if not changed.any():
        return False
    plane = _plane(bytes(out), image)
    values = _values(plane, image)
    if image["format"] in (4, 5):
        colours = _palette(bytes(out), palette)
        index = {tuple(c): i for i, c in reversed(list(enumerate(colours.tolist())))}
        wanted = {tuple(c) for c in want[changed].tolist()}
        if not wanted <= set(index):
            capacity = min(len(colours), 16 if image["format"] == 4 else 256)
            chosen = pixels.nearest_palette(Image.fromarray(want, "RGBA"), capacity)
            colours = np.array([list(c) for c in chosen] + [[0, 0, 0, 0]] * (len(colours) - len(chosen)), np.uint8)
            pal_plane = _plane(bytes(out), palette)
            _put_values(pal_plane, palette, _from_rgba(colours, palette["format"])[None, :])
            _store(out, palette, pal_plane)
            colours = _palette(bytes(out), palette)
            changed[:] = True
            index = {tuple(c): i for i, c in reversed(list(enumerate(colours.tolist())))}
        lookup = {}
        flat = want.reshape(-1, 4)
        for y, x in zip(*np.nonzero(changed)):
            key = tuple(flat[y * image["width"] + x].tolist())
            if key not in lookup:
                lookup[key] = index.get(key)
                if lookup[key] is None:
                    lookup[key] = int(np.argmin(((colours.astype(int) - np.array(key)) ** 2).sum(axis=1)))
            values[y, x] = lookup[key]
    else:
        values[changed] = _from_rgba(want, image["format"])[changed]
    _put_values(plane, image, values)
    _store(out, image, plane)
    return True


def write(data: bytes, images: Dict[int, Image.Image], params: Dict[str, Any]) -> bytes:
    out = bytearray(data)
    pictures = _pictures(data)
    changed = False
    for index, image in images.items():
        _name, head, palette = pictures[index]
        changed = _write_picture(out, head, palette, image) or changed
    return bytes(out) if changed else data
