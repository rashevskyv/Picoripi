"""Grezzo GMSG v1 message files of Majora's Mask 3D (``message/eu/eue.gmsg``) and their text <-> editor tags.

Layout (little endian)::

    0x00 "GMSG"  0x04 u32 version (1)  0x08 u32 message count  0x0C u32 language bit (eue 0x10, eug 0x20...)
    0x10 per message, 20 bytes: u16 id, u16 next id, u32 prices, u8 box style, u8 position/flags,
         u8 item icon, u8 0, u32 text offset (0 = no text), u32 text length (with the end code)
    texts: in table order, each padded with zeros to 4 bytes

A text is UTF-8. ``0x7F`` starts a control code: a 0 pad byte when the next byte would sit at an odd
offset (from the message start), a u16 code, then its argument (``CODES``; the u32 of ``sfx`` is
4-byte aligned with two zero bytes). ``plural`` is followed by two strings, each ended by a 0 byte and
padded to 2 bytes. The editor shows the codes with the names of the N64 Majora's Mask plugin where the
code is the same (``{color:red}``, ``{quicktext-on}``, ``{name}``...): code 1 is ``\\n``, a text-box
break is followed by a line break, the end code is left out (saving adds it).
"""
from __future__ import annotations

import re
import struct
from typing import Dict, List, Optional, Tuple

HEADER = struct.Struct("<4sIII")
ENTRY = struct.Struct("<HHIBBBBII")
END, NEWLINE, BOX_BREAK, PLURAL = 0x00, 0x01, 0x02, 0x20
# code -> (editor name, argument bytes). Unseen codes (0x1A, 0x1F, 0x30) have no known size and are refused.
CODES: Dict[int, Tuple[str, int]] = {
    0x02: ("box-break", 0), 0x03: ("name", 0), 0x04: ("timer-postman", 0), 0x05: ("timer-minigame", 0),
    0x06: ("chest-flags", 0), 0x07: ("rupees-selected", 0), 0x08: ("rupees-total", 0), 0x09: ("stray-fairies", 0),
    0x0A: ("tokens", 0), 0x0B: ("owl-warp", 0), 0x0C: ("stray-fairies-left-woodfall", 0),
    0x0D: ("stray-fairies-left-snowhead", 0), 0x0E: ("stray-fairies-left-great-bay", 0),
    0x0F: ("stray-fairies-left-stone-tower", 0), 0x10: ("points-boat-archery", 0), 0x11: ("lottery-code", 2),
    0x12: ("lottery-code-guess", 0), 0x13: ("held-item-price", 0), 0x14: ("bomber-code", 0),
    0x15: ("spider-house-mask-code", 2), 0x16: ("hours-until-moon-crash", 0), 0x17: ("time-until-moon-crash", 0),
    0x18: ("time-until-new-day", 0), 0x19: ("hs-town-shooting-gallery", 0), 0x1B: ("hs-horse-back-balloon", 0),
    0x1C: ("hs-deku-playground", 2), 0x1D: ("hs-time-boat-archery", 0), 0x1E: ("number", 0), 0x20: ("plural", 2),
    0x21: ("zora-eggs-left", 0), 0x22: ("ordinal", 2), 0x23: ("catch-day", 0), 0x24: ("fish-of-the-day", 0),
    0x25: ("btn", 2), 0x26: ("xpos", 2), 0x27: ("quicktext-on", 0), 0x28: ("quicktext-off", 0), 0x29: ("delay", 2),
    0x2A: ("layout", 2), 0x2B: ("event", 2), 0x2C: ("persistent", 0), 0x2D: ("text-speed", 2),
    0x2E: ("background", 0), 0x2F: ("choices", 2), 0x31: ("flow", 2), 0x32: ("sfx", 4), 0x33: ("input-bank", 0),
    0x34: ("input-doggy-racetrack-bet", 0), 0x35: ("input-bomber-code", 0), 0x36: ("input-lottery-code", 0),
    0x37: ("indent", 0), 0x38: ("center", 0), 0x39: ("right", 0), 0x3A: ("color", 2),
}
BY_NAME = {name: (code, size) for code, (name, size) in CODES.items()}
VALUES = {
    "color": {0x01: "red", 0x02: "green", 0x03: "blue", 0x04: "yellow", 0x05: "light-blue", 0x06: "pink",
              0x07: "silver", 0x08: "orange", 0x0B: "default"},
    "btn": {0x01: "A", 0x02: "B", 0x03: "X", 0x04: "Y", 0x05: "L", 0x06: "R", 0x11: "circle-pad"},
    "flow": {0x00: "wait", 0x01: "continue"},
}
HEX = {"sfx": 8, "plural": 4, "ordinal": 4, "layout": 4}   # shown as hex with this many digits
PLURAL_ELSE, PLURAL_END = "plural-else", "plural-end"
TAG_RE = re.compile(r"\{[a-z0-9-]+(?::[A-Za-z0-9-]+)?\}")


