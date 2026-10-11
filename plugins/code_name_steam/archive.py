"""Code Name: S.T.E.A.M. message archives (``mess/EU_English/*.bin``, LZ13 in the game): labelled UTF-16 strings.

The same container as Fire Emblem Awakening's message archives, without the archive name in front of the text.
Header (little endian): u32 file size, u32 text region size, u32 pointer count (0), u32 message count, 16 zero
bytes. The text region starts at 0x20: UTF-16LE strings, each NUL-terminated and padded to 4 bytes. After it:
``message count`` pairs (u32 text offset from 0x20, u32 label offset) and the labels (ASCII / Shift-JIS,
NUL-terminated). Messages may share one copy of a string (the file decides which). The ``CommonParams`` folder
has the same layout with empty texts (the labels are what the game looks up); only ``EU_English`` is edited.
"""
from __future__ import annotations

import struct
from typing import Dict, List, Sequence, Tuple


class FormatError(ValueError):
    pass


def _label(raw: bytes) -> str:
    """A label is ASCII, or UTF-8 Japanese in the speaker tables."""
    try:
        return raw.decode("utf-8")
    except UnicodeDecodeError:
        return raw.decode("cp932", "replace")


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
        if self.labels_at > len(raw):
            raise FormatError("not a message archive (table)")
        self.labels: List[str] = []
        self.texts: List[str] = []
        self.offsets: List[int] = []
        for i in range(count):
            text_off, label_off = struct.unpack_from("<II", raw, table + i * 8)
            at = self.labels_at + label_off
            if text_off >= self.text_size or at >= len(raw):
                raise FormatError("not a message archive (offsets)")
            self.labels.append(_label(raw[at:raw.index(b"\0", at)]))
            self.offsets.append(text_off)
            self.texts.append(self._string(0x20 + text_off))

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
        region = bytearray()
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
    except (FormatError, UnicodeDecodeError, ValueError, struct.error, IndexError):
        return None


def labelled(raw: bytes) -> List[Tuple[str, str]]:
    archive = Archive(raw)
    return list(zip(archive.labels, archive.texts))
