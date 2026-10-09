"""Final Fantasy Tactics A2 (DS) text: the message packs of ``master/pc.bin`` and the game's character codes.

The game keeps its text in five packs, each an index (``*_rom*.idx``) and a data file (``*.pak``) inside the
``pc.bin`` archive; ``_0`` / ``0`` is the English set of the European version (1 German, 2 Spanish, 3 French):
``system/rom/JD_message`` (menus, names and descriptions: 55 string tables), ``JH_questtext`` (quest texts),
``JH_uwasatext`` (rumours), ``JH_freepapermes`` (notices) and ``event/rom/ev_msg`` (event dialogue).
The workspace scripts keep each pack as one ``.a2msg`` file: ``MAGIC``, the kind (``T`` string tables /
``S`` one string per member), u32 index size, the index, the data.

Index: u32 0, then 6 bytes per member (see ``members``); the last record is the end of the data.
A string table: u16 count, then (u32 byte length, u32 offset, u16 line count) per string, then the strings.
A single string: u16, u16, u32 byte length, u32, u16 line count, the string; zero filler to 4 bytes.
A record of the index also holds the member's exact size (see ``members``); members of the menu packs start
32-byte aligned, those of ev_msg 4-byte aligned, and the menu tables are padded to 32 bytes, the event ones to 4.
(Layouts after Rurusachi's FFTA2 Editor, MIT.)

Text codes: one byte below ``0xC0`` is a glyph (``core.font_formats.ffta2.CHARACTERS``; the glyph number is the code minus 1);
``0xC0``-``0xCF`` take one parameter byte: ``C0 00`` breaks the line, ``C1 00`` ends the text, ``C3 00`` ends
a page, the others insert values, icons and choices. A string ends with ``00`` or with ``C1 00``; the editor
hides that ending and writes it back.
"""
from __future__ import annotations

import re
import struct
from typing import Dict, List, Optional, Tuple

from core.font_formats.ffta2 import CHARACTERS

MAGIC = b"A2MS"
LINE, END, PAGE, OPTION_END = 0xC0, 0xC1, 0xC3, 0xC8

CHAR_CODES = {char: code for code, char in CHARACTERS.items()}
CHAR_CODES.update({"[": 0x88, "]": 0x89})
TAG_RE = re.compile(r"\[(?:end|page|C[0-9A-F]:[0-9A-F]{2}|x[0-9A-F]{2})\]")
TAG_TIPS = {
    "C2": "Wait / pause in the text", "C3": "New page", "C4": "Value (C4)", "C5": "Value (C5)", "C6": "Value (C6)",
    "C7": "Choice: the default option", "C8": "Choice: end of an option", "C9": "Value (C9)",
    "CA": "A value the game fills in (a name, a number)", "CB": "A button or icon picture",
    "CC": "Value (CC)", "CD": "Value (CD)", "CE": "Value (CE)", "CF": "Value (CF)",
}


class FormatError(ValueError):
    """The bytes are not an FFTA2 message pack, or a text cannot be encoded."""


# -- codes <-> editor text ---------------------------------------------------------------------------------

def _codes(raw: bytes) -> List[bytes]:
    """The string as a list of codes (one byte, or two for 0xC0-0xCF)."""
    out, at = [], 0
    while at < len(raw):
        size = 2 if raw[at] >= 0xC0 and at + 1 < len(raw) else 1
        out.append(raw[at:at + size])
        at += size
    return out


def split_tail(raw: bytes) -> Tuple[bytes, bytes]:
    """``(body, ending)``: the ending is the final ``00`` or ``C1 00`` the editor does not show."""
    codes = _codes(raw)
    if codes and codes[-1] == b"\x00":
        codes.pop()
        tail = b"\x00"
        if codes and codes[-1] == b"\xc1\x00":
            codes.pop()
            tail = b"\xc1\x00\x00"
        return b"".join(codes), tail
    if codes and codes[-1] == b"\xc1\x00":
        return b"".join(codes[:-1]), b"\xc1\x00"
    return raw, b""