class FormatError(ValueError):
    """Not a GMSG file, or a text this module cannot read or write."""


class Gmsg:
    """The message table (kept byte for byte, but for the text offsets and lengths) and the raw texts."""

    def __init__(self, data: bytes):
        data = bytes(data)
        if len(data) < HEADER.size or data[:4] != b"GMSG":
            raise FormatError("Not a GMSG message file")
        _magic, version, count, _language = HEADER.unpack_from(data)
        if version != 1 or HEADER.size + count * ENTRY.size > len(data):
            raise FormatError(f"GMSG version {version} with {count} messages is not supported")
        self.header = data[:HEADER.size]
        self.entries: List[bytes] = []
        self.ids: List[int] = []
        self.texts: List[Optional[bytes]] = []
        for index in range(count):
            at = HEADER.size + index * ENTRY.size
            fields = ENTRY.unpack_from(data, at)
            offset, size = fields[7], fields[8]
            if size and offset + size > len(data):
                raise FormatError(f"GMSG message {index} runs past the file end")
            self.entries.append(data[at:at + ENTRY.size])
            self.ids.append(fields[0])
            self.texts.append(data[offset:offset + size] if size else None)

    def attributes(self, index: int) -> Dict[str, int]:
        """Box style, position (low 4 bits of the flags), item icon, next id of a message."""
        message_id, next_id, _prices, style, flags, icon, _pad, _o, _s = ENTRY.unpack(self.entries[index])
        return {"message_id": message_id, "next_id": next_id, "textbox_type": style,
                "textbox_position": flags & 0x0F, "item_icon": icon}

    def build(self) -> bytes:
        """The file laid out as the game's own: the table, then the texts in table order."""
        at = HEADER.size + len(self.entries) * ENTRY.size
        table, body = bytearray(self.header), bytearray()
        for entry, text in zip(self.entries, self.texts):
            row = bytearray(entry)
            struct.pack_into("<II", row, 12, at + len(body) if text else 0, len(text) if text else 0)
            if text:
                body += text + bytes(-len(text) % 4)
            table += row
        return bytes(table + body)


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
        at += 1
        if at & 1:
            if raw[at:at + 1] != b"\0":
                raise FormatError("GMSG control code without its pad byte")
            at += 1
        if at + 2 > len(raw):
            raise FormatError("GMSG text ends inside a control code")
        code = raw[at] | raw[at + 1] << 8
        at += 2
        if code == END:
            if any(raw[at:]):
                raise FormatError("GMSG text continues after its end code")
            return "".join(out)
        if code == NEWLINE:
            out.append("\n")
            continue
        if code not in CODES:
            raise FormatError(f"Unknown GMSG control code 0x{code:02X}")
        name, size = CODES[code]
        if size == 4 and at & 3:
            if raw[at:at + 2] != b"\0\0":
                raise FormatError("GMSG sound code without its alignment")
            at += 2
        argument = raw[at:at + size]
        at += size
        out.append(_tag(name, argument))
        if code == BOX_BREAK:
            out.append("\n")
        elif code == PLURAL:
            for closing in (PLURAL_ELSE, PLURAL_END):
                end = raw.find(b"\0", at)
                if end < 0:
                    raise FormatError("GMSG plural form without its end")
                out.append(_decode(raw[at:end]) + f"{{{closing}}}")
                at = end + 1 + ((end + 1) & 1)
                if any(raw[end + 1:at]):
                    raise FormatError("GMSG plural form with a non-zero pad")
    raise FormatError("GMSG text without its end code")


def _tag(name: str, argument: bytes) -> str:
    if not argument:
        return f"{{{name}}}"
    value = int.from_bytes(argument, "little")
    shown = VALUES.get(name, {}).get(value)
    if shown is None:
        shown = f"0x{value:0{HEX[name]}X}" if name in HEX else str(value)
    return f"{{{name}:{shown}}}"


def _decode(text: bytes) -> str:
    try:
        return bytes(text).decode("utf-8")
    except UnicodeDecodeError as error:
        raise FormatError(f"GMSG text is not UTF-8: {error}") from None


def from_editor(text: str) -> bytes:
    """Editor text -> stored text with its end code."""
    text = str(text).replace("\r\n", "\n")
    out = bytearray()
    at = 0
    for match in TAG_RE.finditer(text):
        _plain(text[at:match.start()], out)
        name = _encode_tag(match.group()[1:-1], out)
        at = match.end()
        if name == "box-break" and text.startswith("\n", at):
            at += 1
    _plain(text[at:], out)
    _control(out, END, b"")
    return bytes(out)


