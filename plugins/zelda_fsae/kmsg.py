"""KMSG message files of Four Swords Anniversary Edition (``eu.kmsg``, ``all.kmsg`` in the DSiWare NitroFS).

Layout (little endian)::

    0x00 "KMSG"  0x04 u32 version (1)  0x08 u32 message count  0x0C u32 0
    0x10 per message: u32 id, then 10 x (u32 offset, u32 size) -- one text per language slot (84 bytes)
    texts: 4-byte aligned, zero padded; a size of 0 means the language is absent

Language slots: 0 Japanese, 1 English (US), 2 English (EU), 3 German, 4 French (EU), 5 French (US),
6 Spanish (EU), 7 Spanish (US), 8 Italian, 9 unused. ``all.kmsg`` has slots 0-8, ``eu.kmsg`` (the file the
European game reads) slots 2, 3, 4, 6 and 8.

A text is UTF-8 (the Japanese slot UTF-16) with control codes: byte ``0x7F``, a zero byte when the next
byte is at an odd offset (the code is read as an aligned u16), the u16 code and its u16 arguments; code 0
ends the text. The argument count of each code is ``ARGS``.
"""
from __future__ import annotations

import struct
from typing import Dict, List, Optional, Sequence, Tuple, Union

SLOTS = 10
EN_EU = 2
LANGUAGES = ("Japanese (JA)", "English (US)", "English (EU)", "German (DE)", "French (EU)", "French (US)",
             "Spanish (EU)", "Spanish (US)", "Italian (IT)", "")
# code -> number of u16 arguments (every code of the Western slots; 0x0D occurs once, in a Spanish text)
ARGS = {0: 0, 1: 0, 2: 1, 3: 1, 4: 0, 5: 1, 6: 0, 7: 1, 8: 1, 9: 1, 10: 1, 11: 1, 12: 1, 13: 3, 14: 0, 17: 1}
_ROW = struct.Struct("<I20I")

Token = Union[str, Tuple[int, ...]]


class FormatError(ValueError):
    """Not a KMSG file, or a text with a code this module does not know."""


class Kmsg:
    """Message ids and the raw text of every language slot."""

    def __init__(self, data: bytes):
        data = bytes(data)
        if len(data) < 16 or data[:4] != b"KMSG":
            raise FormatError("Not a KMSG file")
        version, count = struct.unpack_from("<II", data, 4)
        if version != 1 or 16 + count * _ROW.size > len(data):
            raise FormatError(f"KMSG version {version} with {count} messages is not supported")
        self.ids: List[int] = []
        self.texts: List[List[Optional[bytes]]] = []
        for index in range(count):
            row = _ROW.unpack_from(data, 16 + index * _ROW.size)
            texts: List[Optional[bytes]] = []
            for slot in range(SLOTS):
                offset, size = row[1 + 2 * slot], row[2 + 2 * slot]
                if size and offset + size > len(data):
                    raise FormatError(f"KMSG message {row[0]} slot {slot} runs past the file end")
                texts.append(data[offset:offset + size] if size else None)
            self.ids.append(row[0])
            self.texts.append(texts)

    def build(self, share: bool = True) -> bytes:
        """The table, then the texts message by message, slot by slot, each 4-byte aligned.

        ``share``: a text met again (the credits in every language) points at the first copy, as the
        Russian build does to keep ``eu.kmsg`` within its original size; without it the layout is that of
        the game's own ``all.kmsg`` (byte for byte).
        """
        at = 16 + len(self.ids) * _ROW.size
        table, body = bytearray(), bytearray()
        placed: Dict[bytes, int] = {}
        for message_id, texts in zip(self.ids, self.texts):
            row = [message_id]
            for text in texts:
                if not text:
                    row += [0, 0]
                    continue
                if not share or text not in placed:
                    placed[text] = at + len(body)
                    body += text + bytes(-len(text) % 4)
                row += [placed[text], len(text)]
            table += _ROW.pack(*row)
        return struct.pack("<4sIII", b"KMSG", 1, len(self.ids), 0) + bytes(table) + bytes(body)


def tokens(raw: bytes) -> List[Token]:
    """Text runs (str) and control codes (tuples ``(code, *arguments)``) of one UTF-8 text, up to code 0."""
    out: List[Token] = []
    text = bytearray()
    at = 0
    while at < len(raw):
        if raw[at] != 0x7F:
            text.append(raw[at])
            at += 1
            continue
        if text:
            out.append(_decode(text))
            text = bytearray()
        at += 1 + (at + 1) % 2
        if at + 2 > len(raw):
            raise FormatError("KMSG text ends inside a control code")
        code = struct.unpack_from("<H", raw, at)[0]
        if code not in ARGS:
            raise FormatError(f"Unknown KMSG control code 0x{code:02X}")
        arguments = struct.unpack_from(f"<{ARGS[code]}H", raw, at + 2)
        at += 2 + 2 * ARGS[code]
        out.append((code, *arguments))
        if code == 0:
            return out
    if text:
        out.append(_decode(text))
    return out


def _decode(text: bytearray) -> str:
    try:
        return text.decode("utf-8")
    except UnicodeDecodeError as error:
        raise FormatError(f"KMSG text is not UTF-8: {error}") from None


def encode(parts: Sequence[Token]) -> bytes:
    """The bytes of a text (the inverse of ``tokens``); the codes are aligned as the game reads them."""
    out = bytearray()
    for part in parts:
        if isinstance(part, str):
            out += part.encode("utf-8")
            continue
        code, *arguments = part
        if ARGS.get(code) != len(arguments):
            raise FormatError(f"KMSG code {code} takes {ARGS.get(code)} arguments, not {len(arguments)}")
        out.append(0x7F)
        if len(out) % 2:
            out.append(0)
        out += struct.pack(f"<{1 + len(arguments)}H", code, *arguments)
    return bytes(out)


def slot_texts(kmsg: Kmsg, slot: int) -> Dict[int, bytes]:
    """``{message id: raw text}`` of one language slot."""
    return {message_id: texts[slot] for message_id, texts in zip(kmsg.ids, kmsg.texts) if texts[slot]}
