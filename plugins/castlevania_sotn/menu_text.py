"""Shift-JIS menu lines of Symphony of the Night drawn the way the game draws them (pure, no Qt).

The console's 16x15 Kanji/ASCII font (KROM2) is in the PlayStation BIOS, not on the disc, so the
BIOS file is read from the user's copy (console key ``psx_bios``); no glyph data is shipped.
The game expands each 16x15 glyph to 12x16 (``func_80106A28``) and then trims and places it by ink
(``func_800F99B8``): leading empty byte columns go, a glyph advances by its last ink byte column,
plus one when that column holds a high-nibble pixel, plus one when shorter than six columns. A byte is
two pixels, and a space adds two more bytes.
"""
from __future__ import annotations

from typing import Callable, List, Optional, Tuple

BIOS_KROM_OFFSET = 0x66000     # BIOS ROM address BFC66000: the range 0x8140-0x84BF table (file offset)
GLYPH_BYTES = 30               # 16 x 15 one-bit glyph: 15 rows of two bytes
ROW_BYTES = 6                  # 12 px per row after the expansion, two px per byte
ROWS = 16
STRIP_STRIDE = 0x90            # the line buffer of ``func_800F99B8`` (arg2 false): 144 bytes = 288 px
DOUBLE_SPACE = 0x8140
RIGHT_DOUBLE_QUOTE = 0x8168    # the game skips the next two bytes after it

# (first code, index of that code in the glyph table): the range 0x8140-0x84BF, from the decomp.
_RANGE_ONE = ((0x8140, 0x0000), (0x8180, 0x003F), (0x81B8, 0x006C), (0x81C8, 0x0074),
              (0x81DA, 0x007B), (0x81F0, 0x008A), (0x81FC, 0x0092), (0x824F, 0x0093),
              (0x8260, 0x009D), (0x8281, 0x00B7), (0x829F, 0x00D1), (0x8340, 0x0124),
              (0x8380, 0x0163), (0x839F, 0x017A), (0x83BF, 0x0192), (0x8440, 0x01AA),
              (0x8470, 0x01CB), (0x8480, 0x01DA), (0x849F, 0x01EC))
# Per lead byte: (low byte ranges, _RANGE_ONE entry). ``None`` means the lead has no entry here.
_RANGES = {
    0x81: (((0x40, 0x7F, 0), (0x80, 0xAD, 1), (0xB8, 0xC0, 2), (0xC8, 0xCF, 3),
            (0xDA, 0xE9, 4), (0xF0, 0xF8, 5), (0xFC, 0xFD, 6))),
    0x82: (((0x4F, 0x59, 7), (0x60, 0x7A, 8), (0x81, 0x9B, 9), (0x9F, 0xF2, 10))),
    0x83: (((0x40, 0x7F, 11), (0x80, 0x97, 12), (0x9F, 0xB7, 13), (0xBF, 0xD7, 14))),
    0x84: (((0x40, 0x61, 15), (0x70, 0x7F, 16), (0x80, 0x92, 17), (0x9F, 0xBF, 18))),
}

# ceil(index / 2) for the expanded nibbles, the decomp's D_800AC934 table
_HALF_UP = (0, 1, 1, 2, 2, 3, 3, 4, 4, 5, 5, 6, 6, 7, 7, 8, 8)


def glyph_index(code: int) -> Optional[int]:
    """Index of a Shift-JIS code in the BIOS table, or None outside the ported range (0x8140-0x84BF)."""
    lead, low = code >> 8, code & 0xFF
    for lo_first, lo_last, entry in _RANGES.get(lead, ()):
        if lo_first <= low < lo_last:
            base, offset = _RANGE_ONE[entry]
            return code - base + offset
    return None


def glyph_at(bios: bytes, code: int) -> Optional[bytes]:
    """The 30 glyph bytes of ``code`` in a BIOS image, or None when the code or the file is out of range."""
    index = glyph_index(code)
    if index is None:
        return None
    start = BIOS_KROM_OFFSET + index * GLYPH_BYTES
    glyph = bytes(bios[start:start + GLYPH_BYTES])
    return glyph if len(glyph) == GLYPH_BYTES else None


