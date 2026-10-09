"""PAPA record tables of the Marvelous 3DS farm games (Harvest Moon 3D: A New Beginning and its successors).

A table (a member of ``Msg.xbb`` or of a ``GameData/*.xbb`` archive) is ``PAPA``, u32 0, u32 section offset
(0x0C), then the section: u32 size (to the first entry), u32 entry count, u32 entry offsets. An entry is u32
size, u32 field count, u32 field offsets (from the entry start; 0 = an empty field), then the fields, each
padded to 4 bytes: field 0 names the record type (``Msg``, ``ItemData``), a UTF-16 field holds the text, an
ASCII field the label (``CookMsg000``, ``ITEM_SICKLE``). Which columns are text is read from the data: every
row decodes as a terminated UTF-16 string and most rows are words, not identifiers (``i_to_0000``). Control
characters in the text are shown as ``{XX}`` tags; ``<MYNAME>`` style markup is plain text.
"""
from __future__ import annotations

import re
import struct
from typing import Dict, List, Optional, Sequence

MAGIC = b"PAPA"
TAG_RE = re.compile(r"\{[0-9A-F]{2}\}|<[A-Za-z_/][^<>]*>")
_CONTROL = re.compile(r"[\x00-\x09\x0b-\x1f]")
_IDENT = re.compile(r"^[A-Za-z0-9_./-]*[_0-9][A-Za-z0-9_./-]*$")


class FormatError(ValueError):
    """Not a PAPA table."""


def decode(blob: bytes) -> Optional[str]:
    """The text of a UTF-16 field, or None when the field is not one."""
    end = -1
    for at in range(0, len(blob) - 1, 2):
        if blob[at] == 0 and blob[at + 1] == 0:
            end = at
            break
    if end < 0 or any(blob[end + 2:]):
        return None
    try:
        text = blob[:end].decode("utf-16-le")
    except UnicodeDecodeError:
        return None
    if any(0xD800 <= ord(ch) <= 0xDFFF or ord(ch) == 0xFFFE or ord(ch) == 0xFFFF for ch in text):
        return None
    return _CONTROL.sub(lambda m: "{%02X}" % ord(m.group()), text)


def encode(text: str) -> bytes:
    raw = re.sub(r"\{([0-9A-F]{2})\}", lambda m: chr(int(m.group(1), 16)), text).encode("utf-16-le") + b"\0\0"
    return raw + bytes(-len(raw) % 4)


def _wordy(text: str) -> bool:
    """Words a person wrote (``Copper Sickle``), not an identifier (``i_to_0000``, ``MAP_FARM``) and not a
    number that happens to decode (one character, or letters from outside the Latin range)."""
    if len(text) < 2 or _IDENT.match(text) or not re.search(r"[A-Za-z]", text):
        return False
    return sum(1 for ch in text if ord(ch) < 0x250 or ch.isspace()) >= len(text) * 0.8


class Entry:
    """One record: ``offsets`` per field (0 = empty) and the data blob at each used offset.

    A slot of a column that holds plain values (1, 2040...), not offsets, is left as it is: ``value_columns``
    (found by the table: a column is an offset column when every non-zero slot of every row is a 4-byte
    aligned position inside the data area of its entry)."""

    def __init__(self, raw: bytes, at: int):
        self.size, count = struct.unpack_from("<II", raw, at)
        self.offsets: List[int] = list(struct.unpack_from(f"<{count}I", raw, at + 8)) if self.size else []
        self.data_start = 8 + 4 * len(self.offsets)
        self.raw, self.at = raw, at
        self.value_columns: set = set()
        self.blobs: Dict[int, bytes] = {}

    def plausible(self, value: int) -> bool:
        return self.data_start <= value < self.size and value % 4 == 0

    def _is_offset(self, column: int) -> bool:
        return self.offsets[column] != 0 and column not in self.value_columns

    def cut(self, value_columns: set) -> None:
        self.value_columns = value_columns
        bounds = sorted(set(self.offsets[c] for c in range(len(self.offsets)) if self._is_offset(c))) + [self.size]
        self.blobs = {o: self.raw[self.at + o:self.at + bounds[i + 1]] for i, o in enumerate(bounds[:-1])}

    def field(self, column: int) -> Optional[bytes]:
        """The data of a field; None past the last field or for a slot that holds a value; b"" when empty."""
        if column >= len(self.offsets) or column in self.value_columns:
            return None
        return self.blobs.get(self.offsets[column], b"")

    def set_field(self, column: int, blob: bytes) -> None:
        old = self.offsets[column]
        if old:
            self.blobs[old] = blob
        else:   # an empty field gets data: a new offset past the others
            new = max(self.blobs, default=0) + 1
            self.offsets[column] = new
            self.blobs[new] = blob

    def pack(self) -> bytes:
        if not self.size:
            return bytes(8)
        where, pos = {}, self.data_start
        body = b""
        for old in sorted(self.blobs):
            where[old] = pos
            body += self.blobs[old]
            pos += len(self.blobs[old])
        slots = [where[o] if self._is_offset(c) else o for c, o in enumerate(self.offsets)]
        return struct.pack(f"<II{len(self.offsets)}I", pos, len(self.offsets), *slots) + body


