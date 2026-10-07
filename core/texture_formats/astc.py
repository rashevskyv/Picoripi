"""ASTC (LDR, 2D) block decoder, pure Python: 128-bit blocks of ``bw`` x ``bh`` texels to RGBA8.

Follows the Khronos ASTC specification: block mode (weight grid, range, dual plane), one to four
partitions with the spec's partition hash, colour endpoint modes 0-13 (the LDR ones; an HDR endpoint
mode or a reserved encoding decodes to magenta, as the hardware's error colour), integer sequence encoding
with trits and quints, bilinear weight infill and void-extent blocks. Endpoints are expanded to 16
bits by bit replication and the result's top byte is kept (sRGB data is returned as stored).

There is no encoder: ``core.texture_formats.txtr`` stores an edited ASTC texture as RGBA8.
"""
from __future__ import annotations

from functools import lru_cache
from typing import List, Optional, Sequence, Tuple

ERROR = (255, 0, 255, 255)
_ERROR = bytes(ERROR)
_REV8 = bytes(int(f"{i:08b}"[::-1], 2) for i in range(256))

# Quantisation levels of the integer sequence encoding: (levels, trits, quints, bits).
_RANGES = [(2, 0, 0, 1), (3, 1, 0, 0), (4, 0, 0, 2), (5, 0, 1, 0), (6, 1, 0, 1), (8, 0, 0, 3), (10, 0, 1, 1),
           (12, 1, 0, 2), (16, 0, 0, 4), (20, 0, 1, 2), (24, 1, 0, 3), (32, 0, 0, 5), (40, 0, 1, 3),
           (48, 1, 0, 4), (64, 0, 0, 6), (80, 0, 1, 4), (96, 1, 0, 5), (128, 0, 0, 7), (160, 0, 1, 5),
           (192, 1, 0, 6), (256, 0, 0, 8)]


def _bit(value: int, index: int) -> int:
    return (value >> index) & 1


def _trit_table() -> List[Tuple[int, ...]]:
    out = []
    for t in range(256):
        if (t >> 2) & 7 == 7:
            c = ((t >> 5) & 7) << 2 | (t & 3)
            t4 = t3 = 2
        else:
            c = t & 31
            if (t >> 5) & 3 == 3:
                t4, t3 = 2, _bit(t, 7)
            else:
                t4, t3 = _bit(t, 7), (t >> 5) & 3
        if c & 3 == 3:
            t2, t1 = 2, _bit(c, 4)
            t0 = _bit(c, 3) << 1 | (_bit(c, 2) & (1 - _bit(c, 3)))
        elif (c >> 2) & 3 == 3:
            t2, t1, t0 = 2, 2, c & 3
        else:
            t2, t1 = _bit(c, 4), (c >> 2) & 3
            t0 = _bit(c, 1) << 1 | (_bit(c, 0) & (1 - _bit(c, 1)))
        out.append((t0, t1, t2, t3, t4))
    return out


def _quint_table() -> List[Tuple[int, ...]]:
    out = []
    for q in range(128):
        if (q >> 1) & 3 == 3 and (q >> 5) & 3 == 0:
            q2 = _bit(q, 0) << 2 | (_bit(q, 4) & (1 - _bit(q, 0))) << 1 | (_bit(q, 3) & (1 - _bit(q, 0)))
            q1 = q0 = 4
        else:
            if (q >> 1) & 3 == 3:
                q2 = 4
                c = ((q >> 3) & 3) << 3 | ((~q >> 5) & 3) << 1 | (q & 1)
            else:
                q2 = (q >> 5) & 3
                c = q & 31
            if c & 7 == 5:
                q1, q0 = 4, (c >> 3) & 3
            else:
                q1, q0 = (c >> 3) & 3, c & 7
        out.append((q0, q1, q2))
    return out


_TRITS = _trit_table()
_QUINTS = _quint_table()


def ise_size(count: int, level: int) -> int:
    _levels, trits, quints, bits = _RANGES[level]
    if trits:
        return count * bits + (count * 8 + 4) // 5
    if quints:
        return count * bits + (count * 7 + 2) // 3
    return count * bits


