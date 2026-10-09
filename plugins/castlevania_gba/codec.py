"""Text codes of Castlevania: Harmony of Dissonance (HoD) and Aria of Sorrow (AoS) on the GBA, both ways.

The workspace scripts keep every string as its raw bytes (``strings.cvtext``, see ``rules``); this module turns
those bytes into editor text and back. One table per game:

AoS (one byte a code): ``20``-``7E`` ASCII (``5C`` is drawn as the yen sign; ``[`` / ``]`` are shown full width
so they never read as a tag), ``90`` / ``91`` Œ œ, ``A0``-``FF`` Latin-1 where the font has the glyph; ``06``
breaks the line; ``02``, ``03``, ``05`` and ``07`` take one parameter byte; ``0B``-``10`` are button pictures and
``13`` a number the game fills in.

HoD (u16 little endian codes): ``81xx``-``84xx`` are glyphs of the Shift-JIS font (full-width Latin is shown as
plain ASCII: the capitals and digits of the text use it), ``8540``-``858B`` are narrow letters (the game draws
a Shift-JIS glyph with its own width: ``ALIASES``); ``F006`` breaks the line; ``F001``, ``F002``, ``F003`` and
``F007`` take one u16 parameter.

Ukrainian letters: AoS has no Cyrillic, so every letter gets a blank cell of the font (``UA_SLOTS``); HoD has the
Russian Shift-JIS letters, and Ґ Є І Ї ґ є і ї get blank cells after я. The cells stay empty until somebody
draws the letters in the Font Editor. A code with no character is written ``[xHH]`` (AoS) / ``[xHHHH]`` (HoD).
"""
from __future__ import annotations

import re
import unicodedata
from typing import Dict, List, Tuple

UA_LETTERS = "АБВГҐДЕЄЖЗИІЇЙКЛМНОПРСТУФХЦЧШЩЬЮЯабвгґдеєжзиіїйклмнопрстуфхцчшщьюя"

# -- Aria of Sorrow ----------------------------------------------------------------------------------------

# Font cells (codes) that are blank in both AoS fonts, in code order: one per Ukrainian letter.
AOS_FREE = ([0x8E, 0x8F] + list(range(0x92, 0xA7)) + [0xA8, 0xA9] + list(range(0xAC, 0xBA)) + list(range(0xBC, 0xC0))
            + [0xC3, 0xC5, 0xC6] + list(range(0xCC, 0xD6)) + [0xD7, 0xD9, 0xDA, 0xDD, 0xDE, 0xE1, 0xE3, 0xE5, 0xE6, 0xEC,
                                                                0xED, 0xF0, 0xF1, 0xF2, 0xF3, 0xF5, 0xF7])
AOS_UA_SLOTS: Dict[str, int] = dict(zip(UA_LETTERS, AOS_FREE))
# Latin-1 cells with a glyph in the AoS font (the others are blank).
_AOS_LATIN = {0xA7, 0xAA, 0xAB, 0xBA, 0xBB, 0xC0, 0xC1, 0xC2, 0xC4, 0xC7, 0xC8, 0xC9, 0xCA, 0xCB, 0xD6, 0xD8, 0xDB,
              0xDC, 0xDF, 0xE0, 0xE2, 0xE4, 0xE7, 0xE8, 0xE9, 0xEA, 0xEB, 0xEE, 0xEF, 0xF4, 0xF6, 0xF9, 0xFB, 0xFC}


def _aos_chars() -> Dict[int, str]:
    chars = {code: chr(code) for code in range(0x20, 0x7F)}
    chars.update({0x5B: "［", 0x5C: "¥", 0x5D: "］", 0x90: "Œ", 0x91: "œ", 0xBA: "°"})
    chars.update({code: chr(code) for code in _AOS_LATIN if code != 0xBA})
    chars.update({code: letter for letter, code in AOS_UA_SLOTS.items()})
    return chars


# -- Harmony of Dissonance ---------------------------------------------------------------------------------

