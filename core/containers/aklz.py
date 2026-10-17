"""Skies of Arcadia Legends (GameCube) ``AKLZ`` files: an LZSS stream with a 4096-byte ring buffer.

Layout (the GameCube script and table files of the USA disc, ``files/field/*.sct`` and the other folders):

  0   4 bytes  ``AKLZ``
  4   8 bytes  two constant words (``7e 3f 51 64``, ``3d cc cc cd``): kept as they are when a file is written
  12  u32 BE   size of the decompressed data
  16  stream   groups of one flag byte and eight items; flag bit 0 (least significant first) = 1 is a literal
               byte, 0 is a reference of two bytes ``b0 b1``: ring offset ``b0 | (b1 & 0xF0) << 4`` and copy
               length ``(b1 & 0x0F) + 3``. The ring starts zero-filled with the write index at 0xFEE.

A reference reads the ring at its absolute index, so a copy can overlap the bytes it writes, as in LZSS.
The decoder stops when it has the decompressed size. ``encode`` writes a valid stream of the same layout, not
the original encoder's bytes: ``decode(encode(x)) == x`` is the round-trip rule.
"""
from __future__ import annotations

import struct
from typing import Dict, List, Tuple

MAGIC = b"AKLZ"
CONSTANT_WORDS = b"\x7e\x3f\x51\x64\x3d\xcc\xcc\xcd"
HEADER_SIZE = 16
RING_SIZE = 4096
RING_START = 0xFEE
MIN_MATCH = 3
MAX_MATCH = 18


def is_aklz(data: bytes) -> bool:
    return data[:4] == MAGIC


def decompressed_size(data: bytes) -> int:
    if len(data) < HEADER_SIZE or not is_aklz(data):
        raise ValueError("not an AKLZ file")
    return struct.unpack_from(">I", data, 12)[0]


def decode(data: bytes) -> bytes:
    """The decompressed body of an AKLZ file. ValueError when the stream ends before the declared size."""
    size = decompressed_size(data)
    ring = bytearray(RING_SIZE)
    write = RING_START
    out = bytearray()
    pos = HEADER_SIZE
    n = len(data)
    while len(out) < size:
        if pos >= n:
            raise ValueError("AKLZ stream ends before the declared size")
        flags = data[pos]
        pos += 1
        for bit in range(8):
            if len(out) >= size:
                break
            if (flags >> bit) & 1:
                if pos >= n:
                    raise ValueError("AKLZ stream ends inside a literal")
                value = data[pos]
                pos += 1
                out.append(value)
                ring[write] = value
                write = (write + 1) & (RING_SIZE - 1)
                continue
            if pos + 1 >= n:
                raise ValueError("AKLZ stream ends inside a reference")
            b0, b1 = data[pos], data[pos + 1]
            pos += 2
            offset = b0 | ((b1 & 0xF0) << 4)
            length = (b1 & 0x0F) + MIN_MATCH
            for k in range(length):
                value = ring[(offset + k) & (RING_SIZE - 1)]
                out.append(value)
                ring[write] = value
                write = (write + 1) & (RING_SIZE - 1)
    return bytes(out[:size])


def encode(body: bytes) -> bytes:
    """An AKLZ file that holds ``body``. Greedy matching over the last 4096 bytes; literal bytes otherwise."""
    tokens: List[Tuple[int, int, int]] = []   # (kind, a, b): kind 1 literal (a = byte), 0 reference (a = pos, b = len)
    last_seen: Dict[bytes, List[int]] = {}
    i = 0
    n = len(body)
    while i < n:
        best_len = 0
        best_pos = 0
        if i + MIN_MATCH <= n:
            key = body[i:i + MIN_MATCH]
            for cand in reversed(last_seen.get(key, [])):
                if i - cand > RING_SIZE:
                    break
                length = 0
                while length < MAX_MATCH and i + length < n and body[cand + length] == body[i + length]:
                    length += 1
                if length > best_len:
                    best_len, best_pos = length, cand
                    if length == MAX_MATCH:
                        break
        if best_len >= MIN_MATCH:
            tokens.append((0, best_pos, best_len))
            step = best_len
        else:
            tokens.append((1, body[i], 0))
            step = 1
        for j in range(i, i + step):
            if j + MIN_MATCH <= n:
                bucket = last_seen.setdefault(body[j:j + MIN_MATCH], [])
                bucket.append(j)
                if len(bucket) > 64:
                    del bucket[0]
        i += step
    stream = bytearray()
    for start in range(0, len(tokens), 8):
        group = tokens[start:start + 8]
        flags = 0
        items = bytearray()
        for bit, (kind, a, b) in enumerate(group):
            if kind == 1:
                flags |= 1 << bit
                items.append(a)
            else:
                ring_index = (RING_START + a) & (RING_SIZE - 1)
                items.append(ring_index & 0xFF)
                items.append(((ring_index >> 4) & 0xF0) | (b - MIN_MATCH))
        stream.append(flags)
        stream += items
    return MAGIC + CONSTANT_WORDS + struct.pack(">I", n) + bytes(stream)