def _control(out: bytearray, code: int, argument: bytes) -> None:
    out.append(0x7F)
    if len(out) & 1:
        out.append(0)
    out += struct.pack("<H", code)
    if len(argument) == 4 and len(out) & 3:
        out += b"\0\0"
    out += argument


def _plain(chunk: str, out: bytearray) -> None:
    if "{" in chunk or "}" in chunk:
        raise FormatError(f"Unknown tag in {chunk!r}")
    for number, line in enumerate(chunk.split("\n")):
        if number:
            _control(out, NEWLINE, b"")
        out += line.encode("utf-8")


def _encode_tag(inner: str, out: bytearray) -> str:
    name, _, value = inner.partition(":")
    if name in (PLURAL_ELSE, PLURAL_END) and not value:
        out.append(0)
        if len(out) & 1:
            out.append(0)
        return name
    if name not in BY_NAME:
        raise FormatError(f"Unknown tag {{{inner}}}")
    code, size = BY_NAME[name]
    if bool(size) != bool(value):
        raise FormatError(f"Tag {{{name}}} needs a value" if size else f"Tag {{{name}}} takes no value")
    named = {shown: number for number, shown in VALUES.get(name, {}).items()}
    try:
        number = named[value] if value in named else int(value, 16 if value.lower().startswith("0x") else 10) if value else 0
        _control(out, code, number.to_bytes(size, "little"))
    except (ValueError, OverflowError):
        raise FormatError(f"Bad value in tag {{{inner}}}") from None
    return name


MEANINGS = {
    "box-break": "Next text box", "name": "Player name", "timer-postman": "Postman's timer",
    "timer-minigame": "Minigame timer", "chest-flags": "Chest count (guess)", "rupees-selected": "Rupees chosen",
    "rupees-total": "Rupees in total", "stray-fairies": "Stray Fairies", "tokens": "Gold Skulltula tokens",
    "owl-warp": "Owl statue (guess)", "stray-fairies-left-woodfall": "Stray Fairies left in Woodfall",
    "stray-fairies-left-snowhead": "Stray Fairies left in Snowhead",
    "stray-fairies-left-great-bay": "Stray Fairies left in Great Bay",
    "stray-fairies-left-stone-tower": "Stray Fairies left in Stone Tower", "points-boat-archery": "Boat archery points",
    "lottery-code": "Lottery winning numbers of day N", "lottery-code-guess": "The player's lottery numbers",
    "held-item-price": "Price of the held item", "bomber-code": "Bombers' code",
    "spider-house-mask-code": "Spider House mask code, colour N", "hours-until-moon-crash": "Hours until the moon falls",
    "time-until-moon-crash": "Time until the moon falls", "time-until-new-day": "Time until the new day",
    "hs-town-shooting-gallery": "Shooting gallery high score", "hs-horse-back-balloon": "Balloon record",
    "hs-deku-playground": "Best time of day N", "hs-time-boat-archery": "Boat archery high score",
    "number": "A number (notebook, fishing, hints)", "plural": "Singular form for number code N, then the plural",
    PLURAL_ELSE: "Plural form follows", PLURAL_END: "End of the plural forms", "zora-eggs-left": "Zora eggs left",
    "ordinal": "English ordinal suffix of a number", "catch-day": "Day of the catch", "fish-of-the-day": "Fish of the day",
    "btn": "Button picture", "xpos": "Pen to this horizontal pixel", "quicktext-on": "Instant text on",
    "quicktext-off": "Instant text off", "delay": "Wait N frames", "layout": "Story text layout",
    "event": "End: wait for the scene", "persistent": "Keep the box open", "text-speed": "Text speed",
    "background": "Background picture", "choices": "N choices (the last N lines)",
    "flow": "End of the box: wait for A, or continue", "sfx": "Sound effect", "input-bank": "Bank amount input",
    "input-doggy-racetrack-bet": "Doggy Racetrack bet input", "input-bomber-code": "Bombers' code input",
    "input-lottery-code": "Lottery numbers input", "indent": "Indented line", "center": "Centre this line",
    "right": "Right-align this line", "color": "Text colour",
}


def describe(tag: str) -> str:
    """A tooltip for a tag, or "" for text that is not one."""
    if not TAG_RE.fullmatch(tag):
        return ""
    name, _, value = tag[1:-1].partition(":")
    meaning = MEANINGS.get(name, "")
    return f"{meaning}: {value}" if meaning and value else meaning
