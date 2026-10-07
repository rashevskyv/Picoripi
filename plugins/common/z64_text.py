"""Zelda 64 message text (OoT, MM): control codes as ``{tags}``, the message table, rebuilding the text file.

A game supplies a ``TextFormat``: its control codes, newline and end bytes, the
text-box breaks after which the editor shows a line break, the message header
size and the font's extra characters.  Everything else is shared.
"""
from __future__ import annotations

import re
import struct
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple

TABLE_END_ID = 0xFFFF
_TAG_RE = re.compile(r"\{([^{}]+)\}")


@dataclass(frozen=True)
class Control:
    name: str                                   # tag text: {name} or {name:value}
    args: int = 0                               # argument bytes after the code
    values: Dict[int, str] = field(default_factory=dict)   # symbolic names of argument values


@dataclass
class TextFormat:
    controls: Dict[int, Control]
    newline: int
    end: int
    box_breaks: frozenset = frozenset()         # codes after which a new text box starts
    header_size: int = 0                        # bytes before the text of every message (MM: 11)
    charmap: Dict[int, str] = field(default_factory=dict)   # font characters beyond ASCII

    def __post_init__(self):
        self.by_name = {c.name: (code, c) for code, c in self.controls.items()}
        self.by_char = {ch: code for code, ch in self.charmap.items()}

    # -- body <-> editor text ---------------------------------------------------------

    def decode(self, body: bytes) -> str:
        """Body bytes (no header, no end byte) -> editor text."""
        out: List[str] = []
        i = 0
        while i < len(body):
            c = body[i]
            control = self.controls.get(c)
            if c == self.newline:
                out.append("\n")
                i += 1
            elif control is not None:
                if control.args:
                    value = int.from_bytes(body[i + 1:i + 1 + control.args], "big")
                    out.append(f"{{{control.name}:{control.values.get(value, value)}}}")
                else:
                    out.append(f"{{{control.name}}}")
                if c in self.box_breaks:
                    out.append("\n")
                i += 1 + control.args
            elif c in self.charmap:
                out.append(self.charmap[c])
                i += 1
            elif 0x20 <= c < 0x7F and c not in (0x7B, 0x7D):
                out.append(chr(c))
                i += 1
            else:
                out.append(f"{{x:{c:02X}}}")
                i += 1
        return "".join(out)

    def encode(self, text: str, extra_chars: Optional[Dict[str, int]] = None) -> bytes:
        """Editor text -> body bytes.  ``extra_chars`` maps translated letters to font slots."""
        out = bytearray()
        pos = 0
        while pos < len(text):
            ch = text[pos]
            if ch == "{":
                m = _TAG_RE.match(text, pos)
                if not m:
                    raise ValueError(f"Malformed tag at {pos}: {text[pos:pos + 20]!r}")
                code = self._encode_tag(m.group(1), out)
                pos = m.end()
                if code in self.box_breaks and text.startswith("\n", pos):
                    pos += 1
                continue
            if ch == "\n":
                out.append(self.newline)
            elif extra_chars and ch in extra_chars:
                out.append(extra_chars[ch])
            elif ch in self.by_char:
                out.append(self.by_char[ch])
            elif 0x20 <= ord(ch) < 0x7F:
                out.append(ord(ch))
            else:
                raise ValueError(f"No font slot for {ch!r}")
            pos += 1
        return bytes(out)

    def _encode_tag(self, inner: str, out: bytearray) -> Optional[int]:
        if inner.lower().startswith("x:") and len(inner) == 4:
            out.append(int(inner[2:], 16))
            return None
        if inner in self.by_name and not self.by_name[inner][1].args:
            code = self.by_name[inner][0]
            out.append(code)
            return code
        name, _, value = inner.rpartition(":")
        if name not in self.by_name or not self.by_name[name][1].args:
            raise ValueError(f"Unknown tag {{{inner}}}")
        code, control = self.by_name[name]
        by_value = {v: k for k, v in control.values.items()}
        number = by_value[value] if value in by_value else int(value)
        out.append(code)
        out += number.to_bytes(control.args, "big")
        return code

    def split(self, raw: bytes) -> Tuple[bytes, bytes, bytes]:
        """(header, body, rest) of one stored message: the body stops at the end byte."""
        i = self.header_size
        while i < len(raw) and raw[i] != self.end:
            control = self.controls.get(raw[i])
            i += 1 + (control.args if control else 0)
        return raw[:self.header_size], raw[self.header_size:i], raw[i:]


@dataclass
class Message:
    message_id: int
    header: bytes
    body: bytes
    info: int = 0          # the table entry's byte 2 (OoT: textbox type and position)


def read_table(code: bytes, table_offset: int) -> List[Tuple[int, int, int]]:
    """(id, info byte, offset into the text file) of every table entry, the 0xFFFF terminator included."""
    entries = []
    offset = table_offset
    while True:
        message_id, info, _pad, address = struct.unpack_from(">HBBI", code, offset)
        entries.append((message_id, info, address & 0xFFFFFF))
        offset += 8
        if message_id == TABLE_END_ID:
            return entries


def read_messages(fmt: TextFormat, code: bytes, table_offset: int, data: bytes) -> List[Message]:
    """Every message in table order."""
    entries = read_table(code, table_offset)
    messages = []
    for (message_id, info, start), (next_id, _info, next_start) in zip(entries, entries[1:]):
        end = next_start if next_id != TABLE_END_ID else len(data)
        header, body, _rest = fmt.split(data[start:end])
        messages.append(Message(message_id, header, body, info))
    return messages


def build_messages(fmt: TextFormat, messages: List[Message], code: bytes, table_offset: int,
                   segment: int) -> Tuple[bytes, bytes]:
    """(new text file, new code): messages packed 4-byte aligned, the table rewritten in place."""
    data = bytearray()
    new_code = bytearray(code)
    offset = table_offset
    for message in messages:
        message_id, info, pad, address = struct.unpack_from(">HBBI", code, offset)
        if message_id != message.message_id:
            raise ValueError(f"Message order changed at table entry {(offset - table_offset) // 8}")
        # A table keeps its own segment (MM: messages 0x08, credits 0x07); ``segment`` fills an empty one.
        struct.pack_into(">HBBI", new_code, offset, message_id, info, pad,
                         ((address >> 24 or segment) << 24) | len(data))
        data += message.header + message.body + bytes([fmt.end])
        data += b"\0" * (-len(data) % 4)
        offset += 8
    return bytes(data), bytes(new_code)
