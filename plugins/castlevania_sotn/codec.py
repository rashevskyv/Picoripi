"""Castlevania: Symphony of the Night (PlayStation, USA) text bytes <-> editor text.

The game writes text in two ways:

- **8x8 font** (menus, item and enemy names, cutscene dialogue, actor names): one byte is one cell
  of the 16x16 cell font sheet (``BIN/F_GAME.BIN``). Menu strings store the cell number and end with
  ``FF 00``; cutscene scripts store ``cell + 0x20`` (so English letters are plain ASCII there).
  ``FF xx`` inside a menu string is a game escape and reads ``{FFxx}``.
- **Shift-JIS** (descriptions, the librarian's bestiary, save and option messages): ASCII and
  two-byte Shift-JIS, ending with ``00``. The glyphs come from the console's BIOS font, which has
  Latin, Cyrillic (no Ґ Є Ї), kana and kanji. ``81 68 81 68`` reads ``”`` (the game draws one ``”``
  and skips the next two bytes); ``@`` breaks the line in bestiary texts.

A byte or code with no character reads as a tag (``{8F}``, ``{8168}``) and is written back as it is.
Ukrainian letters reach the 8x8 font through the translation map (letter -> a free cell's character).
"""
from __future__ import annotations

import re
from typing import Dict, Optional, Set

# The 256 cells of the 8x8 font sheet, row by row (sotn-decomp tools/sotn_str, with cell 0x02 = '"').
CELLS = (
    ' !"#$%&\'()男+,-./'
    '0123456789:人手=玉?'
    '石ABCDEFGHIJKLMNO'
    'PQRSTUVWXYZ[剣]盾_'
    '書abcdefghijklmno'
    'pqrstuvwxyz炎氷雷~女'
    '力。「」、・ヲァィゥェォャュョッ'
    'ーアイウエオカキクケコサシスセソ'
    'タチツテトナニヌネノハヒフヘホマ'
    'ミムメモヤユヨラリルレロワンﾞﾟ'
    '子悪魔人妖精をぁぃぅぇぉゃゅょっ'
    '金あいうえおかきくけこさしすせそ'
    'たちつてとなにぬねのはひふへほま'
    'みむめもやゆよらりるれろわん指輪'
    '←↖↑↗→↘↓↙○×□△名刀聖血'
    '✈★☀☁☃♂♀©®§¶∑大光邪月'
)
assert len(CELLS) == 256
# a character -> its cell (the first cell that shows it; a second cell of the same glyph reads as a tag)
CELL_OF: Dict[str, int] = {}
for _cell, _char in enumerate(CELLS):
    CELL_OF.setdefault(_char, _cell)

TAG_RE = re.compile(r"\{([0-9A-F]{2}|[0-9A-F]{4})\}")
ANY_TAG_RE = re.compile(r"\{[^{}]*\}")
S8_END = b"\xff\x00"
CS_OFFSET = 0x20            # cutscene and credits bytes are the cell number + 0x20
QUOTE_SJ = b"\x81\x68\x81\x68"
# Ukrainian letters the BIOS font draws with a Latin glyph.
SJ_LATIN = {"І": "I", "і": "i"}


def _cell_char(cell: int) -> Optional[str]:
    if not 0 <= cell < 256:
        return None
    char = CELLS[cell]
    return char if CELL_OF[char] == cell else None


def decode_cells(raw: bytes, offset: int = 0, reverse_map: Optional[Dict[str, str]] = None) -> str:
    """Editor text of 8x8-font bytes (menu: ``offset`` 0, cutscene: 0x20); ``FF xx`` reads ``{FFxx}``."""
    back = reverse_map or {}
    out = []
    i = 0
    while i < len(raw):
        b = raw[i]
        if b == 0xFF and offset == 0 and i + 1 < len(raw):
            out.append("{FF%02X}" % raw[i + 1])
            i += 2
            continue
        char = _cell_char(b - offset)
        out.append(back.get(char, char) if char is not None else "{%02X}" % b)
        i += 1
    return "".join(out)


def encode_cells(text: str, offset: int = 0, mapping: Optional[Dict[str, str]] = None,
                 missing: Optional[Set[str]] = None) -> bytes:
    """8x8-font bytes of editor text; a character with no cell becomes ``?`` and goes to ``missing``."""
    mapping = mapping or {}
    out = bytearray()
    pos = 0
    for match in TAG_RE.finditer(text):
        out += _cells(text[pos:match.start()], offset, mapping, missing)
        out += bytes.fromhex(match.group(1))
        pos = match.end()
    out += _cells(text[pos:], offset, mapping, missing)
    return bytes(out)


