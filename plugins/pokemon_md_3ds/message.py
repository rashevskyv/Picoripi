"""SIR0 message files of the Mystery Dungeon 3DS games and their text as tagged strings.

A message file (``message/*.bin`` in Gates to Infinity, a member of ``message_en.bin`` in Super Mystery Dungeon):
``SIR0``, u32 content header offset, u32 pointer list offset, u32 0; the strings from 0x10 (UTF-16LE, each ending in
0000); padding to 4; the entry table, 12 bytes per message (u32 string offset, u32 name hash, u32 flags) sorted by
hash; the content header (u32 count, u32 table offset); padding to 16; the pointer list (every pointer's offset as
a big-endian 7-bit varint delta: 4, 8, the table's string offsets, the header's table offset; a 0 ends it); padding to
16. ``rebuild`` lays the same thing out again around new strings, so text may grow.

The strings are shown in file order (the order the game's writers used, not the hash order of the table). Text:
U+000A is a line break; a control code (``codes.py``) is ``[name]``, or ``[name:LL:UUUU...]`` with the code's low
byte and the units it takes; a code the table does not know, or a stray control unit, is ``[XXXX]``; a literal
bracket is doubled (``[[``, ``]]``). ``encode`` turns a tag the table does not know back into its literal characters.
"""
from __future__ import annotations

import re
import struct
from typing import Dict, List, Optional, Tuple

from .codes import GAMES, TABLES, Code

MAGIC = b"SIR0"
TAG_RE = re.compile(r"\[(?!\[)[^\[\]]*\]")
_HEX2 = re.compile(r"[0-9A-Fa-f]{2}$")
_HEX4 = re.compile(r"[0-9A-Fa-f]{4}$")
_CODE_MIN, _CODE_MAX = 0xA000, 0xFEFF


class FormatError(ValueError):
    pass


def _lookup(game: str):
    table = TABLES[game]
    by_value = {c.value: c for c in table if c.flags == 0}
    by_family = {c.value & 0xFF00: c for c in table if c.flags != 0}
    by_name = {c.name.rstrip(":"): c for c in table}
    return by_value, by_family, by_name


_LOOKUPS = {game: _lookup(game) for game in GAMES}


# ---------------------------------------------------------------- text <-> units

def decode(units: List[int], game: str) -> str:
    by_value, by_family, _names = _LOOKUPS[game]
    out, i, n = [], 0, len(units)
    while i < n:
        u = units[i]
        i += 1
        if u == 0x0A:
            out.append("\n")
        elif u == 0x5B:
            out.append("[[")
        elif u == 0x5D:
            out.append("]]")
        elif _CODE_MIN <= u <= _CODE_MAX:
            code: Optional[Code] = by_value.get(u) or by_family.get(u & 0xFF00)
            if code is None:
                out.append(f"[{u:04X}]")
                continue
            parts = [code.name.rstrip(":")]
            if code.flags:
                parts.append(f"{u & 0xFF:02X}")
            take = 2 if code.flags == 2 else code.units
            parts.extend(f"{v:04X}" for v in units[i:i + take])
            i += min(take, n - i)
            out.append("[" + ":".join(parts) + "]")
        elif u < 0x20:
            out.append(f"[{u:04X}]")
        else:
            out.append(chr(u))
    return "".join(out)


def parse_tag(tag: str, game: str) -> Optional[List[int]]:
    """The units of ``[...]`` (without doubled brackets), or None when the tag is not one of this game's."""
    inner = tag[1:-1]
    if _HEX4.fullmatch(inner):
        return [int(inner, 16)]
    _values, _families, by_name = _LOOKUPS[game]
    parts = inner.split(":")
    for i in range(len(parts), 0, -1):
        code = by_name.get(":".join(parts[:i]))
        if code is None:
            continue
        rest = parts[i:]
        if not all(_HEX2.fullmatch(p) or _HEX4.fullmatch(p) for p in rest):
            return None
        value = code.value
        if code.flags and rest and _HEX2.fullmatch(rest[0]):
            value = (value & 0xFF00) | int(rest[0], 16)
            rest = rest[1:]
        return [value] + [int(p, 16) for p in rest]
    return None


