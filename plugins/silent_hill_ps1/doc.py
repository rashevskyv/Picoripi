"""The text of one Silent Hill (PlayStation) file as Picoripi blocks, and how to write it back.

Two kinds of file hold text, and the plugin finds them by their shape (it gets bytes, not names):

* a map overlay (``VIN\\MAP*.BIN`` and the menu overlays): its word at 0x34 points at a table of
  message pointers; each message is a NUL-terminated string in the same file. One block: the messages.
  The USA disc links its overlays at ``OVERLAY_BASE``; the PAL disc (SLES_015.14) at ``PAL_OVERLAY_BASE``
  and its translated strings use bytes 0x80-0xFF, so the PAL check accepts those bytes too.
* ``1ST\\BODYPROG.BIN`` (decrypted, USA): the item name and description tables (195 pointers each) and the
  title menu (four pointers: CONTINUE, START, OPTION, EXTRA).
* ``VIN\\ITEM_*.BIN`` (PAL): 4 zero bytes, then 195 name and description pointer pairs. Two blocks.
* ``VIN\\OPTION.BIN`` and ``VIN\\SAVELOAD.BIN`` (USA): the option and save/load menu strings, found by
  their text (``menu_slots.py``). One block each.

A string is edited in place. Its room is the bytes it has now: the string, its NUL, and the zero bytes
after it up to the next string of the same file. An edit that does not fit its room is not written;
the caller gets the reason (``Overflow``).
"""
from __future__ import annotations

import struct
from dataclasses import dataclass
from typing import List, Optional, Sequence, Tuple

from . import codec, pal_text
from .menu_slots import menu_group

OVERLAY_BASE = 0x800C9578          # USA map overlay link base (the port's USA_OVL_BASE)
PAL_OVERLAY_BASE = 0x800CB370      # PAL map overlay link base (the port's EUR_OVL_BASE)
BODY_BASE = 0x80024B60             # BODYPROG link base (the port's USA_BODY_VRAM)
ITEM_NAME_TABLE = 0x800ADB60 - BODY_BASE
ITEM_DESC_TABLE = 0x800ADE6C - BODY_BASE
ITEM_COUNT = 195
PAL_ITEM_BASE = 0x800C8B68         # PAL item table base (VIN\ITEM_*.BIN)
PAL_ITEM_PREFIX = 4                # 4 zero bytes before the first name/description pair
PAL_ITEM_MIN_NAMES = 8             # fewer readable names and the file is not an item table
TITLE_MENU_TABLE = 0x84F30          # file offset of the four title menu pointers
TITLE_MENU_COUNT = 4
MESSAGE_LIMIT = 176                 # the port's MSG_COUNT_MAX (largest map table is 159)
PAL_MIN_MESSAGES = 4                # a PAL overlay needs this many in-file messages to count as text


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


def _string_end(data: bytes, start: int, mode: str = "ascii") -> int:
    """The NUL ending the string at ``start``, or -1 when it is not game text in ``mode``.

    ``ascii``: the USA text (tab, newline, 0x20-0x7E). ``high``: also 0x80-0xFF (the PAL message text).
    ``any``: every byte but NUL (the PAL item names carry control bytes)."""
    end = data.find(b"\0", start, min(len(data), start + 512))
    if end <= start:
        return -1
    if mode == "any":
        return end
    for byte in data[start:end]:
        if byte in (0x09, 0x0A) or 0x20 <= byte < 0x7F or (mode == "high" and byte >= 0x80):
            continue
        return -1
    return end


def _message_starts(data: bytes, base: int = OVERLAY_BASE, mode: str = "ascii") -> List[int]:
    table = _u32(data, 0x34)
    if table is None or table < base:
        return []
    table -= base
    starts: List[int] = []
    for i in range(MESSAGE_LIMIT):
        pointer = _u32(data, table + 4 * i)
        if pointer is None or pointer < base or pointer - base >= len(data):
            break
        start = pointer - base
        if _string_end(data, start, mode) < 0:
            break
        starts.append(start)
    return starts


def _pointer_starts(data: bytes, table: int, count: int, base: int, stride: int = 4,
                    mode: str = "ascii") -> Optional[List[int]]:
    """The string starts of a pointer table; a null pointer (an empty entry) is left out."""
    starts = []
    for i in range(count):
        pointer = _u32(data, table + stride * i)
        if pointer is None:
            return None
        if pointer == 0:
            continue
        if pointer < base or pointer - base >= len(data):
            return None
        start = pointer - base
        if _string_end(data, start, mode) < 0:
            return None
        starts.append(start)
    return starts


def is_body(data: bytes) -> bool:
    if len(data) < TITLE_MENU_TABLE + 4 * TITLE_MENU_COUNT or len(data) < ITEM_DESC_TABLE + 4 * ITEM_COUNT:
        return False
    return (_pointer_starts(data, TITLE_MENU_TABLE, TITLE_MENU_COUNT, BODY_BASE) is not None
            and _pointer_starts(data, ITEM_NAME_TABLE, ITEM_COUNT, BODY_BASE) is not None)


