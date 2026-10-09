"""Harvest Moon 3D: The Tale of Two Towns (3DS, EUR) message packs and their 16-bit text codes.

``mes_data.bin`` (menus, items, system) and ``event_mes_data.bin`` (dialogue, events) are packs: u32 count,
u32 0, then (size, next offset) pairs and the entries, 4-byte aligned. A text entry (``Table``) starts with
the end offsets of its strings (u32 each, counted from 4 bytes before the entry), then the strings as u16
codes: ``0x0800 + i`` is cell ``i`` of the game's 8x16 font (``CHARS``: ASCII from the space, five Japanese
marks, the accented Latin letters; cells 159 and up are free and take the Ukrainian letters), ``0x2328`` a
line break, ``0x270E`` the end of a string and any other code a control (``{1000}`` = a variable). The game
reads the English file; ``*_fr_*.bin`` and ``*_ge.bin`` are the other languages.
"""
from __future__ import annotations

import re
import struct
from typing import List, Sequence, Tuple

ASCII = "".join(chr(c) for c in range(0x20, 0x7F)).replace("\\", "¥")
ACCENTS = "ÇüéâäàåçêëèïîìÄÅÉæÆôöòûùÿÖÜáíóúñÑ¿¡ÂÀÊËÈÎÏßÔÕÙÍÒãÓÕõõÚÎÁœŒÃ"
UKRAINIAN = "АБВГҐДЕЄЖЗИІЇЙКЛМНОПРСТУФХЦЧШЩЬЮЯабвгґдеєжзиіїйклмнопрстуфхцчшщьюя«»–—"
FIRST_FREE = 159
CHARS = ASCII + "。「」、・" + ACCENTS
assert len(CHARS) == FIRST_FREE
CHARS += UKRAINIAN
CELLS = 256
TEXT_PAGE, NEWLINE, END = 0x0800, 0x2328, 0x270E
TAG_RE = re.compile(r"\{[0-9A-F]{4}\}")
_CODE_OF = {}
for _i, _ch in enumerate(CHARS):
    _CODE_OF.setdefault(_ch, TEXT_PAGE + _i)
_CODE_OF["\\"] = TEXT_PAGE + 60


class FormatError(ValueError):
    """Not a message pack or table."""


# ---------------------------------------------------------------- packs

def read_pack(data: bytes) -> List[bytes]:
    if len(data) < 8:
        raise FormatError("too short for a pack")
    count = struct.unpack_from("<I", data, 0)[0]
    base = 8 + count * 8
    if count == 0 or base > len(data):
        raise FormatError("not a pack")
    items, start = [], 0
    for i in range(count):
        size, nxt = struct.unpack_from("<II", data, 8 + i * 8)
        last = i + 1 == count
        if (base + start + size > len(data) and not last) or (nxt < start + size and not last):
            raise FormatError("pack entry out of range")
        items.append(data[base + start:base + start + size])   # the last entry may claim bytes past the end
        start = nxt
    return items


def write_pack(items: Sequence[bytes], original: bytes = b"") -> bytes:
    """A pack of ``items``. The last entry's header pair is copied from ``original`` while that entry is
    unchanged (its "next" word is unused and its size may overshoot the file by two bytes in the game's files)."""
    head = bytearray(struct.pack("<II", len(items), 0))
    body = bytearray()
    for item in items:
        body += item
        body += bytes(-len(body) % 4)
        head += struct.pack("<II", len(item), len(body))
    if original and len(original) >= 8 + len(items) * 8:
        at = len(items) * 8
        head[-4:] = original[4 + at:8 + at]
        if read_pack(original)[-1] == items[-1]:
            head[-8:-4] = original[at:4 + at]
    return bytes(head) + bytes(body)


# ---------------------------------------------------------------- codes

def decode(codes: Sequence[int]) -> str:
    out = []
    for code in codes:
        if TEXT_PAGE <= code < TEXT_PAGE + len(CHARS):
            out.append(CHARS[code - TEXT_PAGE])
        elif code == NEWLINE:
            out.append("\n")
        else:
            out.append("{%04X}" % code)
    return "".join(out)


def encode(text: str) -> List[int]:
    codes: List[int] = []
    at = 0
    while at < len(text):
        tag = TAG_RE.match(text, at)
        if tag:
            codes.append(int(tag.group()[1:5], 16))
            at = tag.end()
            continue
        ch = text[at]
        at += 1
        if ch == "\n":
            codes.append(NEWLINE)
        elif ch in _CODE_OF:
            codes.append(_CODE_OF[ch])
        elif ch == "\r":
            continue
        else:
            raise ValueError(f"the game's font has no cell for {ch!r}")
    return codes


# ---------------------------------------------------------------- tables

class Table:
    """A text entry of a pack: strings with end offsets. ``build`` gives the same bytes for unchanged texts."""

    def __init__(self, raw: bytes):
        self.raw = raw
        ends: List[int] = []
        while 4 * len(ends) + 4 <= len(raw):
            end = struct.unpack_from("<I", raw, 4 * len(ends))[0] - 4
            if end > len(raw) or end < 4 * (len(ends) + 1) or (ends and end <= ends[-1]):
                break
            ends.append(end)
        self.strings: List[Tuple[int, ...]] = []
        start = 4 * len(ends)
        for end in ends:
            self.strings.append(struct.unpack_from(f"<{(end - start) // 2}H", raw, start))
            start = end
        self.tail = raw[start:]
        if any(code >> 8 == TEXT_PAGE >> 8 for codes in self.strings for code in codes) is False:
            self.strings, self.tail = [], raw   # binary data, not text

    def is_text(self) -> bool:
        return bool(self.strings)

    def texts(self) -> List[str]:
        return [decode(codes[:-1] if codes and codes[-1] == END else codes) for codes in self.strings]

    def build(self, texts: Sequence[str]) -> bytes:
        if list(texts) == self.texts():
            return self.raw
        if len(texts) != len(self.strings):
            raise ValueError(f"the table holds {len(self.strings)} strings, {len(texts)} were given")
        body = bytearray()
        ends = []
        base = 4 * len(self.strings)
        for text, old in zip(texts, self.strings):
            codes = encode(text)
            if old and old[-1] == END:
                codes.append(END)
            body += struct.pack(f"<{len(codes)}H", *codes)
            ends.append(base + len(body) + 4)
        return struct.pack(f"<{len(ends)}I", *ends) + bytes(body) + self.tail
