"""Shift-JIS character codes of 3DS fonts and texts that are keyed by Shift-JIS (Atlus: Shin Megami Tensei IV).

A code is the one or two bytes of the character as a big-endian number (``0x8260`` = ``Ａ``). The eight Ukrainian
letters that Shift-JIS lacks get the free codes after the Cyrillic row of JIS X 0208 (``0x8492``..``0x8499``); a
font that maps them and a text encoder that writes them agree through this table. A code no table knows is
kept as a private-use character (``U+F0000 + code``).
"""
from __future__ import annotations

UKRAINIAN = {"Ґ": 0x8492, "Є": 0x8493, "І": 0x8494, "Ї": 0x8495, "ґ": 0x8496, "є": 0x8497, "і": 0x8498, "ї": 0x8499}
_BY_CODE = {code: char for char, code in UKRAINIAN.items()}
_PRIVATE = 0xF0000


def decode(code: int) -> str:
    """The character of a Shift-JIS code."""
    if code in _BY_CODE:
        return _BY_CODE[code]
    raw = bytes([code]) if code < 0x100 else code.to_bytes(2, "big")
    try:
        char = raw.decode("cp932")
    except UnicodeDecodeError:
        return chr(_PRIVATE + code)
    return char if len(char) == 1 and encode(char) == code else chr(_PRIVATE + code)


def encode(char: str) -> int:
    """The Shift-JIS code of a character (``decode``'s inverse); raises for a character the table lacks."""
    if char in UKRAINIAN:
        return UKRAINIAN[char]
    if ord(char) >= _PRIVATE:
        return ord(char) - _PRIVATE
    return int.from_bytes(char.encode("cp932"), "big")
