"""The prologue caption of Symphony of the Night (ST0.BIN, ``prologue_script_en``): the script, the editor
lines and the draw in the console's 12 x 16 font. Pure, no Qt; the BIOS file is passed in.

The script is bytes: text, then ``01 xx`` (line break; ``xx`` is the next line's x offset in halfwords of
the caption panel), ``02 xx`` (page break, same offset) and ``00`` (end). The first line's x (0x16) is in
the code (``func_801B101C``), so it is not in the script. The draw (``func_801B1298``) places one glyph
every 3 halfwords (12 px) and a space every 2 (8 px). ``func_801B11E8`` maps one byte to a Shift-JIS code
(ASCII only); ``CAVE`` reads the second byte of a Shift-JIS lead byte, so Cyrillic reaches the BIOS font.
"""
from __future__ import annotations

import re
import struct
from dataclasses import dataclass
from typing import List, Optional, Sequence, Set, Tuple

from PIL import Image

from . import codec, menu_text

LINE_BREAK = 1
PAGE_BREAK = 2
END = 0
FIRST_X = 0x16                 # the first line's x offset (startY = 0x216 in func_801B101C)
PAGE_TAG = "{PAGE}"
TAG_RE = re.compile(r"(\{[0-9A-F]{2}\}|\{[0-9A-F]{4}\})")
# RAM of ST0 starts at this address; the file offset of an address is address - BASE
BASE = 0x80180000
# The draw code: ``func_801B11E8`` (the byte to glyph wrapper) and the two words that load the script.
GLYPH_WRAPPER = 0x311E8        # file offset of func_801B11E8 (its first word is replaced by a jump)
GLYPH_WRAPPER_WORD = 0x27BDFFE8  # addiu $sp, $sp, -0x18, the word that the jump replaces
SCRIPT_LOAD = 0x312FC          # file offset of ``lui $a0, hi`` (``addiu $a0, $a0, lo`` follows)
LUI_A0, ADDIU_A0 = 0x3C040000, 0x24840000
# Panel geometry of the preview (see render_page): 4 px a halfword, 22 px a line, the sprite at x 32.
PANEL_W = 512
LINE_PITCH = 22
GLYPH_ROWS = 16
SPRITE_X = 32
WRAP_LO, WRAP_HI = 224, 256    # a glyph never starts in [224, 256) of the panel: the cursor skips to 256
# The lead-byte reader (96 bytes, RAM 0x8019AB30 = file 0x1AB30). It returns the glyph of the lead byte and
# its trail byte, read from ``g_Dialogue.scriptCur``; every other byte takes the original path.
CAVE_HEX = (
    "7fffa2241f00422c0700401420ffa2241000422c0400401400000000e8ffbd277cc40608000000001c80033ccc2463240000668c"
    "000000000000c7900100c624000066ac00220500252087000480023c00c8428cffff84300800400025280000"
)
CAVE = bytes.fromhex(CAVE_HEX)
CAVE_SIZE = len(CAVE)


class ScrollError(ValueError):
    """The caption does not fit the script or the draw code."""


@dataclass
class Caption:
    raw: bytes       # the line's text bytes
    brk: int         # LINE_BREAK, PAGE_BREAK, or END for the last line
    x: int           # the line's x offset (FIRST_X for the first line)


def read_script(data: bytes, start: int, end: int) -> Tuple[List[Caption], int]:
    """The lines of the caption script at ``start`` and the script's length including its end byte."""
    lines: List[Caption] = []
    raw = bytearray()
    x = FIRST_X
    i = start
    while True:
        if i >= end:
            raise ScrollError(f"the caption at {start:#x} has no end byte before {end:#x}")
        byte = data[i]
        if byte == END:
            lines.append(Caption(bytes(raw), END, x))
            return lines, i + 1 - start
        if byte in (LINE_BREAK, PAGE_BREAK):
            if i + 1 >= end:
                raise ScrollError(f"the caption at {i:#x} has a break without its x offset")
            lines.append(Caption(bytes(raw), byte, x))
            x = data[i + 1]
            raw = bytearray()
            i += 2
            continue
        raw.append(byte)
        i += 1


