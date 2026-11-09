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


def compress_matched(data: bytes, smallest: bool = False) -> bytes:
    """Yay0 with back-references: the Yaz0 matcher's stream split into Yay0's mask, link and chunk streams.

    The two formats code a link the same way (12-bit distance, length nibble or an extra length byte); Yaz0 keeps
    the flags, links and literals in one stream, Yay0 in three. The default is greedy with one-step lazy matching over
    every candidate in the window (a few seconds, a little smaller than Nintendo's encoder on Luigi's Mansion);
    ``smallest`` is the optimal parse, minutes on a 300 KB archive.
    """
    from core.containers import yaz0

    packed = yaz0.compress_smallest(data) if smallest else yaz0.compress(data, max_candidates=None)
    size = len(data)
    masks, links, chunks = [], bytearray(), bytearray()
    word = bits = done = 0
    src = 16
    while done < size:
        flags = packed[src]
        src += 1
        for bit in range(8):
            if done >= size:
                break
            literal = flags & (0x80 >> bit)
            word, bits = (word << 1) | (1 if literal else 0), bits + 1
            if bits == 32:
                masks.append(word)
                word = bits = 0
            if literal:
                chunks.append(packed[src])
                src, done = src + 1, done + 1
                continue
            high, low = packed[src], packed[src + 1]
            links += bytes((high, low))
            src += 2
            if high >> 4:
                done += (high >> 4) + 2
            else:
                chunks.append(packed[src])
                done += packed[src] + 0x12
                src += 1
    if bits:
        masks.append(word << (32 - bits))
    mask_bytes = struct.pack(f">{len(masks)}I", *masks)
    link_off = 16 + len(mask_bytes)
    return (_MAGIC + struct.pack(">III", size, link_off, link_off + len(links)) + mask_bytes + bytes(links)
            + bytes(chunks))


def compress(data: bytes) -> bytes:
    """Yay0 with literal bytes only: every mask bit is set and the link table is empty.

    ponytail: no back-references, so the output is larger than a Nintendo encoder's but fast; ``compress_matched``
    is for a member with no room to grow.
    """
    size = len(data)
    masks = b"".join(struct.pack(">I", 0xFFFFFFFF) for _ in range((size + 31) // 32))
    link_off = 16 + len(masks)
    return _MAGIC + struct.pack(">III", size, link_off, link_off) + masks + bytes(data)
