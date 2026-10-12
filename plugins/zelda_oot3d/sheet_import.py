"""Import of a translator's spreadsheet into the English slot of ``message/eu/eu.qm``.

The sheet has one row per message (row 1 is the header): ``ID`` in column C, ``English (EU)`` in column F and the
Ukrainian text in column G. Control codes are written as ``⟦NAME⟧`` or ``⟦NAME:ARG⟧`` (``ARG`` is hex, or a colour
name for ``COLOR``). The names follow the 3DS code table of the translator's stage6 tools. They differ from the
editor tags of ``qm.py`` for some codes; both read the same bytes.

Rules (from the translator's stage6 importer; the output matches its shipped ``eu.qm`` byte for byte):

- An empty Ukrainian cell takes the sheet's English text. An empty English cell keeps the game's own bytes.
- A text with ``⟦END⟧`` followed by more text has that text moved in front of the end code.
- Plain text loses carriage returns, newlines and combining acute accents. Line breaks are ``⟦NL⟧``.
- ``⟦END⟧`` in the sheet is the end code itself; nothing is added after it.
"""
from __future__ import annotations

import re
import struct
from dataclasses import dataclass, field
from typing import Dict, List, Sequence, Tuple

from . import qm

# Code -> sheet name, for the codes that the game's text uses.
SHEET_NAMES: Dict[int, str] = {
    0x00: "END", 0x01: "WAIT", 0x02: "SPACE", 0x03: "GOTO", 0x04: "INSTANT_ON", 0x05: "INSTANT_OFF",
    0x06: "SHOP_BOX", 0x07: "EVENT", 0x08: "DELAY", 0x0A: "CLOSE_AFTER", 0x0B: "PLAYER_NAME", 0x0C: "OCARINA",
    0x0E: "SOUND", 0x0F: "ITEM", 0x10: "SPEED", 0x11: "BACKGROUND", 0x12: "MARATHON_TIME", 0x13: "RACE_TIME",
    0x14: "ARCHERY_SCORE", 0x15: "SKULLTULAS", 0x16: "FISH_WEIGHT", 0x17: "HYRULE_TIME", 0x18: "VARIABLE",
    0x19: "UNSKIPPABLE", 0x1A: "CHOICE_2", 0x1B: "CHOICE_3", 0x1C: "NL", 0x1D: "COLOR", 0x1E: "CENTER",
    0x23: "UNKNOWN_23", 0x24: "ICON", 0x25: "CREDIT_TITLE", 0x26: "IF_FLAG", 0x27: "ELSE", 0x28: "ENDIF",
    0x29: "IF_NOT_MQ", 0x2A: "ELSE_MQ", 0x2B: "ENDIF_MQ",
}
# Code -> number of argument bytes that follow it.
ARG_BYTES: Dict[int, int] = {
    0x00: 0, 0x01: 0, 0x02: 1, 0x03: 2, 0x04: 0, 0x05: 0, 0x06: 1, 0x07: 0, 0x08: 1, 0x0A: 1, 0x0B: 0,
    0x0C: 0, 0x0E: 5, 0x0F: 1, 0x10: 1, 0x11: 3, 0x12: 0, 0x13: 0, 0x14: 0, 0x15: 0, 0x16: 0, 0x17: 0,
    0x18: 1, 0x19: 0, 0x1A: 4, 0x1B: 6, 0x1C: 0, 0x1D: 1, 0x1E: 0, 0x23: 1, 0x24: 1, 0x25: 3, 0x26: 1,
    0x27: 0, 0x28: 0, 0x29: 0, 0x2A: 0, 0x2B: 0,
}
NAME_TO_CODE: Dict[str, int] = {name: code for code, name in SHEET_NAMES.items()}
COLOR_CODE = 0x1D
COLOR_CODES: Dict[str, int] = {
    "WHITE": 0x00, "RED": 0x41, "GREEN": 0x42, "BLUE": 0x43, "LIGHT_BLUE": 0x44, "PINK": 0x45,
    "YELLOW": 0x46, "BLACK": 0x47,
}
TAG_RE = re.compile(r"⟦([^⟧]+)⟧")
END_TAG = "⟦END⟧"
ACUTE = "́"


class SheetError(ValueError):
    """A sheet cell that cannot be written to the game's text."""


def normalize_plain(text: str) -> str:
    """Plain sheet text as the game stores it: no carriage returns, newlines or combining acute accents."""
    return text.replace(ACUTE, "").replace("\r", "").replace("\n", "")


def repair_terminal_text(text: str) -> Tuple[str, bool]:
    """Move text that follows ``⟦END⟧`` in front of the end code. Returns ``(text, changed)``."""
    position = text.rfind(END_TAG)
    if position < 0:
        return text, False
    suffix = text[position + len(END_TAG):]
    if not suffix.strip():
        return text, False
    return text[:position] + suffix + END_TAG, True


def encode_message(text: str) -> bytes:
    """Sheet text -> stored text. Control codes become ``7F code args``; plain text becomes UTF-8."""
    out = bytearray()
    at = 0
    for match in TAG_RE.finditer(text):
        out += normalize_plain(text[at:match.start()]).encode("utf-8")
        out += _encode_tag(match.group(1))
        at = match.end()
    out += normalize_plain(text[at:]).encode("utf-8")
    return bytes(out)


