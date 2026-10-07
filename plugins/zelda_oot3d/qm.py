"""Grezzo QM message files of Ocarina of Time 3D (``message/eu/eu.qm``) and their text <-> editor tags.

Layout (little endian)::

    0x00 "QM\\0\\0"  0x04 u32 version (4)  0x08 u32 message count  0x0C u32 0
    0x10 per message, 0x60 bytes: u32 id, u32 0, u32 box type, u32 box position, 16 x 00,
         8 x (u32 offset, u32 length) -- one text per language slot; length 0 = no text
    texts: message by message, slot by slot, 4-byte aligned; a length includes the 7F 00 end code

Slots of the European file: 0 English, 1 German, 2 French, 4 Spanish, 6 Italian (3, 5, 7 empty).
A text is UTF-8; ``0x7F`` starts a control code: one code byte and a fixed number of argument bytes
(``CODES``). The codes follow N64 Ocarina of Time, so the editor shows them with the names the
N64 plugin uses: ``{color:red}``, ``{box-break}``, ``{textid:0x0205}``... A text-box break is followed
by a line break in the editor; ``7F 1C`` is a line break; the end code is left out (saving adds it).
"""
from __future__ import annotations

import re
import struct
from typing import Dict, List, Optional, Tuple

SLOTS = 8
ENGLISH = 0
LANGUAGES = ("English (EU)", "German (DE)", "French (FR)", "", "Spanish (ES)", "", "Italian (IT)", "")
ENTRY = 0x60
END, NEWLINE = 0x00, 0x1C
BOX_BREAKS = frozenset({0x01, 0x08})
# code -> (editor name, argument bytes); 3DS-only codes have descriptive names.
CODES: Dict[int, Tuple[str, int]] = {
    0x01: ("box-break", 0), 0x02: ("xpos", 1), 0x03: ("textid", 2), 0x04: ("quicktext-on", 0),
    0x05: ("quicktext-off", 0), 0x06: ("persistent", 1), 0x07: ("event", 0), 0x08: ("box-break-delayed", 1),
    0x0A: ("fade", 1), 0x0B: ("name", 0), 0x0C: ("ocarina", 0), 0x0E: ("sfx", 5), 0x0F: ("item-icon", 1),
    0x10: ("text-speed", 1), 0x11: ("background", 3), 0x12: ("marathon-time", 0), 0x13: ("race-time", 0),
    0x14: ("points", 0), 0x15: ("tokens", 0), 0x16: ("fish-info", 0), 0x17: ("time", 0), 0x18: ("highscore", 1),
    0x19: ("unskippable", 0), 0x1A: ("two-choice", 4), 0x1B: ("three-choice", 6), 0x1D: ("color", 1),
    0x1E: ("center", 0), 0x23: ("record", 1), 0x24: ("button", 1), 0x25: ("credits", 3), 0x26: ("plural", 1),
    0x27: ("plural-else", 0), 0x28: ("plural-end", 0), 0x29: ("mq", 0), 0x2A: ("mq-else", 0), 0x2B: ("mq-end", 0),
}
BY_NAME = {name: (code, args) for code, (name, args) in CODES.items()}
VALUES = {
    "color": {0x00: "default", 0x41: "red", 0x42: "green", 0x43: "blue", 0x44: "light-blue", 0x45: "pink",
              0x46: "yellow", 0x47: "black"},
    "button": {0x06: "A", 0x07: "B", 0x0A: "L", 0x0B: "R"},
}
HEX = {"textid": 4, "sfx": 10, "background": 6, "credits": 6}   # shown as hex with this many digits
TAG_RE = re.compile(r"\{[a-z0-9-]+(?::[A-Za-z0-9-]+)?\}")


class FormatError(ValueError):
    """Not a QM file, or a text this module cannot read or write."""


class Qm:
    """The message table (kept byte for byte) and the raw text of every language slot."""

    def __init__(self, data: bytes):
        data = bytes(data)
        if len(data) < 16 or data[:4] != b"QM\0\0":
            raise FormatError("Not a QM message file")
        version, count = struct.unpack_from("<II", data, 4)
        if version != 4 or 16 + count * ENTRY > len(data):
            raise FormatError(f"QM version {version} with {count} messages is not supported")
        self.header = data[:16]
        self.entries: List[bytes] = []
        self.ids: List[int] = []
        self.texts: List[List[Optional[bytes]]] = []
        for index in range(count):
            entry = data[16 + index * ENTRY:16 + (index + 1) * ENTRY]
            slots = struct.unpack_from(f"<{2 * SLOTS}I", entry, 0x20)
            texts: List[Optional[bytes]] = []
            for slot in range(SLOTS):
                offset, size = slots[2 * slot], slots[2 * slot + 1]
                if size and offset + size > len(data):
                    raise FormatError(f"QM message {index} slot {slot} runs past the file end")
                texts.append(data[offset:offset + size] if size else None)
            self.entries.append(entry)
            self.ids.append(struct.unpack_from("<I", entry)[0])
            self.texts.append(texts)

    def attributes(self, index: int) -> Tuple[int, int]:
        """``(box type, box position)`` of a message."""
        return struct.unpack_from("<II", self.entries[index], 8)

    def build(self) -> bytes:
        """The file laid out as the game's own: the table, then the texts message by message."""
        at = 16 + len(self.entries) * ENTRY
        table, body = bytearray(), bytearray()
        for entry, texts in zip(self.entries, self.texts):
            row = bytearray(entry)
            for slot, text in enumerate(texts):
                place = (at + len(body), len(text)) if text else (0, 0)
                struct.pack_into("<II", row, 0x20 + 8 * slot, *place)
                if text:
                    body += text + bytes(-len(text) % 4)
            table += row
        return self.header + bytes(table) + bytes(body)