def encode(text: str, game: str) -> List[int]:
    units: List[int] = []
    i, n = 0, len(text)
    while i < n:
        ch = text[i]
        if text.startswith("[[", i):
            units.append(0x5B)
            i += 2
        elif text.startswith("]]", i):
            units.append(0x5D)
            i += 2
        elif ch == "[":
            match = TAG_RE.match(text, i)
            parsed = parse_tag(match.group(0), game) if match else None
            if parsed is None:
                units.append(0x5B)
                i += 1
            else:
                units.extend(parsed)
                i = match.end()
        elif ch == "\n":
            units.append(0x0A)
            i += 1
        else:
            units.append(ord(ch))
            i += 1
    return units


# ---------------------------------------------------------------- file

def _varint(value: int) -> bytes:
    out = [value & 0x7F]
    value >>= 7
    while value:
        out.append(0x80 | (value & 0x7F))
        value >>= 7
    return bytes(reversed(out))


class File:
    """The entries of a message file: ``(hash, flags, units)`` in table order, and the file order of the strings."""

    def __init__(self, raw: bytes):
        if raw[:4] != MAGIC or len(raw) < 0x20:
            raise FormatError("not a SIR0 message file")
        header = struct.unpack_from("<I", raw, 4)[0]
        count, table = struct.unpack_from("<II", raw, header)
        if table + count * 12 != header:
            raise FormatError("not a message table")
        self.entries: List[Tuple[int, int, List[int]]] = []
        pointers = []
        for i in range(count):
            pointer, hash_, flags = struct.unpack_from("<III", raw, table + i * 12)
            if pointer < 0x10 or pointer >= table or pointer & 1:
                raise FormatError("not a message table")
            end = raw.index(b"\0\0", pointer)
            while (end - pointer) & 1:
                end = raw.index(b"\0\0", end + 1)
            self.entries.append((hash_, flags, list(struct.unpack_from(f"<{(end - pointer) // 2}H", raw, pointer))))
            pointers.append(pointer)
        self.order = sorted(range(count), key=lambda i: (pointers[i], i))

    def texts(self, game: str) -> List[str]:
        return [decode(self.entries[i][2], game) for i in self.order]

    def rebuild(self, texts: List[str], game: str) -> bytes:
        if len(texts) != len(self.order):
            raise FormatError(f"{len(texts)} strings for {len(self.order)} messages")
        pointers: Dict[int, int] = {}
        body = bytearray()
        for text, index in zip(texts, self.order):
            units = encode(text, game)
            pointers[index] = 0x10 + len(body)
            body += struct.pack(f"<{len(units)}H", *units) + b"\0\0"
        body += bytes(-len(body) % 4)
        table = 0x10 + len(body)
        count = len(self.entries)
        for index, (hash_, flags, _units) in enumerate(self.entries):
            body += struct.pack("<III", pointers[index], hash_, flags)
        header = 0x10 + len(body)
        body += struct.pack("<II", count, table)
        body += bytes(-(0x10 + len(body)) % 16)
        pointer_list = 0x10 + len(body)
        offsets = [4, 8] + [table + i * 12 for i in range(count)] + [header + 4]
        last = 0
        for offset in offsets:
            body += _varint(offset - last)
            last = offset
        body += b"\0"
        body += bytes(-(0x10 + len(body)) % 16)
        return MAGIC + struct.pack("<III", header, pointer_list, 0) + bytes(body)


def attributes(raw: bytes) -> List[Dict[str, str]]:
    """``{"hash", "flags"}`` of every message, in the order ``texts`` gives them."""
    file = File(raw)
    return [{"hash": f"{file.entries[i][0]:08X}", "flags": f"{file.entries[i][1]:08X}"} for i in file.order]
