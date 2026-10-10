"""Grezzo GMSG v3 message files of Ever Oasis (``data/Region_EU/<Language>/main.gmsg``) and their editor text.

Layout (little endian)::

    0x00 "GMSG"  0x04 u32 version (3)  0x08 u32 0x10  0x0C u32 message count  0x10 u32 message table offset
    0x14 u32 record size (16)  0x18 u32 colour table offset  0x1C u32 style row count  0x20 u32 style rows offset
    colours (16 RGBA) and style rows (28 bytes: text id hash, flag, font scales ...) -- kept as they are
    message table: 16 bytes per message: u32 id, u32 flags, u32 text offset, u32 text length
    texts: in table order, every one at a 4-byte boundary

A text is UTF-8. ``0x7F`` starts a control code: a 0 pad byte when the next byte would sit at an odd offset (from
the message start), a u16 code, then its argument: nothing, 4 bytes (aligned to 4 with zero bytes), or strings
(``0x15`` / ``0x16`` one string, ``0x14`` four bytes and three strings; each ends with a 0 byte and is padded to an
even offset). Code 0 ends the text. The editor shows code 1 as a line break, a few codes by name (``{clear}``,
``{wait}``, ``{style:...}``) and the others as ``{cNN}`` / ``{cNN:hex}`` / ``{cNN:text}`` / ``{c14:hex|a|b|c}``. A
message that does not follow this grammar (or would not be written back byte for byte) is shown as one
``{raw:hex}`` tag, so nothing is ever lost.
"""
from __future__ import annotations

import re
import struct
from typing import List, Optional, Tuple

HEADER = struct.Struct("<4s5I")
RECORD = struct.Struct("<4I")
ESC = 0x7F
NO_ARGS = {0x01, 0x02, 0x03, 0x0B, 0x0C, 0x0D, 0x17, 0x18}
STRING_CODES = {0x15, 0x16}
PLURAL = 0x14
NAMES = {0x02: "clear", 0x03: "wait", 0x19: "style"}
BY_NAME = {name: code for code, name in NAMES.items()}
TAG_RE = re.compile(r"\{(?:c[0-9a-f]{2}|clear|wait|style|raw)(?::[^{}]*)?\}")
_TAG_PARTS = re.compile(r"\{(c[0-9a-f]{2}|clear|wait|style|raw)(?::([^{}]*))?\}")


class FormatError(ValueError):
    """Not a GMSG v3 file."""


def _aligned(out: bytearray, to: int) -> None:
    while len(out) % to:
        out.append(0)


def _string(out: bytearray, text: str) -> None:
    out += text.encode("utf-8") + b"\0"
    _aligned(out, 2)


def encode(text: str) -> bytes:
    """Editor text -> message bytes (control codes with their pad bytes, end code)."""
    out = bytearray()
    pos = 0

    def command(code: int, args: Optional[bytes] = None, strings: Tuple[str, ...] = ()) -> None:
        out.append(ESC)
        _aligned(out, 2)
        out.extend(struct.pack("<H", code))
        if args is not None:
            _aligned(out, 4)
            out.extend(args)
        for s in strings:
            _string(out, s)

    while pos < len(text):
        match = TAG_RE.match(text, pos)
        if match is None:
            nxt = text.find("{", pos + 1)
            chunk = text[pos:] if nxt < 0 else text[pos:nxt]
            # a "{" that is not a tag is plain text; line breaks are code 1
            for i, part in enumerate(chunk.split("\n")):
                if i:
                    command(0x01)
                out.extend(part.encode("utf-8"))
            pos += len(chunk)
            continue
        pos = match.end()
        name, arg = _TAG_PARTS.fullmatch(match.group()).groups()
        if name == "raw":
            return bytes.fromhex(arg or "")
        code = BY_NAME[name] if name in BY_NAME else int(name[1:], 16)
        if code == PLURAL:
            head, *words = (arg or "").split("|")
            command(code, bytes.fromhex(head), tuple(words))
        elif code in STRING_CODES:
            command(code, None, (arg or "",))
        elif code in NO_ARGS:
            command(code)
        else:
            command(code, bytes.fromhex(arg) if arg else bytes(4))
    command(0x00)
    return bytes(out)


