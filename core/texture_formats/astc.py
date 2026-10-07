"""ASTC (LDR) blocks: decode every block an encoder can write, encode one simple block kind.

A block is 128 bits, read little endian. Decoding follows the Khronos ASTC specification: void-extent
blocks, every 2D block mode (weight grids with bilinear infill, dual plane), 1-4 partitions (the hash
partition function), the LDR colour endpoint modes 0, 1, 4, 5, 6, 8, 9, 10, 12, 13 and integer sequence
encoding with bits, trits and quints. HDR modes and illegal blocks decode to magenta, as GPUs show them.
Colours are interpolated as UNORM (an sRGB texture decodes the same stored values).

Encoding writes, per block: a void-extent block when all texels are the same colour, else one RGBA
line (endpoint mode 12, 8-bit endpoints) with a 4x4 grid of 2-bit weights (any block size: a bigger block's
grid is filled in by the decoder). That is BC1-like quality
with alpha, enough for lettering; ``surface`` re-encodes only the blocks an edit changed.
"""
from __future__ import annotations

from functools import lru_cache
from typing import List, Sequence, Tuple

from PIL import Image

RGBA = Tuple[int, int, int, int]
ERROR: RGBA = (255, 0, 255, 255)

# quant level index -> (levels, kind, bits); kind: 0 bits only, 3 trit, 5 quint
QUANT = ((2, 0, 1), (3, 3, 0), (4, 0, 2), (5, 5, 0), (6, 3, 1), (8, 0, 3), (10, 5, 1), (12, 3, 2), (16, 0, 4),
         (20, 5, 2), (24, 3, 3), (32, 0, 5), (40, 5, 3), (48, 3, 4), (64, 0, 6), (80, 5, 4), (96, 3, 5),
         (128, 0, 7), (160, 5, 5), (192, 3, 6), (256, 0, 8))


def _bit(value: int, index: int) -> int:
    return (value >> index) & 1


def _trits(t: int) -> Tuple[int, ...]:
    if (t >> 2) & 7 == 7:
        c = ((t >> 5) & 7) << 2 | (t & 3)
        t4 = t3 = 2
    else:
        c = t & 0x1F
        if (t >> 5) & 3 == 3:
            t4, t3 = 2, _bit(t, 7)
        else:
            t4, t3 = _bit(t, 7), (t >> 5) & 3
    if c & 3 == 3:
        t2, t1, t0 = 2, _bit(c, 4), _bit(c, 3) << 1 | (_bit(c, 2) & ~_bit(c, 3) & 1)
    elif (c >> 2) & 3 == 3:
        t2, t1, t0 = 2, 2, c & 3
    else:
        t2, t1, t0 = _bit(c, 4), (c >> 2) & 3, _bit(c, 1) << 1 | (_bit(c, 0) & ~_bit(c, 1) & 1)
    return t0, t1, t2, t3, t4


def _quints(q: int) -> Tuple[int, ...]:
    if (q >> 1) & 3 == 3 and (q >> 5) & 3 == 0:
        q0 = _bit(q, 0)
        return 4, 4, q0 << 2 | (_bit(q, 4) & ~q0 & 1) << 1 | (_bit(q, 3) & ~q0 & 1)
    if (q >> 1) & 3 == 3:
        q2, c = 4, ((q >> 3) & 3) << 3 | (~(q >> 5) & 3) << 1 | (q & 1)
    else:
        q2, c = (q >> 5) & 3, q & 0x1F
    if c & 7 == 5:
        return (c >> 3) & 3, 4, q2
    return c & 7, (c >> 3) & 3, q2


_TRITS = tuple(_trits(t) for t in range(256))
_QUINTS = tuple(_quints(q) for q in range(128))


def ise_bits(count: int, quant: int) -> int:
    _levels, kind, bits = QUANT[quant]
    extra = (8 * count + 4) // 5 if kind == 3 else (7 * count + 2) // 3 if kind == 5 else 0
    return count * bits + extra


