r"""Ikenie no Yoru message table (``MES0``): one table of a package entry, e.g. ``package/ch01_01/028a.mes``.

Layout (big endian): magic ``MES0``, u16 message count, u16 number of the table's first message in the game's
global list, a u16 offset per message, then the messages, each UTF-16 text + ``000B`` + ``0000``, padded to 4
bytes; the table is padded to 0x20 bytes. Offsets count from the start of the table, so a table stays under
64 KB. (The English patch wrote its tables without the ``0000``; the game reads both.)

Control codes are UTF-16 units below 0x20: ``000A`` breaks the line, ``000C`` starts the next page,
``0001 n`` is the name of girl n (the player names them), ``0003`` + a float sets the text size and ``0007`` +
RGBA the colour. The editor shows them as ``{PAGE}``, ``{NAME:1}``, ``{SIZE:3F800000}``, ``{COLOR:FF0000FF}``;
every other unit below 0x20 (debug leftovers, a code at the end of a message) is ``{U0008}``. ``{`` in the text
is ``{U007B}``, so the conversion is lossless.
"""
from __future__ import annotations

import re
import struct
from typing import List

MAGIC = b"MES0"
END = 0x000B
UNUSED = "※未"                                   # the game's placeholder for an unused slot: ※未使用枠, ※未
TAG_RE = re.compile(r"\{(?:PAGE|NAME:\d+|SIZE:[0-9A-F]{8}|COLOR:[0-9A-F]{8}|U[0-9A-F]{4})\}")
_TOKEN = re.compile(r"\{(PAGE|NAME:(\d+)|SIZE:([0-9A-F]{8})|COLOR:([0-9A-F]{8})|U([0-9A-F]{4}))\}")
# kana and kanji; 十 is the game's D-pad icon in the English text
_JAPANESE = re.compile(r"[぀-ヿ㐀-區卂-鿿ｦ-ﾟ]")


def is_mes(raw: bytes) -> bool:
    return bytes(raw[:4]) == MAGIC and len(raw) >= 8


def units(raw: bytes) -> List[List[int]]:
    """Every message as UTF-16 code units, without the end mark."""
    if not is_mes(raw):
        raise ValueError("Not an Ikenie no Yoru message table (MES0)")
    count = struct.unpack_from(">H", raw, 4)[0]
    out = []
    for offset in struct.unpack_from(f">{count}H", raw, 8):
        message = []
        while True:
            unit = struct.unpack_from(">H", raw, offset)[0]
            if unit == END:
                break
            message.append(unit)
            offset += 2
        out.append(message)
    return out


def first_number(raw: bytes) -> int:
    return struct.unpack_from(">H", raw, 6)[0]


def build(messages: List[List[int]], first: int = 0) -> bytes:
    """A table of ``messages`` (code units) laid out as the game does; ``first`` as in the original table."""
    count = len(messages)
    out = bytearray(MAGIC + struct.pack(">HH", count, first) + bytes(2 * count))
    out += bytes(-len(out) % 4)
    for index, message in enumerate(messages):
        if len(out) > 0xFFFF:
            raise ValueError("The message table is longer than 64 KB")
        struct.pack_into(">H", out, 8 + 2 * index, len(out))
        out += struct.pack(f">{len(message) + 2}H", *message, END, 0)
        out += bytes(-len(out) % 4)
    return bytes(out + bytes(-len(out) % 0x20))


def to_editor(message: List[int]) -> str:
    out, at = [], 0
    while at < len(message):
        unit = message[at]
        if unit == 0x000A:
            out.append("\n")
        elif unit == 0x000C:
            out.append("{PAGE}")
        elif unit == 0x0001 and at + 1 < len(message):
            out.append(f"{{NAME:{message[at + 1]}}}")
            at += 1
        elif unit in (0x0003, 0x0007) and at + 2 < len(message):
            name = "SIZE" if unit == 0x0003 else "COLOR"
            out.append(f"{{{name}:{message[at + 1]:04X}{message[at + 2]:04X}}}")
            at += 2
        elif unit < 0x20 or unit == 0x7B or 0xD800 <= unit < 0xE000:
            out.append(f"{{U{unit:04X}}}")
        else:
            out.append(chr(unit))
        at += 1
    return "".join(out)


def from_editor(text: str) -> List[int]:
    out: List[int] = []
    at = 0
    for match in _TOKEN.finditer(text):
        out += _plain(text[at:match.start()])
        kind, name, size, colour, unit = match.groups()
        if kind == "PAGE":
            out.append(0x000C)
        elif name is not None:
            out += [0x0001, int(name)]
        elif size or colour:
            value = int(size or colour, 16)
            out += [0x0003 if size else 0x0007, value >> 16, value & 0xFFFF]
        else:
            out.append(int(unit, 16))
        at = match.end()
    return out + _plain(text[at:])


def _plain(text: str) -> List[int]:
    data = text.replace("\r\n", "\n").encode("utf-16-be")
    return list(struct.unpack(f">{len(data) // 2}H", data))


def is_japanese(text: str) -> bool:
    """A message the English patch left Japanese (kana or kanji outside tags; not the unused-slot mark)."""
    plain = TAG_RE.sub("", text)
    return not plain.startswith(UNUSED) and bool(_JAPANESE.search(plain))