def expand(glyph: bytes) -> bytes:
    """``func_80106A28`` kind 0: 16 x 15 one-bit glyph to the 12 x 16 four-bit bitmap (96 bytes)."""
    words: List[int] = []
    p = 0

    def bits(value: int) -> Tuple[List[int], int]:
        out = []
        for _ in range(4):
            out.append(value & 1)
            value >>= 1
        return out, value

    for _ in range(15):
        val0 = val1 = val2 = 0
        (b0, b1, b2, b3), row = bits(glyph[p])
        val1 |= (b0 * 3 + b1) << 4
        val1 |= b1 * 2 + b2 * 2
        val0 |= (b2 + b3 * 3) << 12
        (b0, b1, b2, b3), row = bits(row)
        val0 |= (b0 * 3 + b1) << 8
        val0 |= (b1 * 2 + b2 * 2) << 4
        val0 |= b2 + b3 * 3
        p += 1
        (b0, b1, b2, b3), row = bits(glyph[p])
        val2 |= (b0 * 3 + b1) << 12
        val2 |= (b1 * 2 + b2 * 2) << 8
        val2 |= (b2 + b3 * 3) << 4
        (b0, b1, b2, b3), row = bits(row)
        val2 |= b0 * 3 + b1
        val1 |= (b1 * 2 + b2 * 2) << 12
        val1 |= (b2 + b3 * 3) << 8
        words += [val0, val1, val2]
        p += 1
    words += [0, 0, 0]
    out = bytearray()
    for word in words:
        packed = (_HALF_UP[((word >> 12) & 0xF) * 4] << 12 | _HALF_UP[((word >> 8) & 0xF) * 4] << 8
                  | _HALF_UP[((word >> 4) & 0xF) * 4] << 4 | _HALF_UP[(word & 0xF) * 4])
        out.append(packed & 0xFF)
        out.append(packed >> 8)
    return bytes(out)


def _trim_and_measure(cells: bytearray, is_space: bool) -> int:
    """Trim the leading empty columns in place, then return the advance in bytes (``func_800F99B8``)."""
    for _ in range(ROW_BYTES):
        if is_space or any(cells[i * ROW_BYTES] for i in range(ROWS)):
            break
        for i in range(ROWS):
            start = i * ROW_BYTES
            cells[start:start + ROW_BYTES - 1] = cells[start + 1:start + ROW_BYTES]
            cells[start + ROW_BYTES - 1] = 0
    last = 0
    for i in range(ROWS):
        for j in range(ROW_BYTES):
            if cells[i * ROW_BYTES + j] and last < j:
                last = j
    if any(cells[i * ROW_BYTES + last] & 0xF0 for i in range(ROWS)):
        last += 1
    if last < ROW_BYTES:
        last += 1
    return last


def draw_line(text: bytes, glyph_of: Callable[[int], Optional[bytes]]) -> Tuple[bytearray, int, int]:
    """Lay out one line like ``func_800F99B8``: ``(strip, used bytes, glyphs outside the range)``.

    ``glyph_of`` maps a Shift-JIS code to 30 glyph bytes, or None (the glyph is drawn blank and counted).
    """
    strip = bytearray(STRIP_STRIDE * ROWS + ROW_BYTES)
    used = 0
    missing = 0
    pos = 0
    while pos < len(text):
        extra = 0
        ch = text[pos]
        pos += 1
        if 0x61 <= ch <= 0x7A:
            code = ch + 0x8220
        elif 0x41 <= ch <= 0x5A:
            code = ch + 0x821F
        elif ch == 0x20:
            code = DOUBLE_SPACE
            extra = 2
        else:
            code = (ch << 8) + (text[pos] if pos < len(text) else 0)
            pos += 1
            if code == RIGHT_DOUBLE_QUOTE:
                pos += 2
            if code == DOUBLE_SPACE:
                ch = 0x20
                extra = 2
        glyph = glyph_of(code)
        if glyph is None:
            missing += 1
            glyph = bytes(GLYPH_BYTES)
        cells = bytearray(expand(glyph))
        advance = _trim_and_measure(cells, is_space=(ch == 0x20))
        for i in range(ROWS):
            start = i * STRIP_STRIDE + used
            strip[start:start + ROW_BYTES] = cells[i * ROW_BYTES:(i + 1) * ROW_BYTES]
        used += advance + extra
        if used >= STRIP_STRIDE:
            break
    return strip, used, missing


def ink_rows(strip: bytes, used: int) -> List[List[int]]:
    """The ink of a laid-out line: one list of 0/1 per pixel row, two pixels per byte, low nibble left."""
    rows = []
    for i in range(ROWS):
        row = []
        for c in range(min(used, STRIP_STRIDE)):
            value = strip[i * STRIP_STRIDE + c]
            row.append(1 if value & 0x0F else 0)
            row.append(1 if value >> 4 else 0)
        rows.append(row)
    return rows


def width_px(text: bytes, glyph_of: Callable[[int], Optional[bytes]]) -> int:
    """Pixel width of a laid-out line (the used bytes times two)."""
    return draw_line(text, glyph_of)[1] * 2
