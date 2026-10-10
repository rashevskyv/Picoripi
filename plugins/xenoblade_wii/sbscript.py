"""Xenoblade Chronicles script files (``SB  ``, version 2): the string pool, its text lines, and the file written
back with new lines.

Header: ``SB  ``, u8 2, u8 0, u8 flags, u8 0, then 13 u32 section offsets, the first always 0x40 (the Wii file
big-endian, the New 3DS port little-endian). Every section starts with u32 data offset, u32 count, u32 entry
size, then a table of ``count`` offsets of that size, relative to the section start plus the data offset.
Section 4 is the string pool: NPC talk, event lines, heart-to-hearts, choices, and the developers' Shift-JIS
debug prints and identifiers.

Wii (flags bit 1): the pool's strings follow its table and are scrambled: from the first string to the next
section, each whole 32-bit big-endian word is rotated left by 2 bits (a last partial word stays as it is). The
3DS port keeps them plain, and for 142 scripts moved them behind the last section with u32 tables, leaving the
old pool room in place.

Writing: when the table and every string fit the pool's room (up to the next section), they are laid out there.
Else a 3DS script gets its changed strings at the end of the file (only their table entries change; a u16 table
that cannot reach that far becomes u32 in the same room with every string at the end), as the port did; a Wii
script gets a bigger pool and the sections behind it move (their offsets in the header follow). Unchanged lines
give the original bytes.

A text line is a pool string that is valid UTF-8 and reads as words for the player (``is_text``): identifiers,
function names, debug prints and the Japanese NPC labels stay out of the project.
"""
from __future__ import annotations

import re
import struct
from typing import List, Tuple

MAGIC = b"SB  "
SECTIONS = 13
POOL = 4
SCRAMBLED = 2
_FMT = {1: "B", 2: "H", 4: "I"}
_DEBUG = re.compile(r"\(\)|==|=====|\s:\s*$|^\s|@set|\[function|^\w+ err$|[\u3000-\u9fff\uff00-\uffef]")
_WORD = re.compile(r"^[A-Z][A-Za-z'’.,!?-]*$")


def endian_of(data: bytes) -> str:
    if len(data) < 0x40 or data[:4] != MAGIC:
        return ""
    return ">" if data[8:12] == b"\0\0\0\x40" else "<" if data[8:12] == b"\x40\0\0\0" else ""


def is_script(data: bytes) -> bool:
    return bool(endian_of(data))


def _layout(data: bytes, e: str) -> Tuple[int, int, int, int, List[int]]:
    """``(pool section, its end, entry size, base of the offsets, table)``."""
    sections = struct.unpack_from(f"{e}{SECTIONS}I", data, 8)
    sec = sections[POOL]
    end = min([o for o in sections if o > sec] or [len(data)])
    start, count, size = struct.unpack_from(e + "III", data, sec)
    table = list(struct.unpack_from(f"{e}{count}{_FMT[size]}", data, sec + start))
    return sec, end, size, sec + start, table


def _rotate(data: bytearray, start: int, end: int, e: str, left: bool) -> None:
    """Rotate every whole 32-bit word of ``data[start:end]`` by 2 bits (left = scramble)."""
    for at in range(start, end - 3, 4):
        v = int.from_bytes(data[at:at + 4], "big" if e == ">" else "little")
        v = ((v << 2) | (v >> 30)) if left else ((v >> 2) | (v << 30))
        data[at:at + 4] = (v & 0xFFFFFFFF).to_bytes(4, "big" if e == ">" else "little")


def _plain(data: bytes, e: str) -> bytes:
    if not data[6] & SCRAMBLED:
        return bytes(data)
    sec, end, size, base, table = _layout(data, e)
    out = bytearray(data)
    _rotate(out, base + len(table) * size, end, e, left=False)
    return bytes(out)


def pool(data: bytes) -> List[bytes]:
    """Every string of the pool, unscrambled (without the NUL)."""
    e = endian_of(data)
    plain = _plain(data, e)
    _sec, _end, _size, base, table = _layout(plain, e)
    return [bytes(plain[base + o:plain.index(b"\0", base + o)]) for o in table]


