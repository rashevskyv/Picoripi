"""N64 IPL3 header checksum (CIC-6105): the two words at ROM 0x10 and 0x14.

The checksum covers ROM 0x1000 to 0x101000. The 6105 variant reads a table word from the boot code at
ROM 0x750 + (address & 0xFF). Verified: both words of the US Conker header match this computation.
"""
from __future__ import annotations

import struct

from . import n64_archive as na

SEED_6105 = 0xDF26F436
START = 0x1000
END = 0x101000
TABLE_BASE = 0x750
CRC_OFFSET = 0x10
MASK = 0xFFFFFFFF


def _rotl(value: int, shift: int) -> int:
    shift &= 31
    if shift == 0:
        return value
    return ((value << shift) | (value >> (32 - shift))) & MASK


def compute(rom: bytes) -> tuple[int, int]:
    """Return (CRC1, CRC2) for a normalized big-endian ROM."""
    if len(rom) < END:
        raise na.RomError("ROM is too short for the header checksum")
    t1 = t2 = t3 = t4 = t5 = t6 = SEED_6105
    address = START
    for (d,) in struct.iter_unpack(">I", rom[START:END]):
        if ((t6 + d) & MASK) < t6:
            t4 = (t4 + 1) & MASK
        t6 = (t6 + d) & MASK
        t3 ^= d
        r = _rotl(d, d & 0x1F)
        t5 = (t5 + r) & MASK
        if t2 > d:
            t2 ^= r
        else:
            t2 ^= (t6 ^ d)
        table = struct.unpack_from(">I", rom, TABLE_BASE + (address & 0xFF))[0]
        t1 = (t1 + (table ^ d)) & MASK
        address += 4
    return (t6 ^ t4 ^ t3) & MASK, (t5 ^ t2 ^ t1) & MASK


def fix(rom: bytes) -> bytes:
    """Return the ROM with its two header checksum words recomputed."""
    crc1, crc2 = compute(rom)
    out = bytearray(rom)
    struct.pack_into(">II", out, CRC_OFFSET, crc1, crc2)
    return bytes(out)


def is_valid(rom: bytes) -> bool:
    return struct.unpack_from(">II", rom, CRC_OFFSET) == compute(rom)