def to_editor(raw: bytes) -> str:
    """Stored text (up to its end code) -> editor text."""
    out: List[str] = []
    text = bytearray()
    at = 0
    while at < len(raw):
        if raw[at] != 0x7F:
            text.append(raw[at])
            at += 1
            continue
        out.append(_decode(text))
        text = bytearray()
        if at + 1 >= len(raw):
            raise FormatError("QM text ends inside a control code")
        code = raw[at + 1]
        if code == END:
            return "".join(out)
        if code == NEWLINE:
            out.append("\n")
            at += 2
            continue
        if code not in CODES:
            raise FormatError(f"Unknown QM control code 0x{code:02X}")
        name, size = CODES[code]
        argument = raw[at + 2:at + 2 + size]
        at += 2 + size
        out.append(_tag(name, argument))
        if code in BOX_BREAKS:
            out.append("\n")
    out.append(_decode(text))
    return "".join(out)


def _tag(name: str, argument: bytes) -> str:
    if not argument:
        return f"{{{name}}}"
    if name.endswith("-choice") and argument == b"\xff" * len(argument):
        return f"{{{name}}}"
    value = int.from_bytes(argument, "big")
    shown = VALUES.get(name, {}).get(value)
    if shown is None:
        shown = f"0x{value:0{HEX[name]}X}" if name in HEX else str(value)
    return f"{{{name}:{shown}}}"


def _decode(text: bytearray) -> str:
    try:
        return text.decode("utf-8")
    except UnicodeDecodeError as error:
        raise FormatError(f"QM text is not UTF-8: {error}") from None


def from_editor(text: str) -> bytes:
    """Editor text -> stored text with its end code."""
    text = str(text).replace("\r\n", "\n")
    out = bytearray()
    at = 0
    for match in TAG_RE.finditer(text):
        out += _plain(text[at:match.start()])
        code = _encode_tag(match.group()[1:-1], out)
        at = match.end()
        if code in BOX_BREAKS and text.startswith("\n", at):
            at += 1
    out += _plain(text[at:])
    return bytes(out) + bytes((0x7F, END))


def _plain(chunk: str) -> bytes:
    if "{" in chunk or "}" in chunk:
        raise FormatError(f"Unknown tag in {chunk!r}")
    return chunk.encode("utf-8").replace(b"\n", bytes((0x7F, NEWLINE)))


def _encode_tag(inner: str, out: bytearray) -> int:
    name, _, value = inner.partition(":")
    if name not in BY_NAME:
        raise FormatError(f"Unknown tag {{{inner}}}")
    code, size = BY_NAME[name]
    out += bytes((0x7F, code))
    if not size:
        if value:
            raise FormatError(f"Tag {{{name}}} takes no value")
        return code
    if not value:
        if not name.endswith("-choice"):
            raise FormatError(f"Tag {{{name}}} needs a value")
        out += b"\xff" * size
        return code
    named = {shown: number for number, shown in VALUES.get(name, {}).items()}
    try:
        number = named[value] if value in named else int(value, 16 if value.lower().startswith("0x") else 10)
        out += number.to_bytes(size, "big")
    except (ValueError, OverflowError):
        raise FormatError(f"Bad value in tag {{{inner}}}") from None
    return code


MEANINGS = {
    "box-break": "Next text box (wait for A)", "xpos": "Pen to this horizontal pixel", "textid": "Continue with message",
    "quicktext-on": "Instant text on", "quicktext-off": "Instant text off", "persistent": "Keep the box open",
    "event": "Wait for the scene", "box-break-delayed": "Next text box after N frames",
    "fade": "Close the box after N frames", "name": "Player name", "ocarina": "Ocarina input", "sfx": "Sound effect",
    "item-icon": "Item picture", "text-speed": "Text speed", "background": "Background picture",
    "marathon-time": "Marathon time", "race-time": "Race time", "points": "Points", "tokens": "Gold Skulltula count",
    "fish-info": "Fish weight", "time": "Time of day", "highscore": "High score", "unskippable": "Cannot be skipped",
    "two-choice": "Two choices (the last two lines)", "three-choice": "Three choices (the last three lines)",
    "color": "Text colour", "center": "Centre this line", "record": "Record value (Boss Challenge)",
    "button": "Button picture", "credits": "Credits page timing", "plural": "Singular form for number N, then the plural",
    "plural-else": "Plural form follows", "plural-end": "End of the plural forms",
    "mq": "Text of the normal world, then the mirrored Master Quest text", "mq-else": "Master Quest text follows",
    "mq-end": "End of the Master Quest text",
}


def describe(tag: str) -> str:
    """A tooltip for a tag, or "" for text that is not one."""
    if not TAG_RE.fullmatch(tag):
        return ""
    name, _, value = tag[1:-1].partition(":")
    meaning = MEANINGS.get(name, "")
    return f"{meaning}: {value}" if meaning and value else meaning


def slot_texts(qm: Qm, slot: int) -> Dict[int, bytes]:
    """``{message id: raw text}`` of one language slot."""
    return {message_id: texts[slot] for message_id, texts in zip(qm.ids, qm.texts) if texts[slot]}
