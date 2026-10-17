"""PAL menus and credits: NUL-terminated glyph strings (no pointer table found for them).

A run is a string of glyph bytes (0x20..0xA4) ending in a NUL byte. It is text when it decodes to at least three
letters. Its room is the run and the zero bytes after it, up to the next byte that is not zero: an edit must fit the
room (the same rule as ``doc.parse``). Unchanged runs keep their bytes.

The four files are recognised by their size (and by a text in the title menu and the option menu):
OPTION.BIN, SAVELOAD.BIN, STF_ROLL.BIN, and BODYPROG.BIN, where only the title and the difficulty windows are read.
"""
from typing import List, Optional, Sequence, Tuple

from . import pal_text
from .doc import Slot

GLYPH_LO, GLYPH_HI = 0x20, 0xA4
MAX_PAD = 64
Window = Tuple[int, int]

BODYPROG_WINDOWS: List[Window] = [(0x18D0, 0x1900), (0x1E00, 0x1F40)]   # difficulty (0x18E0); title menu (0x1ED0)
_OPTION_SIG_OFF, _OPTION_SIG = 0x42C, bytes(pal_text.byte_of(c) for c in "ВИХІД")
_SAVELOAD_SIG_OFF, _SAVELOAD_SIG = 0x4, bytes(pal_text.byte_of(c) for c in "СЛОТ")
_BODYPROG_SIG_OFF, _BODYPROG_SIG = 0x1ED0, bytes(pal_text.byte_of(c) for c in "ЗАВАН")


def windows_for(data: bytes) -> Optional[List[Window]]:
    """The windows to read for a file of this PAL disc, or None when the file is not a menu or credits file."""
    size = len(data)
    if size == 20736 and data[_OPTION_SIG_OFF:_OPTION_SIG_OFF + len(_OPTION_SIG)] == _OPTION_SIG:
        return [(0, size)]
    if size == 20992 and data[_SAVELOAD_SIG_OFF:_SAVELOAD_SIG_OFF + len(_SAVELOAD_SIG)] == _SAVELOAD_SIG:
        return [(0, size)]
    if size == 15104:
        return [(0, size)]
    if size == 668928 and data[_BODYPROG_SIG_OFF:_BODYPROG_SIG_OFF + len(_BODYPROG_SIG)] == _BODYPROG_SIG:
        return list(BODYPROG_WINDOWS)
    return None


def find(data: bytes, windows: Sequence[Window]) -> List[Slot]:
    out: List[Slot] = []
    n = len(data)
    for lo, hi in windows:
        i = lo
        while i < hi:
            if not (GLYPH_LO <= data[i] <= GLYPH_HI):
                i += 1
                continue
            j = i
            while j < n and GLYPH_LO <= data[j] <= GLYPH_HI:
                j += 1
            if j < n and data[j] == 0 and j - i >= 3:
                text = pal_text.decode_glyph(data[i:j])
                if sum(ch.isalpha() for ch in text) >= 3:
                    k = j + 1
                    while k < n and data[k] == 0 and k - j <= MAX_PAD:
                        k += 1
                    out.append(Slot(i, k - i, text))
                    i = k
                    continue
            i = j
    return out


def build(source: bytes, edited: Sequence[str], windows: Sequence[Window]) -> Tuple[bytes, List[str]]:
    """``source`` with the edited runs written in place. A run that does not fit its room keeps its bytes."""
    out = bytearray(source)
    problems: List[str] = []
    for index, slot in enumerate(find(source, windows)):
        if index >= len(edited) or edited[index] == slot.text:
            continue
        try:
            raw = pal_text.encode_glyph(edited[index])
        except ValueError as error:
            problems.append(f"run {index} at {slot.start:#x}: {error}")
            continue
        if len(raw) + 1 > slot.room:
            problems.append(f"run {index} at {slot.start:#x}: {len(raw) + 1} bytes, room {slot.room}")
            continue
        out[slot.start:slot.start + slot.room] = raw + bytes(slot.room - len(raw))
    return bytes(out), problems
