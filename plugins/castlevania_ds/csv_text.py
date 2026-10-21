"""Text of a Castlevania DS project in CSV (one row ``0xHEX,text`` per string) -> the game's string bytes.

The CSV names a code with a word in braces: ``{NEWCHAR}``, ``{WAITINPUT}``, ``{SAMECHAR}``, ``{NEXTACTION}``,
``{CHOICE}``, ``{PORTRAIT 0xNN}``, ``{NAME 0xNN}``, ``{TEXTCOLOR AZURE}``, ``{ENDCHOICE 0xNNNN}``, ``{BUTTON Y}``.
A line break is a backslash-n followed by a real newline; the real newline after a portrait or a page tag is
only a display line break and is not in the game. A letter is written as its character; the letters of a
font layout (``codec.layout``) take the code the layout gives them, so the bytes match the font of the game.
"""
from __future__ import annotations

import csv
import re
from typing import Dict, Iterable, Optional

from . import codec

TOKEN = re.compile(r"\{[^{}]*\}|\\n|.", re.S)
SIMPLE_TAGS = {"NEWCHAR": [0xE4], "WAITINPUT": [0xE5], "SAMECHAR": [0xE9], "NEXTACTION": [0xE2, 0x01],
               "CHOICE": [0xE2, 0x03]}
PARAM_TAGS = {"PORTRAIT": 0xE3, "NAME": 0xE7, "CMD": 0xE2}
COLORS = {"WHITE": 0x01, "AZURE": 0x06}
BUTTON_CODES = {name: 0xEB + i for i, name in enumerate(codec.BUTTONS)}


class CsvError(ValueError):
    """A string that cannot be written in the game's codes."""


def read_rows(paths: Iterable[str]) -> Dict[int, str]:
    """``{string id: text}`` from CSV files (quoted fields, doubled quotes, embedded newlines)."""
    rows: Dict[int, str] = {}
    for path in paths:
        with open(path, encoding="utf-8-sig", newline="") as handle:
            for record in csv.reader(handle):
                if not record:
                    continue
                match = re.fullmatch(r"0x([0-9A-Fa-f]+)", record[0].strip())
                if not match:
                    raise CsvError(f"{path}: a row must start with 0xHEX, not {record[0][:12]!r}")
                rows[int(match.group(1), 16)] = ",".join(record[1:])
    return rows


def _tag_bytes(body: str) -> bytes:
    if body in SIMPLE_TAGS:
        return bytes(SIMPLE_TAGS[body])
    match = re.fullmatch(r"BUTTON (\w+)", body)
    if match and match.group(1) in BUTTON_CODES:
        return bytes([BUTTON_CODES[match.group(1)]])
    match = re.fullmatch(r"(PORTRAIT|NAME|CMD) 0x([0-9A-F]{2})", body)
    if match:
        return bytes([PARAM_TAGS[match.group(1)], int(match.group(2), 16)])
    match = re.fullmatch(r"TEXTCOLOR (WHITE|AZURE)", body)
    if match:
        return bytes([0xE8, COLORS[match.group(1)]])
    match = re.fullmatch(r"TEXTCOLOR 0x([0-9A-F]{2})", body)
    if match:
        return bytes([0xE8, int(match.group(1), 16)])
    match = re.fullmatch(r"ENDCHOICE 0x([0-9A-F]{4})", body)
    if match:
        return bytes([0xE1]) + bytes.fromhex(match.group(1))
    raise CsvError(f"No game code for {{{body}}}")


def from_csv(text: str, layout_name: Optional[str] = None) -> bytes:
    """The game's bytes of one CSV text. ``layout_name``: a font layout of ``codec.layout``."""
    aliases = codec.layout(layout_name)[1] if layout_name else {}
    out = bytearray()
    tokens = TOKEN.findall(str(text))
    i = 0
    while i < len(tokens):
        token = tokens[i]
        i += 1
        if token == "\\n":
            out.append(codec.NEWLINE)
            if i < len(tokens) and tokens[i] == "\n":
                i += 1                                  # the real newline after the backslash-n
        elif token == "\n":
            continue                                    # a display line break after a tag
        elif token.startswith("{") and token.endswith("}"):
            out += _tag_bytes(token[1:-1])
        elif token in aliases:
            out.append(aliases[token])
        elif token in codec.CODES:
            out.append(codec.CODES[token])
        else:
            raise CsvError(f"No game code for {token!r}")
    if codec.END in out:
        raise CsvError("The code EA ends a string; it cannot be inside one")
    return bytes(out)


def bank_from_rows(rows: Dict[int, str], bank: dict, layout_name: Optional[str] = None) -> dict:
    """A copy of a string bank (``unpack`` output) whose strings are the CSV rows; the rest keep their bytes."""
    strings = list(bank.get("strings") or [])
    for index, text in sorted(rows.items()):
        if index >= len(strings):
            raise CsvError(f"String {index:#x} is outside the table of {len(strings)} strings")
        strings[index] = from_csv(text, layout_name).hex()
    return {**bank, "strings": strings, "layout": layout_name or ""}