def ise_decode(stream: int, count: int, quant: int) -> List[Tuple[int, int]]:
    """``count`` values of a sequence starting at bit 0 of ``stream``: ``(trit/quint or 0, low bits)``."""
    _levels, kind, bits = QUANT[quant]
    stream &= (1 << ise_bits(count, quant)) - 1      # bits past the sequence read as zero
    mask = (1 << bits) - 1
    out: List[Tuple[int, int]] = []
    if kind == 0:
        return [(0, (stream >> (i * bits)) & mask) for i in range(count)]
    # a group of 5 trits (3 quints): each value's low bits, then the next bits of the packed digits
    packed_lengths = (2, 2, 1, 2, 1) if kind == 3 else (3, 2, 2)
    pos = 0
    while len(out) < count:
        lows, packed, shift = [], 0, 0
        for length in packed_lengths:
            lows.append((stream >> pos) & mask)
            pos += bits
            packed |= ((stream >> pos) & ((1 << length) - 1)) << shift
            pos += length
            shift += length
        digits = _TRITS[packed] if kind == 3 else _QUINTS[packed]
        out.extend(zip(digits, lows))
    return out[:count]


def _replicate(value: int, bits: int, to: int) -> int:
    if bits == 0:
        return 0
    out, have = 0, 0
    while have < to:
        out = out << bits | value
        have += bits
    return out >> (have - to)


_COLOR_TC = {3: {1: 204, 2: 93, 3: 44, 4: 22, 5: 11, 6: 5}, 5: {1: 113, 2: 54, 3: 26, 4: 13, 5: 6}}


def _color_b(kind: int, bits: int, v: int) -> int:
    if bits == 1:
        return 0
    if kind == 3:
        b = (v >> 1) & ((1 << (bits - 1)) - 1)
        return {2: b * 0x116, 3: b * 0x85, 4: b * 0x41, 5: b << 5 | b >> 2, 6: b << 4 | b >> 4}[bits]
    b = (v >> 1) & ((1 << (bits - 1)) - 1)
    return {2: b * 0x10C, 3: b << 7 | b << 1 | b >> 1, 4: b << 6 | b >> 1, 5: b << 5 | b >> 3}[bits]


@lru_cache(maxsize=None)
def unquantize_color(quant: int, digit: int, low: int) -> int:
    _levels, kind, bits = QUANT[quant]
    if kind == 0:
        return _replicate(low, bits, 8)
    a = 0x1FF if low & 1 else 0
    t = digit * _COLOR_TC[kind][bits] + _color_b(kind, bits, low)
    t ^= a
    return (a & 0x80) | (t >> 2)


@lru_cache(maxsize=None)
def unquantize_weight(quant: int, digit: int, low: int) -> int:
    _levels, kind, bits = QUANT[quant]
    if kind == 0:
        value = _replicate(low, bits, 6)
    elif bits == 0:
        value = (0, 32, 63)[digit] if kind == 3 else (0, 16, 32, 47, 63)[digit]
    else:
        a = 0x7F if low & 1 else 0
        b = (low >> 1) & ((1 << (bits - 1)) - 1)
        if kind == 3:
            c, base = {1: (50, 0), 2: (23, b * 0x45), 3: (11, b << 5 | b)}[bits]
        else:
            c, base = {1: (28, 0), 2: (13, b * 0x42)}[bits]
        t = (digit * c + base) ^ a
        value = (a & 0x20) | (t >> 2)
    return value + 1 if value > 32 else value


def block_mode(mode: int):
    """``(grid width, grid height, dual plane, weight quant)`` of a 2D block mode, or None when reserved."""
    a = (mode >> 5) & 3
    h, d = _bit(mode, 9), _bit(mode, 10)
    base = _bit(mode, 4)
    if mode & 3:
        base |= (mode & 3) << 1
        b = (mode >> 7) & 3
        kind = (mode >> 2) & 3
        if kind == 0:
            x, y = b + 4, a + 2
        elif kind == 1:
            x, y = b + 8, a + 2
        elif kind == 2:
            x, y = a + 2, b + 8
        elif mode & 0x100:
            x, y = (b & 1) + 2, a + 2
        else:
            x, y = a + 2, (b & 1) + 6
    else:
        base |= ((mode >> 2) & 3) << 1
        if (mode >> 2) & 3 == 0:
            return None
        b = (mode >> 9) & 3
        kind = (mode >> 7) & 3
        if kind == 0:
            x, y = 12, a + 2
        elif kind == 1:
            x, y = a + 2, 12
        elif kind == 2:
            x, y, d, h = a + 6, b + 6, 0, 0
        elif (mode >> 5) & 3 == 0:
            x, y = 6, 10
        elif (mode >> 5) & 3 == 1:
            x, y = 10, 6
        else:
            return None
    return x, y, bool(d), base - 2 + 6 * h


