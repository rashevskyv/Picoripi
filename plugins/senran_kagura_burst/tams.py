"""``TAMS`` message files of Senran Kagura Burst (3DS): ``romfs/scenario/{hanzo,hebijo}/*.bin``.

Little endian: ``TAMS``, u16 version (0x200), u16 ``nrec`` (the script records), u32 ``nmsg`` (the messages), then a
table ``A`` of ``nmsg + 2`` u16 (the start of the records, the start of the text, the offset of every message), a
table ``B`` of ``nrec`` u16 (the offset of every script record) and the records themselves; a record refers to a
message by its number (``0x0D, 6, n`` shows message ``n``), never by an offset. The texts follow, UTF-16LE, each
ended by a NUL unit, one after another to the end of the file.

Only table ``A`` holds offsets of messages, so a text of any length is written by writing the strings again and
the offsets of ``A``: the records stay as they are. Offsets are u16, so no message may start after byte 65535.

Inside a text ``\\x07`` starts a control code: ``v`` + 5 digits (a voice line), ``b`` + 3 digits, ``s`` + 3 digits,
``c`` + 8 hex digits (text colour RGBA) and ``r`` (the colour back to normal). The editor shows them as
``{v02001}``, ``{b008}``, ``{s022}``, ``{cff0000ff}``, ``{r}``. The page and end markers are the characters
U+25BD and U+25A1 of the game's font; they stay plain characters.
"""
from __future__ import annotations

import re
import struct
from typing import List, Sequence

MAGIC = b"TAMS"
MAX_SIZE = 0x10000

_CODE = re.compile(r"\x07(v\d{5}|b\d{3}|s\d{3}|c[0-9a-f]{8}|r)")
_TAG = re.compile(r"\{(v\d{5}|b\d{3}|s\d{3}|c[0-9a-f]{8}|r)\}")
TAG_RE = _TAG


class FormatError(ValueError):
    pass


def is_tams(raw: bytes) -> bool:
    return bytes(raw[:4]) == MAGIC


def to_editor(text: str) -> str:
    return _CODE.sub(lambda m: "{" + m.group(1) + "}", text)


def from_editor(text: str) -> str:
    return _TAG.sub(lambda m: "\x07" + m.group(1), text)


class Tams:
    def __init__(self, raw: bytes):
        raw = bytes(raw)
        if not is_tams(raw) or len(raw) < 12:
            raise FormatError("not a TAMS message file")
        version, nrec, nmsg = struct.unpack_from("<HHI", raw, 4)
        table_end = 12 + 2 * (nmsg + 2) + 2 * nrec
        if version != 0x200 or table_end > len(raw):
            raise FormatError("unexpected TAMS header")
        offsets = struct.unpack_from(f"<{nmsg + 2}H", raw, 12)
        self.text_start = offsets[1]
        if offsets[0] < table_end or offsets[0] > self.text_start or (nmsg and offsets[2] != self.text_start):
            raise FormatError("unexpected TAMS tables")
        self.raw = raw
        self.head = raw[:12]
        self.prefix = raw[12 + 2 * (nmsg + 2):self.text_start]   # the table B and the records
        self.messages: List[str] = []
        end_of_previous = self.text_start
        for at in offsets[2:]:
            if at != end_of_previous:
                raise FormatError("messages are not back to back")
            end = at
            while raw[end:end + 2] != b"\0\0":
                if end + 2 > len(raw):
                    raise FormatError("a message has no end")
                end += 2
            self.messages.append(raw[at:end].decode("utf-16-le", "surrogatepass"))
            end_of_previous = end + 2
        if end_of_previous != len(raw):
            raise FormatError("data after the last message")

    def build(self, texts: Sequence[str]) -> bytes:
        if len(texts) != len(self.messages):
            raise FormatError(f"{len(texts)} messages for {len(self.messages)} entries")
        body = bytearray()
        offsets = []
        for text in texts:
            offsets.append(self.text_start + len(body))
            body += str(text).encode("utf-16-le", "surrogatepass") + b"\0\0"
        if offsets and offsets[-1] >= MAX_SIZE:
            raise FormatError(f"the last message would start at {offsets[-1]}; the game's u16 offsets stop at "
                              f"{MAX_SIZE - 1}: shorten the texts of this file")
        table_a = struct.unpack_from(f"<{len(self.messages) + 2}H", self.raw, 12)[:2]
        return (self.head + struct.pack(f"<{len(self.messages) + 2}H", *table_a, *offsets) + self.prefix + bytes(body))
