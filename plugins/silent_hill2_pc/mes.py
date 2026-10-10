"""Silent Hill 2 (PC, Enhanced Edition data, also the Switch homebrew data) message files: data\\etc\\message\\*.mes.

Layout (checked on the English and the Russian-pack files):
  * u16 table: entry k is the start of message k divided by two; entry 0 is the message count
  * a message: a header ``00 80 XX``, then text bytes and control bytes, usually ended by ``0e ff ff 00 90``
    (or the next header)

Text: printable ASCII is shown as itself; 0x00 is a space; 0x07 is an apostrophe (DON'T); every other byte is an
opaque tag ``{XX}`` that is kept as it is. ``encode(decode(m)) == m`` for every message of every file.
The table is rebuilt on save, so a changed message may take more bytes (the file is a standalone file on the PC).
"""
from __future__ import annotations

import re
import struct
from typing import List

TAG_RE = re.compile(r"\{([0-9A-Fa-f]{2})\}")
APOSTROPHE = 0x07


def table_starts(data: bytes) -> List[int]:
    count = struct.unpack_from("<H", data, 0)[0]
    if count == 0 or 2 * count > len(data):
        raise ValueError("not a message file: empty table")
    starts = [struct.unpack_from("<H", data, 2 * i)[0] * 2 for i in range(count)]
    if starts[0] != 2 * count or any(starts[i] >= starts[i + 1] for i in range(count - 1)) or starts[-1] >= len(data):
        raise ValueError("not a message file: table does not fit")
    return starts


def split(data: bytes) -> List[bytes]:
    starts = table_starts(data)
    ends = starts[1:] + [len(data)]
    return [data[s:e] for s, e in zip(starts, ends)]


def decode(raw: bytes) -> str:
    out = []
    for b in raw:
        if b == 0x00:
            out.append(" ")
        elif b == APOSTROPHE:
            out.append("'")
        elif 0x21 <= b <= 0x7E and b not in (0x27, 0x7B, 0x7D):
            out.append(chr(b))
        else:
            out.append("{%02X}" % b)
    return "".join(out)


def encode(text: str) -> bytes:
    out = bytearray()
    pos = 0
    for m in TAG_RE.finditer(text):
        out += _plain(text[pos:m.start()])
        out.append(int(m.group(1), 16))
        pos = m.end()
    out += _plain(text[pos:])
    return bytes(out)


def _plain(text: str) -> bytes:
    out = bytearray()
    for ch in text:
        if ch == " ":
            out.append(0x00)
        elif ch == "'":
            out.append(APOSTROPHE)
        elif 0x21 <= ord(ch) <= 0x7E:
            out.append(ord(ch))
        else:
            raise ValueError(f"character {ch!r} is not in the game's text (use {{XX}} for a code)")
    return bytes(out)


def build(messages: List[bytes]) -> bytes:
    """A message file from its messages: the table is rebuilt from the message lengths (each padded to 2 bytes)."""
    padded = [m if len(m) % 2 == 0 else m + b"\x00" for m in messages]
    count = len(padded)
    table = bytearray()
    position = 2 * count
    for m in padded:
        table += struct.pack("<H", position // 2)
        position += len(m)
    return bytes(table) + b"".join(padded)