def to_editor(raw: bytes) -> str:
    body, _tail = split_tail(raw)
    parts = []
    for code in _codes(body):
        first = code[0]
        if len(code) == 2:
            if code == b"\xc0\x00":
                parts.append("\n")
            elif code == b"\xc1\x00":
                parts.append("[end]")
            elif code == b"\xc3\x00":
                parts.append("[page]")
            else:
                parts.append(f"[{first:02X}:{code[1]:02X}]")
        else:
            parts.append(CHARACTERS.get(first) or f"[x{first:02X}]")
    return "".join(parts)


def from_editor(text: str, tail: bytes = b"\x00") -> bytes:
    out = bytearray()
    text = str(text).replace("\r\n", "\n")
    at = 0
    for match in list(TAG_RE.finditer(text)) + [None]:
        for char in text[at:match.start() if match else len(text)]:
            if char == "\n":
                out += b"\xc0\x00"
            elif char in CHAR_CODES:
                out.append(CHAR_CODES[char])
            else:
                raise FormatError(f"The game's font has no character {char!r} (U+{ord(char):04X})")
        if match is None:
            break
        tag = match.group()[1:-1]
        if tag == "end":
            out += b"\xc1\x00"
        elif tag == "page":
            out += b"\xc3\x00"
        elif tag[0] == "x":
            out.append(int(tag[1:], 16))
        else:
            out += bytes((int(tag[:2], 16), int(tag[3:], 16)))
        at = match.end()
    return bytes(out) + tail


def describe(tag: str) -> str:
    if not TAG_RE.fullmatch(tag):
        return ""
    if tag == "[end]":
        return "End of the text"
    if tag == "[page]":
        return "New page"
    if tag.startswith("[x"):
        return f"Glyph or code {tag[2:4]} with no character here"
    return f"{TAG_TIPS.get(tag[1:3], 'Control code')} (parameter {tag[4:6]})"


def line_count(raw: bytes) -> int:
    """The line count the game keeps next to a string: the most lines on one page (FFTA2 Editor's rule)."""
    best, lines, options = 0, 0, 0
    for code in _codes(raw):
        if code[0] in (LINE, END):
            lines += 1
        elif code[0] == OPTION_END:
            options += 1
        if code[0] == END:
            best = max(best, lines + max(0, options - 1))
            lines = options = 0
    return max(1, best)


# -- the pack file ------------------------------------------------------------------------------------------

def _align(value: int, unit: int = 32) -> int:
    return (value + unit - 1) // unit * unit


def split_file(data: bytes) -> Tuple[str, bytes, bytes]:
    """``(kind, index, data)`` of an ``.a2msg`` file."""
    if data[:4] != MAGIC or len(data) < 9:
        raise FormatError("not an FFTA2 message pack (.a2msg)")
    kind = chr(data[4])
    size = struct.unpack_from("<I", data, 5)[0]
    return kind, bytes(data[9:9 + size]), bytes(data[9 + size:])


def join_file(kind: str, index: bytes, pak: bytes) -> bytes:
    return MAGIC + kind.encode("ascii") + struct.pack("<I", len(index)) + index + pak


def _records(index: bytes) -> List[Tuple[int, int]]:
    count = (len(index) - 4) // 6
    return [struct.unpack_from("<IH", index, 4 + 6 * i) for i in range(count)]


def members(index: bytes, pak: bytes) -> List[Optional[bytes]]:
    """The pack's members (None = no member).

    A record is u32 ``offset words << 3 | size words << 27 | flags`` and u16 ``size words >> 5`` (low 3 bits 7 =
    no member); the last record is the end of the data.
    """
    records = _records(index)
    out: List[Optional[bytes]] = []
    for i, (word, high) in enumerate(records[:-1]):
        if word & 7:
            out.append(None)
            continue
        start = (word >> 3) & 0xFFFFFF
        size = (word >> 27) | high << 5
        out.append(pak[start * 4:(start + size) * 4])
    return out


