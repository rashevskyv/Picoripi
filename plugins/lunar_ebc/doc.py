"""A Lunar 2 text file as Picoripi blocks, and the file again from edited blocks.

Kinds of file (``source\\DATA`` of the workspace):

- ``script``: an "ES" block at the start (``EVENT\\*.bin``, ``SYSTEM\\0003.bin``), then the data the
  script uses (voice timing) -- one block, a string per message;
- ``people``: header ``[size, count, offsets of 4 parts]`` with the "ES" block as part 2
  (``PEOPLE\\*.bin``, ``SYSTEM\\2519.bin``); a grown block moves part 4 and the size;
- ``table``: strings that each end with the unit 0xFFFF (``SYSTEM\\2499\\05-12.bin``: items, spells,
  menus, help lines); the game counts its way to a string, so strings may grow;
- ``battle``: monster names, fixed 21-character fields (``BATTLE\\*.bin``);
- ``map``: the place name at 0x38, a fixed field (``MAP\\*.bin``).

Fixed fields are padded with ``_`` (the pen stop) as the game does; the editor shows them without it.
A string that comes back unchanged keeps its original bytes, so an unedited file is rebuilt byte for byte.
"""
from __future__ import annotations

import struct
from typing import Dict, List, Optional, Set, Tuple

from . import codec, es

Blocks = List[List[str]]
STOP = 0xFFFF
PAD = "_"
NAME_ENTRY = 24            # a monster name: 0x06, 21 characters, the end, 0xFFFF
# How far a file may grow (the game's buffers; the largest original file of each kind fits them).
SCRIPT_LIMIT = 0x34000     # an event script and its data are copied into 0x80122000 (0x3C000 cleared)
SYSMSG_LIMIT = 0x80        # the system messages are copied as 0x80 bytes
PEOPLE_LIMIT = 0x45000     # loaded at 0x800BB000; the next buffer the program names is at 0x80100000


class TooLong(ValueError):
    """The edited text does not fit the room the game has for it."""


def _u32(data: bytes, at: int) -> int:
    return struct.unpack_from("<I", data, at)[0]


def _people_header(data: bytes) -> Optional[Tuple[int, ...]]:
    if len(data) < 0x18:
        return None
    total, people, *offsets = struct.unpack_from("<6I", data, 0)
    script = offsets[1]
    if not (offsets[0] == 0x18 and 0x18 < script < total <= len(data) and script % 4 == 0):
        return None
    return (total, people, *offsets) if data[script:script + 4] == es.MAGIC else None


def _battle_names(data: bytes) -> Optional[Tuple[int, int, int]]:
    """``(first entry, count, entry size)`` of a battle file's name table."""
    if len(data) < 16 or _u32(data, 0) > 0x40:
        return None
    at = _u32(data, 4)
    if not 0x0C <= at < len(data) - 12:
        return None
    entry, first = NAME_ENTRY, at + 12
    count = _u32(data, at + 8) // entry
    if not (1 <= count <= 32 and _u32(data, at + 8) % entry == 0 and first + count * entry <= len(data)):
        return None
    for i in range(count):
        e = first + i * entry
        if data[e + 1] != codec.LINE or struct.unpack_from("<H", data, e + entry - 2)[0] != STOP:
            return None
    return first, count, entry


def _map_name(data: bytes) -> Optional[Tuple[int, int]]:
    """``(start, end)`` of a map's name (end just before its 0xFFFF)."""
    if len(data) < 0x6C or _u32(data, 0x20) != 0x4C or data[0x39] != codec.LINE:
        return None
    for at in range(0x38, 0x6C, 2):
        if struct.unpack_from("<H", data, at)[0] == STOP:
            return 0x38, at
    return None


def _table(data: bytes) -> Optional[List[Tuple[int, int]]]:
    """``[(start, end)]`` of the strings of a table (end just before its 0xFFFF)."""
    if len(data) < 4 or len(data) % 2 or data[1] != codec.LINE:
        return None
    out, start = [], 0
    for at in range(0, len(data), 2):
        if struct.unpack_from("<H", data, at)[0] == STOP:
            out.append((start, at))
            start = at + 2
    return out if out and start == len(data) else None


def kind(data: bytes) -> str:
    """``script``, ``people``, ``battle``, ``map`` or ``table``; ValueError for any other file."""
    if data[:4] == es.MAGIC:
        return "script"
    if _people_header(data):
        return "people"
    if _battle_names(data):
        return "battle"
    if _map_name(data):
        return "map"
    if _table(data):
        return "table"
    raise ValueError("no Lunar 2 text in this file")


