"""Vagrant Story text bytes <-> editor text.

One byte is one glyph of the 12x12 font in ``BATTLE/SYSTEM.DAT`` (cell = code, 21 cells a row):
``0x00-0x09`` digits, ``0x0A-0x23`` A-Z, ``0x24-0x3D`` a-z, ``0x3E-0x6A`` accented Latin,
``0x86-0xB9`` punctuation and symbols, ``0x8F`` the space. ``0xE7`` ends a string, ``0xE8`` breaks a
line, ``0xEB`` pads a string to an even length. Codes from ``0xEC`` take one parameter byte; the
editor shows them as readable tags:

=========  =================================  ==========================================
bytes      tag                                meaning (rood-reverse decompilation)
=========  =================================  ==========================================
E5         ``{page}``                         new page
E6         ``{wait}``                         continuation arrow, waits for a button
FA nn      ``{>nn}`` / ``{<nn}``              move the pen right / left nn pixels
                                              (``FA 06`` is shown as a space)
FB nn      ``{down nn}``                      move the pen down nn pixels (nn*8 >= 8)
FB 00-03   ``{color n}``                      text colour
FB 04      ``{center}``                       centre the lines (toggle)
FB 05/06   ``{italic}`` / ``{regular}``       font table 1 (italic) / 0
F8 nn      ``{speed nn}``                     characters per frame (0 = all at once)
F9 nn      ``{sfx nn}``                       sound after each chunk
FD/FE/FF   ``{hex n}`` ``{num n}`` ``{str n}``  printed argument n
other      ``{xNN}`` / ``{xNN:pp}``           raw byte (and its parameter)
=========  =================================  ==========================================

Ukrainian letters reach the game through the translation map: ``{"Б": "À"}`` draws Б with the
glyph of À, so it is written as À's code. The empty cells 0x6B-0x85 are named ``Å å Ø ø ...``
(``EMPTY_CELLS``) so a letter can be put there the same way.
A space is written as 0x8F (one byte; the game draws it 6 pixels wide like ``FA 06``).
"""
from __future__ import annotations

import re
from typing import Dict, Iterable, List, Optional, Set, Tuple

END, NEWLINE, PAD, SPACE = 0xE7, 0xE8, 0xEB, 0x8F
PARAM_FIRST = 0xEC                       # codes from here take one parameter byte
JAPANESE = range(0xEC, 0xF8)             # font pages of the Japanese build (never in English text)

_LATIN_EXTRA = "ŒÀÁÂÄÇÈÉÊËÌÍÎÏÒÓÔÖÙÚÛÜßœàáâäçèéêëìíîïòóôöùúûü"
# 0xAB/0xAC are '{' '}' in the font; the editor shows them full width so they never read as a tag.
_SYMBOLS = "„‼≠≦≧÷·—⋯ !\"#$%&'()=@[];:,./\\<>?_-+*`｛｝♪△□○×←→↑↓"

CHARS: Dict[int, str] = {}
for _i in range(10):
    CHARS[_i] = chr(48 + _i)
for _i in range(26):
    CHARS[0x0A + _i] = chr(65 + _i)
    CHARS[0x24 + _i] = chr(97 + _i)
for _i, _c in enumerate(_LATIN_EXTRA):
    CHARS[0x3E + _i] = _c
for _i, _c in enumerate(_SYMBOLS):
    CHARS[0x86 + _i] = _c
CHARS[0xB7], CHARS[0xB8], CHARS[0xB9] = "★", "◼", "~"
# The 27 cells after ü are empty in the game's font. They are named with Latin-1 letters the game
# does not have, so the translation map and the font editor can put Ukrainian letters on them.
EMPTY_CELLS = range(0x6B, 0x86)
for _i, _c in enumerate("ÅåØøÃãÕõÝýÞþÐð¿¡ªº°±²³µ¶¹¼½"):
    CHARS[EMPTY_CELLS[0] + _i] = _c
LV = 0xB6                                 # one glyph "Lv."
CODES: Dict[str, int] = {char: code for code, char in CHARS.items()}