def _hash52(p: int) -> int:
    m = 0xFFFFFFFF
    p ^= p >> 15
    p = (p - (p << 17)) & m
    p = (p + (p << 7)) & m
    p = (p + (p << 4)) & m
    p ^= p >> 5
    p = (p + (p << 16)) & m
    p ^= p >> 7
    p ^= p >> 3
    p = (p ^ (p << 6)) & m
    p ^= p >> 17
    return p


def _select_partition(seed: int, x: int, y: int, z: int, count: int, small: bool) -> int:
    if small:
        x, y, z = x << 1, y << 1, z << 1
    seed += (count - 1) * 1024
    rnum = _hash52(seed)
    s = [(rnum >> shift) & 0xF for shift in (0, 4, 8, 12, 16, 20, 24, 28, 18, 22, 26)]
    s.append(((rnum >> 30) | (rnum << 2)) & 0xF)
    s = [v * v for v in s]
    if seed & 1:
        sh1, sh2 = (4 if seed & 2 else 5), (6 if count == 3 else 5)
    else:
        sh1, sh2 = (6 if count == 3 else 5), (4 if seed & 2 else 5)
    sh3 = sh1 if seed & 0x10 else sh2
    shifts = (sh1, sh2, sh1, sh2, sh1, sh2, sh1, sh2, sh3, sh3, sh3, sh3)
    s = [v >> sh for v, sh in zip(s, shifts)]
    a = (s[0] * x + s[1] * y + s[10] * z + (rnum >> 14)) & 0x3F
    b = (s[2] * x + s[3] * y + s[11] * z + (rnum >> 10)) & 0x3F
    c = (s[4] * x + s[5] * y + s[8] * z + (rnum >> 6)) & 0x3F
    d = (s[6] * x + s[7] * y + s[9] * z + (rnum >> 2)) & 0x3F
    if count < 4:
        d = 0
    if count < 3:
        c = 0
    if a >= b and a >= c and a >= d:
        return 0
    if b >= c and b >= d:
        return 1
    return 2 if c >= d else 3


@lru_cache(maxsize=4096)
def _partitions(seed: int, count: int, bw: int, bh: int) -> Tuple[int, ...]:
    small = bw * bh < 31
    return tuple(_select_partition(seed, x, y, 0, count, small) for y in range(bh) for x in range(bw))