def _encode_tag(tag: str) -> bytes:
    name, separator, argument = tag.partition(":")
    if name == "COLOR":
        if argument in COLOR_CODES:
            args = bytes([COLOR_CODES[argument]])
        elif separator:
            args = _hex_argument(argument, tag)
        else:
            raise SheetError(f"Tag {tag} needs a colour")
        code = COLOR_CODE
    elif name.startswith("CTRL_"):
        code = _hex_number(name[5:], tag)
        args = _hex_argument(argument, tag) if separator else b""
    elif name in NAME_TO_CODE:
        code = NAME_TO_CODE[name]
        args = _hex_argument(argument, tag) if separator else b""
    else:
        raise SheetError(f"Unknown tag {tag}")
    expected = ARG_BYTES.get(code)
    if expected is None or len(args) != expected:
        raise SheetError(f"Tag {tag} has {len(args)} argument bytes; the game expects {expected}")
    return bytes((0x7F, code)) + args


def _hex_argument(argument: str, tag: str) -> bytes:
    try:
        return bytes.fromhex(argument)
    except ValueError:
        raise SheetError(f"Tag {tag} has a bad hex argument") from None


def _hex_number(text: str, tag: str) -> int:
    try:
        return int(text, 16)
    except ValueError:
        raise SheetError(f"Tag {tag} has a bad code number") from None


def control_codes(raw: bytes) -> List[Tuple[int, bytes]]:
    """``(code, argument bytes)`` of every control code in a stored text, up to the end code."""
    codes: List[Tuple[int, bytes]] = []
    at = 0
    while at < len(raw):
        if raw[at] != 0x7F:
            at += 1
            continue
        if at + 1 >= len(raw):
            raise SheetError("Stored text ends inside a control code")
        code = raw[at + 1]
        if code == 0x00:
            break
        size = ARG_BYTES.get(code)
        if size is None:
            raise SheetError(f"Unknown control code 0x{code:02X}")
        codes.append((code, raw[at + 2:at + 2 + size]))
        at += 2 + size
    return codes


def describe_code(code: int, args: bytes) -> str:
    name = SHEET_NAMES.get(code, f"0x{code:02X}")
    return f"{name}:{args.hex().upper()}" if args else name


@dataclass
class ImportResult:
    """The new ``eu.qm`` and what happened to each row."""

    data: bytes
    translated: int = 0                                       # rows with a Ukrainian text
    fallback_ids: List[int] = field(default_factory=list)      # empty Ukrainian cell: English text used
    repaired_ids: List[int] = field(default_factory=list)      # text after END moved in front of it
    code_changes: List[dict] = field(default_factory=list)     # control codes differ from the game's English


# The table row holds ten (offset, length) pairs from byte 0x10: Japanese, US English, EU English (the game's
# English text), and seven more. The plugin reads the eight from EU English on (``qm.SLOTS``); all ten are rewritten.
LANGUAGE_PAIRS = 10
EU_ENGLISH = 2


def _language_raw(source: bytes, values: Sequence[int], language: int) -> bytes:
    offset, size = values[4 + 2 * language], values[5 + 2 * language]
    return source[offset:offset + size] if size else b""


def build_eu_qm(source: bytes, sheet: dict) -> ImportResult:
    """The English slot of ``source`` (the game's ``eu.qm``) replaced with the sheet's Ukrainian text."""
    count = struct.unpack_from("<I", source, 8)[0]
    rows = sheet["values"][1:]
    if len(rows) != count:
        raise SheetError(f"Sheet has {len(rows)} messages; the game file has {count}")
    result = ImportResult(data=b"")
    table_end = 16 + count * qm.ENTRY
    tables: List[List[int]] = []
    slots: List[List[bytes]] = []
    for index, row in enumerate(rows):
        values = list(struct.unpack_from("<24I", source, 16 + index * qm.ENTRY))
        message_id = values[0]
        if int(row[2]) != message_id:
            raise SheetError(f"Sheet row {index + 2} has ID {row[2]}; the game file has 0x{message_id:X}")
        original = _language_raw(source, values, EU_ENGLISH)
        text = row[6]
        if not text:
            result.fallback_ids.append(message_id)
            text = row[5]
        if isinstance(text, str):
            text, repaired = repair_terminal_text(text)
            if repaired:
                result.repaired_ids.append(message_id)
            raw = encode_message(text)
            if row[6]:
                result.translated += 1
        else:
            raw = original
        if control_codes(raw) != control_codes(original):
            result.code_changes.append({
                "id": f"0x{message_id:08X}",
                "english": [describe_code(c, a) for c, a in control_codes(original)],
                "ukrainian": [describe_code(c, a) for c, a in control_codes(raw)],
            })
        texts = [_language_raw(source, values, language) for language in range(LANGUAGE_PAIRS)]
        texts[EU_ENGLISH] = raw
        tables.append(values)
        slots.append(texts)
    out = bytearray(source[:table_end])
    body = bytearray()
    cursor = table_end
    for index, (values, texts) in enumerate(zip(tables, slots)):
        for language, raw in enumerate(texts):
            while cursor % 4:
                body.append(0)
                cursor += 1
            if raw:
                values[4 + 2 * language], values[5 + 2 * language] = cursor, len(raw)
                body += raw
                cursor += len(raw)
            else:
                values[4 + 2 * language], values[5 + 2 * language] = 0, 0
        struct.pack_into("<24I", out, 16 + index * qm.ENTRY, *values)
    result.data = bytes(out + body)
    return result


def check_editor_readable(data: bytes) -> List[str]:
    """Problems the plugin's own reader reports for the English slot. An empty list means every message opens."""
    try:
        file = qm.Qm(data)
    except qm.FormatError as error:
        return [str(error)]
    problems = []
    for message_id, texts in zip(file.ids, file.texts):
        raw = texts[qm.ENGLISH]
        if not raw:
            continue
        try:
            qm.to_editor(raw)
        except qm.FormatError as error:
            problems.append(f"0x{message_id:08X}: {error}")
    return problems