def _cells(text: str, offset: int, mapping: Dict[str, str], missing: Optional[Set[str]]) -> bytes:
    out = bytearray()
    for char in text:
        cell = CELL_OF.get(mapping.get(char, char))
        if cell is None or not 0 <= cell + offset < 0x100:
            if missing is not None:
                missing.add(char)
            cell = CELL_OF["?"]
        out.append(cell + offset)
    return bytes(out)


def _sj_pair(raw: bytes, i: int) -> Optional[str]:
    pair = raw[i:i + 2]
    if len(pair) < 2:
        return None
    try:
        char = pair.decode("cp932")
    except UnicodeDecodeError:
        return None
    try:
        return char if len(char) == 1 and char.encode("cp932") == pair else None
    except UnicodeEncodeError:
        return None


def is_lead(byte: int) -> bool:
    return 0x81 <= byte <= 0x9F or 0xE0 <= byte <= 0xFC


def decode_sj(raw: bytes, newline: str = "", reverse_map: Optional[Dict[str, str]] = None) -> str:
    """Editor text of Shift-JIS bytes; ``newline`` (``@``) reads as a line break."""
    back = reverse_map or {}
    out = []
    i = 0
    while i < len(raw):
        b = raw[i]
        if raw.startswith(QUOTE_SJ, i):
            out.append("”")
            i += 4
            continue
        if b < 0x80:
            char = chr(b)
            if newline and char == newline:
                out.append("\n")
            elif 0x20 <= b < 0x7F and char not in "{}":
                out.append(back.get(char, char))
            else:
                out.append("{%02X}" % b)
            i += 1
            continue
        if is_lead(b):
            char = _sj_pair(raw, i)
            if char is not None and char != "”":
                out.append(back.get(char, char))
            else:
                out.append("{%02X%02X}" % (b, raw[i + 1]) if i + 1 < len(raw) else "{%02X}" % b)
            i += 2
            continue
        out.append("{%02X}" % b)
        i += 1
    return "".join(out)


def encode_sj(text: str, newline: str = "", mapping: Optional[Dict[str, str]] = None,
              missing: Optional[Set[str]] = None) -> bytes:
    """Shift-JIS bytes of editor text; a character the BIOS font lacks becomes ``?``."""
    mapping = {**SJ_LATIN, **(mapping or {})}
    out = bytearray()
    pos = 0
    for match in TAG_RE.finditer(text):
        out += _sj(text[pos:match.start()], newline, mapping, missing)
        out += bytes.fromhex(match.group(1))
        pos = match.end()
    out += _sj(text[pos:], newline, mapping, missing)
    return bytes(out)


def _sj(text: str, newline: str, mapping: Dict[str, str], missing: Optional[Set[str]]) -> bytes:
    out = bytearray()
    for char in text:
        if char == "\n":
            out += (newline or " ").encode("ascii")
            continue
        if char == "”":
            out += QUOTE_SJ
            continue
        char = mapping.get(char, char)
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


def decode(raw: bytes, enc: str, newline: str = "", reverse_map: Optional[Dict[str, str]] = None) -> str:
    """``enc``: ``s8`` (menu 8x8 string, without ``FF 00``) or ``sj`` (Shift-JIS, without ``00``)."""
    if enc == "s8":
        return decode_cells(raw, 0, reverse_map)
    return decode_sj(raw, newline, reverse_map)


def encode(text: str, enc: str, newline: str = "", mapping: Optional[Dict[str, str]] = None,
           missing: Optional[Set[str]] = None) -> bytes:
    """Bytes of a string with its end bytes (``FF 00`` or ``00``)."""
    if enc == "s8":
        return encode_cells(text, 0, mapping, missing) + S8_END
    return encode_sj(text, newline, mapping, missing) + b"\x00"


def read_raw(data: bytes, at: int, enc: str) -> bytes:
    """The string at ``at`` without its end bytes."""
    if enc == "s8":
        i = at
        while i + 1 < len(data):
            if data[i] == 0xFF:
                if data[i + 1] == 0:
                    return bytes(data[at:i])
                i += 2
                continue
            i += 1
        raise ValueError(f"8x8 string at {at:#x} has no end")
    end = data.find(b"\x00", at)
    if end < 0:
        raise ValueError(f"string at {at:#x} has no end")
    return bytes(data[at:end])
