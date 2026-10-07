"""Level-5 ``.cfg.bin`` tables ("T2B"): parse every entry and write the strings back.

Layout (little endian; StudioElevenLib ``CfgBin.cs``): a 16-byte header (entry count, string table
offset, its length, number of strings), the entries, the string table (NUL-terminated strings), a key
table (CRC32 of each entry name -> its name) and the footer ``01 74 32 62 FE 01 <encoding> 00 01 00``
(encoding 1 = UTF-8, 0 = Shift-JIS). An entry is the CRC32 of its name, a parameter count, two bits of
type per parameter (0 string offset, 1 int, 2 float), padding to 4, then one u32 per parameter. A string
parameter holds an offset into the string table, or -1.

The game's tool writes the string table as every distinct string once, in the order the entries first
refer to it, 0xFF padding to 16 before and after it. ``build`` writes exactly that, so an unedited file
comes back byte for byte (all 2005 English files of Yo-kai Watch do).
"""
from __future__ import annotations

import struct
import zlib
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Sequence

STRING, INT, FLOAT = 0, 1, 2


class FormatError(ValueError):
    """The bytes are not a cfg.bin table this module understands."""


@dataclass
class Entry:
    name: str
    types: List[int]
    values: List = field(default_factory=list)   # str or None for strings, int, float
    value_at: List[int] = field(default_factory=list)


class CfgBin:
    """A parsed table: ``entries`` in file order, ``encoding`` of its strings."""

    def __init__(self, raw: bytes):
        raw = bytes(raw)
        if len(raw) < 0x20 or b"t2b" not in raw[-0x20:]:
            raise FormatError("Not a Level-5 cfg.bin table (no t2b footer)")
        self.raw = raw
        count, self.string_offset, self.string_length, _string_count = struct.unpack_from("<4I", raw)
        footer = raw.rindex(b"\x01t2b\xfe")
        self.encoding = "utf-8" if raw[footer + 6] else "shift-jis"
        try:
            raw[self.string_offset:self.string_offset + self.string_length].decode(self.encoding)
        except UnicodeDecodeError:
            self.encoding = "cp932"      # Yo-kai Watch 1 (Switch): some Japanese tables say UTF-8 but hold Shift-JIS
        keys = self._keys()
        self.entries: List[Entry] = []
        pos = 0x10
        for _ in range(count):
            if pos + 5 > len(raw):
                raise FormatError("cfg.bin entries run past the end of the file")
            crc, params = struct.unpack_from("<IB", raw, pos)
            types = [(raw[pos + 5 + i // 4] >> 2 * (i % 4)) & 3 for i in range(params)]
            at = (pos + 5 + (params + 3) // 4 + 3) & ~3
            entry = Entry(keys.get(crc, f"{crc:08x}"), types)
            for kind in types:
                value = struct.unpack_from("<f" if kind == FLOAT else "<i", raw, at)[0]
                if kind == STRING:
                    value = None if value < 0 else self._string(value)   # -1 (one table: -2): no string
                entry.values.append(value)
                entry.value_at.append(at)
                at += 4
            self.entries.append(entry)
            pos = at
        self.entries_end = pos

    def _string(self, offset: int) -> str:
        start = self.string_offset + offset
        end = self.raw.find(b"\0", start)
        if offset < 0 or end < 0:
            raise FormatError(f"String offset {offset} is outside the string table")
        return self.raw[start:end].decode(self.encoding)

    def _keys(self) -> Dict[int, str]:
        at = (self.string_offset + self.string_length + 15) & ~15
        try:
            _size, count, names_at, _names_len = struct.unpack_from("<4I", self.raw, at)
            keys = {}
            for index in range(count):
                crc, name_at = struct.unpack_from("<Ii", self.raw, at + 16 + 8 * index)
                start = at + names_at + name_at
                keys[crc] = self.raw[start:self.raw.index(b"\0", start)].decode("utf-8", "replace")
            return keys
        except (struct.error, ValueError) as error:
            raise FormatError(f"Broken key table: {error}") from None

    def strings(self) -> List[tuple]:
        """``(entry index, parameter index, text)`` of every string parameter that is not -1, in file order."""
        return [(e, p, value) for e, entry in enumerate(self.entries)
                for p, (kind, value) in enumerate(zip(entry.types, entry.values)) if kind == STRING and value is not None]

    def build(self, texts: Optional[Dict[tuple, str]] = None) -> bytes:
        """The table with ``texts`` ({(entry, parameter): new text}) in place of those strings."""
        texts = texts or {}
        body = bytearray(self.raw[:self.entries_end])
        table = bytearray()
        offsets: Dict[bytes, int] = {}
        for e, p, value in self.strings():
            encoded = texts.get((e, p), value).encode(self.encoding)
            if b"\0" in encoded:
                raise FormatError("A string cannot contain a NUL character")
            if encoded not in offsets:
                offsets[encoded] = len(table)
                table += encoded + b"\0"
            struct.pack_into("<i", body, self.entries[e].value_at[p], offsets[encoded])
        string_offset = (len(body) + 15) & ~15
        out = body + b"\xff" * (string_offset - len(body)) + table
        out += b"\xff" * (-len(out) % 16)
        out += self.raw[(self.string_offset + self.string_length + 15) & ~15:]
        struct.pack_into("<4I", out, 0, len(self.entries), string_offset, len(table), len(offsets))
        return bytes(out)


def crc32(text: str) -> int:
    """The id the games use for names and keys (zlib CRC32 of the UTF-8 bytes)."""
    return zlib.crc32(text.encode("utf-8"))


def u32(value: int) -> int:
    """A parameter read as signed back to the unsigned id."""
    return value & 0xFFFFFFFF


def find(entries: Sequence[Entry], name: str) -> List[Entry]:
    return [entry for entry in entries if entry.name == name]
