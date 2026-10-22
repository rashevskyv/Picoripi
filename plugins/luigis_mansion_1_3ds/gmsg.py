"""The GMSG message table of Luigi's Mansion (3DS, 2018): ``romfs/Region_US/<Language>/main.gmsg`` (2182 messages).

Grezzo GMSG v3 with a header variant: ``GMSG``, u32 version (3), u32 (2), u32 message count at 0x0C, u32 message table
offset at 0x10, u32 (6), then the rest of the header (kept as it is). The table holds 16 bytes per message (u32 id,
u32 flags, u32 text offset, u32 text length); the texts follow the table, each at a 4-byte boundary, and the file may
end with padding, which is kept.

A text is UTF-8. ``0x7F`` starts a control code: a 0 pad byte when the code would sit at an odd offset (from the
message start), a u16 code (little endian), then its argument: none (``NO_ARGS``) or the bytes in ``ARGS`` (4 when the
code is not listed), aligned to 4 when the size is a multiple of 4. Code 0 ends the text. The editor shows code 1 as a
line break, ``{clear}`` (2), ``{wait}`` (3), ``{style:hex}`` (0x19) and the others as ``{cNN:hex}``. A message the
grammar does not fit, or that would not be written back byte for byte, is one ``{raw:hex}`` tag, so nothing is lost.
"""
from __future__ import annotations

import re
import struct
from typing import List, Optional

from core.i18n import tr

RECORD = struct.Struct("<4I")
HEADER = struct.Struct("<4sIIII")
ESC = 0x7F
NO_ARGS = {0x01, 0x02, 0x03, 0x0B, 0x0C, 0x0D, 0x17, 0x18}
ARGS = {0x11: 2, 0x15: 4, 0x19: 16}   # argument bytes found in the file; any other code takes DEFAULT_ARGS
DEFAULT_ARGS = 4
NAMES = {0x02: "clear", 0x03: "wait", 0x19: "style"}
BY_NAME = {name: code for code, name in NAMES.items()}
TAG_RE = re.compile(r"\{(?:c[0-9a-f]{2}|clear|wait|style|raw)(?::[^{}]*)?\}")
_TAG_PARTS = re.compile(r"\{(c[0-9a-f]{2}|clear|wait|style|raw)(?::([^{}]*))?\}")


class FormatError(ValueError):
    pass


def _size(code: int) -> int:
    return ARGS.get(code, DEFAULT_ARGS)


def _decode(raw: bytes) -> str:
    out: List[str] = []
    i, n, text_start = 0, len(raw), 0
    while i < n:
        if raw[i] != ESC:
            if raw[i] < 0x20:
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
            out.append("{" + NAMES.get(code, f"c{code:02x}") + "}")
        else:
            size = _size(code)
            if size % 4 == 0:
                while i % 4:
                    if raw[i] != 0:
                        raise ValueError("pad")
                    i += 1
            if i + size > n:
                raise ValueError("arguments run past the message")
            out.append("{" + NAMES.get(code, f"c{code:02x}") + ":" + raw[i:i + size].hex() + "}")
            i += size
        text_start = i
    raise ValueError("no end code")


def decode(raw: bytes) -> str:
    """Message bytes -> editor text; ``{raw:hex}`` when the grammar does not fit or the bytes would not round-trip."""
    try:
        text = _decode(raw)
        if encode(text) == raw:
            return text
    except (ValueError, IndexError, struct.error):
        pass
    return "{raw:" + raw.hex() + "}"


def encode(text: str) -> bytes:
    """Editor text -> message bytes (control codes with their pad bytes, end code)."""
    out = bytearray()
    pos = 0

    def command(code: int, args: Optional[bytes] = None) -> None:
        out.append(ESC)
        if len(out) % 2:
            out.append(0)
        out.extend(struct.pack("<H", code))
        if args is not None:
            if len(args) % 4 == 0:
                while len(out) % 4:
                    out.append(0)
            out.extend(args)

    while pos < len(text):
        match = TAG_RE.match(text, pos)
        if match is None:
            nxt = text.find("{", pos + 1)
            chunk = text[pos:] if nxt < 0 else text[pos:nxt]
            for index, part in enumerate(chunk.split("\n")):
                if index:
                    command(0x01)
                out.extend(part.encode("utf-8"))
            pos += len(chunk)
            continue
        pos = match.end()
        name, arg = _TAG_PARTS.fullmatch(match.group()).groups()
        if name == "raw":
            return bytes.fromhex(arg or "")
        code = BY_NAME[name] if name in BY_NAME else int(name[1:], 16)
        if code in NO_ARGS:
            command(code)
        else:
            command(code, bytes.fromhex(arg) if arg else bytes(_size(code)))
    command(0x00)
    return bytes(out)


class Table:
    """One ``main.gmsg``: ``texts()`` is the editor view, ``ids()`` the message ids, ``build(texts)`` the new file."""

    def __init__(self, data: bytes):
        data = bytes(data)
        if len(data) < HEADER.size or data[:4] != b"GMSG":
            raise FormatError(tr("Not a GMSG message file"))
        _magic, version, _variant, count, table = HEADER.unpack_from(data)
        if version != 3 or table + count * RECORD.size > len(data):
            raise FormatError(tr("GMSG version {0} with {1} messages is not supported", version, count))
        self.data = data
        self.table = table
        self._ids: List[int] = []
        self._flags: List[int] = []
        self._messages: List[bytes] = []
        ends = [table + count * RECORD.size]
        for index in range(count):
            mid, flags, off, size = RECORD.unpack_from(data, table + index * RECORD.size)
            if off + size > len(data):
                raise FormatError(tr("GMSG message {0} runs past the file end", index))
            self._ids.append(mid)
            self._flags.append(flags)
            self._messages.append(data[off:off + size])
            ends.append(off + size)
        self._tail = data[max(ends):]   # padding after the last text, kept as it is

    def texts(self) -> List[str]:
        return [decode(m) if m else "" for m in self._messages]

    def ids(self) -> List[str]:
        return [str(mid) for mid in self._ids]

    def build(self, texts) -> bytes:
        """The file with ``texts`` (one per message); an unchanged text keeps its original bytes."""
        texts = list(texts)
        if len(texts) != len(self._messages):
            raise FormatError(tr("{0} texts for {1} messages", len(texts), len(self._messages)))
        head = bytearray(self.data[:self.table])
        records = bytearray()
        body = bytearray()
        start = self.table + len(self._messages) * RECORD.size
        for index, text in enumerate(texts):
            old = self._messages[index]
            if text == (decode(old) if old else ""):
                raw = old
            else:
                raw = encode(str(text)) if str(text) else b""
            if raw:
                body += b"\0" * (-(start + len(body)) % 4)
                records += RECORD.pack(self._ids[index], self._flags[index], start + len(body), len(raw))
                body += raw
            else:   # an empty message keeps the offset it had
                records += RECORD.pack(self._ids[index], self._flags[index],
                                       RECORD.unpack_from(self.data, self.table + index * RECORD.size)[2], 0)
        return bytes(head + records + body + self._tail)
