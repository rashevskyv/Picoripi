"""Link's Awakening DX dialog text: decode, encode and in-place writes.

A dialog is one run of bytes that ends with 0xFF. Letters, digits and punctuation use the codes of
the LADX-Disassembly dialog charmap (constants/charmaps/dialog.asm). Accents and symbols have their
own codes. Symbols show as ``<name>`` tokens, and a code without a name shows as ``{XX}``.

Editing rule: a dialog is replaced in place. The new text must encode to no more bytes than the
old run. The rest of the run is padded with spaces (0x20), so the 0xFF end code and every other
pointer stay where they are. A ROM without edits rebuilds byte for byte.
"""
from __future__ import annotations

import re
from typing import Dict

from .rom import DialogRef

TERMINATOR = 0xFF
PAD = 0x20
SCAN_LIMIT = 4096

# Plain characters: their charmap codes.
_CODE_OF: Dict[str, int] = {
    " ": 0x20, "!": 0x21, '"': 0x22, "#": 0x23, "&": 0x26, "(": 0x28, ")": 0x29, ",": 0x2C,
    "-": 0x2D, ".": 0x2E, ":": 0x3A, ";": 0x3B, "?": 0x3F, "'": 0x5E, "+": 0x7F, "/": 0xFD,
}
_CODE_OF.update({str(digit): 0x30 + digit for digit in range(10)})
_CODE_OF.update({chr(0x41 + i): 0x41 + i for i in range(26)})
_CODE_OF.update({chr(0x61 + i): 0x61 + i for i in range(26)})

# Accents and other single symbols.
_ACCENTS: Dict[int, str] = {
    0x80: "Á", 0x81: "É", 0x82: "Í", 0x83: "Ó", 0x84: "Ú", 0x85: "Ü", 0x86: "Ñ", 0x88: "Ç",
    0x89: "á", 0x8A: "é", 0x8B: "í", 0x8C: "ó", 0x8D: "ú", 0x8E: "ü", 0x8F: "ñ",
    0x90: "à", 0x91: "è", 0x92: "ì", 0x93: "ò", 0x94: "ù", 0x95: "ä", 0x96: "ë", 0x97: "ï",
    0x98: "ö", 0x9A: "¡", 0x9B: "¿", 0x9C: "`",
    0xB0: "â", 0xB1: "ê", 0xB2: "î", 0xB3: "ô", 0xB4: "û",
}

# Named symbols (item icons, buttons, the choice marker).
_TOKENS: Dict[int, str] = {
    0xD9: "<flower>", 0xDA: "<footprint>", 0xDC: "<skull>", 0xDD: "<link>", 0xDE: "<marin>",
    0xDF: "<tarin>", 0xE0: "<yoshi>", 0xE1: "<ribbon>", 0xE2: "<dogfood>", 0xE3: "<bananas>",
    0xE4: "<stick>", 0xE5: "<honeycomb>", 0xE6: "<pineapple>", 0xE7: "<flower2>", 0xE8: "<broom>",
    0xE9: "<fishhook>", 0xEA: "<bra>", 0xEB: "<scale>", 0xEC: "<glass>", 0xED: "<letter>",
    0xEE: "<dpad>", 0xF0: "<up>", 0xF1: "<down>", 0xF2: "<left>", 0xF3: "<right>", 0xFE: "<ask>",
}

_TEXT_OF: Dict[int, str] = {code: ch for ch, code in _CODE_OF.items()}
_TEXT_OF.update(_ACCENTS)
_TEXT_OF.update(_TOKENS)
_CODE_BY_TEXT: Dict[str, int] = {text: code for code, text in _TEXT_OF.items()}
_PIECE_RE = re.compile(r"<[a-z0-9]+>|\{[0-9A-F]{2}\}|.", re.DOTALL)


class TextError(ValueError):
    """Text that cannot be written into the dialog."""


class TextTooLong(TextError):
    """The new text needs more bytes than the old dialog run."""


def span_length(rom: bytes, start: int) -> int:
    """Number of bytes from ``start`` up to, not including, the 0xFF end code."""
    end = rom.find(bytes([TERMINATOR]), start, start + SCAN_LIMIT)
    if end < 0:
        raise TextError(f"no end code within {SCAN_LIMIT} bytes of 0x{start:05X}")
    return end - start


def decode_bytes(data: bytes) -> str:
    """Text for the bytes of one dialog run (without the end code)."""
    return "".join(_TEXT_OF.get(code, "{%02X}" % code) for code in data)


def encode_text(text: str) -> bytes:
    """Bytes for text that uses the same tokens as decode_bytes."""
    out = bytearray()
    for piece in _PIECE_RE.findall(text):
        if len(piece) == 4 and piece[0] == "{" and piece[3] == "}":
            out.append(int(piece[1:3], 16))
            continue
        code = _CODE_BY_TEXT.get(piece)
        if code is None:
            raise TextError(f"{piece!r} is not in the DX dialog charmap")
        out.append(code)
    return bytes(out)


def read_text(rom: bytes, ref: DialogRef) -> str:
    """Text of one dialog, read from the ROM bytes."""
    return decode_bytes(rom[ref.rom : ref.rom + span_length(rom, ref.rom)])


def write_text(rom: bytearray, ref: DialogRef, text: str) -> None:
    """Write ``text`` into the dialog run in place and pad the rest of the run with spaces."""
    room = span_length(rom, ref.rom)
    data = encode_text(text)
    if len(data) > room:
        raise TextTooLong(f"{ref.name}: {len(data)} bytes do not fit in {room}")
    rom[ref.rom : ref.rom + room] = data + bytes([PAD]) * (room - len(data))
