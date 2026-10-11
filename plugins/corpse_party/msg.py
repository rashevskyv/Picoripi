"""Corpse Party (3DS) ``*_scriptlist.MSG``: the chapter's messages in 128-byte slots.

A slot is 120 bytes of text and an 8-byte tail. A tail is ``u16 index, 0x01, zeros`` (or eight 0xFF bytes); a slot
without a tail goes on into the next one (its whole 128 bytes are text), so a message is the slots up to and
including the first slot with a tail, and its text area is those slots plus the 120 text bytes of the last one. The text is lines, each ended by a NUL; the lines of
a message need not follow each other (a choice list starts its second line at the next slot). A text is shown as
its lines joined by ``\\n``; a byte outside printable ASCII is ``{xNN}`` (0xFF opens a line that waits for a key).

An unedited message keeps its bytes. An edited one keeps the start of every line where the new line still fits
before the next line, else the lines are packed one after another; a text longer than the message's area is
refused (the file cannot grow).
"""
from __future__ import annotations

import re
from typing import List

SLOT = 128
TEXT = 120
_ESC = re.compile(r"\{x([0-9a-fA-F]{2})\}")


class MsgError(ValueError):
    pass


def _has_tail(slot: bytes) -> bool:
    tail = slot[TEXT:]
    return (tail[2] == 1 and not any(tail[3:])) or tail == b"\xff" * 8


def is_msg(raw: bytes) -> bool:
    if not raw or len(raw) % SLOT or b"\0" not in raw[:SLOT]:
        return False
    return not raw.startswith((b"table", b"FFNT", b"CTPK", b"SARC"))


def decode_line(raw: bytes) -> str:
    out = []
    for b in raw:
        if 0x20 <= b < 0x7F and b not in b"{}":
            out.append(chr(b))
        else:
            out.append("{x%02x}" % b)
    return "".join(out)


def encode_line(text: str) -> bytes:
    out = bytearray()
    pos = 0
    while pos < len(text):
        m = _ESC.match(text, pos)
        if m:
            out.append(int(m.group(1), 16))
            pos = m.end()
            continue
        ch = text[pos]
        if ord(ch) >= 0x7F or ord(ch) < 0x20:
            raise MsgError(f"{ch!r} cannot be written (ASCII and {{xNN}} bytes only)")
        out.append(ord(ch))
        pos += 1
    return bytes(out)


class Message:
    __slots__ = ("first", "slots", "area", "lines", "starts")

    def __init__(self, first: int, slots: int, area: bytes) -> None:
        self.first, self.slots, self.area = first, slots, area
        self.lines: List[bytes] = []
        self.starts: List[int] = []
        for m in re.finditer(rb"[^\0]+", area):
            self.lines.append(m.group())
            self.starts.append(m.start())

    @property
    def text(self) -> str:
        return "\n".join(decode_line(line) for line in self.lines)

    def room(self) -> int:
        return len(self.area)


class Msg:
    def __init__(self, raw: bytes) -> None:
        if not is_msg(raw):
            raise MsgError("not a Corpse Party message file")
        self.raw = bytes(raw)
        self.messages: List[Message] = []
        count = len(raw) // SLOT
        i = 0
        while i < count:
            j = i
            while j < count and not _has_tail(raw[j * SLOT:(j + 1) * SLOT]):
                j += 1
            last = min(j, count - 1)
            area = raw[i * SLOT:last * SLOT] + raw[last * SLOT:last * SLOT + TEXT]
            self.messages.append(Message(i, last - i + 1, area))
            i = last + 1

    def texts(self) -> List[str]:
        return [m.text for m in self.messages]

    def rebuild(self, texts: List[str]) -> bytes:
        if len(texts) != len(self.messages):
            raise MsgError(f"{len(texts)} texts for {len(self.messages)} messages")
        out = bytearray(self.raw)
        for message, text in zip(self.messages, texts):
            if text == message.text:
                continue
            lines = [encode_line(part) for part in text.split("\n")] if text else []
            area = _layout(message, lines)
            at = message.first * SLOT
            out[at:at + len(area)] = area
        return bytes(out)


def _layout(message: Message, lines: List[bytes]) -> bytes:
    room = message.room()
    if lines and len(lines) == len(message.starts):
        # keep every line where it was while it still ends before the next line (or the area's end)
        ends = message.starts[1:] + [room]
        if all(start + len(line) + 1 <= end for line, start, end in zip(lines, message.starts, ends)):
            area = bytearray(room)
            for line, start in zip(lines, message.starts):
                area[start:start + len(line)] = line
            return bytes(area)
    packed = b"\0".join(lines) + (b"\0" if lines else b"")
    if len(packed) > room:
        raise MsgError(f"the message at slot {message.first} is {len(packed) - room} bytes too long (room {room})")
    return packed + b"\0" * (room - len(packed))