def _decode_ise(value: int, start: int, count: int, level: int) -> List[int]:
    """``count`` integers of quantisation ``level`` from the bits of ``value`` at ``start`` (LSB first)."""
    _levels, trits, quints, bits = _RANGES[level]
    mask = (1 << bits) - 1
    value = (value >> start) & ((1 << ise_size(count, level)) - 1)   # bits past the sequence read as 0
    out: List[int] = []
    pos = 0

    def take(n: int) -> int:
        nonlocal pos
        got = (value >> pos) & ((1 << n) - 1)
        pos += n
        return got

    if trits:
        while len(out) < count:
            m, t = [], 0
            for i, tbits in enumerate((2, 2, 1, 2, 1)):
                m.append(take(bits) & mask)
                shift = (0, 2, 4, 5, 7)[i]
                t |= take(tbits) << shift
            for i in range(5):
                out.append(_TRITS[t][i] << bits | m[i])
    elif quints:
        while len(out) < count:
            m, q = [], 0
            for i, qbits in enumerate((3, 2, 2)):
                m.append(take(bits) & mask)
                q |= take(qbits) << (0, 3, 5)[i]
            for i in range(3):
                out.append(_QUINTS[q][i] << bits | m[i])
    else:
        for _ in range(count):
            out.append(take(bits))
    return out[:count]


@lru_cache(maxsize=None)
def _colour_unquant(level: int) -> Tuple[int, ...]:
    """Every value of a colour quantisation level to 0-255."""
    levels, trits, quints, bits = _RANGES[level]
    out = []
    for v in range(levels):
        if not trits and not quints:
            x = v << (8 - bits)
            out.append((x | (x >> bits) | (x >> (2 * bits)) | (x >> (3 * bits))) & 0xFF if bits < 8 else v)
            continue
        d, m = v >> bits, v & ((1 << bits) - 1)
        a = 0x1FF if m & 1 else 0
        bit = [(m >> i) & 1 for i in range(bits)]
        if trits:
            c = (204, 93, 44, 22, 11, 5)[bits - 1]
            pattern = {1: [], 2: ["b000b0bb0"], 3: ["cb000cbcb"], 4: ["dcb000dcb"], 5: ["edcb000ed"],
                       6: ["fedcb000f"]}[bits]
        else:
            c = (113, 54, 26, 13, 6)[bits - 1]
            pattern = {1: [], 2: ["b0000bb00"], 3: ["cb0000cbc"], 4: ["dcb0000dc"], 5: ["edcb0000e"]}[bits]
        b = 0
        if pattern:
            letters = {"b": bit[1] if bits > 1 else 0, "c": bit[2] if bits > 2 else 0, "d": bit[3] if bits > 3 else 0,
                       "e": bit[4] if bits > 4 else 0, "f": bit[5] if bits > 5 else 0}
            for ch in pattern[0]:
                b = b << 1 | (letters[ch] if ch != "0" else 0)
        t = d * c + b
        t ^= a
        out.append((a & 0x80) | (t >> 2))
    return tuple(out)


@lru_cache(maxsize=None)
def _weight_unquant(level: int) -> Tuple[int, ...]:
    """Every value of a weight quantisation level to 0-64."""
    levels, trits, quints, bits = _RANGES[level]
    out = []
    for v in range(levels):
        if not trits and not quints:
            x = v << (6 - bits)
            result = (x | (x >> bits) | (x >> (2 * bits)) | (x >> (3 * bits)) | (x >> (4 * bits))) & 0x3F
        elif bits == 0:
            result = ((0, 32, 63) if trits else (0, 16, 32, 47, 63))[v]
        else:
            d, m = v >> bits, v & ((1 << bits) - 1)
            a = 0x7F if m & 1 else 0
            bit = [(m >> i) & 1 for i in range(bits)]
            if trits:
                c, pattern = {1: (50, ""), 2: (23, "b000b0b"), 3: (11, "cb000cb")}[bits]
            else:
                c, pattern = {1: (28, ""), 2: (13, "b0000b0")}[bits]
            b = 0
            for ch in pattern:
                b = b << 1 | ({"b": bit[1] if bits > 1 else 0, "c": bit[2] if bits > 2 else 0}[ch] if ch != "0" else 0)
            t = (d * c + b) ^ a
            result = (a & 0x20) | (t >> 2)
        out.append(result + 1 if result > 32 else result)
    return tuple(out)


