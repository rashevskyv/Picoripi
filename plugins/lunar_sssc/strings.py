"""The game's name and menu tables: the first (deflated) chunk of SYSTEM.DAT, unpacked to ``00_0001.bin``.

Fourteen tables of 128 u16 slots each (byte offsets, 0 = empty) open the chunk; the 0xFF-ended strings
follow from offset 0xE00 up to the data behind them (0x599C in the USA game), whose place is fixed. A
rebuild lays the strings out again in slot order inside that room; strings that come out the same
share their bytes.
"""
from __future__ import annotations

import struct
from typing import Dict, List, Tuple

TABLES, SLOTS = 14, 128
HEADER = TABLES * SLOTS * 2
NAMES = ("Party names", "Monsters", "Weapons and armour", "Accessories and items", "Weapon and armour help",
         "Accessory and item help", "Battle skills", "Unused", "Map places", "Dungeon places", "Event titles",
         "Music titles", "Menus and battle", "Memory card")


def slots(data: bytes) -> List[List[Tuple[int, int]]]:
    """``[[(slot, offset)]]`` per table, empty slots left out. Raises ValueError for another file."""
    if len(data) <= HEADER:
        raise ValueError("too short for the name tables")
    values = struct.unpack_from(f"<{TABLES * SLOTS}H", data, 0)
    used = [v for v in values if v]
    if not used or min(used) != HEADER or max(used) >= len(data) or data[HEADER] not in (0x0E, 0xFF):
        raise ValueError("not the name tables")
    return [[(slot, values[t * SLOTS + slot]) for slot in range(SLOTS) if values[t * SLOTS + slot]]
            for t in range(TABLES)]


def end_of_strings(data: bytes) -> int:
    """Where the data behind the strings starts: just after the last string, aligned to 4."""
    last = max(offset for table in slots(data) for _slot, offset in table)
    end = data.index(b"\xff", last) + 1
    return (end + 3) & ~3


def rebuild(data: bytes, new: Dict[Tuple[int, int], bytes]) -> bytes:
    """``data`` with the strings of ``{(table, slot): 0xFF-ended bytes}`` replaced (others kept)."""
    if not new:
        return bytes(data)
    tables = slots(data)
    room = end_of_strings(data)
    out = bytearray(data)
    placed: Dict[object, int] = {}
    pos = HEADER
    entries = sorted((offset, t, slot) for t, table in enumerate(tables) for slot, offset in table)
    for offset, t, slot in entries:                  # in the game's order: unchanged tables come out the same
        raw = new.get((t, slot))
        key: object = ("new", raw) if raw is not None else ("old", offset)
        if raw is None:
            raw = data[offset:data.index(b"\xff", offset) + 1]
        if key not in placed:
            if pos + len(raw) > room:
                raise ValueError(f"The name and menu tables do not fit: {pos + len(raw) - room} bytes too long "
                                 f"(room {room - HEADER} bytes). Shorten some names or help lines.")
            out[pos:pos + len(raw)] = raw
            placed[key] = pos
            pos += len(raw)
        struct.pack_into("<H", out, (t * SLOTS + slot) * 2, placed[key])
    out[pos:room] = bytes(room - pos)
    return bytes(out)
