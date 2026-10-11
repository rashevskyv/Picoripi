"""The messages of one Silent Hill 3 (PC) ``*_eng_msg.mes`` file as Picoripi strings, and how to write them back.

A ``.mes`` file is a table of 16-bit offsets followed by the strings. The first u16 is the number of
strings ``n``; the table holds ``n`` offsets, each counted in 2-byte units from the start of the file.
String ``k`` runs from offset ``k`` to offset ``k + 1`` (the last one ends at the file end). The table
is checked on every read; a file that does not fit this layout is not opened.

Unchanged strings are written back from their own bytes, so a file that was not edited is rebuilt
byte for byte. An edited string is encoded by ``codec`` and padded with a zero byte to a whole unit.
"""
from __future__ import annotations

import struct
from typing import List, Sequence, Tuple

from . import codec


def strings(data: bytes) -> List[bytes]:
    """The raw bytes of every string of the file; raises ValueError when the table does not fit."""
    if len(data) < 2 or len(data) % 2:
        raise ValueError("message file: size is not a whole number of units")
    count = struct.unpack_from("<H", data, 0)[0]
    if count == 0 or 2 * count > len(data):
        raise ValueError("message file: bad string count")
    offsets = list(struct.unpack_from("<%dH" % count, data, 0))
    if offsets[0] != count:
        raise ValueError("message file: the first string does not start after the table")
    end_units = len(data) // 2
    offsets.append(end_units)
    for k in range(count):
        if offsets[k + 1] < offsets[k]:
            raise ValueError("message file: offsets go backwards")
    return [data[offsets[k] * 2:offsets[k + 1] * 2] for k in range(count)]


def texts(data: bytes) -> List[str]:
    return [codec.decode(raw) for raw in strings(data)]


def build(source: bytes, new_texts: Sequence[str]) -> Tuple[bytes, List[str]]:
    """The file with the edited strings; returns (bytes, problems). A string that cannot be encoded keeps
    its own bytes and is reported."""
    raws = strings(source)
    if len(new_texts) != len(raws):
        return source, [f"string count {len(new_texts)} differs from {len(raws)} in the source"]
    problems: List[str] = []
    parts: List[bytes] = []
    for k, (raw, text) in enumerate(zip(raws, new_texts)):
        if codec.decode(raw) == text:
            parts.append(raw)
            continue
        try:
            body = codec.encode(text)
        except ValueError as error:
            problems.append(f"string {k}: {error}")
            parts.append(raw)
            continue
        if len(body) % 2:
            body += b"\0"
        parts.append(body)
    count = len(raws)
    offsets = [count]
    for part in parts:
        offsets.append(offsets[-1] + len(part) // 2)
    head = struct.pack("<%dH" % count, *offsets[:count])
    return head + b"".join(parts), problems
