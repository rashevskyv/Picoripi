"""QuickLZ 1.5 level 3 streams (the Xenoblade Chronicles 3D port's font sheets and map members; header byte 0x4F).

Header: one flags byte (bit 0 compressed, bit 1 the 9-byte header, bits 2-3 the level, bit 6 set), u32 size of
the whole stream, u32 decompressed size (little-endian). Then 32-bit little-endian control words: their bits,
lowest first, tell each item (0 a literal byte, 1 a back reference); the top bit is a sentinel, so a word holds
31 items. A level-3 reference (read as a little-endian u32 ``f``): ``f & 3 == 0`` -> one byte, distance
``(f & 0xFF) >> 2``, length 3; ``f & 2 == 0`` -> two bytes, distance ``(f & 0xFFFF) >> 2``, length 3;
``f & 1 == 0`` -> two bytes, distance ``(f & 0xFFFF) >> 6``, length ``((f >> 2) & 15) + 3``;
``f & 127 != 3`` -> three bytes, distance ``(f >> 7) & 0x1FFFF``, length ``((f >> 2) & 31) + 2``; else four
bytes, distance ``f >> 15``, length ``((f >> 7) & 255) + 3``. The last 11 bytes are literals whatever the
control bits say (a control word still sits where 31 items were used).
"""
from __future__ import annotations

import struct
from typing import Dict, List, Tuple

MAGIC = 0x4F              # compressed, 9-byte header, level 3, bit 6
_TAIL = 10                # UNCONDITIONAL_MATCHLEN + UNCOMPRESSED_END
_MAX_DISTANCE = 0x1FFFF
_MAX_LEN = 258
_CHAIN = 64


def is_quicklz(data: bytes, offset: int = 0) -> bool:
    if len(data) < offset + 9 or data[offset] & 0x43 != 0x43 or (data[offset] >> 2) & 3 != 3:
        return False
    size, plain = struct.unpack_from("<II", data, offset + 1)
    return 9 <= size <= len(data) - offset and plain > 0


def sizes(data: bytes, offset: int = 0) -> Tuple[int, int]:
    """``(stream size, decompressed size)``."""
    return struct.unpack_from("<II", data, offset + 1)


def decompress(data: bytes, offset: int = 0) -> bytes:
    flags = data[offset]
    size, plain = struct.unpack_from("<II", data, offset + 1)
    if not flags & 1:                                  # stored
        return bytes(data[offset + 9:offset + 9 + plain])
    src, out = offset + 9, bytearray()
    last_matchstart = plain - 1 - _TAIL
    cword = 1
    try:
        while True:
            if cword == 1:
                cword = int.from_bytes(data[src:src + 4], "little")
                src += 4
            if cword & 1:
                cword >>= 1
                f = int.from_bytes(data[src:src + 4].ljust(4, b"\0"), "little")
                if f & 3 == 0:
                    dist, length, src = (f & 0xFF) >> 2, 3, src + 1
                elif f & 2 == 0:
                    dist, length, src = (f & 0xFFFF) >> 2, 3, src + 2
                elif f & 1 == 0:
                    dist, length, src = (f & 0xFFFF) >> 6, ((f >> 2) & 15) + 3, src + 2
                elif f & 127 != 3:
                    dist, length, src = (f >> 7) & 0x1FFFF, ((f >> 2) & 31) + 2, src + 3
                else:
                    dist, length, src = f >> 15, ((f >> 7) & 255) + 3, src + 4
                if not 0 < dist <= len(out):
                    raise ValueError("QuickLZ: a reference before the start")
                start = len(out) - dist
                for k in range(length):
                    out.append(out[start + k])
            elif len(out) < last_matchstart:
                out.append(data[src])
                src += 1
                cword >>= 1
            else:
                while len(out) < plain:
                    if cword == 1:
                        src += 4
                        cword = 1 << 31
                    out.append(data[src])
                    src += 1
                    cword >>= 1
                return bytes(out)
    except IndexError as error:
        raise ValueError("QuickLZ: the stream ends early") from error


def compress(data: bytes) -> bytes:
    """A level-3 stream that ``decompress`` (and the game) read back as ``data``."""
    n = len(data)
    out = bytearray(9)
    cword_at = len(out)
    out += bytes(4)
    cword = 1 << 31
    heads: Dict[bytes, List[int]] = {}
    pos = 0

    def flush_cword(at: int, value: int) -> None:
        struct.pack_into("<I", out, at, (value >> 1) | (1 << 31))

    while pos <= n - 1 - _TAIL:
        if cword & 1:
            flush_cword(cword_at, cword)
            cword_at = len(out)
            out += bytes(4)
            cword = 1 << 31
        best = dist = 0
        limit = min(_MAX_LEN, n - 4 - pos)                  # never into the last 4 bytes
        if limit >= 3:
            for cand in reversed(heads.get(data[pos:pos + 3], [])[-_CHAIN:]):
                if pos - cand > _MAX_DISTANCE:
                    break
                length = 3
                while length < limit and data[cand + length] == data[pos + length]:
                    length += 1
                if length > best:
                    best, dist = length, pos - cand
                    if length == limit:
                        break
        if best >= 3:
            cword = (cword >> 1) | (1 << 31)
            out += _reference(dist, best)
            step = best
        else:
            cword >>= 1
            out.append(data[pos])
            step = 1
        for p in range(pos, min(pos + step, n - 2)):
            heads.setdefault(data[p:p + 3], []).append(p)
        pos += step
    while pos < n:
        if cword & 1:
            flush_cword(cword_at, cword)
            cword_at = len(out)
            out += bytes(4)
            cword = 1 << 31
        out.append(data[pos])
        pos += 1
        cword >>= 1
    while not cword & 1:
        cword >>= 1
    flush_cword(cword_at, cword)
    out[0] = MAGIC
    struct.pack_into("<II", out, 1, len(out), n)
    return bytes(out)


def _reference(dist: int, length: int) -> bytes:
    if length == 3 and dist <= 63:
        return bytes([dist << 2])
    if length == 3 and dist <= 16383:
        return ((dist << 2) | 1).to_bytes(2, "little")
    if length <= 18 and dist <= 1023:
        return (((length - 3) << 2) | (dist << 6) | 2).to_bytes(2, "little")
    if length <= 33:
        return (((length - 2) << 2) | (dist << 7) | 3).to_bytes(3, "little")
    return (((length - 3) << 7) | (dist << 15) | 3).to_bytes(4, "little")


if __name__ == "__main__":                          # self-check: random data round trips
    import random
    rng = random.Random(1)
    for size in (1, 5, 11, 12, 40, 300, 5000):
        sample = bytes(rng.choice(b"\0\0\0abcab") for _ in range(size))
        assert decompress(compress(sample)) == sample, size
    print("ok")