def build_script(raws: Sequence[bytes], brks: Sequence[int], xs: Sequence[int]) -> bytes:
    """The script bytes: line k is ``raws[k]`` then its break ``brks[k]`` (the last is END); the x offset of
    line k+1 (``xs[k + 1]``) follows the break of line k."""
    out = bytearray()
    last = len(raws) - 1
    for k, raw in enumerate(raws):
        out += raw
        if k == last:
            out.append(END)
            break
        out.append(brks[k])
        out.append(xs[k + 1])
    return bytes(out)


def _decode(raw: bytes) -> str:
    """Editor text of caption bytes: ASCII as is (``{`` and ``}`` as tags), Shift-JIS pairs as characters."""
    out = []
    i = 0
    while i < len(raw):
        byte = raw[i]
        if 0x20 <= byte < 0x7F and byte not in (0x7B, 0x7D):
            out.append(chr(byte))
            i += 1
            continue
        if _is_lead(byte) and i + 1 < len(raw):
            pair = raw[i:i + 2]
            try:
                char = pair.decode("cp932")
            except UnicodeDecodeError:
                char = ""
            if len(char) == 1 and char.encode("cp932") == pair:
                out.append(char)
                i += 2
                continue
            out.append("{%02X%02X}" % (byte, raw[i + 1]))
            i += 2
            continue
        out.append("{%02X}" % byte)
        i += 1
    return "".join(out)


def _encode(text: str, missing: Optional[Set[str]]) -> bytes:
    out = bytearray()
    for part in TAG_RE.split(text):
        if TAG_RE.fullmatch(part):
            out += bytes.fromhex(part[1:-1])
            continue
        for char in part.replace("\n", " "):
            char = codec.SJ_LATIN.get(char, char)
            try:
                raw = char.encode("cp932")
            except UnicodeEncodeError:
                raw = b""
            if not raw or raw == b"\x00":
                if missing is not None:
                    missing.add(char)
                raw = b"?"
            out += raw
    return bytes(out)


def to_editor(line: Caption) -> str:
    """The editor text of a line; a page break shows as ``{PAGE}`` at its end."""
    return _decode(line.raw) + (PAGE_TAG if line.brk == PAGE_BREAK else "")


def from_editor(text: str, last: bool, missing: Optional[Set[str]] = None) -> Tuple[bytes, int]:
    """The text bytes and the break kind of an editor line. ``{PAGE}`` ends a page; the last line cannot."""
    body, brk = (text[:-len(PAGE_TAG)], PAGE_BREAK) if text.endswith(PAGE_TAG) else (text, LINE_BREAK)
    if PAGE_TAG in body:
        raise ScrollError("{PAGE} belongs at the end of a line")
    if last:
        if brk == PAGE_BREAK:
            raise ScrollError("the last line of the caption cannot end a page")
        brk = END
    return _encode(body, missing), brk


def _is_lead(byte: int) -> bool:
    """The lead bytes that ``CAVE`` reads with a second byte (0x81-0x9F, 0xE0-0xEF)."""
    return 0x81 <= byte <= 0x9F or 0xE0 <= byte <= 0xEF


def glyph_code(byte: int, trail: Optional[int] = None) -> Optional[int]:
    """The Shift-JIS code ``func_801B11E8`` gives a byte (with its trail byte for a lead), or None for a space."""
    if trail is not None:
        return (byte << 8) | trail
    if byte == 0x20:
        return None
    if byte >= 0x61:
        return byte + 0x8220
    if byte >= 0x41:
        return byte + 0x821F
    special = {0x2C: 0x8143, 0x2E: 0x8144, 0x27: 0x8166}
    return special.get(byte, byte + 0x821F)


