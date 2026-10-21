"""Text box scale of Conker's Bad Fur Day (US): the two divisors of the game's design resolution.

The boot code stores ``width / 292.0`` into D_800380A0 (ROM 0x39E0: ``lui $at, 0x4392``) and ``216 / 216.0`` into
D_800380A4 (ROM 0x3A14: ``lui $at, 0x4358``). The text measuring routine multiplies widths by D_800380A0 and heights
by D_800380A4, so a smaller divisor gives a bigger box. Only the high half of each float is changed; the low half
stays zero, so the new divisor is the nearest float with a zero low half.
"""
from __future__ import annotations

import struct
from typing import Tuple

from . import code_patches as cp

DESIGN_X = 292.0
DESIGN_Y = 216.0
X_OFFSET = 0x39E2   # ROM address of the high halfword of the 292.0 immediate (instruction at 0x39E0)
Y_OFFSET = 0x3A16   # ROM address of the high halfword of the 216.0 immediate (instruction at 0x3A14)
X_EXPECTED = b"\x43\x92"
Y_EXPECTED = b"\x43\x58"
DEFAULT_SCALE = 1.0  # the build uses this box scale; 1.0 keeps the original box and the original bytes


def _high_half(divisor: float) -> int:
    return struct.unpack(">I", struct.pack(">f", divisor))[0] >> 16


def _float_from_high(high: int) -> float:
    return struct.unpack(">f", struct.pack(">I", high << 16))[0]


def scale_patches(scale: float) -> Tuple[cp.RomPatch, ...]:
    """Raw ROM patches for a box scale. 1.0 is the original box and gives no patches."""
    if not scale > 0:
        raise ValueError("box scale must be positive")
    if scale == 1.0:
        return ()
    return (
        cp.RomPatch(offset=X_OFFSET, expected=X_EXPECTED,
                    new=struct.pack(">H", _high_half(DESIGN_X / scale)), note="box width divisor"),
        cp.RomPatch(offset=Y_OFFSET, expected=Y_EXPECTED,
                    new=struct.pack(">H", _high_half(DESIGN_Y / scale)), note="box height divisor"),
    )


def effective_scale(scale: float) -> Tuple[float, float]:
    """The scale the game gets after the high-half rounding, for width and height."""
    if scale == 1.0:
        return 1.0, 1.0
    return (DESIGN_X / _float_from_high(_high_half(DESIGN_X / scale)),
            DESIGN_Y / _float_from_high(_high_half(DESIGN_Y / scale)))
