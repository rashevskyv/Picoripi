"""Kingdom Hearts 3D: Dream Drop Distance message files (``@CTD``): read the texts, write changed texts back.

Little endian. Header (0x20 bytes): ``@CTD``, u32 0x1F7, u32 base id, u16 layout count, u16 message count,
u32 message table offset (0x20), u32 layout table offset, u32 text start, u32 0. Message table: 8 bytes each,
``u32 id`` and ``u32 field = layout_index << 20 | text offset`` (an absolute file offset, 20 bits). Layout table:
20 bytes each (window position, size, alignment: kept as read). The text area holds UTF-16LE strings ending with
a zero code unit; several messages may share a string. Characters of the Unicode private area (U+E000..) are
the game's button icons and colour switches. Layout from OpenKH's ``docs/bbs/file/type/ctd.md`` (Apache-2.0),
checked against the DDD files.

An edited message is appended to the end of the file as a new string and its offset field is pointed at it;
the old string stays where it was (a message that shared it keeps it), so a file is only as long as its edits
need and an unedited file is written back byte for byte.
"""
from __future__ import annotations

import re
import struct
from typing import List, Tuple

MAGIC = b"@CTD"
HEADER = 0x20
OFFSET_MASK = 0xFFFFF
PUA_RE = re.compile("[-]")
TAG_RE = re.compile(r"\{U[0-9A-F]{4}\}")
_EDITOR_TAG = re.compile(r"\{U([0-9A-Fa-f]{4})\}")


def to_editor(text: str) -> str:
    """Private-area characters (icons, colours) as ``{UE026}``."""
    return PUA_RE.sub(lambda m: "{U%04X}" % ord(m.group()), text)


def from_editor(text: str) -> str:
    return _EDITOR_TAG.sub(lambda m: chr(int(m.group(1), 16)), text.replace("\r\n", "\n"))


class Ctd:
    """One parsed message file: ``ids[i]``, ``fields[i]``, ``texts[i]`` for message ``i``."""

    def __init__(self, raw: bytes):
        raw = bytes(raw)
        if raw[:4] != MAGIC or len(raw) < HEADER:
            raise ValueError("Not a CTD message file")
        self.raw = raw
        count = struct.unpack_from("<H", raw, 0x0E)[0]
        self.table = struct.unpack_from("<I", raw, 0x10)[0]
        if self.table + count * 8 > len(raw):
            raise ValueError("The message table runs past the end of the file")
        self.ids: List[int] = []
        self.fields: List[int] = []
        self.texts: List[str] = []
        for i in range(count):
            mid, field = struct.unpack_from("<II", raw, self.table + i * 8)
            offset = field & OFFSET_MASK
            end = offset
            while end + 2 <= len(raw) and raw[end:end + 2] != b"\0\0":
                end += 2
            if offset > len(raw):
                raise ValueError("A text offset is outside the file")
            self.ids.append(mid)
            self.fields.append(field)
            self.texts.append(raw[offset:end].decode("utf-16-le", "surrogatepass"))

    def build(self, new_texts: List[str]) -> bytes:
        """The file with the messages whose text differs from the read one written again."""
        if len(new_texts) != len(self.texts):
            raise ValueError("The message count changed")
        out = bytearray(self.raw)
        appended = {}
        for i, (old, new) in enumerate(zip(self.texts, new_texts)):
            if new == old:
                continue
            if new not in appended:
                if len(out) % 2:
                    out.append(0)
                appended[new] = len(out)
                out += new.encode("utf-16-le", "surrogatepass") + b"\0\0"
            offset = appended[new]
            if offset > OFFSET_MASK:
                raise ValueError("The message file would grow past 1 MiB")
            struct.pack_into("<I", out, self.table + i * 8 + 4, (self.fields[i] & ~OFFSET_MASK) | offset)
        return bytes(out)


def messages(raw: bytes) -> Tuple[List[int], List[str]]:
    ctd = Ctd(raw)
    return ctd.ids, ctd.texts