def decode(raw: bytes) -> str:
    """Message bytes -> editor text; ``{raw:hex}`` when the grammar does not fit or the bytes would not round-trip."""
    try:
        text = _decode(raw)
        if encode(text) == raw:
            return text
    except (ValueError, IndexError, struct.error):
        pass
    return "{raw:" + raw.hex() + "}"


def _decode(raw: bytes) -> str:
    out: List[str] = []
    i, n = 0, len(raw)
    text_start = 0
    while i < n:
        b = raw[i]
        if b != ESC:
            if b < 0x20:
                raise ValueError("control byte in text")
            i += 1
            continue
        out.append(raw[text_start:i].decode("utf-8"))
        i += 1
        if i % 2:
            if raw[i] != 0:
                raise ValueError("pad")
            i += 1
        code = struct.unpack_from("<H", raw, i)[0]
        i += 2
        if code == 0:
            if i != n:
                raise ValueError("data after the end code")
            return "".join(out)
        if code == 0x01:
            out.append("\n")
        elif code in NO_ARGS:
            out.append("{" + (NAMES.get(code) or f"c{code:02x}") + "}")
        elif code in STRING_CODES or code == PLURAL:
            args = ""
            if code == PLURAL:
                while i % 4:
                    if raw[i] != 0:
                        raise ValueError("pad")
                    i += 1
                args = raw[i:i + 4].hex()
                i += 4
            words = []
            for _ in range(3 if code == PLURAL else 1):
                end = raw.index(b"\0", i)
                words.append(raw[i:end].decode("utf-8"))
                i = end + 1
                if i % 2:
                    if raw[i] != 0:
                        raise ValueError("pad")
                    i += 1
            out.append("{" + f"c{code:02x}:" + "|".join(([args] if code == PLURAL else []) + words) + "}")
        else:
            while i % 4:
                if raw[i] != 0:
                    raise ValueError("pad")
                i += 1
            out.append("{" + (NAMES.get(code) or f"c{code:02x}") + ":" + raw[i:i + 4].hex() + "}")
            i += 4
        text_start = i
    raise ValueError("no end code")


class Gmsg:
    """A parsed ``main.gmsg``: ``ids``, ``flags`` and the raw ``messages``; ``texts()`` is the editor view."""

    def __init__(self, data: bytes):
        data = bytes(data)
        if len(data) < HEADER.size or data[:4] != b"GMSG":
            raise FormatError("Not a GMSG message file")
        _magic, version, _hsize, count, table, rec_size = HEADER.unpack_from(data)
        if version != 3 or rec_size != RECORD.size or table + count * RECORD.size > len(data):
            raise FormatError(f"GMSG version {version} with {count} messages is not supported")
        self.data = data
        self.table = table
        self.ids: List[int] = []
        self.flags: List[int] = []
        self.messages: List[bytes] = []
        for index in range(count):
            mid, flags, off, size = RECORD.unpack_from(data, table + index * RECORD.size)
            if off + size > len(data):
                raise FormatError(f"GMSG message {index} runs past the file end")
            self.ids.append(mid)
            self.flags.append(flags)
            self.messages.append(data[off:off + size])

    def texts(self) -> List[str]:
        return [decode(m) if m else "" for m in self.messages]

    def build(self, texts: List[str]) -> bytes:
        """The file with ``texts`` (editor text, one per message); an unchanged text keeps its original bytes."""
        if len(texts) != len(self.messages):
            raise FormatError(f"{len(texts)} texts for {len(self.messages)} messages")
        head = bytearray(self.data[:self.table])
        table = bytearray()
        body = bytearray()
        start = self.table + len(self.messages) * RECORD.size
        for index, text in enumerate(texts):
            old = self.messages[index]
            if text == (decode(old) if old else ""):
                raw = old
            else:
                raw = encode(str(text)) if str(text) else b""
            if raw:
                _aligned(body, 4)
                table += RECORD.pack(self.ids[index], self.flags[index], start + len(body), len(raw))
                body += raw
            else:   # an empty message keeps the offset it had
                table += RECORD.pack(self.ids[index], self.flags[index], self._empty_offset(index), 0)
        return bytes(head + table + body)

    def _empty_offset(self, index: int) -> int:
        """An empty message keeps the offset it had."""
        return RECORD.unpack_from(self.data, self.table + index * RECORD.size)[2]
