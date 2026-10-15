"""Text codes of Final Fantasy Tactics Advance (GBA, USA), both ways, and the game's LZSS decoder.

Facts (Data Crystal's FFTA pages, checked against the game's reader at 0x08013E9C-0x080142D8):

- A character is two bytes, big endian ``80XX``-``8CXX``: ``80A6``-``80AF`` digits, ``80B0``-``80C9`` A-Z,
  ``80CA``-``80E3`` a-z, ``80E4``-``8122`` punctuation and symbols, ``8000``-``80A5`` kana, ``8123`` on kanji.
- ``40 XX`` is a control: ``40 73`` space, ``40 6E`` new line; ``CONTROL_PARAMS`` gives the bytes that follow
  (the reader's jump table at 0x080140AC). ``40 53 XY`` (a two-way choice) is followed by two pieces of text, each
  ended by ``00``; the editor shows those two ends as ``[sep]``. ``00`` ends the string. The editor shows a line
  break after a ``[clear]`` that does not end the text (a new page); that line break is not written.
- Strings of the pointer tables (``rom_text.ABS_TABLES``) have no header. One that starts with ``01`` is
  single-byte: each byte is the low byte of an ``80XX`` code plus one, ``00`` ends it.
- Strings of the offset tables start with a u16 header (``rom_text``): bit 0 single-byte (another dialect: bytes
  below 0x80 are ``80XX`` codes, 0x80-0x96 controls, ``FF`` ends), bit 1 LZSS (``lzss_decode``), the other bits are
  the window and stay as they are.

The game has no Cyrillic. ``UA_CODES`` gives each Ukrainian letter a kana code (only Japanese leftover strings use
them); the letters are drawn into those cells of the font by the translator. A character with no code is refused by name.
"""
from __future__ import annotations

import re
import struct
from typing import Dict, List, Tuple

from core.i18n import tr

UA_LETTERS = "АБВГҐДЕЄЖЗИІЇЙКЛМНОПРСТУФХЦЧШЩЬЮЯабвгґдеєжзиіїйклмнопрстуфхцчшщьюя"
UA_FIRST = 0x8053                      # katakana ァ onwards: 66 cells, all below 0x80A0
UA_CODES: Dict[str, int] = {letter: UA_FIRST + i for i, letter in enumerate(UA_LETTERS)}

_PUNCTUATION = {
    0x80E4: ".", 0x80E5: "「", 0x80E6: "」", 0x80E7: "『", 0x80E8: "』", 0x80E9: "…", 0x80EA: "?", 0x80EB: "!",
    0x80EC: ",", 0x80ED: "·", 0x80EE: ":", 0x80EF: "_", 0x80F0: "々", 0x80F1: "/", 0x80F2: "~", 0x80F3: "‘",
    0x80F4: "'", 0x80F5: "“", 0x80F6: "\"", 0x80F7: "(", 0x80F8: ")", 0x80F9: "{", 0x80FA: "}", 0x80FB: "［",
    0x80FC: "］", 0x80FD: "+", 0x80FE: "-", 0x80FF: "±", 0x8100: "×", 0x8101: "=", 0x8102: "<", 0x8103: ">",
    0x8104: "∞", 0x8105: "♂", 0x8106: "♀", 0x8107: "%", 0x8108: "&", 0x8109: "*", 0x810A: "▒", 0x810B: "—",
    0x810C: "|", 0x810D: "▲", 0x810E: "▼", 0x810F: "◀", 0x8110: "▶", 0x8111: "○", 0x8112: "△", 0x8113: "□",
    0x8114: "■", 0x8115: "♪", 0x8116: ";", 0x8117: "◎", 0x8122: "ー",
}


def _chars() -> Dict[int, str]:
    chars = {0x80A6 + i: str(i) for i in range(10)}
    chars.update({0x80B0 + i: chr(65 + i) for i in range(26)})
    chars.update({0x80CA + i: chr(97 + i) for i in range(26)})
    chars.update(_PUNCTUATION)
    chars.update({0x8118 + i: chr(0xFF10 + i) for i in range(10)})     # the fixed-width digits
    chars.update({code: letter for letter, code in UA_CODES.items()})
    return chars


CHARS: Dict[int, str] = _chars()
CODES: Dict[str, int] = {char: code for code, char in CHARS.items()}

# Control code -> bytes of parameters after ``40 XX`` (0x80140AC). Codes not listed take none.
CONTROL_PARAMS = {0x21: 1, 0x25: 1, 0x3C: 1, 0x3E: 1, 0x53: 1, 0x66: 2, 0x67: 1, 0x6C: 1, 0x72: 1, 0x74: 1}
# The controls the reader knows; any other ``40 XX`` is not text.
KNOWN_CONTROLS = set(CONTROL_PARAMS) | {0x61, 0x62, 0x63, 0x6B, 0x6E, 0x70, 0x73, 0x75, 0x77, 0x78, 0x79}
NAMES = {0x61: "wait", 0x63: "clear", 0x70: "next", 0x72: "crn", 0x25: "var", 0x3E: "sp", 0x74: "delay",
         0x53: "choice"}
