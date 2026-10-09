"""Text codes of the DS Castlevania games (Dawn of Sorrow, Portrait of Ruin, Order of Ecclesia; USA), both ways.

The workspace scripts keep every string as its raw bytes (``strings.cvdstext``); this module turns them into
editor text and back. One byte a code (DSVEdit ``dsvlib/text.rb``, ``decode_string_usa``):

- ``00``-``5E``: ASCII ``20``-``7E`` (``[`` / ``]`` are shown full width so they never read as a tag);
- ``5F``-``BE``: the accented Latin letters and signs of ``SPECIAL``; Ukrainian letters take the cells of the
  ones the English text never uses (``UA_SLOTS``): the glyphs stay as they are until somebody redraws them in
  the Font Editor;
- ``E6`` breaks the line; ``E4`` (new text box) and ``E9`` (new page, same speaker) are shown with a line break
  after them; ``E5`` waits for a button; ``E2``, ``E3``, ``E7``, ``E8`` take one parameter byte, ``E1`` two
  (big endian); ``EB``-``F4`` are button pictures. ``EA`` ends a string and never appears in one.

A code with no character is written ``[xHH]``.
"""
from __future__ import annotations

import re
from typing import Dict, List, Tuple

SPECIAL = "・¡¢£¨©®°±´¸¿ÀÁÂÃÄÅÆÇÈÉÊËÌÍÎÏÐÑÒÓÔÕÖ×ØÙÚÛÜÝßàáâãäåæçèéêëìíîïðñòóôõö÷øùúûüýŒœˆ˜‐‗‘’‚“”„•…′″›※€™«»⁰"
UA_LETTERS = "АБВГҐДЕЄЖЗИІЇЙКЛМНОПРСТУФХЦЧШЩЬЮЯабвгґдеєжзиіїйклмнопрстуфхцчшщьюя"
# Signs a translation may want, and letters the English text of a game uses: never given to a Ukrainian letter.
_KEEP = set("¡¿©®°±×÷‘’‚“”„•…«»€™çñ")
FREE_CODES = [0x5F + i for i, char in enumerate(SPECIAL) if char not in _KEEP]
UA_SLOTS: Dict[str, int] = dict(zip(UA_LETTERS, FREE_CODES))
END = 0xEA
BUTTONS = ("L", "R", "A", "B", "X", "Y", "LEFT", "RIGHT", "UP", "DOWN")


def _chars() -> Dict[int, str]:
    chars = {code: chr(code + 0x20) for code in range(0x5F)}
    chars[0x3B], chars[0x3D] = "［", "］"
    chars.update({0x5F + i: char for i, char in enumerate(SPECIAL)})
    chars.update({code: letter for letter, code in UA_SLOTS.items()})
    return chars


CHARS = _chars()
CODES = {char: code for code, char in CHARS.items()}
CODES.update({"[": 0x3B, "]": 0x3D})
SIMPLE = {0xE4: "[box]", 0xE5: "[wait]", 0xE9: "[same]", **{0xEB + i: f"[{b}]" for i, b in enumerate(BUTTONS)}}
PARAMS = {0xE2: "cmd", 0xE3: "face", 0xE7: "name", 0xE8: "color"}
PAIRS = {(0xE2, 0x01): "[next]", (0xE2, 0x03): "[choice]"}
BREAKS = ("[box]", "[same]")
NEWLINE = 0xE6
_TAGS = {tag: code for code, tag in SIMPLE.items()}
_PAIR_CODES = {tag: pair for pair, tag in PAIRS.items()}
_PARAM_CODES = {name: code for code, name in PARAMS.items()}

TAG_RE = re.compile(r"\[(?:(?:cmd|face|name|color):[0-9A-Fa-f]{2}|endchoice:[0-9A-Fa-f]{4}|x[0-9A-Fa-f]{2}|box|wait|same|"
                    r"next|choice|L|R|A|B|X|Y|LEFT|RIGHT|UP|DOWN)\]")


class EncodeError(ValueError):
    """A text that cannot be written in the game's codes."""


