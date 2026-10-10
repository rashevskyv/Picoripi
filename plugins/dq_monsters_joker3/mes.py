"""Dragon Quest Monsters: Joker 3 (3DS) ``.mes`` message tables (``data/Message``, ``data/Script/Field``).

Layout: u32 bucket count; ``buckets`` x (u32 entries in the bucket, u32 offset of its first entry); the entries
(u32 text offset, ASCII label NUL-terminated and padded to 4 bytes) in bucket order; the UTF-16LE texts,
NUL-terminated and padded to 4 bytes. The hash table and labels are kept as they are; only the text block is
rebuilt, so a text may grow.
"""
from __future__ import annotations

import struct
from typing import List, Sequence, Tuple


class FormatError(ValueError):
    pass


class Table:
    def __init__(self, raw: bytes) -> None:
        self.raw = raw
        self.labels: List[str] = []
        self.entry_at: List[int] = []
        self.entries: List[bytes] = []
        self.text_start = len(raw)
        if not raw:
            return                                   # some event tables are empty
        if len(raw) < 4:
            raise FormatError("too short for a .mes table")
        buckets = struct.unpack_from("<I", raw, 0)[0]
        if 4 + buckets * 8 > len(raw):
            raise FormatError("not a .mes table")
        count = sum(struct.unpack_from("<II", raw, 4 + i * 8)[0] for i in range(buckets))
        self.raw = raw
        self.labels: List[str] = []
        self.entry_at: List[int] = []     # offset of each entry's text-offset field
        pos = 4 + buckets * 8
        for _ in range(count):
            if pos + 4 > len(raw):
                raise FormatError("entries run past the file")
            self.entry_at.append(pos)
            end = raw.index(b"\0", pos + 4)
            label = raw[pos + 4:end]
            if not label or any(c < 0x20 or c > 0x7E for c in label):
                raise FormatError("entry label is not ASCII")
            self.labels.append(label.decode("ascii"))
            pos = (end + 1 + 3) & ~3
        self.text_start = pos
        self.entries: List[bytes] = []
        for at in self.entry_at:
            text_off = struct.unpack_from("<I", raw, at)[0]
            end = text_off
            while raw[end:end + 2] != b"\0\0":
                end += 2
                if end >= len(raw):
                    raise FormatError("unterminated text")
            self.entries.append(raw[text_off:end])

    def texts(self) -> List[str]:
        return [e.decode("utf-16-le") for e in self.entries]

    def build(self, texts: Sequence[str]) -> bytes:
        if len(texts) != len(self.entries):
            raise FormatError(f"{len(texts)} strings for {len(self.entries)} entries")
        out = bytearray(self.raw[:self.text_start])
        placed = {}      # original text offset -> new offset (entries that shared a text keep sharing it)
        order = sorted(range(len(texts)), key=lambda i: struct.unpack_from("<I", self.raw, self.entry_at[i])[0])
        for i in order:
            original = struct.unpack_from("<I", self.raw, self.entry_at[i])[0]
            if original not in placed:
                blob = str(texts[i]).encode("utf-16-le") + b"\0\0"
                placed[original] = len(out)
                out += blob + bytes(-len(blob) % 4)
            struct.pack_into("<I", out, self.entry_at[i], placed[original])
        return bytes(out)


def pairs(raw: bytes) -> List[Tuple[str, str]]:
    table = Table(raw)
    return list(zip(table.labels, table.texts()))