def is_text(raw: bytes) -> bool:
    """A line for the player: UTF-8, not an identifier or a debug print."""
    try:
        text = raw.decode("utf-8")
    except UnicodeDecodeError:
        return False
    if not text or not any(c.isalpha() for c in text) or _DEBUG.search(text):
        return False
    if "<" in text or " " in text.strip() or any(ord(c) > 0x7F for c in text):
        return True
    return bool(_WORD.match(text)) and "_" not in text


def read(data: bytes) -> List[str]:
    return [raw.decode("utf-8") for raw in pool(data) if is_text(raw)]


def write(data: bytes, texts: List[str]) -> bytes:
    """``data`` with its text lines set to ``texts`` (as ``read`` lists them)."""
    e = endian_of(data)
    strings = pool(data)
    lines = [i for i, raw in enumerate(strings) if is_text(raw)]
    if len(texts) != len(lines):
        raise ValueError(f"the script has {len(lines)} text lines, the project {len(texts)}")
    new = list(strings)
    for i, text in zip(lines, texts):
        new[i] = text.encode("utf-8")
    if new == strings:
        return bytes(data)
    scrambled = bool(data[6] & SCRAMBLED)
    sec, end, size, base, table = _layout(data, e)
    count = len(table)
    if size < 4 and count * size + sum(len(raw) + 1 for raw in new[:-1]) > 0xFFFF:
        if not scrambled:
            return _append(data, e, sec, end, size, base, table, strings, new)
        size = 4                                         # a Wii pool that outgrows u16 offsets
    room = _room(e, count, size, new)
    partial = (end - sec - 12 - count * size) % 4 if scrambled else 0    # unscrambled bytes: padding only
    if len(room) <= end - sec - partial:                 # 1. everything in the pool's own room
        out = bytearray(data)
        out[sec:end] = room + bytes(end - sec - len(room))
        if scrambled:
            _rotate(out, sec + 12 + count * size, end, e, left=True)
        return bytes(out)
    if scrambled:                                        # Wii: a bigger pool, the sections behind it move
        room += bytes(-len(room) % 4)
        if (len(room) - 12 - count * size) % 4:          # the last partial word holds padding only
            room += bytes(4)
        out = bytearray(data[:sec]) + room + data[end:]
        delta = len(room) - (end - sec)
        sections = struct.unpack_from(f"{e}{SECTIONS}I", data, 8)
        struct.pack_into(f"{e}{SECTIONS}I", out, 8, *[o + delta if o > sec else o for o in sections])
        _rotate(out, sec + 12 + count * size, sec + len(room), e, left=True)
        return bytes(out)
    return _append(data, e, sec, end, size, base, table, strings, new)


def _room(e: str, count: int, size: int, strings: List[bytes]) -> bytes:
    """The pool section: header, table, then the strings right after it."""
    blob, offsets = bytearray(), []
    for raw in strings:
        offsets.append(count * size + len(blob))
        blob += raw + b"\0"
    return struct.pack(e + "III", 12, count, size) + struct.pack(f"{e}{count}{_FMT[size]}", *offsets) + bytes(blob)


def _append(data, e, sec, end, size, base, table, strings, new) -> bytes:
    """3DS: changed strings behind the last section (or every string, with a u32 table in the old room)."""
    out = bytearray(data)
    count = len(table)
    tail = bytearray(bytes(-len(out) % 4))
    moved = list(table)
    for i, raw in enumerate(new):
        if raw != strings[i]:
            moved[i] = len(out) + len(tail) - base
            tail += raw + b"\0" + bytes(-(len(raw) + 1) % 4)
    if size == 4 or max(moved) <= 0xFFFF:
        struct.pack_into(f"{e}{count}{_FMT[size]}", out, base, *moved)
        return bytes(out + tail)
    if 12 + count * 4 > end - sec:
        raise ValueError("the script's string table does not fit its room as u32 entries")
    tail, moved = bytearray(bytes(-len(out) % 4)), []
    for raw in new:
        moved.append(len(out) + len(tail) - (sec + 12))
        tail += raw + b"\0" + bytes(-(len(raw) + 1) % 4)
    room = struct.pack(e + "III", 12, count, 4) + struct.pack(f"{e}{count}I", *moved)
    out[sec:end] = room + bytes(end - sec - len(room))
    return bytes(out + tail)
