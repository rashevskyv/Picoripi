"""Text files of Capcom's MT Framework Mobile games on 3DS (Monster Hunter 3 Ultimate, 4 Ultimate, Stories).

Four formats, all little endian; ``parse(data)`` picks one by its magic and gives a ``TextFile``: the editable
strings (English only), a label per string and ``build(strings)`` -> the file again. Unchanged strings keep
their bytes, so an unedited file builds back byte for byte; a string may grow or shrink.

``GMD`` (MH3U, UTF-8): a 0x20-byte header (magic, version, language, label count, string count, label block
size, string block size, name size), the name + NUL, label entries (u32 string index, u32 pointer), the label
block, then the strings, each NUL-terminated, to the end of the file. Line breaks are ``\\r\\n``.

``lmd`` (MH4U v0x0001010B, Stories v0x0000010F, UTF-16): header u32 count, u32 count 2, u32 string count, then
the offsets of three tables and of the file name. Table C holds (offset, length, length) per string (length in
UTF-16 units, without the NUL); each string ends with a NUL and is padded to 4 bytes; the name follows. Only
table C, the strings and the name offset change.

``QTDS`` (MH3U quests): header ``QTDS`` + u32 5, then five fields (title, goal, failure condition, client,
description), each in five languages (English, French, German, Italian, Spanish) as u32 byte length + UTF-8. The
fields are separated by 2, 24 and 6 bytes of quest data; the rest of the quest follows the last field.

MH4U quest (``v005``): the u32 at 0xBC points to five language tables (English, French, Spanish, German,
Italian), each seven pointers to NUL-terminated UTF-16 strings (title, goal, failure condition, description,
monsters, client, subquest). All strings and tables lie in one region that ends at the language tables. An
edited English text is laid out again at the start of that region; the other languages follow while they fit,
and a language that no longer fits shows the English (translated) text.
"""
from __future__ import annotations

import re
import struct
from dataclasses import dataclass, field
from typing import Callable, List, Optional

TAG_RE = re.compile(r"<[A-Z/][^<>\n]{0,30}>|%[0-9]*[sdcxXf]")
QUEST_FIELDS = ("Title", "Goal", "Failure condition", "Client", "Description")
MIB_FIELDS = ("Title", "Goal", "Failure condition", "Description", "Monsters", "Client", "Subquest")


class FormatError(ValueError):
    """Not a text file of these games."""


@dataclass
class TextFile:
    kind: str
    strings: List[str]
    labels: List[str]
    _build: Callable[[List[str]], bytes] = field(repr=False, default=None)

    def build(self, strings: List[str]) -> bytes:
        return self._build(list(strings))


def to_editor(text: str) -> str:
    return text.replace("\r\n", "\n")


def from_editor(text: str, crlf: bool) -> str:
    text = text.replace("\r\n", "\n")
    return text.replace("\n", "\r\n") if crlf else text


def _align(value: int, to: int) -> int:
    return (value + to - 1) // to * to


# ---------------------------------------------------------------- GMD

def parse_gmd(data: bytes) -> TextFile:
    if data[:4] != b"GMD\0" or len(data) < 0x20:
        raise FormatError("not a GMD file")
    _ver, _lang, nlab, nstr, labsz, strsz, namesz = struct.unpack_from("<7I", data, 4)
    entries = 0x20 + namesz + 1
    labels_at = entries + nlab * 8
    strings_at = labels_at + labsz
    if strings_at + strsz != len(data):
        raise FormatError("GMD sizes do not match the file")
    raw = data[strings_at:].split(b"\0")
    if len(raw) != nstr + 1 or raw[-1]:
        raise FormatError("GMD string count does not match")
    names = data[labels_at:strings_at].split(b"\0")
    labels = [""] * nstr
    for i in range(nlab):
        index = struct.unpack_from("<I", data, entries + i * 8)[0]
        if index < nstr and i < len(names):
            labels[index] = names[i].decode("utf-8", "replace")
    strings = [item.decode("utf-8") for item in raw[:-1]]
    head = bytearray(data[:strings_at])

    def build(new: List[str]) -> bytes:
        body = b"".join(text.encode("utf-8") + b"\0" for text in new)
        struct.pack_into("<I", head, 0x18, len(body))
        return bytes(head) + body
    return TextFile("gmd", strings, labels, build)


# ---------------------------------------------------------------- lmd