HOD_FONT_FIRST, HOD_FONT_ROWS = 0x81, 4          # the font holds Shift-JIS rows 81-84, 188 cells each
HOD_DEFAULT_WIDTH = 6
# 8540 + i -> (Shift-JIS glyph, x offset, width): the ROM table at 0x0C5470 (u16 glyph, u8 x, u8 width; two
# sets of 38 -- the text uses the first).
_ALIAS_TABLE = bytes.fromhex(
    "40810004438100044481000445810004468100044781000449810104688201048182000682820006838200068482000685820006"
    "868200068782000688820006898202028a8200068b8200068c8201038d8200068e8200068f820006908200069182000692820005"
    "938200069482000595820006968200069782000698820006998200069a82000666810004698102046a8100049081000640810004"
    "438100044481000445810004468100044781000449810203688202038182000582820005838200058482000585820005868200048782"
    "000688820005898202028a8200058b8200058c8201038d8200068e8200058f8200059082000591820005928200059382000594820004"
    "95820005968200069782000698820006998200059a82000566810103698102036a81010390810006")
ALIASES: Dict[int, Tuple[int, int, int]] = {
    0x8540 + i: (int.from_bytes(_ALIAS_TABLE[4 * i:4 * i + 2], "little"), _ALIAS_TABLE[4 * i + 2], _ALIAS_TABLE[4 * i + 3])
    for i in range(len(_ALIAS_TABLE) // 4)}
HOD_UA_SLOTS: Dict[str, int] = {letter: 0x8492 + i for i, letter in enumerate("ҐЄІЇґєії")}


def hod_glyph_codes() -> List[int]:
    """The Shift-JIS code of every glyph of the HoD text font, in font order."""
    seconds = [b for b in range(0x40, 0xFD) if b != 0x7F]
    return [(first << 8) | second for first in range(HOD_FONT_FIRST, HOD_FONT_FIRST + HOD_FONT_ROWS)
            for second in seconds]


def _sjis_char(code: int) -> str:
    try:
        char = bytes([code >> 8, code & 0xFF]).decode("cp932")
    except UnicodeDecodeError:
        return ""
    plain = unicodedata.normalize("NFKC", char)
    if len(plain) == 1 and plain not in "[]\\" and plain.isprintable():
        return plain
    return char if len(char) == 1 and char.isprintable() else ""


def _hod_chars() -> Dict[int, str]:
    chars: Dict[int, str] = {}
    taken = set(HOD_UA_SLOTS)
    for code in range(0x8540, 0x8566):                       # the narrow letters the text uses
        char = _sjis_char(ALIASES[code][0])
        if char and char not in taken:
            chars[code] = char
            taken.add(char)
    for code in hod_glyph_codes():
        char = _sjis_char(code)
        if char and char not in taken:
            chars[code] = char
            taken.add(char)
    chars.update({code: letter for letter, code in HOD_UA_SLOTS.items()})
    return chars


# -- the codec -------------------------------------------------------------------------------------------

class EncodeError(ValueError):
    """A text that cannot be written in the game's codes."""


class Codec:
    """One game's codes: ``decode(bytes) -> editor text`` and ``encode(editor text) -> bytes``."""

    def __init__(self, unit: int, chars: Dict[int, str], newline: int, simple: Dict[int, str],
                 params: Dict[int, str], pairs: Dict[Tuple[int, int], str], breaks: Tuple[str, ...] = ()):
        self.unit, self.chars, self.newline = unit, chars, newline
        self.simple, self.params, self.pairs, self.breaks = simple, params, pairs, breaks
        self.codes = {char: code for code, char in chars.items()}
        self.digits = 2 * unit
        self.tag_codes = {tag: code for code, tag in simple.items()}
        self.pair_codes = {tag: pair for pair, tag in pairs.items()}
        self.param_codes = {name: code for code, name in params.items()}

    def _units(self, data: bytes) -> List[int]:
        if self.unit == 1:
            return list(data)
        return [data[i] | data[i + 1] << 8 for i in range(0, len(data) - 1, 2)]

    def decode(self, data: bytes) -> str:
        units, out, i = self._units(bytes(data)), [], 0
        while i < len(units):
            code = units[i]
            if code in self.params and i + 1 < len(units):
                tag = self.pairs.get((code, units[i + 1])) or f"[{self.params[code]}:{units[i + 1]:0{self.digits}X}]"
                out.append(tag + ("\n" if tag in self.breaks else ""))
                i += 2
                continue
            if code == self.newline:
                out.append("\n")
            elif code in self.simple:
                out.append(self.simple[code])
            elif code in self.chars:
                out.append(self.chars[code])
            else:
                out.append(f"[x{code:0{self.digits}X}]")
            i += 1
        return "".join(out)

    def encode(self, text: str, strict: bool = True) -> bytes:
        units: List[int] = []
        tokens = re.findall(r"\[[^\[\]\n]*\]|\n|.", str(text), flags=re.S)
        i = 0
        while i < len(tokens):
            token = tokens[i]
            i += 1
            if token == "\n":
                units.append(self.newline)
            elif token in self.pair_codes:
                units.extend(self.pair_codes[token])
                if token in self.breaks and i < len(tokens) and tokens[i] == "\n":
                    i += 1                               # the line break the editor shows after it
            elif token in self.tag_codes:
                units.append(self.tag_codes[token])
            elif token in self.codes:
                units.append(self.codes[token])
            elif (match := re.fullmatch(r"\[([a-z]+):([0-9A-Fa-f]{1,4})\]", token)) and match.group(1) in self.param_codes:
                units += [self.param_codes[match.group(1)], int(match.group(2), 16)]
            elif match := re.fullmatch(r"\[x([0-9A-Fa-f]{1,4})\]", token):
                units.append(int(match.group(1), 16))
            elif strict:
                raise EncodeError(f"No game code for {token!r}")
            else:
                units.append(self.codes["?"])
        limit = 1 << (8 * self.unit)
        if any(not 0 <= unit < limit for unit in units):
            raise EncodeError("A code is out of range")
        if self.unit == 1:
            return bytes(units)
        return b"".join(unit.to_bytes(2, "little") for unit in units)

    def unknown_chars(self, text: str) -> List[str]:
        """Characters of ``text`` (outside tags) the game has no code for."""
        plain = re.sub(r"\[[^\[\]\n]*\]", "", str(text))
        return sorted({char for char in plain if char != "\n" and char not in self.codes})


AOS = Codec(1, _aos_chars(), 0x06,
            simple={0x0B: "[A]", 0x0C: "[B]", 0x0D: "[L]", 0x0E: "[R]", 0x0F: "[UP]", 0x10: "[DOWN]", 0x13: "[num]"},
            params={0x02: "fx", 0x03: "face", 0x05: "wait", 0x07: "name"},
            pairs={(0x05, 0x09): "[page]", (0x05, 0x04): "[box]"}, breaks=("[page]", "[box]"))
HOD = Codec(2, _hod_chars(), 0xF006,
            simple={0xF004: "[clear]", 0xF005: "[wait]", 0xF009: "[scroll]"},
            params={0xF001: "insert", 0xF002: "fx", 0xF003: "face", 0xF007: "name"}, pairs={})
CODECS = {"aos": AOS, "hod": HOD}

TAG_RE = re.compile(r"\[(?:(?:fx|face|wait|name|insert):[0-9A-Fa-f]{1,4}|x[0-9A-Fa-f]{2,4}|page|box|A|B|L|R|UP|DOWN|"
                    r"num|clear|wait|scroll)\]")
DESCRIPTIONS = {
    "[page]": "Wait for a button, then a new page", "[box]": "Wait for a button, then a new speaker box",
    "[wait]": "Wait for a button", "[clear]": "Clear the text box", "[scroll]": "Scroll to a new page",
    "[A]": "A button picture", "[B]": "B button picture", "[L]": "L button picture", "[R]": "R button picture",
    "[UP]": "Up arrow picture", "[DOWN]": "Down arrow picture", "[num]": "A number the game fills in",
}
_PARAM_DESCRIPTIONS = {"face": "Portrait", "name": "Speaker name", "insert": "A name the game fills in",
                       "fx": "Effect", "wait": "Wait"}


def describe(tag: str) -> str:
    """A tooltip for a tag."""
    if tag in DESCRIPTIONS:
        return DESCRIPTIONS[tag]
    match = re.fullmatch(r"\[([a-z]+):([0-9A-Fa-f]+)\]", tag)
    if match and match.group(1) in _PARAM_DESCRIPTIONS:
        return f"{_PARAM_DESCRIPTIONS[match.group(1)]} {match.group(2)}"
    if tag.startswith("[x"):
        return "A code with no letter in the font"
    return ""


def line_width(text: str, font_map: Dict[str, dict], default: int) -> int:
    """Pixels of the widest line of ``text`` (``font_map``: character -> {"width"}; tags draw nothing)."""
    best = 0
    for line in str(text).split("\n"):
        total = 0
        for token in re.findall(r"\[[^\[\]\n]*\]|.", line):
            if len(token) > 1:
                continue
            entry = font_map.get(token)
            total += int(entry.get("width", default)) if isinstance(entry, dict) else default
        best = max(best, total)
    return best
