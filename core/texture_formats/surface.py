"""Read and write one texture surface (one mip level) inside a file, element by element.

A surface is ``width`` x ``height`` pixels of a ``Codec``, padded up to whole elements. Its elements
lie at ``offsets`` (bytes from ``base``, row by row; contiguous when ``None``). Writing compares the
new pixels with the stored ones element by element and encodes again only the elements that differ,
so an unchanged image writes the same bytes and an edit touches only what was redrawn.
"""
from __future__ import annotations

from typing import List, Optional, Sequence

from PIL import Image

from core.texture_formats.pixels import ASTC_BLOCKS, Codec

_SLOW = frozenset({"pica:ETC1", "pica:ETC1A4", "BC7", *(f"ASTC{w}x{h}" for w, h in ASTC_BLOCKS)})


def _padded(codec: Codec, width: int, height: int):
    bw, bh = codec.block
    return -(-width // bw) * bw, -(-height // bh) * bh


def surface_bytes(codec: Codec, width: int, height: int) -> int:
    """Bytes of a contiguous surface."""
    pw, ph = _padded(codec, width, height)
    return pw // codec.block[0] * (ph // codec.block[1]) * codec.size


def _gather(data: bytes, base: int, codec: Codec, count: int, offsets: Optional[Sequence[int]]) -> bytes:
    if offsets is None:
        return bytes(data[base:base + count * codec.size])
    size = codec.size
    return b"".join(data[base + o:base + o + size] for o in offsets)


def read_padded(data: bytes, base: int, codec: Codec, width: int, height: int,
                offsets: Optional[Sequence[int]] = None) -> Image.Image:
    pw, ph = _padded(codec, width, height)
    count = pw // codec.block[0] * (ph // codec.block[1])
    raw = _gather(data, base, codec, count, offsets)
    if len(raw) < count * codec.size:
        raise ValueError(f"Texture data is cut short ({len(raw)} of {count * codec.size} bytes)")
    return codec.decode(raw, pw, ph)


def read(data: bytes, base: int, codec: Codec, width: int, height: int,
         offsets: Optional[Sequence[int]] = None) -> Image.Image:
    """The surface as an RGBA image of its own size."""
    image = read_padded(data, base, codec, width, height, offsets)
    return image if image.size == (width, height) else image.crop((0, 0, width, height))


def write(out: bytearray, base: int, codec: Codec, width: int, height: int, image: Image.Image,
          offsets: Optional[Sequence[int]] = None, force: bool = False) -> int:
    """Store ``image`` (``width`` x ``height``) into ``out``; returns how many elements changed.

    ``force`` encodes every element (the codec changed meaning, e.g. a new palette)."""
    if image.size != (width, height):
        raise ValueError(f"The image is {image.size[0]}x{image.size[1]}, the texture {width}x{height}")
    old = read_padded(out, base, codec, width, height, offsets)
    new = old.copy()
    new.paste(image.convert("RGBA"), (0, 0))
    bw, bh = codec.block
    pw, ph = old.size
    wide = pw // bw
    before, after = old.tobytes(), new.tobytes()
    row = pw * 4
    changed: List[int] = []
    for ey in range(ph // bh):
        band = slice(ey * bh * row, (ey + 1) * bh * row)
        if not force and before[band] == after[band]:
            continue
        for ex in range(wide):
            if force or any(before[(ey * bh + y) * row + ex * bw * 4:(ey * bh + y) * row + (ex + 1) * bw * 4]
                            != after[(ey * bh + y) * row + ex * bw * 4:(ey * bh + y) * row + (ex + 1) * bw * 4]
                            for y in range(bh)):
                changed.append(ey * wide + ex)
    if not changed:
        return 0
    size = codec.size
    # Pure-Python block encoders go element by element (only what changed); the rest encode once.
    whole = None if codec.name in _SLOW else codec.encode(new)
    for index in changed:
        if whole is not None:
            element = whole[index * size:(index + 1) * size]
        else:
            ex, ey = index % wide, index // wide
            element = codec.encode(new.crop((ex * bw, ey * bh, (ex + 1) * bw, (ey + 1) * bh)))
        at = base + (index * size if offsets is None else offsets[index])
        out[at:at + size] = element
    return len(changed)


def mip_levels(image: Image.Image, count: int) -> List[Image.Image]:
    """``image`` and its ``count - 1`` smaller mip levels (each half the size, at least 1 pixel)."""
    levels = [image]
    width, height = image.size
    for level in range(1, count):
        size = (max(1, width >> level), max(1, height >> level))
        levels.append(image.resize(size, Image.Resampling.LANCZOS))
    return levels
