"""Fire Emblem Awakening message archives (``m/U/*.bin``, LZ11 in the game): labelled UTF-16 strings.

Header (little endian): u32 file size, u32 text region size, u32 pointer count (0 in a message archive), u32
message count, 16 zero bytes. The text region at 0x20 starts with the archive name (``MESS_ARCHIVE_xxx``, ASCII,
padded to 4), then the UTF-16LE strings, each NUL-terminated and padded to 4 bytes. After it: the pointer table
(``pointer count`` u32), then ``message count`` pairs (u32 text offset from 0x20, u32 label offset) and the labels
(Shift-JIS, NUL-terminated). Messages may share one copy of a string (the file decides which).
"""
from __future__ import annotations

import struct
from typing import Dict, List, Sequence, Tuple


class FormatError(ValueError):
    pass


class Archive:
    """A parsed message archive: ``labels`` and ``texts`` in message order."""

    def __init__(self, raw: bytes):
        if len(raw) < 0x20:
            raise FormatError("too short for a message archive")
        self.raw = bytes(raw)
        size, self.text_size, pointers, count = struct.unpack_from("<4I", raw, 0)
        if size != len(raw) or pointers or 0x20 + self.text_size > len(raw):
            raise FormatError("not a message archive (size, pointers)")
        table = 0x20 + self.text_size
        self.labels_at = table + count * 8
        name_end = raw.index(b"\0", 0x20)
        self.name = raw[0x20:name_end].decode("ascii", "replace")
        self.first_text = (name_end + 1 + 3) & ~3
        self.labels: List[str] = []
        self.texts: List[str] = []
        self.offsets: List[int] = []
        for i in range(count):
            text_off, label_off = struct.unpack_from("<II", raw, table + i * 8)
            at = self.labels_at + label_off
            self.labels.append(raw[at:raw.index(b"\0", at)].decode("cp932", "replace"))
            self.offsets.append(text_off)
            self.texts.append(self._string(0x20 + text_off))
        if self.labels_at > len(raw) or (count and max(self.offsets) + 0x20 >= table):
            raise FormatError("not a message archive (table)")

    def _string(self, at: int) -> str:
        end = at
        while self.raw[end:end + 2] not in (b"\0\0", b""):
            end += 2
        return self.raw[at:end].decode("utf-16-le", "replace")

    def build(self, texts: Sequence[str]) -> bytes:
        """The archive with ``texts`` (one per message). Messages that shared one copy in the file still do:
        the copy gets the edited text of the group (the first member's when none was edited)."""
        if len(texts) != len(self.texts):
            raise FormatError(f"{len(texts)} strings for {len(self.texts)} messages")
        chosen: Dict[int, str] = {}
        for text, old, original in zip(texts, self.offsets, self.texts):
            if old not in chosen or str(text) != original:
                chosen[old] = str(text)
        region = bytearray(self.raw[0x20:self.first_text])
        shared: Dict[int, int] = {}
        offsets = []
        for old in self.offsets:
            if old not in shared:
                shared[old] = len(region)
                region += chosen[old].encode("utf-16-le") + b"\0\0"
                region += bytes(-len(region) % 4)
            offsets.append(shared[old])
        table = b"".join(struct.pack("<II", off, struct.unpack_from("<I", self.raw, 0x20 + self.text_size + i * 8 + 4)[0])
                         for i, off in enumerate(offsets))
        labels = self.raw[self.labels_at:]
        out = bytearray(self.raw[:0x20]) + region + table + labels
        struct.pack_into("<II", out, 0, len(out), len(region))
        return bytes(out)


def archive_or_none(raw: bytes):
    try:
        return Archive(raw)
    except (FormatError, UnicodeDecodeError, ValueError, struct.error):
        return None


def labelled(raw: bytes) -> List[Tuple[str, str]]:
    archive = Archive(raw)
    return list(zip(archive.labels, archive.texts))
