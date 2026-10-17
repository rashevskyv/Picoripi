"""Text of the Silent Hill PAL disc (Ukrainian English slot): the glyph codec of the PAL font.

The PAL font sheet (1ST\\FONT16.TIM, 21 x 6 cells, 12 x 16 each) is read by glyph index = byte - 39. A message
with a byte from 0x80 up uses this table (the Ukrainian text); a message without such a byte is plain ASCII
and uses ``codec`` (the English text). The table comes from reading the sheet and the Ukrainian words in the
game files (for example "Мо" + "жлив" + "о," = "Можливо,"). A byte 0xFE is shown as "х" and 0xFF as "ц": the
translation writes them that way and the sheet has no cell for them. Cells that no text uses have no label
and show as ``{XX}``.
"""
from __future__ import annotations

import re
from typing import Dict, List, Optional

from . import codec

FIRST_CODE = 39
BRACE_OPEN, BRACE_CLOSE = 0x7B, 0x7D     # the game's code brackets: {J0(2.5)} is written with ASCII inside
CODE_OPEN, CODE_CLOSE = "⟨", "⟩"   # shown as angle brackets, so they never look like a {XX} tag
_TAG_RE = re.compile(r"\{([0-9A-Fa-f]{2})\}")

# Label of each cell, index = glyph (byte - 39). Several cells can carry one letter; _CANONICAL picks the one written.
_LABELS: List[Optional[str]] = [None] * 126


def _put(start: int, chars: str) -> None:
    for i, ch in enumerate(chars):
        _LABELS[start + i] = ch


_put(0, "'()=+,-./0123456789:;<—>?*")       # 0..25 (22 is the em dash)
_put(26, "АБВГДЕЖЗИЙКЛМНОПРСТУФХЦЧШЩ")             # 26..51 capitals
_put(52, "«!»& '")                      # 52..57 (56 is the space)
_put(58, "абсде")                                 # 58..62
_LABELS[63] = "і"
_LABELS[64] = " "
_LABELS[65] = None                                # used 3 times, not read yet
_LABELS[66] = "і"
_LABELS[67] = "…"                            # ellipsis
_LABELS[68] = " "
_LABELS[69] = "І"
_LABELS[70:78] = ["т", "п", "о", "р", None, "а", "и", "к"]   # 70..77
_LABELS[78:83] = ["ш", None, None, "х", "у"]                 # 78..82
_LABELS[83] = "?"                                            # used once: "маяк?"
_LABELS[84] = None                                           # 0x7B: a brace, not a letter
_LABELS[85:90] = ["Ґ", None, "Є", "Ю", "Я"]                   # 85 Ґ; 86 0x7D: a brace; 87..89 capitals
_LABELS[90:94] = ["ф", "щ", "ч", "ь"]                         # 90..93
_LABELS[94] = None
_LABELS[95:107] = ["а", "б", "в", "г", "д", "ж", "з", "и", "й", "к", "л", "м"]   # 95..106
_LABELS[107] = "н"
_LABELS[108] = None
_LABELS[109:126] = ["п", "р", "с", "т", "у", "ф", "х", "ц", "ч", "ш", "щ", "ї", "ґ", "ь", "є", "ю", "я"]

# The cell written for a letter that has more than one cell (the most used one in the Ukrainian text).
_CANONICAL: Dict[str, int] = {
    "а": 95, "і": 66, "с": 60, "д": 99, "е": 62, "б": 96, "к": 104, "ш": 118, "щ": 91, "ь": 93,
    "ф": 90, "ч": 92, "у": 82, "р": 110, "п": 109, "т": 112, "и": 102,
}
# The translation writes these two letters as the bytes below (no sheet cell is used for them).
_SPECIAL_BYTES = {"х": 0xFE, "ц": 0xFF}
_SPECIAL_CHARS = {0xFE: "х", 0xFF: "ц"}

_BYTE_OF: Dict[str, int] = {}
for _cell, _label in enumerate(_LABELS):
    if _label is not None:
        _BYTE_OF.setdefault(_label, _cell + FIRST_CODE)
for _label, _cell in _CANONICAL.items():
    _BYTE_OF[_label] = _cell + FIRST_CODE
_BYTE_OF.update(_SPECIAL_BYTES)
_BYTE_OF.update({"—": 22 + FIRST_CODE, "«": 52 + FIRST_CODE, "»": 54 + FIRST_CODE,
                 "…": 67 + FIRST_CODE, " ": 56 + FIRST_CODE})


def _is_glyph_message(raw: bytes) -> bool:
    return any(b >= 0x80 for b in raw)


def byte_of(ch: str) -> int:
    """The byte the translation writes for one character (raises KeyError for a letter the sheet lacks)."""
    return _BYTE_OF[ch]


def decode_message(raw: bytes) -> str:
    """Editor text of one message. Glyph text when the message has a byte from 0x80 up, plain ASCII otherwise."""
    if not _is_glyph_message(raw):
        return codec.decode(raw)
    return decode_glyph(raw)


def decode_glyph(raw: bytes) -> str:
    """Glyph text of a message, whatever its bytes (the menus and the credits are ASCII-looking)."""
    out = []
    i = 0
    in_code = False
    while i < len(raw):
        b = raw[i]
        if b == BRACE_OPEN:
            out.append(CODE_OPEN)
            in_code = True
        elif b == BRACE_CLOSE:
            out.append(CODE_CLOSE)
            in_code = False
        elif in_code and 0x20 <= b < 0x7F:                                  # a control code is ASCII inside braces
            out.append(chr(b))
        elif b == 0x5C and i + 1 < len(raw) and raw[i + 1] in (0x6E, 0x74):   # backslash n / backslash t: line, tab
            out.append("\\n" if raw[i + 1] == 0x6E else "\\t")
            i += 2
            continue
        elif b in _SPECIAL_CHARS:
            out.append(_SPECIAL_CHARS[b])
        elif FIRST_CODE <= b < FIRST_CODE + 126 and _LABELS[b - FIRST_CODE] is not None:
            out.append(_LABELS[b - FIRST_CODE])
        else:
            out.append("{%02X}" % b)
        i += 1
    return "".join(out)


def encode_message(text: str, original: bytes) -> bytes:
    """Bytes of an edited text. The mode (glyph or plain) is the one of the message's original bytes; a new
    message (no original bytes) is glyph text when it has a character from 0x80 up."""
    glyph = _is_glyph_message(original) if original else any(ord(c) >= 0x80 for c in text)
    if not glyph:
        return codec.encode(text)
    return encode_glyph(text)


def encode_glyph(text: str) -> bytes:
    """Glyph bytes of a text (the reverse of decode_glyph)."""
    out = bytearray()
    i = 0
    in_code = False
    while i < len(text):
        if text.startswith("\\n", i):
            out += b"\x5c\x6e"
            i += 2
            continue
        if text.startswith("\\t", i):
            out += b"\x5c\x74"
            i += 2
            continue
        m = _TAG_RE.match(text, i)
        if m:
            out.append(int(m.group(1), 16))
            i = m.end()
            continue
        ch = text[i]
        if ch == CODE_OPEN:
            out.append(BRACE_OPEN)
            in_code = True
            i += 1
            continue
        if ch == CODE_CLOSE:
            out.append(BRACE_CLOSE)
            in_code = False
            i += 1
            continue
        if in_code and 0x20 <= ord(ch) < 0x7F:
            out.append(ord(ch))
            i += 1
            continue
        if ch not in _BYTE_OF:
            raise ValueError(f"character {ch!r} has no glyph in the PAL font")
        out.append(_BYTE_OF[ch])
        i += 1
    return bytes(out)