NEWLINE, SPACE, CHOICE, CLEAR = 0x6E, 0x73, 0x53, 0x63
_NAME_CODES = {name: code for code, name in NAMES.items()}

TAG_RE = re.compile(r"\[(?:wait|clear|next|sep|(?:crn|var|sp|delay|choice):[0-9A-F]{2}|c[0-9A-F]{2}(?::[0-9A-F]{2,4})?"
                    r"|x[0-9A-F]{4})\]")
DESCRIPTIONS = {
    "[wait]": "Wait for a button", "[clear]": "Clear the text box", "[next]": "Wait for a button, then a new page",
    "[sep]": "End of a choice answer",
}
_PARAM_DESCRIPTIONS = {"crn": "A character's name (CRN number)", "var": "A name or number the game fills in",
                       "sp": "A space of this many pixels", "delay": "Pause (tenths of a second)",
                       "choice": "A two-way choice; the two answers follow, each ended by [sep]"}


class EncodeError(ValueError):
    """A text that cannot be written in the game's codes; ``char`` is the character with no code, if that is why."""

    def __init__(self, message: str, char: str = ""):
        super().__init__(message)
        self.char = char


def describe(tag: str) -> str:
    """A tooltip for a tag."""
    if tag in DESCRIPTIONS:
        return DESCRIPTIONS[tag]
    match = re.fullmatch(r"\[([a-z]+):([0-9A-F]+)\]", tag)
    if match and match.group(1) in _PARAM_DESCRIPTIONS:
        return f"{_PARAM_DESCRIPTIONS[match.group(1)]} ({match.group(2)})"
    if tag.startswith("[x"):
        return "A character code with no letter in the editor (kana, kanji or a symbol)"
    if tag.startswith("[c"):
        return "A game control code"
    return ""


# -- two-byte text ---------------------------------------------------------------------------------------

def decode_db(data: bytes) -> str:
    """Editor text of a two-byte body (without its final ``00``). Raises ValueError for bytes that are not text."""
    out: List[str] = []
    i, seps = 0, 0
    while i < len(data):
        b = data[i]
        if b == 0:
            if not seps:
                raise ValueError("a 00 byte inside the text")
            out.append("[sep]")
            seps -= 1
            i += 1
            continue
        if b == 0x40:
            if i + 1 >= len(data) or data[i + 1] not in KNOWN_CONTROLS:
                raise ValueError("an unknown control code")
            code = data[i + 1]
            count = CONTROL_PARAMS.get(code, 0)
            params = data[i + 2:i + 2 + count]
            if len(params) != count:
                raise ValueError("a control code is cut off")
            if code == NEWLINE:
                out.append("\n")
            elif code == SPACE:
                out.append(" ")
            else:
                name = NAMES.get(code, f"c{code:02X}")
                out.append(f"[{name}:{params.hex().upper()}]" if count else f"[{name}]")
            if code == CHOICE:
                seps += 2
            i += 2 + count
            if code == CLEAR and i < len(data):
                out.append("\n")                      # a cleared box starts a new page: shown on a new line
            continue
        if i + 1 >= len(data):
            raise ValueError("a character is cut off")
        code = b << 8 | data[i + 1]
        out.append(CHARS.get(code) or f"[x{code:04X}]")
        i += 2
    if seps:
        raise ValueError("a choice without its two answers")
    return "".join(out)


def _tokens(text: str) -> List[str]:
    return re.findall(r"\[[^\[\]\n]*\]|\n|.", str(text), flags=re.S)


def encode_db(text: str) -> bytes:
    """The two-byte body of editor text (without the final ``00``). Raises EncodeError naming a character with no code."""
    out = bytearray()
    tokens = _tokens(text)
    for n, token in enumerate(tokens):
        if token == "\n" and n and tokens[n - 1] == "[clear]":
            continue                                  # the line break shown after a cleared box
        if token == "\n":
            out += bytes((0x40, NEWLINE))
        elif token == " ":
            out += bytes((0x40, SPACE))
        elif token == "[sep]":
            out.append(0)
        elif token in CODES:
            out += struct.pack(">H", CODES[token])
        elif match := re.fullmatch(r"\[x([0-9A-F]{4})\]", token):
            code = int(match.group(1), 16)
            if code >> 8 in (0, 0x40):
                raise EncodeError(tr("{0} is not a character code", token))
            out += struct.pack(">H", code)
        elif match := re.fullmatch(r"\[([a-z]+|c[0-9A-F]{2})(?::([0-9A-F]{2,4}))?\]", token):
            name, params = match.group(1), bytes.fromhex(match.group(2) or "")
            code = int(name[1:], 16) if re.fullmatch(r"c[0-9A-F]{2}", name) else _NAME_CODES.get(name)
            if code is None or code not in KNOWN_CONTROLS or len(params) != CONTROL_PARAMS.get(code, 0):
                raise EncodeError(tr("Unknown tag {0}", token))
            out += bytes((0x40, code)) + params
        else:
            raise EncodeError(f"The character {token!r} has no code in the game's font", token)
    return bytes(out)