def decode(data: bytes) -> str:
    out: List[str] = []
    i = 0
    while i < len(data):
        code = data[i]
        if code == 0xE1 and i + 2 < len(data):
            out.append(f"[endchoice:{data[i + 1]:02X}{data[i + 2]:02X}]")
            i += 3
            continue
        if code in PARAMS and i + 1 < len(data):
            out.append(PAIRS.get((code, data[i + 1])) or f"[{PARAMS[code]}:{data[i + 1]:02X}]")
            i += 2
            continue
        if code == NEWLINE:
            out.append("\n")
        elif code in SIMPLE:
            out.append(SIMPLE[code] + ("\n" if SIMPLE[code] in BREAKS else ""))
        elif code in CHARS:
            out.append(CHARS[code])
        else:
            out.append(f"[x{code:02X}]")
        i += 1
    return "".join(out)


def encode(text: str, strict: bool = True) -> bytes:
    out = bytearray()
    tokens = re.findall(r"\[[^\[\]\n]*\]|\n|.", str(text), flags=re.S)
    i = 0
    while i < len(tokens):
        token = tokens[i]
        i += 1
        if token == "\n":
            out.append(NEWLINE)
        elif token in _TAGS:
            out.append(_TAGS[token])
            if token in BREAKS and i < len(tokens) and tokens[i] == "\n":
                i += 1                                   # the line break the editor shows after it
        elif token in _PAIR_CODES:
            out += bytes(_PAIR_CODES[token])
        elif token in CODES:
            out.append(CODES[token])
        elif match := re.fullmatch(r"\[(cmd|face|name|color):([0-9A-Fa-f]{2})\]", token):
            out += bytes((_PARAM_CODES[match.group(1)], int(match.group(2), 16)))
        elif match := re.fullmatch(r"\[endchoice:([0-9A-Fa-f]{4})\]", token):
            out.append(0xE1)
            out += int(match.group(1), 16).to_bytes(2, "big")
        elif match := re.fullmatch(r"\[x([0-9A-Fa-f]{2})\]", token):
            out.append(int(match.group(1), 16))
        elif strict:
            raise EncodeError(f"No game code for {token!r}")
        else:
            out.append(CODES["?"])
    if END in out:
        raise EncodeError("The code EA ends a string; it cannot be inside one")
    return bytes(out)


def unknown_chars(text: str) -> List[str]:
    """Characters of ``text`` (outside tags) the game has no code for."""
    plain = re.sub(r"\[[^\[\]\n]*\]", "", str(text))
    return sorted({char for char in plain if char != "\n" and char not in CODES})


DESCRIPTIONS = {
    "[box]": "Wait for a button, then a new text box", "[same]": "Wait for a button, then a new page (same speaker)",
    "[wait]": "Wait for a button", "[next]": "Go on with the scene", "[choice]": "A choice",
    **{f"[{b}]": f"{b} button picture" for b in BUTTONS},
}
_PARAM_DESCRIPTIONS = {"face": "Portrait", "name": "Speaker name", "color": "Text colour", "cmd": "Command",
                       "endchoice": "End of a choice"}


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
    """Pixels of the widest line of ``text`` (``font_map``: character -> {"width"}; tags draw nothing, a button
    picture is one cell)."""
    best = 0
    for line in str(text).split("\n"):
        total = 0
        for token in re.findall(r"\[[^\[\]\n]*\]|.", line):
            if len(token) > 1:
                total += default if token.strip("[]") in BUTTONS else 0
                continue
            entry = font_map.get(token)
            total += int(entry.get("width", default)) if isinstance(entry, dict) else default
        best = max(best, total)
    return best


def font_chars() -> Dict[str, int]:
    """``{character: glyph index}`` of both fonts (the glyph index is the text code)."""
    out = {char: code for code, char in CHARS.items()}
    out.update({"[": 0x3B, "]": 0x3D})
    return out


def split_regions(regions) -> List[Tuple[int, int, str]]:
    """``[(first, last, name)]`` from the file's ``regions`` list."""
    return [(int(first), int(last), str(name)) for name, first, last in regions]
