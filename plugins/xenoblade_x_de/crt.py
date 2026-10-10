"""The credits roll of Xenoblade Chronicles X: Definitive Edition (``ui/credit/endroll.crt``): ``CRT\\0``, u32 row
count, u32 rows offset (16), u32 string table offset; a row is 39 u32 (a float position, a flag, two zeros, then
seven text slots of five u32: unknown, size, colour, alignment, string offset into the table or 0xFFFFFFFF for
none). ``read`` lists every used slot's text in row order; ``write`` rebuilds the string table (shared strings
kept shared) and the slot offsets, the rows' other words stay.
"""
from __future__ import annotations

import struct
from typing import List

MAGIC = b"CRT\0"
NONE = 0xFFFFFFFF
WORDS = 39
SLOTS = range(4 + 4, WORDS, 5)      # the string-offset word of each slot


def is_crt(data: bytes) -> bool:
    return len(data) >= 16 and data[:4] == MAGIC and struct.unpack_from("<I", data, 12)[0] <= len(data)


def _rows(data: bytes):
    count, at, strings = struct.unpack_from("<3I", data, 4)
    return count, at, strings


def read(data: bytes) -> List[str]:
    count, at, strings = _rows(data)
    out = []
    for row in range(count):
        words = struct.unpack_from(f"<{WORDS}I", data, at + row * WORDS * 4)
        for k in SLOTS:
            if words[k] != NONE:
                end = data.index(b"\0", strings + words[k])
                out.append(data[strings + words[k]:end].decode("utf-8"))
    return out


def write(data: bytes, texts: List[str]) -> bytes:
    count, at, strings = _rows(data)
    slots = [at + row * WORDS * 4 + 4 * k for row in range(count) for k in SLOTS
             if struct.unpack_from("<I", data, at + row * WORDS * 4 + 4 * k)[0] != NONE]
    if len(slots) != len(texts):
        raise ValueError(f"the credits file has {len(slots)} texts, the project {len(texts)}")
    body = bytearray(data[:strings])
    table, where = bytearray(), {}
    for slot, text in zip(slots, texts):
        if text not in where:
            where[text] = len(table)
            table += text.encode("utf-8") + b"\0"
        struct.pack_into("<I", body, slot, where[text])
    return bytes(body) + bytes(table) + bytes(-len(table) % 16)
