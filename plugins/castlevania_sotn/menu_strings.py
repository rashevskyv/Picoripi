"""The 8x8 menu words of Symphony of the Night (US): the ``g_MenuStr`` pointer table and where each word is drawn.

The table is 110 little-endian pointers in ``DRA.BIN`` at file offset 0x8258 (address 0x800A8258; the DRA
load address is 0x800A0000). Entry i points to the cell-encoded string g_MenuStr[i]. The indices and the
draw calls are from src/dra/menu.c (US build): ``MenuDrawStats``, ``MenuSystemDraw``,
``MenuSoundConfigDraw``, ``func_800F8754`` (the command box). The table was verified on the owner's DRA.BIN:
0 ALUCARD, 1 STR, 12 HP, 92 Equip (the decoded names match the draw calls).
"""
from __future__ import annotations

import struct
from typing import Dict, List, Optional, Sequence, Tuple

DRA_BASE = 0x800A0000
TABLE_OFFSET = 0x8258          # DRA.BIN file offset of g_MenuStr[0]
TABLE_SIZE = 110

# Where a word is drawn: slot -> (screen, x, y). The screens are the menu.c draw calls with the window at rest:
#   "status"   MenuDrawStats(MENU_DG_BG)          "system"   MenuSystemDraw (x 0x20, rows 0x30 + 0x10 i)
#   "popup"    MenuSoundConfigDraw (cursor fitted) "command"  func_800F8754 (window origin fitted)
#   "category" the equipment category label at (8, 40) (cursor dependent; the first is shown)
PLACEMENTS: Dict[int, Tuple[str, int, int]] = {
    0: ("status", 128, 40),                                      # ALUCARD
    1: ("status", 32, 120), 2: ("status", 32, 132), 3: ("status", 32, 144), 4: ("status", 32, 156),
    5: ("status", 32, 176), 6: ("status", 32, 188), 7: ("status", 32, 200),   # EXP NEXT GOLD
    8: ("status", 248, 40), 9: ("status", 208, 192), 10: ("status", 240, 150), 11: ("status", 240, 164),
    12: ("status", 96, 56), 13: ("status", 96, 68), 14: ("status", 96, 80),   # HP MP HEART
    15: ("status", 248, 56), 37: ("status", 260, 68),            # STATUS, GOOD
    16: ("system", 0x20, 0x30), 17: ("system", 0x20, 0x40), 18: ("system", 0x20, 0x50),
    35: ("system", 0x20, 0x60), 32: ("system", 0x20, 0x70), 36: ("system", 0x20, 0x80),
    33: ("popup", 4, 4), 34: ("popup", 4, 20),                  # Stereo, Mono (offsets from the popup origin)
    85: ("category", 8, 40), 86: ("category", 8, 40), 87: ("category", 8, 40),
    88: ("category", 8, 40), 89: ("category", 8, 40), 90: ("category", 8, 40),
    92: ("command", 18, 4), 93: ("command", 14, 20), 94: ("command", 14, 36),   # Equip Spells Relics
    95: ("command", 14, 52), 96: ("command", 2, 68),             # System Familiars
}

# Fitted window origins (owner frames; the decomp has them dynamic): popup (cursorX, cursorY), command (x, y).
POPUP_ORIGIN = (170, 114)
COMMAND_ORIGIN = (158, 100)


def read_table(dra: bytes) -> Optional[List[int]]:
    """The 110 string offsets of g_MenuStr (file offsets in DRA.BIN), or None when the file is too short."""
    if len(dra) < TABLE_OFFSET + 4 * TABLE_SIZE:
        return None
    offsets = []
    for i in range(TABLE_SIZE):
        pointer = struct.unpack_from("<I", dra, TABLE_OFFSET + 4 * i)[0]
        offsets.append(pointer - DRA_BASE)
    return offsets


def slot_for_offset(table: Sequence[int], at: int) -> Optional[int]:
    """The g_MenuStr slot whose string starts at file offset ``at``, or None."""
    try:
        return list(table).index(at)
    except ValueError:
        return None


def placement(slot: int) -> Optional[Tuple[str, int, int]]:
    """Where the slot is drawn: (screen, x, y), with the popup and command origins applied (absolute x, y)."""
    place = PLACEMENTS.get(slot)
    if place is None:
        return None
    screen, x, y = place
    if screen == "popup":
        return screen, POPUP_ORIGIN[0] + x, POPUP_ORIGIN[1] + y
    if screen == "command":
        return screen, COMMAND_ORIGIN[0] + x, COMMAND_ORIGIN[1] + y
    return screen, x, y
