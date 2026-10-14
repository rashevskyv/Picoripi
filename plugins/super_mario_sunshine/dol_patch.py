"""Four words of the retail main.dol that let single-byte Cyrillic show in speech balloons on Dolphin.

Owner decision (2026-10-14). The retail dialogue code treats every byte from 0x80 up as the first byte of a two-byte
character. Each site below compares the byte with 0x80. Changing the compare to 0x100 makes every byte single-byte.
Site B reads the byte as signed (extsb) for the width lookup; the replacement word (ori r3,r3,0) keeps it unsigned.
The patch keeps the executable's size and changes nothing else. Every word is checked before it is written, so a
different main.dol is refused.

Sites (decomp src/GC2D/Talk2D2.cpp at the port's pin 967436b; facts only). DOL offsets from the research table.
  A  Talk2D2.cpp:545   makeBoxLine             cmplwi r0,0x80   -> cmplwi r0,0x100
  B  Talk2D2.cpp:560   width lookup            extsb r3,r3      -> ori r3,r3,0
  C  Talk2D2.cpp:1306  setupBoardTextBox       cmplwi r28,0x80  -> cmplwi r28,0x100
  D  Talk2D2.cpp:1377  setupTextBox            cmplwi r0,0x80   -> cmplwi r0,0x100

Caveat, not verified: the disc holds Shift-JIS text in the four pinnaBeach*.szs dolpic1.bmg files. If the NA game
shows that text, these sites break its two-byte pairs. The NA display of that text is not checked.
"""
import struct
from typing import Tuple

from core.i18n import tr

# (DOL offset, retail word, patched word, site)
PATCHES: Tuple[Tuple[int, int, int, str], ...] = (
    (0x150438, 0x28000080, 0x28000100, "A Talk2D2.cpp:545"),
    (0x150474, 0x7C630774, 0x60630000, "B Talk2D2.cpp:560"),
    (0x14EA34, 0x281C0080, 0x281C0100, "C Talk2D2.cpp:1306"),
    (0x14E704, 0x28000080, 0x28000100, "D Talk2D2.cpp:1377"),
)


def _replace(dol: bytes, from_retail: bool) -> bytes:
    """``dol`` with each site's word swapped: retail to patched, or back. Raises ValueError on any other word."""
    out = bytearray(dol)
    for at, retail, patched, site in PATCHES:
        if at + 4 > len(dol):
            raise ValueError(tr("main.dol is too short for the speech fix ({0})", site))
        before, after = (retail, patched) if from_retail else (patched, retail)
        if struct.unpack_from(">I", dol, at)[0] != before:
            raise ValueError(tr("main.dol: the word at {0:#x} is not the expected instruction ({1})", at, site))
        struct.pack_into(">I", out, at, after)
    return bytes(out)


def apply(dol: bytes) -> bytes:
    """``dol`` with the four words patched. Raises ValueError when a word is not the retail one."""
    return _replace(dol, from_retail=True)


def ensure(dol: bytes) -> bytes:
    """``dol`` with the speech fix in place: a DOL that already has it is returned as it is, a retail one is patched.

    A translated executable carries the fix when it was saved after the patch; any other word raises ValueError.
    """
    if len(dol) >= max(at for at, _retail, _patched, _site in PATCHES) + 4 and all(
            struct.unpack_from(">I", dol, at)[0] == patched for at, _retail, patched, _site in PATCHES):
        return dol
    return apply(dol)


def revert(dol: bytes) -> bytes:
    """``dol`` with the four words put back. Raises ValueError when a word is not the patched one."""
    return _replace(dol, from_retail=False)
