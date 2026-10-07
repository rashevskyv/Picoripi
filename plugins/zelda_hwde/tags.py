"""Hyrule Warriors DE text: game bytes <-> editor text with readable ``{tags}``.

Control codes are ``ESC <letter>`` with one parameter character for some letters:

  ``ESC A n``  ``{c:n}``     colour n (0 names, 2 enemies, 6 places, ...) until ``ESC R``
  ``ESC R``    ``{/c}``      back to the default colour
  ``ESC C n``  ``{C:n}``     colour chosen by side/team n
  ``ESC F n``  ``{form:n}``  grammatical form n of the ``%Ns`` name just before it
                             (the 8/9 form columns of the name tables)
  ``ESC P x``  ``{btn:x}``   controller button icon
  ``ESC K x`` / ``ESC L x``  ``{K:x}`` / ``{L:x}``  element and unit icons
  ``ESC N x`` / ``ESC O x``  ``{N:x}`` / ``{O:x}``  number styling / inserted name
  ``ESC T`` .. ``ESC Z``     ``{ruby}`` .. ``{/ruby}``  Japanese furigana

``%1s``, ``%2s``, ``%s``, ``%d`` are the game's printf placeholders and stay as they are.
A parameter that is not a plain printable character is written ``#HH``. Any other control byte is
``{x:HH}``, any other ESC letter ``{esc:L}``. A literal brace is ``{lb}`` / ``{rb}``.

Characters: the EU/US languages are single-byte cp1252 and the font atlas ``font_eu.g1t`` is a cp1252
grid. Ukrainian needs Cyrillic glyphs, so this plugin reads and writes the cp1251 positions of the
Cyrillic letters (0xC0-0xFF, Ґ ґ Є є І і Ї ї №) on top of cp1252 -- the font must be redrawn to match
(see the format report) -- except × ç é ñ, which the game shows in English and in its language list:
Ч з й с use the free slots of Ъ ъ ы э (0xDA 0xFA 0xFB 0xFD) instead. Wide (UTF-16) cells use the same glyph slots: a character is stored as the
Unicode character cp1252 gives for its byte.
"""

from __future__ import annotations

import re
from typing import List, Union

ESC = 0x1B
_PARAM = {"A": "c", "C": "C", "F": "form", "P": "btn", "K": "K", "L": "L", "N": "N", "O": "O"}
_PLAIN = {"R": "/c", "T": "ruby", "Z": "/ruby"}
_BY_NAME = {name: letter for letter, name in {**_PARAM, **_PLAIN}.items()}

DESCRIPTIONS = {
    "c": "Colour until {/c} (0 names, 1 allies, 2 enemies, 6 places)",
    "/c": "Back to the default colour",
    "C": "Colour chosen by side or team",
    "form": "Grammatical form of the %Ns name just before it (column of the name table)",
    "btn": "Controller button icon",
    "K": "Element icon",
    "L": "Unit or element icon",
    "N": "Number style",
    "O": "Inserted name",
    "ruby": "Japanese furigana start",
    "/ruby": "Japanese furigana end",
}

TAG_RE = re.compile(r"\{(?:/?[A-Za-z]+(?::[^{}]*)?)\}")
PLACEHOLDER_RE = re.compile(r"%[0-9]?[sd]")

# -- code page -----------------------------------------------------------------

_CYRILLIC_SLOTS = list(range(0xC0, 0x100)) + [0xA5, 0xB4, 0xAA, 0xBA, 0xB2, 0xB3, 0xAF, 0xBF, 0xB9]


def _cp1252(b: int) -> str:
    try:
        return bytes([b]).decode("cp1252")
    except UnicodeDecodeError:
        return chr(b)  # the five holes of cp1252 keep their Latin-1 value


# The English text and the language list (shown in every language) use × ç é ñ: those slots stay Latin, and
# their Cyrillic letters Ч з й с take the slots of Russian-only letters (Ъ ъ ы э), which Ukrainian never uses.
_LATIN_KEPT = (0xD7, 0xE7, 0xE9, 0xF1)
MOVED = {0xDA: "Ч", 0xFA: "з", 0xFB: "й", 0xFD: "с"}

DECODE = [_cp1252(b) for b in range(256)]
for _b in _CYRILLIC_SLOTS:
    if _b not in _LATIN_KEPT:
        DECODE[_b] = bytes([_b]).decode("cp1251")
