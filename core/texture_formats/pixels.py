"""Pixel formats of game textures: stored elements to an RGBA image and back.

A ``Codec`` turns a stream of *elements* into an RGBA image (``decode(data, width, height)``) and an
RGBA image into that stream (``encode(image)``); ``width`` and ``height`` are multiples of the
element's ``block`` (pixels) and an element is ``size`` bytes. What an element is depends on the
family:

- ``gx:*`` -- GameCube / Wii: a GX tile (8x8, 8x4 or 4x4 pixels, row by row inside), big endian;
- ``pica:*`` -- 3DS: an 8x8 tile in Morton order, little endian, 4-bit texels low nibble first;
- ``n64:*`` -- N64: linear rows, big endian, 4-bit texels high nibble first;
- plain names (``RGBA8``, ``BC3``...) -- Wii U / Switch: one pixel, or one 4x4 block of a block
  compressed format, in linear order (the surface layout -- ``gx2``, ``tegra`` -- places them).

Grey formats come out as the game draws them: an intensity (GX/N64 ``I4``/``I8``) is grey with alpha
equal to grey, a luminance is opaque grey, an alpha format is white with that alpha. Encoding takes
the ink of what was drawn (``min(max(r, g, b), alpha)``) for one-channel formats, so white on
transparent and white on black both work. Lossy formats (BC, CMPR, ETC1) are encoded block by block;
``surface`` keeps the bytes of every block whose pixels did not change.
"""
from __future__ import annotations

import struct
from dataclasses import dataclass
from functools import lru_cache
from typing import Callable, Dict, List, Optional, Sequence, Tuple

from PIL import Image, ImageChops

from core.texture_formats import etc1

RGBA = Tuple[int, int, int, int]


@dataclass(frozen=True)
class Codec:
    """One pixel format: element size in pixels (``block``) and bytes (``size``), and its two directions."""

    name: str
    block: Tuple[int, int]
    size: int
    decode: Callable[[bytes, int, int], Image.Image]
    encode: Callable[[Image.Image], bytes]


# -- channel helpers ------------------------------------------------------------------------


def _expand(value: int, bits: int) -> int:
    """An n-bit channel to 8 bits by bit replication (what the GPUs do)."""
    if bits >= 8:
        return value
    if bits == 1:
        return 255 if value else 0
    value <<= 8 - bits
    out = value
    while value:
        value >>= bits
        out |= value
    return out & 0xFF


def _quant(value: int, bits: int) -> int:
    """8 bits to an n-bit channel (the inverse of ``_expand`` on its outputs)."""
    return (value * ((1 << bits) - 1) + 127) // 255


def _ink(r: int, g: int, b: int, a: int) -> int:
    return min(max(r, g, b), a)


def _grey(r: int, g: int, b: int, a: int) -> int:
    """Luminance drawn over black (a half-transparent grey is darker)."""
    return max(r, g, b) * a // 255


# -- storage orders ---------------------------------------------------------------------------


@lru_cache(maxsize=32)
def tile_order(width: int, height: int, tile_w: int, tile_h: int) -> Tuple[int, ...]:
    """Pixel index (``y * width + x``) of every stored texel: tiles row by row, rows inside a tile (GX)."""
    return tuple((ty + y) * width + tx + x for ty in range(0, height, tile_h) for tx in range(0, width, tile_w)
                 for y in range(tile_h) for x in range(tile_w))


_MORTON = tuple((((i >> 1) & 1) | ((i >> 2) & 2) | ((i >> 3) & 4), (i & 1) | ((i >> 1) & 2) | ((i >> 2) & 4))
                for i in range(64))  # (y, x) of the n-th texel of an 8x8 PICA tile


@lru_cache(maxsize=32)
def pica_order(width: int, height: int) -> Tuple[int, ...]:
    """Pixel index of every stored texel of a 3DS texture: 8x8 tiles row by row, Morton order inside."""
    return tuple((ty + y) * width + tx + x for ty in range(0, height, 8) for tx in range(0, width, 8)
                 for y, x in _MORTON)


# -- value formats (one number per texel) -----------------------------------------------------