SIMPLE_TAGS = {0xE5: "{page}", 0xE6: "{wait}", LV: "{Lv}"}
_FB_NAMES = {0: "{color 0}", 1: "{color 1}", 2: "{color 2}", 3: "{color 3}", 4: "{center}",
             5: "{italic}", 6: "{regular}"}
_PARAM_NAMES = {0xF8: "speed", 0xF9: "sfx", 0xFD: "hex", 0xFE: "num", 0xFF: "str"}

TAG_RE = re.compile(r"\{[^{}\n]*\}")
_TAG_PARSE = [
    (re.compile(r"\{>(\d+)\}"), lambda m: bytes((0xFA, int(m.group(1))))),
    (re.compile(r"\{<(\d+)\}"), lambda m: bytes((0xFA, 256 - int(m.group(1))))),
    (re.compile(r"\{down (\d+)\}"), lambda m: bytes((0xFB, int(m.group(1)) << 3))),
    (re.compile(r"\{x([0-9A-Fa-f]{2}):([0-9A-Fa-f]{2})\}"), lambda m: bytes((int(m.group(1), 16), int(m.group(2), 16)))),
    (re.compile(r"\{x([0-9A-Fa-f]{2})\}"), lambda m: bytes((int(m.group(1), 16),))),
]
for _code, _name in _PARAM_NAMES.items():
    _TAG_PARSE.append((re.compile(r"\{%s (\d+)\}" % _name), lambda m, c=_code: bytes((c, int(m.group(1))))))
_TAG_EXACT = {tag: bytes((code,)) for code, tag in SIMPLE_TAGS.items()}
_TAG_EXACT.update({tag: bytes((0xFB, value)) for value, tag in _FB_NAMES.items()})


def is_japanese(raw: bytes) -> bool:
    """A string of the Japanese leftovers (debug events): it uses the kanji pages."""
    return any(kind in JAPANESE for kind, _value in tokens(raw) if kind >= PARAM_FIRST)


def tokens(raw: bytes) -> List[Tuple[int, Optional[int]]]:
    """``(code, parameter or None)`` of a string up to its end byte (alignment pads dropped)."""
    out = []
    i, n = 0, len(raw)
    while i < n:
        code = raw[i]
        if code == END:
            break
        if code >= PARAM_FIRST and i + 1 < n:
            out.append((code, raw[i + 1]))
            i += 2
            continue
        if code != PAD:
            out.append((code, None))
        i += 1
    return out


def string_end(data: bytes, start: int) -> int:
    """Offset just after the end byte of the string at ``start`` (parameters may be 0xE7)."""
    i, n = start, len(data)
    while i < n:
        code = data[i]
        if code == END:
            return i + 1
        i += 2 if code >= PARAM_FIRST else 1
    return n


def decode(raw: bytes, reverse_map: Optional[Dict[int, str]] = None) -> str:
    """Editor text of one string; ``reverse_map`` names the codes the translation map took
    (``{0x3F: "Б"}``)."""
    out = []
    for code, param in tokens(raw):
        if param is None:
            if reverse_map and code in reverse_map:
                out.append(reverse_map[code])
            elif code in CHARS:
                out.append(CHARS[code])
            elif code == NEWLINE:
                out.append("\n")
            elif code in SIMPLE_TAGS:
                out.append(SIMPLE_TAGS[code])
            else:
                out.append("{x%02X}" % code)
        elif code == 0xFA:
            if param == 6:
                out.append(" ")
            elif param >= 240:
                out.append("{<%d}" % (256 - param))
            else:
                out.append("{>%d}" % param)
        elif code == 0xFB:
            if param & 0xF8:
                out.append("{down %d}" % (param >> 3) if not param & 7 else "{xFB:%02X}" % param)
            else:
                out.append(_FB_NAMES.get(param, "{xFB:%02X}" % param))
        elif code in _PARAM_NAMES:
            out.append("{%s %d}" % (_PARAM_NAMES[code], param))
        else:
            out.append("{x%02X:%02X}" % (code, param))
    return "".join(out)


_WORD = re.compile(r"[^\W\d_]+")


