"""Peace Walker (HD / Master Collection) language files ``*.olang``: the "RBX" string bank.

Layout (little-endian)::

    "RBX\\0", u32 id, u32 0, u16 0, u16 group count, u32 0x20 (header size),
    u32 strings table, u32 variants table, u32 text area
    groups    [group count] x (u32 hash, u16 first string, u16 string count)
    strings   x (u32 key, u16 first variant, u16 variant count)
    variants  x (u32 language, u32 text offset (from the text area), u32 flags)
    text area: NUL-terminated UTF-8 strings (shared by equal texts)

Each string has one variant per language (6: English 3342, French, German, Italian, Japanese, Spanish; some have
two per language). A line is one English variant, in string order. ``build`` appends each new text at the end of
the text area and points its variant at it; every other byte stays as it was, so an unedited file keeps its bytes.
"""
from __future__ import annotations

import struct
from typing import List, Optional, Sequence, Tuple

MAGIC = b"RBX\0"
ENGLISH = 3342


def is_olang(data: bytes) -> bool:
    return bytes(data[:4]) == MAGIC


def _tables(data: bytes):
    if not is_olang(data):
        raise ValueError("not an RBX language file")
    _magic, _id, _z, _z2, _groups, _head, strings, variants, text = struct.unpack_from("<4sIIHHIIII", data, 0)
    return strings, variants, text


def english(data: bytes) -> List[Tuple[int, str]]:
    """``[(variant index, English text)]`` in string order."""
    data = bytes(data)
    strings, variants, text = _tables(data)
    out = []
    for index in range((variants - strings) // 8):
        _key, first, count = struct.unpack_from("<IHH", data, strings + 8 * index)
        for variant in range(first, first + count):
            language, offset, _flags = struct.unpack_from("<III", data, variants + 12 * variant)
            if language == ENGLISH:
                end = data.index(b"\0", text + offset)
                out.append((variant, data[text + offset:end].decode("utf-8")))
    return out


def lines(data: bytes) -> List[str]:
    return [text for _variant, text in english(data)]


def build(data: bytes, texts: Sequence[Optional[str]]) -> bytes:
    """``data`` with the English texts replaced (None or the same text = unchanged)."""
    data = bytes(data)
    _strings, variants, text = _tables(data)
    out = bytearray(data)
    added = {}
    for (variant, old), new in zip(english(data), texts):
        if new is None or new == old:
            continue
        if new not in added:
            added[new] = len(out) - text
            out += new.encode("utf-8") + b"\0"
        struct.pack_into("<I", out, variants + 12 * variant + 4, added[new])
    return bytes(out) if added else data