def pack_members(items: List[Optional[bytes]], index: bytes = b"", unit: int = 32) -> Tuple[bytes, bytes]:
    """``(index, data)`` for ``items`` (each member padded to ``unit`` bytes). The u16 of an empty record and of the
    end record are taken from ``index`` (the original), as they are no member's size."""
    old = _records(index) if index else []
    out = bytearray(4)
    pak = bytearray()
    for i, item in enumerate(items + [None]):
        high = old[i][1] if i < len(old) and (item is None) else 0
        if i == len(items) and old:
            high = old[-1][1]
        if item is None:
            out += struct.pack("<IH", (len(pak) // 4 << 3 | 7) & 0xFFFFFFFF, high)
            continue
        if len(item) % 4:
            raise FormatError("a member must be a whole number of 4-byte words")
        words = len(item) // 4
        out += struct.pack("<IH", (len(pak) // 4 << 3 | (words & 31) << 27) & 0xFFFFFFFF, words >> 5)
        pak += item + bytes(_align(len(item), unit) - len(item))
    if len(items) % 2 == 0:
        out += bytes(2)
    return bytes(out), bytes(pak)


# -- string tables and single strings ----------------------------------------------------------------------

def read_table(member: bytes) -> List[Tuple[bytes, int]]:
    """``[(string bytes, line count)]`` of a string table."""
    if not member:
        return []
    count = struct.unpack_from("<H", member, 0)[0]
    out = []
    for i in range(count):
        length, offset, lines = struct.unpack_from("<IIH", member, 2 + 10 * i)
        out.append((bytes(member[offset:offset + length]), lines))
    return out


def write_table(strings: List[Tuple[bytes, int]], unit: int = 32) -> bytes:
    if not strings:
        return b""
    head = bytearray(struct.pack("<H", len(strings)))
    body = bytearray()
    start = 2 + 10 * len(strings)
    for raw, lines in strings:
        head += struct.pack("<IIH", len(raw), start + len(body), lines)
        body += raw
    out = head + body
    return bytes(out + bytes(_align(len(out), unit) - len(out)))


def read_single(member: bytes) -> Tuple[bytes, bytes, int]:
    """``(header fields, string bytes, line count)`` of a single-string member."""
    length = struct.unpack_from("<I", member, 4)[0]
    lines = struct.unpack_from("<H", member, 12)[0]
    return bytes(member[:4]) + bytes(member[8:12]), bytes(member[14:14 + length]), lines


def write_single(fields: bytes, raw: bytes, lines: int) -> bytes:
    out = fields[:4] + struct.pack("<I", len(raw)) + fields[4:8] + struct.pack("<H", lines) + raw
    return bytes(out + bytes(_align(len(out), 4) - len(out)))


class Pack:
    """An ``.a2msg`` file: its strings per member (``groups``) and the way back to bytes."""

    def __init__(self, data: bytes):
        self.original = bytes(data)
        self.kind, self.index, pak = split_file(data)
        if self.kind not in "TS":
            raise FormatError(f"unknown message pack kind {self.kind!r}")
        self.members = members(self.index, pak)
        # Menu tables are padded to 32 bytes, event tables (ev_msg) only to 4.
        self.unit = 32 if all(len(m) % 32 == 0 for m in self.members if m) else 4
        # Members start 32-byte aligned in the menu packs, 4-byte aligned in ev_msg.
        starts = [(word >> 3) & 0xFFFFFF for word, _high in _records(self.index) if not word & 7]
        self.pak_unit = 32 if all(start % 8 == 0 for start in starts) else 4
        self.groups: List[List[bytes]] = []
        self.lines: List[List[int]] = []
        self.fields: List[bytes] = []
        for member in self.members:
            if not member:
                self.groups.append([])
                self.lines.append([])
                self.fields.append(b"")
            elif self.kind == "T":
                table = read_table(member)
                self.groups.append([raw for raw, _n in table])
                self.lines.append([n for _raw, n in table])
                self.fields.append(b"")
            else:
                fields, raw, lines = read_single(member)
                self.groups.append([raw])
                self.lines.append([lines])
                self.fields.append(fields)

    def build(self, edited: Dict[Tuple[int, int], bytes]) -> bytes:
        """The file with ``edited`` ({(member, string): new bytes}) put in; nothing edited = the same bytes."""
        if not edited:
            return self.original
        items = list(self.members)
        for number in sorted({m for m, _s in edited}):
            strings = list(self.groups[number])
            lines = list(self.lines[number])
            for (m, s), raw in edited.items():
                if m == number:
                    strings[s] = raw
                    lines[s] = line_count(raw) if lines[s] else 0
            if self.kind == "T":
                items[number] = write_table(list(zip(strings, lines)), self.unit)
            else:
                items[number] = write_single(self.fields[number], strings[0], lines[0])
        index, pak = pack_members(items, self.index, self.pak_unit)
        return join_file(self.kind, index, pak)