class Reader:
    """Decodes strings of a translation: the codes the translation map took read as their letters,
    and in a line that has such a letter, a word written only with letters that look alike in Latin
    and Cyrillic (``Cин``, ``a``) reads as Cyrillic -- but not an abbreviation in capitals (``HP``)."""

    def __init__(self, reverse_map: Optional[Dict[int, str]] = None, lookalike: Optional[Dict[str, str]] = None):
        self.reverse_map = reverse_map or {}
        self.lookalike = lookalike or {}
        self.unique = set(self.reverse_map.values())

    def __call__(self, raw: bytes) -> str:
        text = decode(raw, self.reverse_map)
        if not self.lookalike or not any(char in self.unique for char in text):
            return text
        pieces, pos = [], 0
        for match in TAG_RE.finditer(text):
            pieces.append(_WORD.sub(self._word, text[pos:match.start()]))
            pieces.append(match.group(0))
            pos = match.end()
        pieces.append(_WORD.sub(self._word, text[pos:]))
        return "".join(pieces)

    def _word(self, match) -> str:
        word = match.group(0)
        if not all(char in self.lookalike or char in self.unique for char in word):
            return word
        if len(word) >= 2 and word.isupper() and all(char in self.lookalike for char in word):
            return word
        return "".join(self.lookalike.get(char, char) for char in word)


def encode(text: str, char_codes: Optional[Dict[str, int]] = None, missing: Optional[Set[str]] = None) -> bytes:
    """Game bytes of editor text without the end byte; ``char_codes`` are the translation map's
    letters (``{"Б": 0x3F}``). A character with no glyph becomes ``?`` and goes to ``missing``."""
    out = bytearray()
    pos = 0
    for match in TAG_RE.finditer(text):
        out += _encode_plain(text[pos:match.start()], char_codes, missing)
        out += _encode_tag(match.group(0))
        pos = match.end()
    out += _encode_plain(text[pos:], char_codes, missing)
    return bytes(out)


def _encode_tag(tag: str) -> bytes:
    if tag in _TAG_EXACT:
        return _TAG_EXACT[tag]
    for pattern, make in _TAG_PARSE:
        match = pattern.fullmatch(tag)
        if match:
            return make(match)
    raise ValueError(f"Unknown tag {tag}")


def _encode_plain(text: str, char_codes: Optional[Dict[str, int]], missing: Optional[Set[str]]) -> bytes:
    out = bytearray()
    for char in text:
        if char == "\n":
            out.append(NEWLINE)
        elif char_codes and char in char_codes:
            out.append(char_codes[char])
        elif char in CODES:
            out.append(CODES[char])
        else:
            if missing is not None:
                missing.add(char)
            out.append(CODES["?"])
    return bytes(out)


def terminate(body: bytes, pad: bool = True) -> bytes:
    """``body`` with its end byte, padded with 0xEB to an even length (string tables need it)."""
    raw = body + bytes((END,))
    return raw + bytes((PAD,)) if pad and len(raw) % 2 else raw


def tags_in(text: str) -> Iterable[str]:
    return (match.group(0) for match in TAG_RE.finditer(text))


# -- widths ---------------------------------------------------------------------------------

def line_widths(raw: bytes, widths: List[int], char_codes_width: Optional[Dict[int, int]] = None) -> List[int]:
    """Pixel width of each line of a string as the dialog renderer draws it: the advance of each
    glyph (``widths``, BATTLE.PRG's table; table 1 for italic) plus ``FA`` moves."""
    lines = [0]
    italic = 0
    for code, param in tokens(raw):
        if param is None:
            if code == NEWLINE or code == 0xE5:
                lines.append(0)
            elif code < 0xE5:
                index = code + italic * 0xBD
                lines[-1] += widths[index] if index < len(widths) else 6
        elif code == 0xFA:
            lines[-1] += param - 256 if param >= 240 else param
        elif code == 0xFB and param in (5, 6):
            italic = 1 if param == 5 else 0
        elif code == 0xFE and param > 9:
            lines[-1] += (param // 10) * 6
    return lines
