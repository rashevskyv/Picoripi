"""Pokémon generation V message files (Black, White, Black 2, White 2): one codec for ``pokemon_gen5``.

A file is a table of lines in the same frame as the Switch ``gfmsg`` files: u16 sections (1), u16 line count,
u32 section size, u32 key (0), u32 section offset (0x10); the section: u32 size, then per line {u32 offset,
u16 length in UTF-16 units with the terminator, u16 flags}, then the lines. A line is XOR-encrypted with the
key ``0x7C89 + 0x2983 * index`` (16 bits), rotated left by 3 after every unit; it ends with ``0xFFFF``.

A line that begins with ``0xF100`` is packed: the units after it are a bit stream of 9-bit characters (low
bits first); ``0x1FF`` ends the text and the stream may end earlier, in the middle of it, when the words run
out (the game's own packer fills the spare bits of the last word with the ones of the end mark).

Editor text: ``\\n`` is the line feed (``0xFFFE``); a variable (``0xF000``, code, argument count, arguments) is
a tag: ``{PAGE}`` (BE01), ``{SCROLL}`` (BE00), ``{WAIT 0001}`` (BE02), ``{NULL}`` (BDFF), ``{COLOR 0001}``
(FF00) and ``{VAR 0101 0000}`` for the rest (hex). A character that is not plain text (a button icon of the
font's private-use area, a control code) reads ``{CHAR E447}``.

Writing a line again gives the same bytes when its units did not change; a line that was packed is packed
again.
"""
from __future__ import annotations

import re
import struct
from dataclasses import dataclass
from typing import List, Optional, Sequence

from plugins.common.gfmsg import _crypt  # the same line cipher as the Switch files

NAMES = {0xBE00: "SCROLL", 0xBE01: "PAGE", 0xBE02: "WAIT", 0xBDFF: "NULL", 0xFF00: "COLOR"}
CODES = {name: code for code, name in NAMES.items()}
TAG_RE = re.compile(r"\{(?:(?:[A-Z]+|VAR [0-9A-F]{4}|CHAR [0-9A-F]{4})(?: [0-9A-F]{4})*)\}")
FEED, VARIABLE, PACKED, END = 0xFFFE, 0xF000, 0xF100, 0xFFFF


@dataclass
class Line:
    """One line of a file: its decoded units (no ``0xFFFF``), the header flags and whether it was packed."""

    units: List[int]
    flags: int = 0
    packed: bool = False


def is_gen5msg(data: bytes) -> bool:
    """A message file (a file with no lines passes too: ``a/0/0/2`` holds a few empty ones)."""
    if len(data) < 0x14:
        return False
    sections, count, size, key, offset = struct.unpack_from("<HHIII", data)
    return sections == 1 and key == 0 and offset == 0x10 and size + 0x10 == len(data) and \
        struct.unpack_from("<I", data, 0x10)[0] == size and 4 + 8 * count <= size


def unpack9(words: Sequence[int]) -> List[int]:
    """The 9-bit characters of a packed stream, up to the end mark ``0x1FF``."""
    out, bits, held = [], 0, 0
    for word in words:
        held |= word << bits
        bits += 16
        while bits >= 9:
            char = held & 0x1FF
            held >>= 9
            bits -= 9
            if char == 0x1FF:
                return out
            out.append(char)
    return out