for _b, _ch in MOVED.items():
    DECODE[_b] = _ch
ENCODE = {ch: b for b, ch in enumerate(DECODE)}
_CP1252_BYTE = {_cp1252(b): b for b in range(256)}

Unit = Union[int, str]  # a byte value, or a character that has no byte (only in wide cells)


def units_from_wide(raw: bytes) -> List[Unit]:
    out: List[Unit] = []
    for i in range(0, len(raw) - 1, 2):
        ch = chr(raw[i] | raw[i + 1] << 8)
        out.append(_CP1252_BYTE.get(ch, ch))
    return out


def wide_from_units(units: List[Unit]) -> bytes:
    return "".join(_cp1252(u) if isinstance(u, int) else u for u in units).encode("utf-16-le")


# -- editor text ---------------------------------------------------------------


def _param(u: Unit) -> str:
    ch = DECODE[u] if isinstance(u, int) else u
    if 0x21 <= ord(ch) < 0x7F and ch not in "{}:#":
        return ch
    return f"#{u:02X}" if isinstance(u, int) else f"#{ord(ch):04X}"


def to_editor(units: List[Unit]) -> str:
    out = []
    i = 0
    while i < len(units):
        u = units[i]
        if u == ESC:
            letter = DECODE[units[i + 1]] if i + 1 < len(units) and isinstance(units[i + 1], int) else ""
            if letter in _PARAM and i + 2 < len(units):
                out.append(f"{{{_PARAM[letter]}:{_param(units[i + 2])}}}")
                i += 3
                continue
            if letter in _PLAIN:
                out.append(f"{{{_PLAIN[letter]}}}")
            elif letter and letter.isalpha() and letter.isascii():
                out.append(f"{{esc:{letter}}}")
            else:
                out.append("{x:1B}")
                i += 1
                continue
            i += 2
            continue
        if isinstance(u, str):
            out.append(u)
        elif u == 0x7B:
            out.append("{lb}")
        elif u == 0x7D:
            out.append("{rb}")
        elif u < 0x20 and u != 0x0A:
            out.append(f"{{x:{u:02X}}}")
        else:
            out.append(DECODE[u])
        i += 1
    return "".join(out)


def _param_units(value: str) -> List[Unit]:
    if value.startswith("#") and len(value) in (3, 5):
        n = int(value[1:], 16)
        return [n] if len(value) == 3 else [_CP1252_BYTE.get(chr(n), chr(n))]
    if len(value) != 1:
        raise ValueError(f"tag parameter must be one character: {value!r}")
    return [ENCODE[value]]


def parse_tag(tag: str) -> List[Unit]:
    """Units of one ``{tag}``; ValueError when it is not a tag of this game."""
    m = re.fullmatch(r"\{(/?[A-Za-z]+)(?::([^{}]*))?\}", tag)
    if not m:
        raise ValueError(f"not a tag: {tag!r}")
    name, arg = m.group(1), m.group(2)
    if name == "lb" and arg is None:
        return [0x7B]
    if name == "rb" and arg is None:
        return [0x7D]
    if name == "x" and arg is not None and re.fullmatch(r"[0-9A-Fa-f]{2}", arg):
        return [int(arg, 16)]
    if name == "esc" and arg is not None and len(arg) == 1 and arg.isalpha():
        return [ESC, ord(arg)]
    letter = _BY_NAME.get(name)
    if letter is None:
        raise ValueError(f"unknown tag: {tag!r}")
    if letter in _PARAM:
        if arg is None:
            raise ValueError(f"{tag!r} needs a parameter")
        return [ESC, ord(letter), *_param_units(arg)]
    if arg is not None:
        raise ValueError(f"{tag!r} takes no parameter")
    return [ESC, ord(letter)]


def from_editor(text: str) -> List[Unit]:
    """Editor text back to units. A character outside the code page becomes a str unit."""
    out: List[Unit] = []
    pos = 0
    for m in TAG_RE.finditer(text):
        out.extend(ENCODE.get(ch, ch) for ch in text[pos : m.start()])
        out.extend(parse_tag(m.group()))
        pos = m.end()
    out.extend(ENCODE.get(ch, ch) for ch in text[pos:])
    return out


def describe(tag: str) -> str:
    m = re.fullmatch(r"\{(/?[A-Za-z]+)(?::([^{}]*))?\}", tag or "")
    if not m:
        return ""
    return DESCRIPTIONS.get(m.group(1), "")