@lru_cache(maxsize=256)
def _infill(gw: int, gh: int, bw: int, bh: int) -> Tuple[Tuple[Tuple[int, int], ...], ...]:
    """Per texel: ``((grid index, factor), ...)`` of the bilinear weight infill (factors sum to 16)."""
    ds, dt = (1024 + bw // 2) // (bw - 1), (1024 + bh // 2) // (bh - 1)
    out = []
    for t in range(bh):
        for s in range(bw):
            gs, gt = (ds * s * (gw - 1) + 32) >> 6, (dt * t * (gh - 1) + 32) >> 6
            js, fs, jt, ft = gs >> 4, gs & 0xF, gt >> 4, gt & 0xF
            v0 = js + jt * gw
            w11 = (fs * ft + 8) >> 4
            taps = ((v0, 16 - fs - ft + w11), (v0 + 1, fs - w11), (v0 + gw, ft - w11), (v0 + gw + 1, w11))
            out.append(tuple((i, f) for i, f in taps if f))
    return tuple(out)


def _transfer(a: int, b: int) -> Tuple[int, int]:
    """bit_transfer_signed: ``(a, b)`` -> (signed 6-bit a, b)."""
    b = (b >> 1) | (a & 0x80)
    a = (a >> 1) & 0x3F
    return (a - 0x40 if a & 0x20 else a), b


def _clamp(v: int) -> int:
    return 0 if v < 0 else 255 if v > 255 else v


def _blue(r: int, g: int, b: int, a: int) -> List[int]:
    return [(r + b) >> 1, (g + b) >> 1, b, a]


def endpoints(cem: int, v: Sequence[int]):
    """``(e0, e1)`` RGBA of an LDR endpoint mode, or None (HDR)."""
    if cem == 0:
        return [v[0]] * 3 + [255], [v[1]] * 3 + [255]
    if cem == 1:
        l0 = (v[0] >> 2) | (v[1] & 0xC0)
        l1 = min(255, l0 + (v[1] & 0x3F))
        return [l0] * 3 + [255], [l1] * 3 + [255]
    if cem == 4:
        return [v[0]] * 3 + [v[2]], [v[1]] * 3 + [v[3]]
    if cem == 5:
        d1, b0 = _transfer(v[1], v[0])
        d3, b2 = _transfer(v[3], v[2])
        return [b0] * 3 + [b2], [_clamp(b0 + d1)] * 3 + [_clamp(b2 + d3)]
    if cem in (6, 10):
        alpha0, alpha1 = (v[4], v[5]) if cem == 10 else (255, 255)
        return [(v[0] * v[3]) >> 8, (v[1] * v[3]) >> 8, (v[2] * v[3]) >> 8, alpha0], [v[0], v[1], v[2], alpha1]
    if cem in (8, 12):
        a0, a1 = (v[6], v[7]) if cem == 12 else (255, 255)
        if v[1] + v[3] + v[5] >= v[0] + v[2] + v[4]:
            return [v[0], v[2], v[4], a0], [v[1], v[3], v[5], a1]
        return _blue(v[1], v[3], v[5], a1), _blue(v[0], v[2], v[4], a0)
    if cem in (9, 13):
        d1, b0 = _transfer(v[1], v[0])
        d3, b2 = _transfer(v[3], v[2])
        d5, b4 = _transfer(v[5], v[4])
        if cem == 13:
            d7, b6 = _transfer(v[7], v[6])
        else:
            d7, b6 = 0, 255
        if d1 + d3 + d5 >= 0:
            return [b0, b2, b4, b6], [_clamp(b0 + d1), _clamp(b2 + d3), _clamp(b4 + d5), _clamp(b6 + d7)]
        e0 = _blue(_clamp(b0 + d1), _clamp(b2 + d3), _clamp(b4 + d5), _clamp(b6 + d7))
        return e0, _blue(b0, b2, b4, b6)
    return None


def decode_block(block: bytes, bw: int, bh: int) -> List[RGBA]:
    """The ``bw`` x ``bh`` texels of one block, row by row."""
    texels = bw * bh
    v = int.from_bytes(block, "little")
    if v & 0x1FF == 0x1FC:                        # void extent: one colour
        if _bit(v, 9):
            return [ERROR] * texels
        return [tuple((v >> (64 + 16 * i)) >> 8 & 0xFF for i in range(4))] * texels
    mode = block_mode(v & 0x7FF)
    if mode is None:
        return [ERROR] * texels
    gw, gh, dual, wquant = mode
    planes = 2 if dual else 1
    weight_count = gw * gh * planes
    if gw > bw or gh > bh or wquant > 11 or weight_count > 64:
        return [ERROR] * texels
    weight_bits = ise_bits(weight_count, wquant)
    if not 24 <= weight_bits <= 96:
        return [ERROR] * texels
    parts = ((v >> 11) & 3) + 1
    if dual and parts == 4:
        return [ERROR] * texels
    below = 128 - weight_bits
    if parts == 1:
        cems, config = [(v >> 13) & 0xF], 17
    else:
        config = 29
        field = (v >> 23) & 0x3F
        if field & 3 == 0:
            cems = [field >> 2] * parts
        else:
            high = 3 * parts - 4
            below -= high
            field |= ((v >> below) & ((1 << high) - 1)) << 6
            base = (field & 3) - 1
            cems = [((((field >> (2 + i)) & 1) + base) << 2) | ((field >> (2 + parts + 2 * i)) & 3)
                    for i in range(parts)]
    plane2 = 0
    if dual:
        below -= 2
        plane2 = (v >> below) & 3
    counts = [((cem >> 2) + 1) * 2 for cem in cems]
    total = sum(counts)
    room = below - config
    if total > 18 or room <= 0:
        return [ERROR] * texels
    cquant = next((q for q in range(20, -1, -1) if ise_bits(total, q) <= room), -1)
    if cquant < 4:
        return [ERROR] * texels
    values = [unquantize_color(cquant, d, low) for d, low in ise_decode(v >> config, total, cquant)]
    pairs, at = [], 0
    for cem, n in zip(cems, counts):
        pair = endpoints(cem, values[at:at + n])
        if pair is None:
            return [ERROR] * texels
        pairs.append(pair)
        at += n
    reverse = int(format(v, "0128b")[::-1], 2)     # weights are stored from bit 127 down
    raw = [unquantize_weight(wquant, d, low) for d, low in ise_decode(reverse, weight_count, wquant)]
    if gw == bw and gh == bh:
        texel_weights = [raw[i * planes:i * planes + planes] for i in range(texels)]
    else:
        texel_weights = [[(sum(raw[i * planes + p] * f for i, f in taps) + 8) >> 4 for p in range(planes)]
                         for taps in _infill(gw, gh, bw, bh)]
    seed = (v >> 13) & 0x3FF
    table = _partitions(seed, parts, bw, bh) if parts > 1 else (0,) * texels
    out: List[RGBA] = []
    for index in range(texels):
        e0, e1 = pairs[table[index]]
        weights = texel_weights[index]
        color = []
        for channel in range(4):
            w = weights[1] if dual and channel == plane2 else weights[0]
            c0, c1 = e0[channel] * 257, e1[channel] * 257
            color.append(((c0 * (64 - w) + c1 * w + 32) >> 6) >> 8)
        out.append(tuple(color))
    return out


def decode(data: bytes, width: int, height: int, bw: int = 4, bh: int = 4) -> Image.Image:
    """Blocks in row order -> an RGBA image (``width``, ``height`` are multiples of the block)."""
    wide = width // bw
    pixels = bytearray(width * height * 4)
    cache = {}
    for index in range(wide * (height // bh)):
        block = bytes(data[index * 16:index * 16 + 16])
        texels = cache.get(block)
        if texels is None:
            texels = cache[block] = bytes(c for texel in decode_block(block, bw, bh) for c in texel)
        bx, by = (index % wide) * bw, (index // wide) * bh
        for row in range(bh):
            at = ((by + row) * width + bx) * 4
            pixels[at:at + bw * 4] = texels[row * bw * 4:(row + 1) * bw * 4]
    return Image.frombytes("RGBA", (width, height), bytes(pixels))


# -- encoding -----------------------------------------------------------------------------------------

_LEVELS = (0, 21, 43, 64)       # QUANT_4 weights
_MODE = 0x42                    # 4x4 grid, QUANT_4 weights, one plane


def _void_extent(color: Sequence[int]) -> bytes:
    v = 0x1FC | 0b11 << 10 | ((1 << 52) - 1) << 12
    for i, c in enumerate(color):
        v |= (c * 257) << (64 + 16 * i)
    return v.to_bytes(16, "little")


def encode_block(texels: Sequence[Sequence[int]], bw: int = 4, bh: int = 4) -> bytes:
    """``bw`` x ``bh`` RGBA texels (row by row) -> one block.

    The weight grid is always 4x4: a larger block (8x8, 12x12) gets each grid weight from the mean of the
    texels it covers, and the decoder's infill spreads it back.
    """
    texels = [tuple(t) for t in texels]
    if len(set(texels)) == 1:
        return _void_extent(texels[0])
    distinct = list(dict.fromkeys(texels))
    e0, e1 = max(((a, b) for i, a in enumerate(distinct) for b in distinct[i + 1:]),
                 key=lambda pair: sum((x - y) ** 2 for x, y in zip(*pair)))
    if sum(e1[:3]) < sum(e0[:3]):
        e0, e1 = e1, e0                           # no blue contraction: e1 must not be darker in RGB sum
    axis = [y - x for x, y in zip(e0, e1)]
    length = sum(a * a for a in axis) or 1
    v = _MODE | 12 << 13
    for channel in range(4):
        v |= e0[channel] << (17 + 16 * channel) | e1[channel] << (25 + 16 * channel)
    for index in range(16):
        gx, gy = index % 4, index // 4
        cover = [texels[y * bw + x] for y in range(gy * bh // 4, (gy + 1) * bh // 4)
                 for x in range(gx * bw // 4, (gx + 1) * bw // 4)]
        t = sum(sum((p - q) * a for p, q, a in zip(texel, e0, axis)) for texel in cover) * 64 / length / len(cover)
        weight = min(range(4), key=lambda k: abs(_LEVELS[k] - t))
        v |= (weight & 1) << (127 - 2 * index) | (weight >> 1) << (126 - 2 * index)
    return v.to_bytes(16, "little")


def encode(image: Image.Image, bw: int = 4, bh: int = 4) -> bytes:
    """An RGBA image (multiples of the block size) -> ``bw`` x ``bh`` blocks in row order."""
    image = image.convert("RGBA")
    width, height = image.size
    raw = image.tobytes()
    out = bytearray()
    for by in range(0, height, bh):
        for bx in range(0, width, bw):
            texels = [tuple(raw[((by + y) * width + bx + x) * 4:((by + y) * width + bx + x) * 4 + 4])
                      for y in range(bh) for x in range(bw)]
            out += encode_block(texels, bw, bh)
    return bytes(out)