def _read_values(data: bytes, count: int, bits: int, endian: str, low_first: bool) -> Sequence[int]:
    if bits == 4:
        raw = bytes(data[:(count + 1) // 2])
        high = raw.translate(bytes(b >> 4 for b in range(256)))
        low = raw.translate(bytes(b & 15 for b in range(256)))
        out = bytearray(len(raw) * 2)
        out[0::2], out[1::2] = (low, high) if low_first else (high, low)
        return out[:count]
    if bits == 8:
        return bytes(data[:count])
    if bits == 24:
        order = "little" if endian == "<" else "big"
        return [int.from_bytes(data[i:i + 3], order) for i in range(0, count * 3, 3)]
    code = {16: "H", 32: "I"}[bits]
    return struct.unpack(f"{endian}{count}{code}", bytes(data[:count * bits // 8]))


def _write_values(values: Sequence[int], bits: int, endian: str, low_first: bool) -> bytes:
    if bits == 4:
        first, second = values[0::2], values[1::2]
        if low_first:
            return bytes(a | b << 4 for a, b in zip(first, second))
        return bytes(a << 4 | b for a, b in zip(first, second))
    if bits == 8:
        return bytes(values)
    if bits == 24:
        order = "little" if endian == "<" else "big"
        return b"".join(v.to_bytes(3, order) for v in values)
    code = {16: "H", 32: "I"}[bits]
    return struct.pack(f"{endian}{len(values)}{code}", *values)


def _lookup(decode: Callable[[int], RGBA], bits: int) -> Optional[List[bytes]]:
    return [bytes(decode(v)) for v in range(1 << bits)] if bits <= 16 else None


def value_codec(name: str, bits: int, decode: Callable[[int], RGBA], encode: Callable[[int, int, int, int], int],
                *, endian: str = ">", low_first: bool = False, tile: Optional[Tuple[int, int]] = None,
                pica: bool = False) -> Codec:
    """A format with one ``bits``-bit number per texel, stored in GX tiles (``tile``), PICA tiles or rows."""
    if pica:
        block = (8, 8)
    elif tile:
        block = tile
    else:
        block = (max(1, 8 // bits), 1)
    size = block[0] * block[1] * bits // 8
    table: List[Optional[List[bytes]]] = []

    def order(width: int, height: int) -> Optional[Tuple[int, ...]]:
        if pica:
            return pica_order(width, height)
        if tile:
            return tile_order(width, height, *tile)
        return None

    def dec(data: bytes, width: int, height: int) -> Image.Image:
        if not table:
            table.append(_lookup(decode, bits))
        lut = table[0]
        count = width * height
        values = _read_values(data, count, bits, endian, low_first)
        texels = [lut[v] for v in values] if lut else [bytes(decode(v)) for v in values]
        positions = order(width, height)
        if positions is None:
            raw = b"".join(texels)
        else:
            out = [b""] * count
            for texel, at in zip(texels, positions):
                out[at] = texel
            raw = b"".join(out)
        return Image.frombytes("RGBA", (width, height), raw)

    def enc(image: Image.Image) -> bytes:
        width, height = image.size
        px = image.convert("RGBA").tobytes()
        positions = order(width, height) or range(width * height)
        cache: Dict[bytes, int] = {}
        values = []
        for at in positions:
            texel = px[at * 4:at * 4 + 4]
            value = cache.get(texel)
            if value is None:
                value = cache[texel] = encode(*texel)
            values.append(value)
        return _write_values(values, bits, endian, low_first)

    return Codec(name, block, size, dec, enc)


def _x(v: int, bits: int) -> int:
    return _expand(v, bits)


def _q(v: int, bits: int) -> int:
    return _quant(v, bits)


def _intensity(bits: int):
    def dec(v):
        e = _x(v, bits)
        return e, e, e, e
    return dec, lambda r, g, b, a: _q(_ink(r, g, b, a), bits)


def _luminance(bits: int):
    def dec(v):
        e = _x(v, bits)
        return e, e, e, 255
    return dec, lambda r, g, b, a: _q(_grey(r, g, b, a), bits)


def _alpha(bits: int):
    return (lambda v: (255, 255, 255, _x(v, bits))), (lambda r, g, b, a: _q(_ink(r, g, b, a), bits))


def _packed(layout: Sequence[Tuple[str, int]]):
    """A texel of channels packed high bits first, e.g. ``(("r", 5), ("g", 6), ("b", 5))``."""
    total = sum(bits for _c, bits in layout)

    def dec(v):
        channels = {"r": 0, "g": 0, "b": 0, "a": 255}
        shift = total
        for channel, bits in layout:
            shift -= bits
            channels[channel] = _x((v >> shift) & ((1 << bits) - 1), bits)
        return channels["r"], channels["g"], channels["b"], channels["a"]

    def enc(r, g, b, a):
        channels = {"r": r, "g": g, "b": b, "a": a}
        v = 0
        for channel, bits in layout:
            v = v << bits | _q(channels[channel], bits)
        return v

    return dec, enc


def _two(first: Tuple[str, int], second: Tuple[str, int]):
    """Grey + alpha in one number: ``first`` in the high bits (``i`` = grey, ``a`` = alpha)."""
    (c1, b1), (_c2, b2) = first, second

    def dec(v):
        hi, lo = _x(v >> b2, b1), _x(v & ((1 << b2) - 1), b2)
        grey, alpha = (hi, lo) if c1 == "i" else (lo, hi)
        return grey, grey, grey, alpha

    def enc(r, g, b, a):
        grey = max(r, g, b)
        hi, lo = (grey, a) if c1 == "i" else (a, grey)
        return _q(hi, b1) << b2 | _q(lo, b2)

    return dec, enc


def _rgb5a3():
    def dec(v):
        if v & 0x8000:
            return _x((v >> 10) & 31, 5), _x((v >> 5) & 31, 5), _x(v & 31, 5), 255
        return _x((v >> 8) & 15, 4), _x((v >> 4) & 15, 4), _x(v & 15, 4), _x((v >> 12) & 7, 3)

    def enc(r, g, b, a):
        if _q(a, 3) == 7:
            return 0x8000 | _q(r, 5) << 10 | _q(g, 5) << 5 | _q(b, 5)
        return _q(a, 3) << 12 | _q(r, 4) << 8 | _q(g, 4) << 4 | _q(b, 4)

    return dec, enc


def _bytes_order(order: str):
    """A 32-bit texel whose bytes, in memory order, are the channels ``order`` (e.g. ``"abgr"``)."""
    def dec(v):
        channels = dict(zip(order, v.to_bytes(4, "big")))
        return channels["r"], channels["g"], channels["b"], channels["a"]

    def enc(r, g, b, a):
        channels = {"r": r, "g": g, "b": b, "a": a}
        return int.from_bytes(bytes(channels[c] for c in order), "big")

    return dec, enc


# -- GX RGBA8: a 4x4 tile is 16 AR pairs, then 16 GB pairs ------------------------------------


def _gx_rgba8() -> Codec:
    def dec(data: bytes, width: int, height: int) -> Image.Image:
        out = bytearray(width * height * 4)
        positions = tile_order(width, height, 4, 4)
        for tile in range(len(positions) // 16):
            base = tile * 64
            for i in range(16):
                at = positions[tile * 16 + i] * 4
                out[at:at + 4] = bytes((data[base + 2 * i + 1], data[base + 32 + 2 * i],
                                        data[base + 33 + 2 * i], data[base + 2 * i]))
        return Image.frombytes("RGBA", (width, height), bytes(out))

    def enc(image: Image.Image) -> bytes:
        width, height = image.size
        px = image.convert("RGBA").tobytes()
        positions = tile_order(width, height, 4, 4)
        out = bytearray()
        for tile in range(len(positions) // 16):
            ar, gb = bytearray(), bytearray()
            for i in range(16):
                at = positions[tile * 16 + i] * 4
                r, g, b, a = px[at:at + 4]
                ar += bytes((a, r))
                gb += bytes((g, b))
            out += ar + gb
        return bytes(out)

    return Codec("gx:RGBA8", (4, 4), 64, dec, enc)


# -- block compression ------------------------------------------------------------------------

_BC_SIZE = {1: 8, 2: 16, 3: 16, 4: 8, 5: 16, 7: 16}


def _max_rgb(image: Image.Image) -> Image.Image:
    red, green, blue, _alpha = image.split()
    return ImageChops.lighter(ImageChops.lighter(red, green), blue)


def _bc_codec(n: int, view: str = "") -> Codec:
    """BC1-BC5 (Pillow) and BC7 (decoded by Pillow, encoded by ``bc7``). One- and two-channel formats have a ``view``: BC4 as ink
    (grey = alpha, the default), ``L`` (opaque grey) or ``A`` (white with alpha); BC5 as ``RG`` (the default)
    or ``LA`` (grey + alpha)."""
    def dec(data: bytes, width: int, height: int) -> Image.Image:
        mode = {4: "L", 5: "RGB"}.get(n, "RGBA")
        image = Image.frombytes(mode, (width, height), bytes(data[:(width // 4) * (height // 4) * _BC_SIZE[n]]),
                                "bcn", n)
        if n == 4:
            full = Image.new("L", image.size, 255)
            channels = {"L": (image, image, image, full), "A": (full, full, full, image)}.get(view, (image,) * 4)
            return Image.merge("RGBA", channels)
        if n == 5 and view == "LA":
            red, green, _blue = image.split()
            return Image.merge("RGBA", (red, red, red, green))
        return image.convert("RGBA")

    def enc(image: Image.Image) -> bytes:
        image = image.convert("RGBA")
        if n == 4:
            from core.font_formats import coverage
            channel = ImageChops.multiply(_max_rgb(image), image.getchannel("A")) if view == "L" else coverage(image)
            white = Image.new("L", image.size, 255)
            bc3 = Image.merge("RGBA", (white, white, white, channel)).tobytes("bcn", 3)
            return b"".join(block[:8] for block in _chunks(bc3, 16))   # a BC3 alpha block is a BC4 block
        if n == 5 and view == "LA":
            zero, full = Image.new("L", image.size, 0), Image.new("L", image.size, 255)
            image = Image.merge("RGBA", (_max_rgb(image), image.getchannel("A"), zero, full))
        if n == 7:
            from core.texture_formats import bc7
            return bc7.encode(image)
        return image.tobytes("bcn", n)

    return Codec(f"BC{n}{view}", (4, 4), _BC_SIZE[n], dec, enc)


def _chunks(data: bytes, size: int) -> List[bytes]:
    return [data[i:i + size] for i in range(0, len(data), size)]


# -- GX CMPR: 8x8 tiles of four DXT1 blocks, big-endian colours, first texel in the high bits ------

_REVERSE_PAIRS = bytes(sum(((b >> (2 * i)) & 3) << (6 - 2 * i) for i in range(4)) for b in range(256))


def _gx_to_bc1(block: bytes) -> bytes:
    return bytes((block[1], block[0], block[3], block[2])) + block[4:8].translate(_REVERSE_PAIRS)


def _bc1_to_gx(block: bytes) -> bytes:
    return bytes((block[1], block[0], block[3], block[2])) + block[4:8].translate(_REVERSE_PAIRS)


def _cmpr() -> Codec:
    def blocks_linear(width: int, height: int) -> List[int]:
        """Index in the tile stream of every 4x4 block, row by row."""
        wide = width // 4
        out = [0] * ((width // 4) * (height // 4))
        n = 0
        for ty in range(0, height // 4, 2):
            for tx in range(0, wide, 2):
                for dy, dx in ((0, 0), (0, 1), (1, 0), (1, 1)):
                    out[(ty + dy) * wide + tx + dx] = n
                    n += 1
        return out

    def dec(data: bytes, width: int, height: int) -> Image.Image:
        index = blocks_linear(width, height)
        linear = b"".join(_gx_to_bc1(data[i * 8:i * 8 + 8]) for i in index)
        return Image.frombytes("RGBA", (width, height), linear, "bcn", 1)

    def enc(image: Image.Image) -> bytes:
        width, height = image.size
        linear = _chunks(image.convert("RGBA").tobytes("bcn", 1), 8)
        index = blocks_linear(width, height)
        out = [b""] * len(index)
        for block, at in zip(linear, index):
            out[at] = _bc1_to_gx(block)
        return b"".join(out)

    return Codec("gx:CMPR", (8, 8), 32, dec, enc)


# -- PICA ETC1 / ETC1A4: an 8x8 tile is four 4x4 blocks (Z order), each a little-endian u64 -------------

_ETC_TILE = ((0, 0), (4, 0), (0, 4), (4, 4))


def _pica_etc(alpha: bool) -> Codec:
    block_bytes = 16 if alpha else 8

    def dec(data: bytes, width: int, height: int) -> Image.Image:
        out = bytearray(width * height * 4)
        at = 0
        for ty in range(0, height, 8):
            for tx in range(0, width, 8):
                for bx, by in _ETC_TILE:
                    alphas = int.from_bytes(data[at:at + 8], "little") if alpha else None
                    colour = int.from_bytes(data[at + block_bytes - 8:at + block_bytes], "little")
                    at += block_bytes
                    texels = etc1.decode_block(colour)
                    for x in range(4):
                        for y in range(4):
                            r, g, b = texels[x * 4 + y]
                            a = (alphas >> ((x * 4 + y) * 4) & 15) * 17 if alpha else 255
                            p = ((ty + by + y) * width + tx + bx + x) * 4
                            out[p:p + 4] = bytes((r, g, b, a))
        return Image.frombytes("RGBA", (width, height), bytes(out))

    def enc(image: Image.Image) -> bytes:
        width, height = image.size
        px = image.convert("RGBA").tobytes()
        out = bytearray()
        for ty in range(0, height, 8):
            for tx in range(0, width, 8):
                for bx, by in _ETC_TILE:
                    texels, alphas = [], 0
                    for x in range(4):
                        for y in range(4):
                            p = ((ty + by + y) * width + tx + bx + x) * 4
                            r, g, b, a = px[p:p + 4]
                            texels.append((r, g, b))
                            alphas |= _quant(a, 4) << ((x * 4 + y) * 4)
                    if alpha:
                        out += alphas.to_bytes(8, "little")
                    out += etc1.encode_block(texels).to_bytes(8, "little")
        return bytes(out)

    return Codec("pica:ETC1A4" if alpha else "pica:ETC1", (8, 8), 4 * block_bytes, dec, enc)


def _astc_codec(bw: int, bh: int) -> Codec:
    """ASTC blocks of ``bw`` x ``bh`` texels (``astc``)."""
    from core.texture_formats import astc

    def enc(image: Image.Image) -> bytes:
        return astc.encode(image, bw, bh)

    return Codec(f"ASTC{bw}x{bh}", (bw, bh), 16, lambda data, w, h: astc.decode(data, w, h, bw, bh), enc)


# -- palettes -------------------------------------------------------------------------------------


def palette_codec(name: str, bits: int, palette: Sequence[RGBA], *, tile: Optional[Tuple[int, int]] = None,
                  endian: str = ">") -> Codec:
    """Indices into ``palette`` (GX C4/C8/C14X2 in tiles, N64 CI4/CI8 in rows).

    Encoding picks, for each colour, the palette entry nearest to it."""
    colours = [tuple(c) for c in palette]
    exact = {c: i for i, c in reversed(list(enumerate(colours)))}
    mask = (1 << min(bits, 14)) - 1

    def dec(v):
        v &= mask
        return colours[v] if v < len(colours) else (0, 0, 0, 0)

    def enc(r, g, b, a):
        key = (r, g, b, a)
        if key in exact:
            return exact[key]
        best = min(range(len(colours)), key=lambda i: sum((p - q) ** 2 for p, q in zip(colours[i], key)))
        exact[key] = best
        return best

    return value_codec(name, bits, dec, enc, endian=endian, tile=tile)


def gx_palette_format(fmt: int):
    """``(decode, encode)`` of one GX palette entry (u16): 0 IA8, 1 RGB565, 2 RGB5A3."""
    if fmt == 0:
        return _two(("a", 8), ("i", 8))
    if fmt == 1:
        return _packed((("r", 5), ("g", 6), ("b", 5)))
    if fmt == 2:
        return _rgb5a3()
    raise ValueError(f"GX palette format {fmt} is not supported")


def n64_tlut():
    """``(decode, encode)`` of an N64 palette entry (RGBA16)."""
    return _packed((("r", 5), ("g", 5), ("b", 5), ("a", 1)))


def nearest_palette(image: Image.Image, count: int) -> List[RGBA]:
    """``count`` colours for ``image`` (fewer when it has fewer), transparent ones kept apart."""
    image = image.convert("RGBA")
    colours = image.getcolors(maxcolors=count)
    if colours is not None:
        return [tuple(c) for _n, c in colours]
    quantized = image.quantize(colors=count, method=Image.Quantize.FASTOCTREE)
    flat = quantized.getpalette("RGBA")[:count * 4]
    return [tuple(flat[i:i + 4]) for i in range(0, len(flat), 4)]


def _raw_codec(name: str, raw_mode: str) -> Codec:
    """A 32-bit linear format Pillow reads and writes as it is."""
    def dec(data: bytes, width: int, height: int) -> Image.Image:
        return Image.frombytes("RGBA", (width, height), bytes(data[:width * height * 4]), "raw", raw_mode)

    def enc(image: Image.Image) -> bytes:
        return image.convert("RGBA").tobytes("raw", raw_mode)

    return Codec(name, (1, 1), 4, dec, enc)


# -- the table ---------------------------------------------------------------------------------------


def _build() -> Dict[str, Codec]:
    codecs: Dict[str, Codec] = {}

    def add(codec: Codec) -> None:
        codecs[codec.name] = codec

    # GameCube / Wii (GX)
    add(value_codec("gx:I4", 4, *_intensity(4), tile=(8, 8)))
    add(value_codec("gx:I8", 8, *_intensity(8), tile=(8, 4)))
    add(value_codec("gx:IA4", 8, *_two(("a", 4), ("i", 4)), tile=(8, 4)))
    add(value_codec("gx:IA8", 16, *_two(("a", 8), ("i", 8)), tile=(4, 4)))
    add(value_codec("gx:RGB565", 16, *_packed((("r", 5), ("g", 6), ("b", 5))), tile=(4, 4)))
    add(value_codec("gx:RGB5A3", 16, *_rgb5a3(), tile=(4, 4)))
    add(_gx_rgba8())
    add(_cmpr())
    # 3DS (PICA200)
    pica = dict(endian="<", low_first=True, pica=True)
    add(value_codec("pica:RGBA8", 32, *_bytes_order("rgba"), **pica))   # bytes A, B, G, R (u32 LE = RGBA)
    add(value_codec("pica:RGB8", 24, *_packed((("r", 8), ("g", 8), ("b", 8))), **pica))
    add(value_codec("pica:RGBA5551", 16, *_packed((("r", 5), ("g", 5), ("b", 5), ("a", 1))), **pica))
    add(value_codec("pica:RGB565", 16, *_packed((("r", 5), ("g", 6), ("b", 5))), **pica))
    add(value_codec("pica:RGBA4", 16, *_packed((("r", 4), ("g", 4), ("b", 4), ("a", 4))), **pica))
    add(value_codec("pica:LA8", 16, *_two(("i", 8), ("a", 8)), **pica))
    add(value_codec("pica:HILO8", 16, *_packed((("r", 8), ("g", 8))), **pica))
    add(value_codec("pica:L8", 8, *_luminance(8), **pica))
    add(value_codec("pica:A8", 8, *_alpha(8), **pica))
    add(value_codec("pica:LA4", 8, *_two(("i", 4), ("a", 4)), **pica))
    add(value_codec("pica:L4", 4, *_luminance(4), **pica))
    add(value_codec("pica:A4", 4, *_alpha(4), **pica))
    add(_pica_etc(False))
    add(_pica_etc(True))
    # N64 (rows, big endian)
    add(value_codec("n64:I4", 4, *_intensity(4)))
    add(value_codec("n64:I8", 8, *_intensity(8)))
    add(value_codec("n64:IA4", 4, *_two(("i", 3), ("a", 1))))
    add(value_codec("n64:IA8", 8, *_two(("i", 4), ("a", 4))))
    add(value_codec("n64:IA16", 16, *_two(("i", 8), ("a", 8))))
    add(value_codec("n64:RGBA16", 16, *_packed((("r", 5), ("g", 5), ("b", 5), ("a", 1)))))
    add(value_codec("n64:RGBA32", 32, *_bytes_order("rgba")))
    # Wii U / Switch: one pixel per element, little endian
    le = dict(endian="<")
    add(_raw_codec("RGBA8", "RGBA"))    # bytes R, G, B, A
    add(_raw_codec("BGRA8", "BGRA"))    # bytes B, G, R, A
    add(value_codec("L8", 8, *_luminance(8), **le))
    add(value_codec("A8", 8, *_alpha(8), **le))
    add(value_codec("LA8", 16, *_two(("a", 8), ("i", 8)), **le))   # bytes L, A
    add(value_codec("RGB565", 16, *_packed((("b", 5), ("g", 6), ("r", 5))), **le))   # R in the low bits
    add(value_codec("RGBA4", 16, *_packed((("a", 4), ("b", 4), ("g", 4), ("r", 4))), **le))
    add(value_codec("RGB5A1", 16, *_packed((("a", 1), ("b", 5), ("g", 5), ("r", 5))), **le))
    for n in _BC_SIZE:
        add(_bc_codec(n))
    add(_bc_codec(4, "L"))
    add(_bc_codec(4, "A"))
    add(_bc_codec(5, "LA"))
    for bw, bh in ((4, 4), (8, 8), (10, 10), (12, 12)):
        add(_astc_codec(bw, bh))
    return codecs


_CODECS: Dict[str, Codec] = {}


def codec(name: str) -> Codec:
    """The codec of a pixel format name (``gx:CMPR``, ``pica:ETC1A4``, ``BC3``...)."""
    if not _CODECS:
        _CODECS.update(_build())
    try:
        return _CODECS[name]
    except KeyError:
        raise ValueError(f"Pixel format {name} is not supported") from None


def names() -> List[str]:
    codec("RGBA8")
    return list(_CODECS)
