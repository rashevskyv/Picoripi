"""MSBT message files (Nintendo LMS "MsgStdBn"): read texts and labels, write new texts back.

A file is a 0x20-byte header and sections (``LBL1`` labels, ``ATR1``, ``TSY1``, ``TXT2`` texts, ...),
each padded with 0xAB to 16 bytes. Only ``TXT2`` is rebuilt; every other section is written back as read.
A text is UTF-16 (or UTF-8: encoding 0, Animal Crossing's name tables) with control tags: ``0x0E group type
size params`` opens a tag, ``0x0F group type`` closes one; the control code is one code unit, its fields are u16. Tags travel as ``Tag`` / ``EndTag`` tokens; ``tags.py`` turns them into readable ``{tags}``.
"""
from __future__ import annotations

import struct
from dataclasses import dataclass
from typing import Dict, List, Sequence, Union

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
        if raw[0x0C] not in (0, 1):
            raise ValueError(f"Only UTF-8 and UTF-16 MSBT files are supported (encoding {raw[0x0C]})")
        self.utf8 = raw[0x0C] == 0
        self.byte_codec = "utf-8"          # encoding 0; Animal Crossing's spoken-name tables are Latin-1
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
        try:
            self.messages: List[List[Token]] = self._read_texts(self._section(b"TXT2"))
        except UnicodeDecodeError:
            if not self.utf8:
                raise
            self.byte_codec = "latin-1"
            self.messages = self._read_texts(self._section(b"TXT2"))
        self.labels: Dict[int, str] = self._read_labels(self._section(b"LBL1"))

    def section(self, magic: bytes) -> bytes:
        """The body of a section as read (``ATR1`` attributes...); empty when the file has none."""
        return self._section(magic)

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

    def _next_control(self, body: bytes, position: int, end: int) -> int:
        """Offset of the next 0x00 / 0x0E / 0x0F code unit from ``position`` on (``end`` when none).

        Found with ``bytes.find`` (a reference load parses every language, ~48,000 texts each); a hit at
        an odd distance lies across two code units and is skipped.
        """
        best = end
        if self.utf8:
            units = (b"\x00", b"\x0e", b"\x0f")
        else:
            units = (b"\x00\x00", b"\x0e\x00", b"\x0f\x00") if self.little else (b"\x00\x00", b"\x00\x0e", b"\x00\x0f")
        for unit in units:
            at = body.find(unit, position, best)
            while at != -1 and len(unit) == 2 and (at - position) % 2:
                at = body.find(unit, at + 1, best)
            if at != -1:
                best = at
        return best

    def _codec(self) -> str:
        if getattr(self, "utf8", False):
            return getattr(self, "byte_codec", "utf-8")
        return "utf-16-le" if self.little else "utf-16-be"

    def _read_text(self, body: bytes, position: int, end: int) -> List[Token]:
        e = self.endian
        codec = self._codec()
        unit_size = 1 if self.utf8 else 2
        tokens: List[Token] = []
        end -= (end - position) % unit_size
        while position < end:
            control = self._next_control(body, position, end)
            if control > position:
                tokens.append(body[position:control].decode(codec, "surrogatepass"))
                position = control
            if position >= end:
                break
            unit = body[position] if unit_size == 1 else struct.unpack_from(e + "H", body, position)[0]
            if unit == 0:
                break
            if unit == 0x0E:
                group, kind, size = struct.unpack_from(e + "HHH", body, position + unit_size)
                start = position + unit_size + 6
                tokens.append(Tag(group, kind, bytes(body[start:start + size])))
                position = start + size
            else:
                group, kind = struct.unpack_from(e + "HH", body, position + unit_size)
                tokens.append(EndTag(group, kind))
                position += unit_size + 4
        return tokens

    def encode_text(self, tokens: List[Token]) -> bytes:
        """One TXT2 entry, with its terminating null."""
        e = self.endian
        codec = Msbt._codec(self)
        one_byte = codec in ("utf-8", "latin-1")
        control = "B" if one_byte else "H"
        out = bytearray()
        for token in tokens:
            if isinstance(token, str):
                out += token.encode(codec, "surrogatepass")
            elif isinstance(token, Tag):
                out += struct.pack(e + control + "HHH", 0x0E, token.group, token.type, len(token.params)) + token.params
            else:
                out += struct.pack(e + control + "HH", 0x0F, token.group, token.type)
        return bytes(out) + (b"\x00" if one_byte else b"\x00\x00")

    def build(self, messages: List[List[Token]]) -> bytes:
        """The file with ``messages`` as its texts and every other section unchanged."""
        if len(messages) != len(self.messages):
            raise ValueError(f"The file has {len(self.messages)} messages, got {len(messages)}")
        return self._pack(self.sections, messages)

    def subset(self, indices: Sequence[int], messages: List[List[Token]]) -> bytes:
        """A file with only the messages at ``indices`` (in that order), with ``messages`` as their texts.

        Labels, attributes (ATR1) and the per-message style table (TSY1) follow the kept messages. The labels
        go into one hash slot: the file reads back in the editor; the game's own files are never subset.
        """
        if len(messages) != len(indices):
            raise ValueError("one text per kept message")
        e = self.endian
        new_index = {old: new for new, old in enumerate(indices)}
        entries = bytearray()
        label_count = 0
        for old in indices:
            name = self.labels.get(old)
            if name is None:
                continue
            raw = name.encode("utf-8")
            if len(raw) > 255:
                raise ValueError(f"label too long: {name[:20]}")
            entries += bytes([len(raw)]) + raw + struct.pack(e + "I", new_index[old])
            label_count += 1
        lbl1 = struct.pack(e + "I", 1) + struct.pack(e + "II", label_count, 12) + bytes(entries)
        atr1 = self._section(b"ATR1")
        if atr1:
            count, size = struct.unpack_from(e + "II", atr1, 0)
            rows = b"".join(atr1[8 + old * size:8 + (old + 1) * size] for old in indices)
            atr1 = struct.pack(e + "II", len(indices), size) + rows + atr1[8 + count * size:]
        tsy1 = b"".join(self._section(b"TSY1")[4 * old:4 * old + 4] for old in indices)
        sections = []
        for magic, body in self.sections:
            if magic == b"LBL1":
                body = lbl1
            elif magic == b"ATR1":
                body = atr1
            elif magic == b"TSY1":
                body = tsy1
            sections.append([magic, body])
        return self._pack(sections, messages)

    def _pack(self, sections: List[List], messages: List[List[Token]]) -> bytes:
        """The file from its sections, with TXT2 rebuilt from ``messages``."""
        e = self.endian
        texts = [self.encode_text(tokens) for tokens in messages]
        table = 4 + 4 * len(texts)
        offsets, position = [], table
        for text in texts:
            offsets.append(position)
            position += len(text)
        txt2 = struct.pack(f"{e}I{len(texts)}I", len(texts), *offsets) + b"".join(texts)

        out = bytearray(self.header)
        for magic, body in sections:
            if magic == b"TXT2":
                body = txt2
            out += magic + struct.pack(e + "I", len(body)) + b"\x00" * 8 + body
            out += _SECTION_PAD * (-len(out) % 16)
        struct.pack_into(e + "I", out, 0x12, len(out))
        return bytes(out)