def pack9(chars: Sequence[int]) -> List[int]:
    """The packed stream of characters (each below ``0x1FF``): the spare bits of the last word hold the end
    mark (ones, at most nine), then zeros."""
    value, bits = 0, 0
    for char in chars:
        value |= char << bits
        bits += 9
    words = -(-bits // 16)
    spare = words * 16 - bits
    value |= ((1 << min(spare, 9)) - 1) << bits
    return [(value >> (16 * i)) & 0xFFFF for i in range(words)]


def read(data: bytes) -> List[Line]:
    """Every line of a message file."""
    if not is_gen5msg(data):
        raise ValueError("not a generation V message file")
    count = struct.unpack_from("<H", data, 2)[0]
    lines = []
    for i in range(count):
        offset, length, flags = struct.unpack_from("<IHH", data, 0x14 + 8 * i)
        if length < 1 or 0x10 + offset + 2 * length > len(data):
            raise ValueError(f"line {i} is outside the file")
        units = _crypt(struct.unpack_from(f"<{length}H", data, 0x10 + offset), i)
        if units[-1] != END:
            raise ValueError(f"line {i} has no terminator")
        units = units[:-1]
        packed = bool(units) and units[0] == PACKED
        if packed:
            units = unpack9(units[1:])
        lines.append(Line(units, flags, packed))
    return lines


def encode(line: Line) -> List[int]:
    """The units of a line as stored (packed again when it was; a character above ``0x1FE`` stays plain)."""
    if line.packed and all(unit < 0x1FF for unit in line.units):
        return [PACKED, *pack9(line.units), END]
    return [*line.units, END]


def write(lines: Sequence[Line]) -> bytes:
    """The file of ``lines`` (the inverse of ``read``)."""
    table, body = bytearray(), bytearray()
    start = 4 + 8 * len(lines)
    for i, line in enumerate(lines):
        coded = _crypt(encode(line), i)
        table += struct.pack("<IHH", start + len(body), len(coded), line.flags)
        body += struct.pack(f"<{len(coded)}H", *coded)
    body += b"\0" * (-(len(table) + len(body)) % 4)      # lines follow each other; the file ends on a word
    size = 4 + len(table) + len(body)
    return struct.pack("<HHIIII", 1, len(lines), size, 0, 0x10, size) + bytes(table) + bytes(body)


def _plain(unit: int) -> bool:
    return unit >= 0x20 and not 0xE000 <= unit <= 0xFFFF


def to_editor(units: Sequence[int]) -> str:
    out, k = [], 0
    while k < len(units):
        unit = units[k]
        if unit == FEED:
            out.append("\n")
        elif unit == VARIABLE and k + 2 < len(units):
            code, count = units[k + 1], units[k + 2]
            args = units[k + 3:k + 3 + count]
            k += 2 + count
            name = NAMES.get(code)
            out.append("{" + " ".join([name] if name else ["VAR", f"{code:04X}"])
                       + "".join(f" {a:04X}" for a in args) + "}")
        elif _plain(unit):
            out.append(chr(unit))
        else:
            out.append(f"{{CHAR {unit:04X}}}")
        k += 1
    return "".join(out)


def from_editor(text: str) -> List[int]:
    units: List[int] = []
    pos = 0
    for found in TAG_RE.finditer(text):
        units += _chars(text[pos:found.start()])
        pos = found.end()
        words = found.group(0)[1:-1].split()
        if words[0] == "CHAR" and len(words) == 2:
            units.append(int(words[1], 16))
        elif words[0] == "VAR":
            units += [VARIABLE, int(words[1], 16), len(words) - 2, *(int(w, 16) for w in words[2:])]
        else:
            units += [VARIABLE, CODES[words[0]], len(words) - 1, *(int(w, 16) for w in words[1:])]
    return units + _chars(text[pos:])


def _chars(text: str) -> List[int]:
    out: List[int] = []
    for char in text.replace("\r\n", "\n"):
        out.append(FEED if char == "\n" else ord(char))
    return out


def labelled(data: bytes, index: int) -> Optional[Line]:
    """Line ``index`` of a file, or None."""
    try:
        return read(data)[index]
    except (IndexError, ValueError):
        return None


_DESCRIPTIONS = (
    (r"\{PAGE\}", "Next text box: the text so far is cleared"),
    (r"\{SCROLL\}", "Scroll: the text moves up one line"),
    (r"\{WAIT .*", "Wait (frames)"),
    (r"\{NULL.*", "Empty command"),
    (r"\{COLOR .*", "Colour of the text that follows"),
    (r"\{VAR 01.*", "A name the game inserts (player, Pokémon, move, item...)"),
    (r"\{VAR 02.*", "A number the game inserts"),
    (r"\{CHAR E[0-9A-F]{3}\}", "Button or symbol icon of the font"),
    (r"\{CHAR .*", "Special character"),
)


def describe(tag: str) -> str:
    """Tooltip of an editor tag."""
    return next((text for pattern, text in _DESCRIPTIONS if re.fullmatch(pattern, tag or "")),
                "Game command" if (tag or "").startswith("{VAR ") else "")