def _script_at(data: bytes) -> int:
    return 0 if data[:4] == es.MAGIC else _people_header(data)[3]


def _messages(data: bytes, block: es.Block) -> List[Tuple[int, int]]:
    base = block.start + block.text[0]
    return [(base + offset + 2, base + offset + length) for offset, length in block.messages]


def _fixed(text: str) -> str:
    return text.rstrip(PAD)


def read(data: bytes) -> Tuple[Blocks, Dict[str, str]]:
    """``(blocks, block names)`` of a file."""
    what = kind(data)
    if what in ("script", "people"):
        block = es.parse(data, _script_at(data))
        return [[codec.decode(codec.units(data, a, b)) for a, b in _messages(data, block)]], {}
    if what == "battle":
        first, count, entry = _battle_names(data)
        lines = [_fixed(codec.decode(codec.units(data, first + i * entry, first + i * entry + entry - 2)))
                 for i in range(count)]
        return [lines], {"0": "Monsters"}
    if what == "map":
        start, end = _map_name(data)
        return [[_fixed(codec.decode(codec.units(data, start, end)))]], {"0": "Place name"}
    return [[codec.decode(codec.units(data, a, b)) for a, b in _table(data)]], {}


def _fixed_units(text: str, old: List[int], encoder: codec.Encoder, what: str) -> List[int]:
    """``text`` as a line of exactly the old field's characters (padded with ``_``)."""
    width = len(codec.decode(old))
    new = encoder.encode(text.ljust(width, PAD))
    if len(new) != len(old) or len(codec.decode(new)) != width:
        raise TooLong(f"{what} '{text}' is longer than {width} characters (the field is fixed).")
    return new


def write(source: bytes, blocks: Blocks, missing: Set[str]) -> bytes:
    """``source`` with the texts of ``blocks`` (the shape ``read`` returned)."""
    lines = blocks[0] if blocks else []
    encoder = codec.Encoder()
    what = kind(source)
    out = bytearray(source)
    if what == "battle":
        first, count, entry = _battle_names(source)
        for i, text in enumerate(lines[:count]):
            a = first + i * entry
            old = codec.units(source, a, a + entry - 2)
            if text != _fixed(codec.decode(old)):
                out[a:a + entry - 2] = codec.pack(_fixed_units(text, old, encoder, "Monster name"))
    elif what == "map":
        start, end = _map_name(source)
        old = codec.units(source, start, end)
        if lines and lines[0] != _fixed(codec.decode(old)):
            out[start:end] = codec.pack(_fixed_units(lines[0], old, encoder, "Place name"))
    elif what == "table":
        parts = []
        for i, (a, b) in enumerate(_table(source)):
            old = codec.units(source, a, b)
            text = lines[i] if i < len(lines) else None
            parts.append(source[a:b] if text is None or text == codec.decode(old) else codec.pack(encoder.encode(text)))
        out = bytearray(b"".join(p + b"\xff\xff" for p in parts))
    else:
        out = bytearray(_write_script(source, lines, encoder, what))
    missing |= encoder.missing
    return bytes(out)


def _write_script(source: bytes, lines: List[str], encoder: codec.Encoder, what: str) -> bytes:
    start = _script_at(source)
    block = es.parse(source, start)
    new: Dict[int, bytes] = {}
    for i, (a, b) in enumerate(_messages(source, block)):
        if i < len(lines) and lines[i] != codec.decode(codec.units(source, a, b)):
            body = codec.pack(encoder.encode(lines[i]))
            new[i] = struct.pack("<H", len(body) + 2) + body
    if not new:
        return source
    script = es.rebuild(source, block, new)
    delta = len(script) - block.size
    out = bytearray(source[:start] + script + source[start + block.size:])
    if what == "people":
        header = _people_header(source)
        struct.pack_into("<I", out, 0, header[0] + delta)
        for slot, offset in enumerate(header[2:], start=2):
            if offset > start:
                struct.pack_into("<I", out, slot * 4, offset + delta)
        size, limit = header[0] + delta, PEOPLE_LIMIT
    elif _sysmsg(source, block):
        size, limit = len(script), SYSMSG_LIMIT
    else:
        size, limit = len(script) + _u32(source, block.size + 4), SCRIPT_LIMIT
    if size > limit:
        raise TooLong(f"The script text is {size - limit} bytes too long for the game's buffer "
                      f"(room {limit} bytes). Shorten some messages.")
    return bytes(out)


def _sysmsg(data: bytes, block: es.Block) -> bool:
    """The system messages: a script block with nothing after it."""
    return not any(data[block.size:])
