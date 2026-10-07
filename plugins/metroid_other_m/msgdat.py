r"""Metroid: Other M message file ``message/message_all.dat``: a Team Ninja ``tdpack`` of eight language tables.

Header (big endian): magic ``tdpack\0\0``, u32 0xFF000100, u32 0x30, u32 file size, u32 table count (twice),
u32 0, u32 offset of the table offsets, u32 offset of the table sizes, then those two lists and zero padding up
to the first table. Every table starts on 0x20 bytes, zero padded; the file ends padded the same way.

A table is UTF-8, one message a line: ``\`` + text + ``\`` + CRLF (1899 messages; table 1 is US English, 0
Japanese, then German, French, Spanish, Italian and the American French and Spanish). In a message ``^`` breaks
the line and ``#FONT_SYSTEM``, ``#COLOR_<name>``, ``#ICON_<name>`` and ``#IMG_<name>`` are control codes. They
have no end mark: the game matches its own name lists (``NAMES``, from main.dol and game.rel), so the editor shows
them as ``{COLOR_GREEN}`` and the longest known name wins.
"""
from __future__ import annotations

import re
import struct
from typing import List

MAGIC = b"tdpack\0\0"
ENGLISH = 1
ALIGN = 0x20
NAMES = {
    "FONT": ("SYSTEM",),
    "COLOR": ("BLACK", "BLUE", "RED", "VIOLET", "GREEN", "YELLOW", "WHITE", "GRAY", "ORANGE", "PINK", "BROWN",
              "DARK_BLUE", "LIGHT_GREEN", "DARK_GREEN", "SKY_BLUE"),
    "ICON": ("POWER", "HOME", "PLUS", "MINUS", "CROSS", "A", "B", "ONE", "TWO", "C", "D", "E", "F", "G", "H", "I",
             "J", "TEXT_END"),
    "IMG": ("ADAM", "ANTHONY", "JAMES", "KAGE", "LYLE", "MADERRY", "MB", "MOURICE"),
}
TAGS = sorted((f"{kind}_{name}" for kind, names in NAMES.items() for name in names), key=len, reverse=True)
_CODE = re.compile("#(" + "|".join(TAGS) + ")")
_TAG = re.compile(r"\{(" + "|".join(TAGS) + r")\}")
TAG_RE = re.compile(r"\{(?:" + "|".join(TAGS) + r")\}")


def is_msgdat(raw: bytes) -> bool:
    return bytes(raw[:8]) == MAGIC


def _layout(raw: bytes):
    if not is_msgdat(raw):
        raise ValueError("Not a Metroid: Other M message file (tdpack)")
    count, = struct.unpack_from(">I", raw, 0x14)
    offsets_at, sizes_at = struct.unpack_from(">II", raw, 0x20)
    return count, offsets_at, sizes_at


def tables(raw: bytes) -> List[bytes]:
    """The language tables, as stored."""
    count, offsets_at, sizes_at = _layout(raw)
    offsets = struct.unpack_from(f">{count}I", raw, offsets_at)
    sizes = struct.unpack_from(f">{count}I", raw, sizes_at)
    return [bytes(raw[o:o + s]) for o, s in zip(offsets, sizes)]


def build(raw: bytes, new_tables: List[bytes]) -> bytes:
    """``raw`` with its tables replaced; the same tables give ``raw`` back."""
    count, offsets_at, sizes_at = _layout(raw)
    if len(new_tables) != count:
        raise ValueError(f"The file has {count} tables, not {len(new_tables)}")
    out = bytearray(raw[:struct.unpack_from(">I", raw, offsets_at)[0]])
    for index, table in enumerate(new_tables):
        struct.pack_into(">I", out, offsets_at + 4 * index, len(out))
        struct.pack_into(">I", out, sizes_at + 4 * index, len(table))
        out += table + bytes(-len(table) % ALIGN)
    struct.pack_into(">I", out, 0x10, len(out))
    return bytes(out)


def messages(table: bytes) -> List[str]:
    """The message texts of a table (without the backslashes)."""
    lines = table.decode("utf-8").split("\r\n")
    if lines[-1] != "" or any(len(line) < 2 or line[0] != "\\" or line[-1] != "\\" for line in lines[:-1]):
        raise ValueError("A message table line is not \\text\\")
    return [line[1:-1] for line in lines[:-1]]


def table(texts: List[str]) -> bytes:
    return "".join(f"\\{text}\\\r\n" for text in texts).encode("utf-8")


def to_editor(text: str) -> str:
    """``#COLOR_GREEN`` -> ``{COLOR_GREEN}``, ``^`` -> a line break."""
    return _CODE.sub(r"{\1}", text).replace("^", "\n")


def from_editor(text: str) -> str:
    return _TAG.sub(r"#\1", text.replace("\n", "^"))       # a stray "\r" of the game's text stays as it is