def unknown_chars(text: str) -> List[str]:
    """Characters of ``text`` (outside tags) the game has no code for."""
    return sorted({token for token in _tokens(text) if len(token) == 1 and token not in "\n " and token not in CODES})


# -- single-byte text (pointer tables) ---------------------------------------------------------------------

def decode_sb(data: bytes) -> str:
    """Editor text of a single-byte body (after ``01``, without its ``00``)."""
    out = []
    for b in data:
        code = 0x8000 + b - 1
        out.append(CHARS.get(code) or f"[x{code:04X}]")
    return "".join(out)


def encode_sb(text: str) -> bytes:
    """The single-byte body of ``text``, or raises EncodeError when a character cannot be written that way."""
    out = bytearray()
    for token in _tokens(text):
        code = CODES.get(token)
        match = re.fullmatch(r"\[x([0-9A-F]{4})\]", token)
        if match:
            code = int(match.group(1), 16)
        if code is None or not 0x8000 <= code <= 0x80FE:
            raise EncodeError(f"{token!r} cannot be written in a single-byte name")
        out.append(code - 0x8000 + 1)
    return bytes(out)


# -- strings of the pointer tables ------------------------------------------------------------------------

def plain_length(data: bytes, at: int) -> int:
    """Bytes of the header-less string at ``at`` (its ``00`` included)."""
    if data[at] == 1:
        return data.index(b"\0", at + 1) + 1 - at
    i, seps = at, 0
    while True:
        b = data[i]
        if b == 0:
            if not seps:
                return i + 1 - at
            seps -= 1
            i += 1
        elif b == 0x40:
            if data[i + 1] == CHOICE:
                seps += 2
            i += 2 + CONTROL_PARAMS.get(data[i + 1], 0)
        else:
            i += 2


def decode_plain(raw: bytes) -> str:
    """Editor text of a whole pointer-table string (``raw`` ends with its ``00``)."""
    if raw[:1] == b"\x01":
        return decode_sb(raw[1:-1])
    return decode_db(raw[:-1])


def encode_plain(text: str, single_byte: bool) -> bytes:
    """A pointer-table string: single-byte when the original was and the text allows it, else two-byte."""
    if single_byte:
        try:
            return b"\x01" + encode_sb(text) + b"\0"
        except EncodeError:
            pass
    return encode_db(text) + b"\0"


# -- LZSS --------------------------------------------------------------------------------------------------

def lzss_decode(data: bytes, at: int) -> Tuple[bytes, int]:
    """The FFTA LZSS stream at ``at`` (u32 big-endian size, then the codes): ``(bytes, length of the stream)``."""
    size = struct.unpack_from(">I", data, at)[0]
    out = bytearray()
    p = at + 4

    def copy(length: int, distance: int) -> None:
        for _ in range(length):
            out.append(out[len(out) - distance] if len(out) >= distance else out[0] if out else 0)

    while len(out) < size:
        c = data[p]
        if c & 0x80:
            copy(((c >> 3) & 0xF) + 3, ((c & 7) << 8 | data[p + 1]) + 1)
            p += 2
        elif c & 0x40:
            n = (c & 0x3F) + 1
            out += data[p + 1:p + 1 + n]
            p += 1 + n
        elif c & 0x20:
            out += bytes((c & 0x1F) + 2)
            p += 1
        elif c & 0x10:
            copy(((data[p + 1] >> 6) << 4 | (c & 0xF)) + 4, ((data[p + 1] & 0x3F) << 8 | data[p + 2]) + 1)
            p += 3
        elif c == 2:
            out += bytes(data[p + 1] + 3)
            p += 2
        elif c == 1:
            out += b"\xff" * (data[p + 1] + 3)
            p += 2
        elif c == 0:
            copy(data[p + 1] + 5, (data[p + 2] << 8 | data[p + 3]) + 1)
            p += 4
        else:
            p += 1
        if p > len(data):
            raise ValueError("the LZSS stream runs past the end of the data")
    return bytes(out[:size]), p - at


def line_width(text: str, font_map: Dict[str, dict], default: int) -> int:
    """Pixels of the widest line of ``text`` (``font_map``: character -> {"width"}; ``[sp:XX]`` adds XX)."""
    best = 0
    for line in str(text).split("\n"):
        total = 0
        for token in _tokens(line):
            if token.startswith("[sp:"):
                total += int(token[4:6], 16)
            elif token.startswith("[x"):
                total += default
            elif len(token) == 1:
                entry = font_map.get(token)
                total += int(entry.get("width", default)) if isinstance(entry, dict) else default
        best = max(best, total)
    return best
