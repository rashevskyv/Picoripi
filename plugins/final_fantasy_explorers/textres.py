"""Final Fantasy Explorers text files (``*.textres``, 3DS): a table of ``u32 id`` + a UTF-16LE string.

Little endian. The file starts with ``u32 count << 16 | 0x1000``, then ``count`` records ``u32 id`` (a hash of the
message name) and the string as UTF-16LE with a zero terminator, then 4 bytes (``ff ff 00 00``) that are kept.
Control characters in a string are single code units: ``0x01`` .. ``0x07`` switch colour or style (``0x05`` ends
it), ``0x07`` and ``0x0B``..``0x0E`` insert a name or a number the game supplies, ``0x10`` waits for a button
press, ``0x13`` is a coloured keyword; ``\\n`` is a line break. They show as ``{cNN}`` in the editor.

Found by reading the game's files (nothing public documents the format).
"""
from __future__ import annotations

import re
import struct
from typing import List, Tuple

TAG_RE = re.compile(r"\{c[0-9A-F]{2}\}")
_CTRL = re.compile("[\x00-\x09\x0b-\x1f]")
_EDITOR_TAG = re.compile(r"\{c([0-9A-Fa-f]{2})\}")
HEADER_FLAGS = 0x1000


def to_editor(text: str) -> str:
    return _CTRL.sub(lambda m: "{c%02X}" % ord(m.group()), text)


def from_editor(text: str) -> str:
    return _EDITOR_TAG.sub(lambda m: chr(int(m.group(1), 16)), text.replace("\r\n", "\n"))


class TextRes:
    """One parsed file: ``ids[i]`` and ``texts[i]`` per message, ``tail`` the bytes after the last record."""

    def __init__(self, raw: bytes):
        raw = bytes(raw)
        if len(raw) < 8:
            raise ValueError("Not a textres file")
        head = struct.unpack_from("<I", raw, 0)[0]
        count, flags = head >> 16, head & 0xFFFF
        if flags != HEADER_FLAGS:
            raise ValueError("Not a textres file (header)")
        self.ids: List[int] = []
        self.texts: List[str] = []
        pos = 4
        for _ in range(count):
            if pos + 6 > len(raw):
                raise ValueError("The record table runs past the end of the file")
            self.ids.append(struct.unpack_from("<I", raw, pos)[0])
            start = end = pos + 4
            while end + 2 <= len(raw) and raw[end:end + 2] != b"\0\0":
                end += 2
            if end + 2 > len(raw):
                raise ValueError("A string has no terminator")
            self.texts.append(raw[start:end].decode("utf-16-le", "surrogatepass"))
            pos = end + 2
        self.head = head
        self.tail = raw[pos:]
        self._raw = raw

    def build(self, texts: List[str]) -> bytes:
        """The file with these texts (same ids, order and tail)."""
        if len(texts) != len(self.ids):
            raise ValueError("The message count changed")
        if list(texts) == self.texts:
            return self._raw
        out = bytearray(struct.pack("<I", self.head))
        for mid, text in zip(self.ids, texts):
            out += struct.pack("<I", mid) + text.encode("utf-16-le", "surrogatepass") + b"\0\0"
        return bytes(out + self.tail)


def messages(raw: bytes) -> Tuple[List[int], List[str]]:
    parsed = TextRes(raw)
    return parsed.ids, parsed.texts
