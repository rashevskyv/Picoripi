"""
Yay0 decompression, the Nintendo LZ variant used by GameCube archives (Luigi's Mansion, among others).

Header, all big-endian: "Yay0", u32 decoded size, u32 link table offset, u32 chunk stream offset.
Mask bits start at 0x10, one 32-bit word at a time, most significant bit first. A set bit copies one
literal byte from the chunk stream. A clear bit reads a 16-bit link: distance = (link & 0xFFF) + 1,
length = (link >> 12) + 2, or, when that nibble is 0, the next chunk byte + 0x12.
Layout as in the Yay0 decoder of Luigi's Mansion Recompiled (src/recomp/rarc.cpp).
"""

from __future__ import annotations

import struct

from core.i18n import tr

_MAGIC = b"Yay0"


def decompress(data: bytes, limit: int | None = None) -> bytes:
    """Decompress Yay0 data. ``limit`` stops after that many bytes.

    ponytail: no bounds checks beyond the back-reference; truncated input raises struct.error or IndexError.
    """
    if len(data) < 16:
        raise ValueError(tr("Data too short to be Yay0"))
    if data[:4] != _MAGIC:
        raise ValueError(tr("Invalid Yay0 magic: {0!r}", data[:4]))
    size, link_off, chunk_off = struct.unpack_from(">III", data, 4)
    if limit is not None:
        size = min(size, limit)
    out = bytearray()
    mask_off, mask, bits = 16, 0, 0
    while len(out) < size:
        if bits == 0:
            mask = struct.unpack_from(">I", data, mask_off)[0]
            mask_off += 4
            bits = 32
        if mask & 0x80000000:
            out.append(data[chunk_off])
            chunk_off += 1
        else:
            link = struct.unpack_from(">H", data, link_off)[0]
            link_off += 2
            nibble = link >> 12
            if nibble:
                count = nibble + 2
            else:
                count = data[chunk_off] + 0x12
                chunk_off += 1
            start = len(out) - (link & 0xFFF) - 1
            if start < 0:
                raise ValueError(tr("Invalid Yay0 back-reference"))
            for i in range(count):
                out.append(out[start + i])
        mask = (mask << 1) & 0xFFFFFFFF
        bits -= 1
    return bytes(out[:size])


def compress(data: bytes) -> bytes:
    """Yay0 with literal bytes only: every mask bit is set and the link table is empty.

    ponytail: no back-references, so the output is larger than a Nintendo encoder's. Add the matcher when the
    disc space for a changed archive runs short.
    """
    size = len(data)
    masks = b"".join(struct.pack(">I", 0xFFFFFFFF) for _ in range((size + 31) // 32))
    link_off = 16 + len(masks)
    return _MAGIC + struct.pack(">III", size, link_off, link_off) + masks + bytes(data)
