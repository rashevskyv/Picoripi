"""Infinite Space (DS) script text: ``data/Event/SpaceShip.scx``, every line of text of the game in one file.

Header (little endian): ``scx\\0``, u32 0, u32 slot count, eight u32 counts of the script tables, then at
``0x34`` seven u32 offsets of the tables that follow the text, at ``0x50`` one u32 per slot: the file offset of
its NUL-terminated line (0 = none). The lines lie back to back in slot order from the first one up to the first
table offset; nothing else points into them, so a longer line only moves the tables (and their seven offsets).

A line mixes letters and script commands. Letters are two bytes, ``0x80, 2 * index + 1``, ``index`` in the
game's character list (``CHARACTERS``, the order of ``data/Event/fontlist.txt``); commands are ASCII in square
brackets (``[\\c,1,12]`` speaker / portrait, ``[\\n]`` line break, ``[\\r]`` next window, ``[\\z]`` ...). Two lines
keep Shift-JIS leftovers. The editor shows ``[\\n]`` as a line break and every other command as it is.
"""
from __future__ import annotations

import re
import struct
from dataclasses import dataclass
from typing import List

MAGIC = b"scx\0"
SLOTS_AT = 0x50
TABLES_AT = 0x34
TABLES = 7
# data/Event/fontlist.txt, in the game's order (index 0 = space).
CHARACTERS = (" 0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz"
              "!?-・=/.,()“”:’&")
ALIASES = {"'": "’", "·": "・"}
LETTER = 0x80
_INDEX = {char: n for n, char in enumerate(CHARACTERS)}
_BYTE_TAG = re.compile(r"\[x80([0-9A-Fa-f]{2})\]")
TAG_RE = re.compile(r"\[[^\[\]\n]+\]")          # a script command or a byte tag


class FormatError(ValueError):
    pass


@dataclass
class Script:
    raw: bytes
    slots: List[int]            # file offset of each slot's line (0 = none)
    strings: List[bytes]        # the lines of the used slots, in slot order
    text_end: int

    def build(self, strings: List[bytes]) -> bytes:
        if list(strings) == self.strings:
            return self.raw
        if len(strings) != len(self.strings):
            raise FormatError("The script has a fixed number of lines")
        start = min(o for o in self.slots if o)
        head = bytearray(self.raw[:start])
        body = bytearray()
        lines = iter(strings)
        for n, offset in enumerate(self.slots):
            if offset:
                line = bytes(next(lines))
                if b"\0" in line:
                    raise FormatError("A line cannot hold a NUL byte")
                struct.pack_into("<I", head, SLOTS_AT + 4 * n, start + len(body))
                body += line + b"\0"
        delta = start + len(body) - self.text_end
        for k in range(TABLES):
            value = struct.unpack_from("<I", head, TABLES_AT + 4 * k)[0]
            struct.pack_into("<I", head, TABLES_AT + 4 * k, value + delta)
        return bytes(head) + bytes(body) + self.raw[self.text_end:]


def parse(data: bytes) -> Script:
    data = bytes(data)
    if data[:4] != MAGIC or len(data) < SLOTS_AT:
        raise FormatError("Not an Infinite Space script (scx)")
    count = struct.unpack_from("<I", data, 8)[0]
    if SLOTS_AT + 4 * count > len(data):
        raise FormatError("Broken scx slot table")
    slots = list(struct.unpack_from(f"<{count}I", data, SLOTS_AT))
    text_end = struct.unpack_from("<I", data, TABLES_AT)[0]
    used = [o for o in slots if o]
    if used != sorted(used) or (used and used[0] < SLOTS_AT + 4 * count):
        raise FormatError("The scx lines are not in slot order")
    strings, at = [], used[0] if used else text_end
    for offset in used:
        if offset != at:
            raise FormatError("The scx lines are not back to back")
        end = data.index(b"\0", offset)
        strings.append(data[offset:end])
        at = end + 1
    if at != text_end:
        raise FormatError("The scx text does not end at the first table")
    return Script(data, slots, strings, text_end)


# -- editor text ----------------------------------------------------------------------------------

def to_editor(raw: bytes) -> str:
    out, at, n = [], 0, len(raw)
    while at < n:
        byte = raw[at]
        if byte == ord("["):
            end = raw.find(b"]", at)
            end = n - 1 if end < 0 else end
            command = raw[at:end + 1].decode("cp932", "replace")
            out.append("\n" if command == "[\\n]" else command)
            at = end + 1
        elif byte == LETTER and at + 1 < n:
            code = raw[at + 1]
            index = (code - 1) // 2
            out.append(CHARACTERS[index] if code & 1 and index < len(CHARACTERS) else f"[x80{code:02X}]")
            at += 2
        elif byte >= 0x81 and at + 1 < n:
            out.append(raw[at:at + 2].decode("cp932", "replace"))
            at += 2
        else:
            out.append(chr(byte) if byte >= 0x20 else f"[x{byte:02X}]")
            at += 1
    return "".join(out)


def from_editor(text: str) -> bytes:
    text = str(text).replace("\r\n", "\n")
    out, at, n = bytearray(), 0, len(text)
    while at < n:
        char = text[at]
        if char == "\n":
            out += b"[\\n]"
            at += 1
            continue
        if char == "[":
            end = text.find("]", at)
            if end < 0:
                raise FormatError("A '[' without ']'")
            tag = text[at:end + 1]
            match = _BYTE_TAG.fullmatch(tag)
            if match:
                out += bytes((LETTER, int(match.group(1), 16)))
            elif re.fullmatch(r"\[x([0-9A-Fa-f]{2})\]", tag):
                out.append(int(tag[2:4], 16))
            else:
                out += tag.encode("cp932")
            at = end + 1
            continue
        if char == '"':
            prev = text[at - 1] if at else " "
            char = "“" if prev in " \n([" else "”"
        char = ALIASES.get(char, char)
        if char in _INDEX:
            out += bytes((LETTER, 2 * _INDEX[char] + 1))
        elif ord(char) >= 0x2000:                    # the Japanese leftovers (the font draws none of them)
            try:
                out += char.encode("cp932")
            except UnicodeEncodeError:
                raise FormatError(f"The game font has no {char!r}") from None
        else:
            raise FormatError(f"The game font has no {char!r}")
        at += 1
    return bytes(out)


def has_letters(raw: bytes) -> bool:
    """The line shows text (at least one letter of the font), not only script commands."""
    return re.search(rb"(?<!\[)\x80[\x01-\xff]", bytes(raw)) is not None and to_editor(raw).strip() != ""


_COMMANDS = {
    "n": "Line break (the editor shows it as a new line)",
    "r": "Next window: wait for a button, then clear the box",
    "c": r"Speaker / portrait: [\c,side,character]",
    "z": "Wait for the previous command to finish",
    "e": "Script event (camera, effect, sound): keep as it is",
    "w": "Script variable: keep as it is",
    "b": "Background / picture: keep as it is",
    "x": "End of the scene's text",
    "f": "Flag / face change: keep as it is",
    "m": "Music: keep as it is",
    "v": "Voice / sound: keep as it is",
    "y": "Choice: keep as it is",
    "s": "Sound effect: keep as it is",
}


def describe(tag: str) -> str:
    """A tooltip for a command tag."""
    match = re.fullmatch(r"\[\\([a-z])[^\]]*\]", tag)
    if match:
        return _COMMANDS.get(match.group(1), "Script command: keep as it is")
    if _BYTE_TAG.fullmatch(tag):
        return "A character code the font list does not name"
    return ""