def parse_lmd(data: bytes) -> TextFile:
    if data[:4] != b"lmd\0" or len(data) < 0x24:
        raise FormatError("not an lmd file")
    _count, _count2, nstr, _a, _b, table, name_at = struct.unpack_from("<7I", data, 8)
    pos = table + nstr * 12
    if pos > len(data):
        raise FormatError("lmd table out of range")
    strings = []
    for i in range(nstr):
        offset, length, length2 = struct.unpack_from("<III", data, table + i * 12)
        if offset != pos or length != length2:
            raise FormatError("lmd strings are not in the expected order")
        strings.append(data[offset:offset + length * 2].decode("utf-16-le"))
        pos = _align(offset + length * 2 + 2, 4)
    if pos != name_at:
        raise FormatError("lmd name is not after the strings")
    head, tail = bytearray(data[:table + nstr * 12]), data[name_at:]

    def build(new: List[str]) -> bytes:
        out = bytearray(head)
        for i, text in enumerate(new):
            raw = text.encode("utf-16-le")
            struct.pack_into("<III", out, table + i * 12, len(out), len(raw) // 2, len(raw) // 2)
            out += raw + b"\0\0"
            out += bytes(_align(len(out), 4) - len(out))
        struct.pack_into("<I", out, 0x20, len(out))
        return bytes(out) + tail
    return TextFile("lmd", strings, [""] * nstr, build)


# ---------------------------------------------------------------- MH3U quests

QTDS_GAPS = (2, 24, 6, 0, None)


def parse_qtds(data: bytes) -> TextFile:
    if data[:4] != b"QTDS" or struct.unpack_from("<I", data, 4)[0] != 5:
        raise FormatError("not an MH3U quest")
    pos, fields, gaps = 8, [], []
    for gap in QTDS_GAPS:
        values = []
        for _lang in range(5):
            size = struct.unpack_from("<I", data, pos)[0]
            if pos + 4 + size > len(data):
                raise FormatError("quest string out of range")
            values.append(data[pos + 4:pos + 4 + size])
            pos += 4 + size
        fields.append(values)
        if gap is not None:
            gaps.append(data[pos:pos + gap])
            pos += gap
    tail = data[pos:]
    strings = [values[0].decode("utf-8") for values in fields]

    def build(new: List[str]) -> bytes:
        out = bytearray(data[:8])
        for n, values in enumerate(fields):
            for lang, raw in enumerate(values):
                raw = new[n].encode("utf-8") if lang == 0 else raw
                out += struct.pack("<I", len(raw)) + raw
            if n < len(gaps):
                out += gaps[n]
        return bytes(out) + tail
    return TextFile("quest", strings, list(QUEST_FIELDS), build)


# ---------------------------------------------------------------- MH4U quests

def _utf16z(data: bytes, at: int) -> bytes:
    end = at
    while data[end:end + 2] != b"\0\0":
        end += 2
        if end >= len(data):
            raise FormatError("quest string has no end")
    return data[at:end]


def parse_mib(data: bytes) -> TextFile:
    if len(data) < 0xC0 or data[4:8] != b"v005":
        raise FormatError("not an MH4U quest")
    lang_at = struct.unpack_from("<I", data, 0xBC)[0]
    if lang_at + 20 > len(data):
        raise FormatError("quest language table out of range")
    tables = list(struct.unpack_from("<5I", data, lang_at))
    pointers = [list(struct.unpack_from("<7I", data, t)) for t in tables]
    start = min(p for row in pointers for p in row)
    if not all(start <= p < lang_at for p in tables + [p for row in pointers for p in row]):
        raise FormatError("quest text is not in one region")
    texts = [[_utf16z(data, p) for p in row] for row in pointers]
    strings = [raw.decode("utf-16-le") for raw in texts[0]]

    def build(new: List[str]) -> bytes:
        if new == strings:
            return data
        region = bytearray()

        def put(row: List[bytes]) -> int:
            at = []
            for raw in row:
                at.append(start + len(region))
                region.extend(raw + b"\0\0")
            region.extend(bytes(_align(len(region), 4) - len(region)))
            table = start + len(region)
            region.extend(struct.pack("<7I", *at))
            return table
        english = put([text.encode("utf-16-le") for text in new])
        if start + len(region) > lang_at:
            raise FormatError(f"quest text is {start + len(region) - lang_at} bytes too long for this quest")
        new_tables = [english]
        for row in texts[1:]:
            size = sum(len(raw) + 2 for raw in row) + 3 + 28
            new_tables.append(put(row) if start + len(region) + size <= lang_at else english)
        out = bytearray(data)
        out[start:lang_at] = bytes(region) + bytes(lang_at - start - len(region))
        struct.pack_into("<5I", out, lang_at, *new_tables)
        return bytes(out)
    return TextFile("mib", strings, list(MIB_FIELDS), build)


PARSERS = {b"GMD\0": parse_gmd, b"lmd\0": parse_lmd, b"QTDS": parse_qtds}


def parse(data: bytes) -> Optional[TextFile]:
    """The text of a file of these games, or None when it is none of the four formats."""
    data = bytes(data)
    parser = PARSERS.get(data[:4]) or (parse_mib if data[4:8] == b"v005" else None)
    if parser is None:
        return None
    return parser(data)


def describe(tag: str) -> str:
    """A tooltip for a tag."""
    if tag.startswith("%"):
        return "A value the game fills in (number or name)"
    if tag.startswith(("<COL", "</COL")):
        return "Text colour on / off"
    if tag.startswith("<SUBS"):
        return "A word the game fills in"
    if tag.startswith("<ICON"):
        return "An icon"
    return "Game control code"