class Table:
    """A PAPA table: ``texts()`` are the strings of its text columns, entry by entry; ``build`` writes them back."""

    def __init__(self, raw: bytes):
        if raw[:4] != MAGIC or len(raw) < 0x14:
            raise FormatError("not a PAPA table")
        section = struct.unpack_from("<I", raw, 8)[0]
        size, count = struct.unpack_from("<II", raw, section)
        offsets = struct.unpack_from(f"<{count}I", raw, section + 8)
        self.raw = raw
        self.section = section
        self.head = raw[:section + size]
        self.entries = [Entry(raw, off) for off in offsets]
        width = max((len(e.offsets) for e in self.entries), default=0)
        value_columns = {c for c in range(width)
                         if any(len(e.offsets) > c and e.offsets[c] and not e.plausible(e.offsets[c])
                                for e in self.entries)}
        for entry in self.entries:
            entry.cut(value_columns)
        end = max([section + size] + [off + max(e.size, 8) for off, e in zip(offsets, self.entries)])
        self.tail = raw[end:]
        self.columns = self._text_columns()

    def _text_columns(self) -> List[int]:
        width = max((len(e.offsets) for e in self.entries), default=0)
        columns = []
        for column in range(1, width):
            fields = [e.field(column) for e in self.entries if e.field(column) is not None]
            texts = [decode(f) if f else "" for f in fields]
            if texts and all(t is not None for t in texts):
                words = sum(1 for t in texts if _wordy(t))
                if words and words * 2 >= sum(1 for t in texts if t):
                    columns.append(column)
        return columns

    @property
    def tag(self) -> str:
        for entry in self.entries:
            if entry.offsets:
                return (entry.field(0) or b"").rstrip(b"\0").decode("ascii", "replace")
        return ""

    def label(self, index: int) -> str:
        """The ASCII label of an entry (``MES_BAD_SEASON``), else its number."""
        entry = self.entries[index]
        for column in range(1, len(entry.offsets)):
            blob = entry.field(column) or b""
            text = blob.rstrip(b"\0")
            if text and len(text) + 1 <= len(blob) <= len(text) + 4 and re.fullmatch(rb"[A-Za-z0-9_]+", text):
                return text.decode("ascii")
        return str(index)

    def _cells(self):
        for index, entry in enumerate(self.entries):
            for column in self.columns:
                if entry.field(column) is not None:
                    yield index, column

    def ids(self) -> List[str]:
        return [self.label(i) if len(self.columns) == 1 else f"{self.label(i)}#{c}" for i, c in self._cells()]

    def texts(self) -> List[str]:
        return [decode(self.entries[i].field(c)) or "" for i, c in self._cells()]

    def build(self, texts: Sequence[str]) -> bytes:
        if list(texts) == self.texts():
            return self.raw
        cells = list(self._cells())
        if len(texts) != len(cells):
            raise ValueError(f"the table holds {len(cells)} strings, {len(texts)} were given")
        for text, (index, column) in zip(texts, cells):
            entry = self.entries[index]
            if text != (decode(entry.field(column)) or ""):   # an unchanged field keeps its bytes
                entry.set_field(column, encode(text) if text else b"")
        head = bytearray(self.head)
        body = bytearray()
        offsets = []
        for entry in self.entries:
            offsets.append(len(head) + len(body))
            body += entry.pack()
        struct.pack_into(f"<{len(offsets)}I", head, self.section + 8, *offsets)
        return bytes(head) + bytes(body) + self.tail
