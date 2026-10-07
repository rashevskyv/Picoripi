"""Retro Studios STRG string tables of the Wii Metroid Prime games (as on Metroid Prime Trilogy), big endian.

Header: magic 0x87654321, u32 version, u32 language count, u32 string count. Then:

- version 0 (Prime 1): languages (fourcc, u32 offset); at each offset from the end of that table: u32 size,
  string offsets from after the size field, UTF-16 strings ending in 0.
- version 1 (Prime 2): languages (fourcc, u32 offset, u32 size), a name table, then at each offset the string
  offsets from that language's start and UTF-16 strings.
- version 3 (Prime 3, the Trilogy menu): a name table, the language fourccs, per language u32 size and the
  string offsets from the start of the string data; each string is u32 length (with its 0) and UTF-8.

The name table: u32 name count, u32 size, then (u32 name offset, u32 string index) and the names.

``build`` writes the given strings as the text of every language (one shared copy), which keeps the table
small enough for its slot in the package and shows the translation whatever the console language is. Building
the original English strings gives the original bytes back.
"""
from __future__ import annotations

import struct
from typing import Dict, List

MAGIC = 0x87654321
ENGLISH = "ENGL"


class Strg:
    """One string table: ``languages`` (fourccs), ``strings`` {language: [text]}, ``raw`` (the file)."""

    def __init__(self, raw: bytes):
        self.raw = bytes(raw)
        magic, self.version, langs, count = struct.unpack_from(">IIII", raw)
        if magic != MAGIC or self.version not in (0, 1, 3):
            raise ValueError("Not a Metroid Prime STRG")
        self.count = count
        self.names = b""                 # the name table, kept as it is
        self.strings: Dict[str, List[str]] = {}
        if self.version == 3:
            self._read_v3(langs)
        else:
            self._read_utf16(langs)

    def _name_table(self, at: int) -> int:
        size = struct.unpack_from(">I", self.raw, at + 4)[0]
        self.names = self.raw[at:at + 8 + size]
        return at + 8 + size

    def _read_utf16(self, langs: int) -> None:
        raw, step = self.raw, 8 if self.version == 0 else 12
        table = [struct.unpack_from(">4sI", raw, 16 + step * i) for i in range(langs)]
        self.languages = [fourcc.decode("ascii") for fourcc, _off in table]
        start = 16 + step * langs
        if self.version == 1:
            start = self._name_table(start)
        for lang, (_fourcc, offset) in zip(self.languages, table):
            base = start + offset + (4 if self.version == 0 else 0)
            offsets = struct.unpack_from(f">{self.count}I", raw, base)
            self.strings[lang] = [_utf16(raw, base + off) for off in offsets]

    def _read_v3(self, langs: int) -> None:
        raw = self.raw
        at = self._name_table(16)
        self.languages = [raw[at + 4 * i:at + 4 * i + 4].decode("ascii") for i in range(langs)]
        at += 4 * langs
        tables = []
        for _ in range(langs):
            tables.append(struct.unpack_from(f">{self.count}I", raw, at + 4))
            at += 4 + 4 * self.count
        for lang, offsets in zip(self.languages, tables):
            texts = []
            for off in offsets:
                length = struct.unpack_from(">I", raw, at + off)[0]
                texts.append(raw[at + off + 4:at + off + 4 + length].rstrip(b"\0").decode("utf-8"))
            self.strings[lang] = texts

    @property
    def english(self) -> List[str]:
        return list(self.strings.get(ENGLISH) or next(iter(self.strings.values()), []))

    def build(self, texts: List[str]) -> bytes:
        """The table with ``texts`` as the strings of every language."""
        texts = list(texts)
        if len(texts) != self.count:
            raise ValueError(f"STRG has {self.count} strings, got {len(texts)}")
        if texts == self.english:
            return self.raw
        langs = len(self.languages)
        head = struct.pack(">IIII", MAGIC, self.version, langs, self.count)
        if self.version == 3:
            data, offsets, seen = bytearray(), [], {}
            for text in texts:
                if text not in seen:
                    seen[text] = len(data)
                    encoded = text.encode("utf-8") + b"\0"
                    data += struct.pack(">I", len(encoded)) + encoded
                offsets.append(seen[text])
            table = struct.pack(f">I{self.count}I", len(data), *offsets)
            out = head + self.names + b"".join(lang.encode("ascii") for lang in self.languages) + table * langs + data
        else:
            first = 4 * self.count
            offsets, data = [], bytearray()
            for text in texts:
                offsets.append(first + len(data))
                data += text.encode("utf-16-be") + b"\0\0"
            block = struct.pack(f">{self.count}I", *offsets) + data
            if self.version == 0:
                langs_table = b"".join(lang.encode("ascii") + bytes(4) for lang in self.languages)
                out = head + langs_table + struct.pack(">I", len(block)) + block
            else:
                langs_table = b"".join(lang.encode("ascii") + struct.pack(">II", 0, len(block)) for lang in self.languages)
                out = head + langs_table + self.names + block
        return bytes(out) + b"\xff" * (-len(out) % 32)


def _utf16(raw: bytes, at: int) -> str:
    end = at
    while raw[end:end + 2] != b"\0\0":
        end += 2
    return raw[at:end].decode("utf-16-be")
