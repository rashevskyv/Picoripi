"""Capcom ``GMD`` message tables of Monster Hunter Stories (Switch, MT Framework 2, version 0x00010302).

``GMD\0``, u32 version, u32 language, u32 hash, u32 0, u32 label count, u32 string count, u32 label area size, u32
string area size, u32 name length, the name and a NUL; then ``label count`` 32-byte records (u32 index, u32 two
hashes, u32 0xCDCDCDCD, u64 offset of the label in the label area, 8 zero bytes); 0x800 bytes of hash buckets; the
label area (NUL-ended names); the string area (UTF-8, each string ended by a NUL, one per record, in record order).
Rebuilding writes the new string area and its size; everything else is copied. Markup like ``<COL F00000FF>``,
``<SPNM NAVI>``, ``<PAGE>``, ``<ICON ...>`` is plain text in the strings; a line break is CR LF.
"""
from __future__ import annotations

import struct
from typing import List, Sequence

MAGIC = b"GMD\0"
HEAD = struct.Struct("<4sIIIIIIIII")
SIZE_AT = 0x20


class Table:
    """A GMD v2 table. ``build`` returns the original bytes while no string changed."""

    def __init__(self, raw: bytes):
        if raw[:4] != MAGIC or len(raw) < HEAD.size:
            raise ValueError("not a GMD table")
        self.raw = bytes(raw)
        (_m, self.version, self.language, _hash, _zero, self.labels, self.strings, self.label_size,
         self.string_size, name_size) = HEAD.unpack_from(raw, 0)
        if self.version != 0x00010302:
            raise ValueError(f"unsupported GMD version {self.version:#x}")
        self.items_at = HEAD.size + name_size + 1
        self.label_at = self.items_at + 32 * self.labels + 0x800
        self.string_at = self.label_at + self.label_size
        if self.string_at + self.string_size != len(raw):
            raise ValueError("GMD sizes do not match the file")
        pool = raw[self.string_at:]
        parts = pool.split(b"\0")
        if parts and parts[-1] == b"":
            parts = parts[:-1]
        if len(parts) != self.strings:
            raise ValueError(f"GMD holds {len(parts)} strings, the header says {self.strings}")
        self._texts = [p.decode("utf-8") for p in parts]
        self._ids = []
        for i in range(self.labels):
            off = struct.unpack_from("<Q", raw, self.items_at + 32 * i + 16)[0]
            at = self.label_at + off
            self._ids.append(raw[at:raw.index(b"\0", at)].decode("utf-8", "replace") or str(i))

    def texts(self) -> List[str]:
        return list(self._texts)

    def ids(self) -> List[str]:
        return list(self._ids) if len(self._ids) == len(self._texts) else [str(i) for i in range(len(self._texts))]

    def build(self, texts: Sequence[str]) -> bytes:
        if list(texts) == self._texts:
            return self.raw
        if len(texts) != len(self._texts):
            raise ValueError(f"the table holds {len(self._texts)} strings, {len(texts)} were given")
        pool = b"".join(t.encode("utf-8") + b"\0" for t in texts)
        out = bytearray(self.raw[:self.string_at]) + pool
        struct.pack_into("<I", out, SIZE_AT, len(pool))
        return bytes(out)
