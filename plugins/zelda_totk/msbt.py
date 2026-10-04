"""MSBT message files (Nintendo LMS "MsgStdBn"): read texts and labels, write new texts back.

A file is a 0x20-byte header and sections (``LBL1`` labels, ``ATR1``, ``TSY1``, ``TXT2`` texts, ...),
each padded with 0xAB to 16 bytes. Only ``TXT2`` is rebuilt; every other section is written back as read.
A text is UTF-16 with control tags: ``0x0E group type size params`` opens a tag, ``0x0F group type``
closes one. Tags travel as ``Tag`` / ``EndTag`` tokens; ``tags.py`` turns them into readable ``{tags}``.
"""
from __future__ import annotations

import struct
from dataclasses import dataclass
from typing import Dict, List, Union

MAGIC = b"MsgStdBn"
_SECTION_PAD = b"\xab"


@dataclass(frozen=True)
class Tag:
    """An opening control tag with its raw parameter bytes."""

    group: int
    type: int
    params: bytes = b""


@dataclass(frozen=True)
class EndTag:
    """A closing control tag (``0x0F``)."""

    group: int
    type: int


Token = Union[str, Tag, EndTag]


class Msbt:
    """One parsed MSBT file. ``messages[i]`` is the token list of TXT2 entry ``i``; ``labels[i]`` its label."""

    def __init__(self, raw: bytes):
        raw = bytes(raw)
        if raw[:8] != MAGIC:
            raise ValueError("Not an MSBT file")
        self.little = raw[8:10] == b"\xff\xfe"
        self.endian = "<" if self.little else ">"
        if raw[0x0C] != 1:
            raise ValueError(f"Only UTF-16 MSBT files are supported (encoding {raw[0x0C]})")
        self.header = raw[:0x20]
        self.sections: List[List] = []  # [magic, body]
        count = struct.unpack_from(self.endian + "H", raw, 0x0E)[0]
        position = 0x20
        for _ in range(count):
            magic = raw[position:position + 4]
            size = struct.unpack_from(self.endian + "I", raw, position + 4)[0]
            body = raw[position + 16:position + 16 + size]
            if len(body) != size:
                raise ValueError(f"Section {magic!r} runs past the end of the file")
            self.sections.append([magic, body])
            position += 16 + size
            position += -position % 16
        self.messages: List[List[Token]] = self._read_texts(self._section(b"TXT2"))
        self.labels: Dict[int, str] = self._read_labels(self._section(b"LBL1"))

    def _section(self, magic: bytes) -> bytes:
        for name, body in self.sections:
            if name == magic:
                return body
        return b""

    def _read_labels(self, body: bytes) -> Dict[int, str]:
        labels: Dict[int, str] = {}
        if not body:
            return labels
        e = self.endian
        slots = struct.unpack_from(e + "I", body, 0)[0]
        for slot in range(slots):
            count, offset = struct.unpack_from(e + "II", body, 4 + slot * 8)
            for _ in range(count):
                length = body[offset]
                name = body[offset + 1:offset + 1 + length].decode("utf-8", "replace")
                index = struct.unpack_from(e + "I", body, offset + 1 + length)[0]
                labels[index] = name
                offset += 1 + length + 4
        return labels

    def _read_texts(self, body: bytes) -> List[List[Token]]:
        if not body:
            return []
        e = self.endian
        count = struct.unpack_from(e + "I", body, 0)[0]
        offsets = list(struct.unpack_from(f"{e}{count}I", body, 4))
        messages = []
        for index, start in enumerate(offsets):
            end = offsets[index + 1] if index + 1 < count else len(body)
            messages.append(self._read_text(body, start, end))
        return messages

    def _read_text(self, body: bytes, position: int, end: int) -> List[Token]:
        e = self.endian
        codec = "utf-16-le" if self.little else "utf-16-be"
        tokens: List[Token] = []
        chars = bytearray()

        def flush():
            if chars:
                tokens.append(chars.decode(codec, "surrogatepass"))
                chars.clear()

        while position + 2 <= end:
            unit = struct.unpack_from(e + "H", body, position)[0]
            if unit == 0:
                break
            if unit == 0x0E:
                flush()
                group, kind, size = struct.unpack_from(e + "HHH", body, position + 2)
                tokens.append(Tag(group, kind, bytes(body[position + 8:position + 8 + size])))
                position += 8 + size
            elif unit == 0x0F:
                flush()
                group, kind = struct.unpack_from(e + "HH", body, position + 2)
                tokens.append(EndTag(group, kind))
                position += 6
            else:
                chars += body[position:position + 2]
                position += 2
        flush()
        return tokens

    def encode_text(self, tokens: List[Token]) -> bytes:
        """One TXT2 entry, with its terminating null."""
        e = self.endian
        codec = "utf-16-le" if self.little else "utf-16-be"
        out = bytearray()
        for token in tokens:
            if isinstance(token, str):
                out += token.encode(codec, "surrogatepass")
            elif isinstance(token, Tag):
                out += struct.pack(e + "HHHH", 0x0E, token.group, token.type, len(token.params)) + token.params
            else:
                out += struct.pack(e + "HHH", 0x0F, token.group, token.type)
        return bytes(out) + b"\x00\x00"

    def build(self, messages: List[List[Token]]) -> bytes:
        """The file with ``messages`` as its texts and every other section unchanged."""
        if len(messages) != len(self.messages):
            raise ValueError(f"The file has {len(self.messages)} messages, got {len(messages)}")
        e = self.endian
        texts = [self.encode_text(tokens) for tokens in messages]
        table = 4 + 4 * len(texts)
        offsets, position = [], table
        for text in texts:
            offsets.append(position)
            position += len(text)
        txt2 = struct.pack(f"{e}I{len(texts)}I", len(texts), *offsets) + b"".join(texts)

        out = bytearray(self.header)
        for magic, body in self.sections:
            if magic == b"TXT2":
                body = txt2
            out += magic + struct.pack(e + "I", len(body)) + b"\x00" * 8 + body
            out += _SECTION_PAD * (-len(out) % 16)
        struct.pack_into(e + "I", out, 0x12, len(out))
        return bytes(out)