@lru_cache(maxsize=None)
def _block_mode(mode: int) -> Optional[Tuple[int, int, int, int]]:
    """(grid width, grid height, dual plane, weight level) of a block mode, or None when reserved."""
    r = (mode >> 4) & 1
    h, d, a = (mode >> 9) & 1, (mode >> 10) & 1, (mode >> 5) & 3
    if mode & 3:
        r |= (mode & 3) << 1
        b = (mode >> 7) & 3
        kind = (mode >> 2) & 3
        if kind == 0:
            w, hh = b + 4, a + 2
        elif kind == 1:
            w, hh = b + 8, a + 2
        elif kind == 2:
            w, hh = a + 2, b + 8
        else:
            b &= 1
            w, hh = (b + 2, a + 2) if mode & 0x100 else (a + 2, b + 6)
    else:
        r |= ((mode >> 2) & 3) << 1
        if (mode >> 2) & 3 == 0:
            return None
        b = (mode >> 9) & 3
        kind = (mode >> 7) & 3
        if kind == 0:
            w, hh = 12, a + 2
        elif kind == 1:
            w, hh = a + 2, 12
        elif kind == 2:
            w, hh, d, h = a + 6, b + 6, 0, 0
        else:
            if a == 0:
                w, hh = 6, 10
            elif a == 1:
                w, hh = 10, 6
            else:
                return None
    level = (r - 2) + 6 * h        # index into _RANGES (levels 2..32)
    if r < 2 or w * hh * (d + 1) > 64:
        return None
    return w, hh, d, level


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


@lru_cache(maxsize=4096)
def _partitions(seed: int, count: int, bw: int, bh: int) -> Tuple[int, ...]:
    small = bw * bh < 31
    rnum = _hash52(seed + (count - 1) * 1024)
    s = [(rnum >> sh) & 0xF for sh in (0, 4, 8, 12, 16, 20, 24, 28, 18, 22, 26)]
    s.append(((rnum >> 30) | (rnum << 2)) & 0xF)
    s = [v * v for v in s]
    if seed & 1:
        sh1, sh2 = (4 if seed & 2 else 5), (6 if count == 3 else 5)
    else:
        sh1, sh2 = (6 if count == 3 else 5), (4 if seed & 2 else 5)
    sh3 = sh1 if seed & 0x10 else sh2
    shifts = (sh1, sh2, sh1, sh2, sh1, sh2, sh1, sh2, sh3, sh3, sh3, sh3)
    s = [v >> sh for v, sh in zip(s, shifts)]
    out = []
    for y in range(bh):
        for x in range(bw):
            xx, yy = (x << 1, y << 1) if small else (x, y)
            a = (s[0] * xx + s[1] * yy + (rnum >> 14)) & 0x3F
            b = (s[2] * xx + s[3] * yy + (rnum >> 10)) & 0x3F
            c = (s[4] * xx + s[5] * yy + (rnum >> 6)) & 0x3F if count >= 3 else 0
            d = (s[6] * xx + s[7] * yy + (rnum >> 2)) & 0x3F if count >= 4 else 0
            if a >= b and a >= c and a >= d:
                out.append(0)
            elif b >= c and b >= d:
                out.append(1)
            elif c >= d:
                out.append(2)
            else:
                out.append(3)
    return tuple(out)