def _pal_item_starts(data: bytes) -> Optional[Tuple[List[int], List[int]]]:
    """(name starts, description starts) of a PAL item file, or None when the file is not one.

    The pairs are read one by one. A pair whose pointer does not name a NUL-ended string is left out:
    the translated ITEM_ENG.BIN and ITEM_FRN.BIN hold such pointers in their upper entries."""
    if len(data) < PAL_ITEM_PREFIX + 8 or data[:PAL_ITEM_PREFIX] != bytes(PAL_ITEM_PREFIX):
        return None
    names: List[int] = []
    descs: List[int] = []
    for k in range(ITEM_COUNT):
        at = PAL_ITEM_PREFIX + 8 * k
        if at + 8 > len(data):
            break
        name, desc = _item_string(data, _u32(data, at)), _item_string(data, _u32(data, at + 4))
        if name is not None:
            names.append(name)
        if desc is not None:
            descs.append(desc)
    if len(names) < PAL_ITEM_MIN_NAMES:
        return None
    return names, descs


def _item_string(data: bytes, pointer: Optional[int]) -> Optional[int]:
    """File offset of the item string a pointer names, or None (null, out of the file, no NUL)."""
    if not pointer or pointer < PAL_ITEM_BASE or pointer - PAL_ITEM_BASE >= len(data):
        return None
    start = pointer - PAL_ITEM_BASE
    return start if _string_end(data, start, "any") >= 0 else None


def _groups_of(data: bytes) -> List[Tuple[str, List[int], str]]:
    """(label, string starts, text mode) for every block of the file, in block order."""
    if is_body(data):
        names = _pointer_starts(data, ITEM_NAME_TABLE, ITEM_COUNT, BODY_BASE) or []
        descs = _pointer_starts(data, ITEM_DESC_TABLE, ITEM_COUNT, BODY_BASE) or []
        menu = _pointer_starts(data, TITLE_MENU_TABLE, TITLE_MENU_COUNT, BODY_BASE) or []
        return [("item names", names, "ascii"), ("item descriptions", descs, "ascii"),
                ("title menu", menu, "ascii")]
    menu = menu_group(data)
    # the USA menu layouts are matched by file size; the PAL OPTION.BIN has the USA SAVELOAD size
    if menu is not None and any(_string_end(data, start) >= 0 for start in menu[1]):
        return [(menu[0], menu[1], "ascii")]
    starts = _message_starts(data)
    if starts:
        return [("messages", starts, "ascii")]
    starts = _message_starts(data, PAL_OVERLAY_BASE, mode="high")
    if len(starts) >= PAL_MIN_MESSAGES:
        return [("messages", starts, "high")]
    pal_items = _pal_item_starts(data)     # last: an item table also passes the looser pointer checks
    if pal_items is not None:
        names, descs = pal_items
        return [("item names", names, "any"), ("item descriptions", descs, "any")]
    return []


def _unique(starts: Sequence[int]) -> List[int]:
    seen, out = set(), []
    for start in starts:
        if start not in seen:
            seen.add(start)
            out.append(start)
    return out


def parse(data: bytes, pal: bool = False) -> List[Group]:
    """The blocks of the file. Strings that are not plain game text are left out."""
    groups = _groups_of(data)
    all_starts = sorted({s for _, starts, _ in groups for s in starts})
    groups_out: List[Group] = []
    for label, starts, mode in groups:
        slots = []
        for start in _unique(starts):
            end = _string_end(data, start, mode)
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
            raw = data[start:end]
            slots.append(Slot(start, room, pal_text.decode_message(raw) if pal else codec.decode(raw)))
        groups_out.append(Group(label, slots))
    return groups_out


def texts(data: bytes, pal: bool = False) -> List[List[str]]:
    return [[slot.text for slot in group.slots] for group in parse(data, pal)]


def labels(data: bytes) -> List[str]:
    return [group.label for group in parse(data)]


def build(source: bytes, edited: Sequence[Sequence[str]], pal: bool = False) -> Tuple[bytes, List[str]]:
    """``source`` with the edited texts written in place. Returns (bytes, problems); a text that does
    not fit its room or has a character the game cannot print keeps its original bytes."""
    out = bytearray(source)
    problems: List[str] = []
    for gi, group in enumerate(parse(source, pal)):
        if gi >= len(edited):
            break
        for si, slot in enumerate(group.slots):
            if si >= len(edited[gi]):
                break
            new_text = edited[gi][si]
            if new_text == slot.text:
                continue
            try:
                raw = (pal_text.encode_message(new_text, source[slot.start:slot.start + slot.room]) if pal
                       else codec.encode(new_text))
            except ValueError as error:
                problems.append(f"{group.label} #{si}: {error}")
                continue
            if len(raw) + 1 > slot.room:
                problems.append(f"{group.label} #{si}: {len(raw) + 1} bytes, room {slot.room}")
                continue
            out[slot.start:slot.start + slot.room] = raw + bytes(slot.room - len(raw))
    return bytes(out), problems
