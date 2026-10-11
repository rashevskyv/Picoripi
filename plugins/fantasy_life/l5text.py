"""Fantasy Life text files: a Level-5 table of UTF-16 strings, alone or as the first item of a small container.

Table (little endian, at ``base`` in the file; ``base`` is 0 for a plain table)::

    +0x00 u32 0x1D038013  +0x0C u32 payload size (the table's bytes - 0x20)  +0x10 u32 0x20
    +0x20 u32 id  u32 0  u32 0  u32 string count  u32 4  u32 offset of the offset list (0x38)
    +offset: count * u32 offsets of the strings (from ``base``), then the strings: UTF-16, NUL-terminated and
    padded to 4 bytes

Container: ``u32 n`` (1..8), ``n + 1`` u32 offsets (the first is 4 + 4 * (n + 1)), the items back to back.

Text is plain UTF-16. Control sequences use units below 0x20 and from 0xFFF0 on: they are shown as
``{c:XXXX.XXXX...}`` tags (one per run), except the line break (``FFF0 FFFF 0004 0000``, preceded by one ``FFFF``
pad unit when it would start between two 4-byte words), which is a real new line.
"""
from __future__ import annotations

import re
import struct
from typing import List, Optional, Tuple

TABLE_MAGIC = 0x1D038013
TAG_RE = re.compile(r"\{c:[0-9a-f]{4}(?:\.[0-9a-f]{4})*\}")
_BREAK = (0xFFF0, 0xFFFF, 0x0004, 0x0000)


class FormatError(ValueError):
    """Not a Fantasy Life text file."""


def _is_control(unit: int) -> bool:
    return unit < 0x20 or unit >= 0xFFF0


def _table_at(data: bytes, base: int) -> Optional[Tuple[int, int, int]]:
    """``(count, offset list at, end)`` of a table at ``base`` or None."""
    if len(data) < base + 0x40 or struct.unpack_from("<I", data, base)[0] != TABLE_MAGIC:
        return None
    count, stride, at = struct.unpack_from("<III", data, base + 0x2C)
    if stride != 4 or not 0 < count <= 200000 or base + at + 4 * count > len(data):
        return None
    end = base + struct.unpack_from("<I", data, base + 0x0C)[0] + 0x20
    if end > len(data):
        return None
    return count, at, end


def _content(units: Tuple[int, ...]) -> Tuple[int, ...]:
    """The units of a string without its NUL terminator and padding. A command (``FFFx FFFF n 0`` and ``n - 4``
    more bytes) is taken whole, so a command that ends with zeros keeps them."""
    i, last, n = 0, 0, len(units)
    while i < n:
        unit = units[i]
        if unit >= 0xFFF0 and i + 3 < n and units[i + 1] == 0xFFFF:
            i += 2 + units[i + 2] // 2
            last = min(i, n)
            continue
        i += 1
        if unit:
            last = i
    return units[:last]


def decode(entry: bytes) -> str:
    """One string's bytes as editor text."""
    units = _content(struct.unpack(f"<{len(entry) // 2}H", entry[:len(entry) // 2 * 2]))
    out: List[str] = []
    run: List[int] = []
    pos = 0              # units written so far (for the alignment of a break)

    def flush() -> None:
        nonlocal pos
        if not run:
            return
        seq = tuple(run)
        if seq == _BREAK or (seq[:1] == (0xFFFF,) and seq[1:] == _BREAK and pos % 2 == 1):
            out.append("\n")
        else:
            out.append("{c:" + ".".join(f"{u:04x}" for u in seq) + "}")
        pos += len(seq)
        run.clear()

    for unit in units:
        if _is_control(unit):
            run.append(unit)
        else:
            flush()
            out.append(chr(unit) if not 0xD800 <= unit < 0xE000 else "�")
            pos += 1
    flush()
    return "".join(out)


def encode(text: str, pad4: bool = True) -> bytes:
    """Editor text -> the string's bytes: units, a NUL, zero padding to 4 bytes (``pad4``: the table pads)."""
    units: List[int] = []
    pos = 0
    while pos < len(text):
        tag = TAG_RE.match(text, pos)
        if tag:
            units += [int(u, 16) for u in tag.group()[3:-1].split(".")]
            pos = tag.end()
        elif text[pos] == "\n":
            if len(units) % 2:
                units.append(0xFFFF)
            units += _BREAK
            pos += 1
        else:
            j = pos
            while j < len(text) and text[j] != "\n" and not TAG_RE.match(text, j):
                j += 1
            raw = text[pos:j].encode("utf-16-le", "surrogatepass")
            units += struct.unpack(f"<{len(raw) // 2}H", raw)
            pos = j
    units.append(0)
    raw = struct.pack(f"<{len(units)}H", *units)
    return raw + bytes(-len(raw) % 4) if pad4 else raw


class L5Text:
    """A parsed text file: ``strings`` (editor text) and ``build``."""

    def __init__(self, data: bytes):
        self.data = bytes(data)
        self.base = 0
        found = _table_at(self.data, 0)
        self.container: List[int] = []
        if found is None and len(self.data) > 16:
            n = struct.unpack_from("<I", self.data, 0)[0]
            if 1 <= n <= 8 and struct.unpack_from("<I", self.data, 4)[0] == 4 + 4 * (n + 1):
                offs = struct.unpack_from(f"<{n + 1}I", self.data, 4)
                for k in range(n):
                    found = _table_at(self.data, offs[k])
                    if found is not None:
                        self.base, self.container = offs[k], list(offs)
                        break
        if found is None:
            raise FormatError("not a Fantasy Life text table")
        self.count, self.list_at, self.end = found
        offs = struct.unpack_from(f"<{self.count}I", self.data, self.base + self.list_at)
        if any(a > b for a, b in zip(offs, offs[1:])):
            raise FormatError("string offsets are not ascending")
        self.entries = [self.data[self.base + o:self.base + (offs[i + 1] if i + 1 < self.count else self.end - self.base)]
                        for i, o in enumerate(offs)]
        # most tables pad every string to 4 bytes; some (older ones) run the strings together
        self.pad4 = all(len(e) % 4 == 0 for e in self.entries)
        self.strings = [decode(e) for e in self.entries]
        self.exact = [encode(s, self.pad4) == e for s, e in zip(self.strings, self.entries)]

    def build(self, texts: List[str]) -> bytes:
        if len(texts) != self.count:
            raise FormatError(f"{len(texts)} strings for {self.count}")
        entries = []
        for i, text in enumerate(texts):
            entries.append(self.entries[i] if text == self.strings[i] else encode(text, self.pad4))
        offsets, at = [], self.list_at + 4 * self.count
        for e in entries:
            offsets.append(at)
            at += len(e)
        table = bytearray(self.data[self.base:self.base + self.list_at])
        table += struct.pack(f"<{self.count}I", *offsets) + b"".join(entries)
        struct.pack_into("<I", table, 0x0C, len(table) - 0x20)
        if not self.container:
            return bytes(table)
        # container: the table item is replaced, the offsets of the items behind it move
        n = len(self.container) - 1
        item = self.container.index(self.base)
        old_len = self.container[item + 1] - self.base
        shift = len(table) - old_len
        offs = [o + shift if k > item else o for k, o in enumerate(self.container)]
        head = struct.pack("<I", n) + struct.pack(f"<{n + 1}I", *offs)
        return head + self.data[self.container[0]:self.base] + bytes(table) + self.data[self.container[item + 1]:]