@lru_cache(maxsize=256)
def _infill(bw: int, bh: int, gw: int, gh: int) -> Tuple[Tuple[Tuple[int, int], ...], ...]:
    """Per texel: the (grid index, factor) pairs of the bilinear weight infill (factors sum to 16)."""
    ds = (1024 + bw // 2) // (bw - 1) if bw > 1 else 0
    dt = (1024 + bh // 2) // (bh - 1) if bh > 1 else 0
    out = []
    for t in range(bh):
        for s in range(bw):
            gs = (ds * s * (gw - 1) + 32) >> 6
            gt = (dt * t * (gh - 1) + 32) >> 6
            js, fs, jt, ft = gs >> 4, gs & 15, gt >> 4, gt & 15
            w11 = (fs * ft + 8) >> 4
            parts = []
            for dx, dy, f in ((0, 0, 16 - fs - ft + w11), (1, 0, fs - w11), (0, 1, ft - w11), (1, 1, w11)):
                if f:
                    parts.append(((jt + dy) * gw + js + dx, f))
            out.append(tuple(parts))
    return tuple(out)


def _transfer(a: int, b: int) -> Tuple[int, int]:
    b = (b >> 1) | (a & 0x80)
    a = (a >> 1) & 0x3F
    if a & 0x20:
        a -= 0x40
    return a, b


def _clamp(values) -> Tuple[int, ...]:
    return tuple(0 if v < 0 else 255 if v > 255 else v for v in values)


def _blue(r: int, g: int, b: int, a: int) -> Tuple[int, int, int, int]:
    return (r + b) >> 1, (g + b) >> 1, b, a


def _endpoints(cem: int, v: Sequence[int]) -> Optional[Tuple[Tuple[int, ...], Tuple[int, ...]]]:
    if cem == 0:
        return (v[0], v[0], v[0], 255), (v[1], v[1], v[1], 255)
    if cem == 1:
        l0 = (v[0] >> 2) | (v[1] & 0xC0)
        l1 = min(l0 + (v[1] & 0x3F), 255)
        return (l0, l0, l0, 255), (l1, l1, l1, 255)
    if cem == 4:
        return (v[0], v[0], v[0], v[2]), (v[1], v[1], v[1], v[3])
    if cem == 5:
        o0, b0 = _transfer(v[1], v[0])
        o1, b1 = _transfer(v[3], v[2])
        return _clamp((b0, b0, b0, b1)), _clamp((b0 + o0, b0 + o0, b0 + o0, b1 + o1))
    if cem == 6:
        return ((v[0] * v[3]) >> 8, (v[1] * v[3]) >> 8, (v[2] * v[3]) >> 8, 255), (v[0], v[1], v[2], 255)
    if cem == 8 or cem == 12:
        alpha0, alpha1 = (v[6], v[7]) if cem == 12 else (255, 255)
        if v[1] + v[3] + v[5] >= v[0] + v[2] + v[4]:
            return (v[0], v[2], v[4], alpha0), (v[1], v[3], v[5], alpha1)
        return _blue(v[1], v[3], v[5], alpha1), _blue(v[0], v[2], v[4], alpha0)
    if cem == 9 or cem == 13:
        o0, b0 = _transfer(v[1], v[0])
        o1, b1 = _transfer(v[3], v[2])
        o2, b2 = _transfer(v[5], v[4])
        oa, ba = _transfer(v[7], v[6]) if cem == 13 else (0, 255)
        if o0 + o1 + o2 >= 0:
            return _clamp((b0, b1, b2, ba)), _clamp((b0 + o0, b1 + o1, b2 + o2, ba + oa))
        return (_clamp(_blue(b0 + o0, b1 + o1, b2 + o2, ba + oa)), _clamp(_blue(b0, b1, b2, ba)))
    if cem == 10:
        return ((v[0] * v[3]) >> 8, (v[1] * v[3]) >> 8, (v[2] * v[3]) >> 8, v[4]), (v[0], v[1], v[2], v[5])
    return None     # HDR endpoint modes


def decode_block(block: bytes, bw: int, bh: int) -> bytes:
    """The RGBA bytes of the ``bw`` x ``bh`` texels of one 16-byte block, row by row."""
    count = bw * bh
    value = int.from_bytes(block, "little")
    mode = value & 0x7FF
    if mode & 0x1FF == 0x1FC:                 # void extent: one colour
        if mode & 0x200:
            return _ERROR * count
        colour = tuple(((value >> (64 + 16 * i)) & 0xFFFF) >> 8 for i in range(4))
        return bytes(colour) * count
    decoded = _block_mode(mode)
    if decoded is None:
        return _ERROR * count
    gw, gh, dual, wlevel = decoded
    if gw > bw or gh > bh:
        return _ERROR * count
    parts = ((value >> 11) & 3) + 1
    if parts == 4 and dual:
        return _ERROR * count
    nweights = gw * gh * (dual + 1)
    weight_bits = ise_size(nweights, wlevel)
    if not 24 <= weight_bits <= 96:
        return _ERROR * count
    below = 128 - weight_bits
    if parts == 1:
        cems = [(value >> 13) & 0xF]
        colour_start = 17
    else:
        seed = (value >> 13) & 0x3FF
        low = (value >> 23) & 0x3F
        if low & 3 == 0:
            cems = [low >> 2] * parts
        else:
            high_size = 3 * parts - 4
            below -= high_size
            encoded = low | (((value >> below) & ((1 << high_size) - 1)) << 6)
            base = (encoded & 3) - 1
            cems = [((((encoded >> (2 + i)) & 1) + base) << 2) for i in range(parts)]
            for i in range(parts):
                cems[i] |= (encoded >> (2 + parts + 2 * i)) & 3
        colour_start = 29
    plane2 = 0
    if dual:
        below -= 2
        plane2 = (value >> below) & 3
    nvalues = sum(((cem >> 2) + 1) * 2 for cem in cems)
    if nvalues > 18:
        return _ERROR * count
    room = below - colour_start
    level = next((lv for lv in range(len(_RANGES) - 1, -1, -1) if ise_size(nvalues, lv) <= room), -1)
    if level < 4:          # fewer than 6 levels cannot hold endpoints
        return _ERROR * count
    raw = _decode_ise(value, colour_start, nvalues, level)
    table = _colour_unquant(level)
    colours = [table[v] for v in raw]
    endpoints = []
    at = 0
    for cem in cems:
        n = ((cem >> 2) + 1) * 2
        ends = _endpoints(cem, colours[at:at + n])
        if ends is None:
            return _ERROR * count
        endpoints.append(ends)
        at += n
    reversed_value = int.from_bytes(bytes(_REV8[b] for b in reversed(block)), "little")
    wraw = _decode_ise(reversed_value, 0, nweights, wlevel)
    wtable = _weight_unquant(wlevel)
    weights = [wtable[v] for v in wraw]
    planes = [weights[0::2], weights[1::2]] if dual else [weights]
    if (gw, gh) == (bw, bh):
        texel_weights = [list(plane) for plane in planes]
    else:
        fill = _infill(bw, bh, gw, gh)
        texel_weights = [[(sum(plane[i] * f for i, f in pairs) + 8) >> 4 for pairs in fill] for plane in planes]
    owners = _partitions(seed, parts, bw, bh) if parts > 1 else (0,) * count
    w0 = texel_weights[0]
    if not dual:
        tables = [_ramp(e0, e1) for e0, e1 in endpoints]
        return b"".join(tables[owners[t]][w0[t]] for t in range(count))
    w1 = texel_weights[1]
    out = bytearray()
    for texel in range(count):
        e0, e1 = endpoints[owners[texel]]
        for channel in range(4):
            w = w1[texel] if channel == plane2 else w0[texel]
            out.append(_lerp(e0[channel], e1[channel], w))
    return bytes(out)


def _lerp(a: int, b: int, w: int) -> int:
    return ((a * 257 * (64 - w) + b * 257 * w + 32) >> 6) >> 8


@lru_cache(maxsize=65536)
def _ramp(e0: Tuple[int, ...], e1: Tuple[int, ...]) -> Tuple[bytes, ...]:
    """The RGBA bytes of every weight 0-64 between two endpoints."""
    return tuple(bytes(_lerp(a, b, w) for a, b in zip(e0, e1)) for w in range(65))


def decode(data: bytes, width: int, height: int, bw: int, bh: int) -> bytes:
    """RGBA8 bytes of a ``width`` x ``height`` image stored as linear ASTC blocks (row by row)."""
    across, down = -(-width // bw), -(-height // bh)
    pixels = bytearray(width * height * 4)
    cache = {}
    for by in range(down):
        for bx in range(across):
            at = (by * across + bx) * 16
            block = bytes(data[at:at + 16])
            texels = cache.get(block)
            if texels is None:
                texels = decode_block(block, bw, bh)
                if len(cache) < 4096:
                    cache[block] = texels
            x0 = bx * bw
            take = 4 * min(bw, width - x0)
            for ty in range(min(bh, height - by * bh)):
                start = ((by * bh + ty) * width + x0) * 4
                pixels[start:start + take] = texels[ty * bw * 4:ty * bw * 4 + take]
    return bytes(pixels)
