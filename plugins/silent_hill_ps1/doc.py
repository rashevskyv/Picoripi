"""The text of one Silent Hill (PlayStation) file as Picoripi blocks, and how to write it back.

Two kinds of file hold text, and the plugin finds them by their shape (it gets bytes, not names):

* a map overlay (``VIN\\MAP*.BIN`` and the menu overlays): its word at 0x34 points at a table of
  message pointers; each message is a NUL-terminated string in the same file. One block: the messages.
* ``1ST\\BODYPROG.BIN`` (decrypted): the item name and description tables (195 pointers each) and the
  title menu (four pointers: CONTINUE, START, OPTION, EXTRA).

A string is edited in place. Its room is the bytes it has now: the string, its NUL, and the zero bytes
after it up to the next string of the same file. An edit that does not fit its room is not written;
the caller gets the reason (``Overflow``).
"""
from __future__ import annotations

import struct
from dataclasses import dataclass
from typing import List, Optional, Sequence, Tuple

from . import codec

OVERLAY_BASE = 0x800C9578          # USA map overlay link base (the port's USA_OVL_BASE)
BODY_BASE = 0x80024B60             # BODYPROG link base (the port's USA_BODY_VRAM)
ITEM_NAME_TABLE = 0x800ADB60 - BODY_BASE
ITEM_DESC_TABLE = 0x800ADE6C - BODY_BASE
ITEM_COUNT = 195
TITLE_MENU_TABLE = 0x84F30          # file offset of the four title menu pointers
TITLE_MENU_COUNT = 4
MESSAGE_LIMIT = 176                 # the port's MSG_COUNT_MAX (largest map table is 159)


class Overflow(ValueError):
    """The new text does not fit the room of its string."""


@dataclass(frozen=True)
class Slot:
    start: int                      # file offset of the string
    room: int                       # bytes it may take, its NUL and the zero padding after it included
    text: str                       # the string as editor text


@dataclass
class Group:
    label: str
    slots: List[Slot]


def _u32(data: bytes, at: int) -> Optional[int]:
    if at < 0 or at + 4 > len(data):
        return None
    return struct.unpack_from("<I", data, at)[0]


def _string_end(data: bytes, start: int) -> int:
    """The NUL ending the string at ``start``, or -1 when the text is not plain game text."""
    end = data.find(b"\0", start, min(len(data), start + 512))
    if end <= start:
        return -1
    for byte in data[start:end]:
        if byte not in (0x09, 0x0A) and not (0x20 <= byte < 0x7F):
            return -1
    return end


def _message_starts(data: bytes) -> List[int]:
    table = _u32(data, 0x34)
    if table is None or table < OVERLAY_BASE:
        return []
    table -= OVERLAY_BASE
    starts: List[int] = []
    for i in range(MESSAGE_LIMIT):
        pointer = _u32(data, table + 4 * i)
        if pointer is None or pointer < OVERLAY_BASE or pointer - OVERLAY_BASE >= len(data):
            break
        start = pointer - OVERLAY_BASE
        if _string_end(data, start) < 0:
            break
        starts.append(start)
    return starts


def _pointer_starts(data: bytes, table: int, count: int, base: int) -> Optional[List[int]]:
    """The string starts of a pointer table; a null pointer (an empty entry) is left out."""
    starts = []
    for i in range(count):
        pointer = _u32(data, table + 4 * i)
        if pointer is None:
            return None
        if pointer == 0:
            continue
        if pointer < base or pointer - base >= len(data):
            return None
        start = pointer - base
        if _string_end(data, start) < 0:
            return None
        starts.append(start)
    return starts


def is_body(data: bytes) -> bool:
    if len(data) < TITLE_MENU_TABLE + 4 * TITLE_MENU_COUNT or len(data) < ITEM_DESC_TABLE + 4 * ITEM_COUNT:
        return False
    return (_pointer_starts(data, TITLE_MENU_TABLE, TITLE_MENU_COUNT, BODY_BASE) is not None
            and _pointer_starts(data, ITEM_NAME_TABLE, ITEM_COUNT, BODY_BASE) is not None)


def _groups_of(data: bytes) -> List[Tuple[str, List[int]]]:
    """(label, string starts) for every block of the file, in block order."""
    if is_body(data):
        names = _pointer_starts(data, ITEM_NAME_TABLE, ITEM_COUNT, BODY_BASE) or []
        descs = _pointer_starts(data, ITEM_DESC_TABLE, ITEM_COUNT, BODY_BASE) or []
        menu = _pointer_starts(data, TITLE_MENU_TABLE, TITLE_MENU_COUNT, BODY_BASE) or []
        return [("item names", names), ("item descriptions", descs), ("title menu", menu)]
    starts = _message_starts(data)
    if starts:
        return [("messages", starts)]
    return []


def _unique(starts: Sequence[int]) -> List[int]:
    seen, out = set(), []
    for start in starts:
        if start not in seen:
            seen.add(start)
            out.append(start)
    return out


def parse(data: bytes) -> List[Group]:
    """The blocks of the file. Strings that are not plain game text are left out."""
    groups = _groups_of(data)
    all_starts = sorted({s for _, starts in groups for s in starts})
    groups_out: List[Group] = []
    for label, starts in groups:
        slots = []
        for start in _unique(starts):
            end = _string_end(data, start)
            if end < 0:
                continue
            following = [s for s in all_starts if s > start]
            limit = following[0] if following else len(data)
            padding = 0
            pos = end + 1
            while pos < min(limit, len(data)) and data[pos] == 0:
                padding += 1
                pos += 1
            room = end + 1 - start + padding
            slots.append(Slot(start, room, codec.decode(data[start:end])))
        groups_out.append(Group(label, slots))
    return groups_out


def texts(data: bytes) -> List[List[str]]:
    return [[slot.text for slot in group.slots] for group in parse(data)]


def labels(data: bytes) -> List[str]:
    return [group.label for group in parse(data)]


def build(source: bytes, edited: Sequence[Sequence[str]]) -> Tuple[bytes, List[str]]:
    """``source`` with the edited texts written in place. Returns (bytes, problems); a text that does
    not fit its room or has a character the game cannot print keeps its original bytes."""
    out = bytearray(source)
    problems: List[str] = []
    for gi, group in enumerate(parse(source)):
        if gi >= len(edited):
            break
        for si, slot in enumerate(group.slots):
            if si >= len(edited[gi]):
                break
            new_text = edited[gi][si]
            if new_text == slot.text:
                continue
            try:
                raw = codec.encode(new_text)
            except ValueError as error:
                problems.append(f"{group.label} #{si}: {error}")
                continue
            if len(raw) + 1 > slot.room:
                problems.append(f"{group.label} #{si}: {len(raw) + 1} bytes, room {slot.room}")
                continue
            out[slot.start:slot.start + slot.room] = raw + bytes(slot.room - len(raw))
    return bytes(out), problems