def _cells(raw: bytes, x: int, glyph_of) -> List[Tuple[int, Optional[bytes]]]:
    """(panel x, glyph bytes or None) of each glyph of a line, with the game's cursor and wrap rule."""
    cursor = 4 * x
    out: List[Tuple[int, Optional[bytes]]] = []
    i = 0
    while i < len(raw):
        byte = raw[i]
        i += 1
        if _is_lead(byte) and i < len(raw):
            code = glyph_code(byte, raw[i])
            i += 1
        else:
            code = glyph_code(byte)
        if code is None:
            cursor += 8
        else:
            out.append((cursor, glyph_of(code)))
            cursor += 12
        if WRAP_LO <= cursor < WRAP_HI:
            cursor += 32
    return out


def _ink(glyph: bytes) -> List[List[int]]:
    """The 12 x 16 ink of an expanded glyph (menu_text.expand): one list of 0/1 per row."""
    rows = []
    cells = menu_text.expand(glyph)
    for row in range(GLYPH_ROWS):
        line = []
        for byte in cells[row * 6:row * 6 + 6]:
            line.append(1 if byte & 0x0F else 0)
            line.append(1 if byte >> 4 else 0)
        rows.append(line)
    return rows


def render_page(bios: bytes, page: Sequence[Tuple[int, bytes]]) -> Image.Image:
    """The page of caption lines on the 512-wide panel, ink in white on transparent. ``page`` is (x, text bytes)
    per line, top to bottom."""
    rows = max(len(page), 1)
    panel = Image.new("RGBA", (PANEL_W, LINE_PITCH * (rows - 1) + GLYPH_ROWS), (0, 0, 0, 0))
    pixels = panel.load()
    for row, (x, raw) in enumerate(page):
        for px, glyph in _cells(raw, x, lambda code: menu_text.glyph_at(bios, code)):
            if glyph is None:
                continue
            ink = _ink(glyph)
            left = SPRITE_X + px if px < WRAP_HI else px
            for dy, line in enumerate(ink):
                for dx, on in enumerate(line):
                    if on and 0 <= left + dx < PANEL_W:
                        pixels[left + dx, row * LINE_PITCH + dy] = (255, 255, 255, 255)
    return panel


def point_words(source: bytes) -> Optional[Tuple[int, int]]:
    """The two words that load the script address (``lui $a0``, ``addiu $a0``), or None when they differ."""
    lui, addiu = struct.unpack_from("<II", source, SCRIPT_LOAD)
    if lui >> 16 != LUI_A0 >> 16 or addiu >> 16 != ADDIU_A0 >> 16:
        return None
    return lui, addiu


def script_start(data: bytes) -> int:
    """The file offset of the caption script: where the draw code's ``lui``/``addiu`` pair points."""
    words = point_words(data)
    if words is None:
        raise ScrollError("the caption draw code does not load the script the way this plugin expects")
    lo = words[1] & 0xFFFF
    lo -= 0x10000 if lo & 0x8000 else 0
    return ((words[0] & 0xFFFF) << 16) + lo - BASE


def point_at(out: bytearray, source: bytes, ram: int) -> None:
    """Load ``ram`` (a RAM address) into the script pointer of the draw code (``lui``/``addiu`` pair)."""
    if point_words(source) is None:
        raise ScrollError("the caption draw code does not load the script the way this plugin expects")
    hi = ((ram + 0x8000) >> 16) & 0xFFFF
    lo = ram & 0xFFFF
    struct.pack_into("<II", out, SCRIPT_LOAD, LUI_A0 | hi, ADDIU_A0 | lo)


def install_cave(out: bytearray, source: bytes, cave_at: int) -> None:
    """The lead-byte reader at ``cave_at`` and the jump that makes ``func_801B11E8`` use it."""
    if struct.unpack_from("<I", source, GLYPH_WRAPPER)[0] != GLYPH_WRAPPER_WORD:
        raise ScrollError("the glyph wrapper does not start the way this plugin expects")
    out[cave_at:cave_at + CAVE_SIZE] = CAVE
    jump = 0x08000000 | (((BASE + cave_at) >> 2) & 0x03FFFFFF)
    struct.pack_into("<I", out, GLYPH_WRAPPER, jump)
