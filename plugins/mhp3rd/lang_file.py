"""Yakumo translation files (``*.lang``) for Monster Hunter Portable 3rd HD.

A parsed file keeps every original line. Saving writes the same lines back, and only an
edited value changes, so an unchanged file round-trips byte for byte. The rules follow
``profiles/mhp3rd/host/text/language.cpp`` in TeamGDB/Yakumo (MIT): lines end at ``\\n``,
trailing ``\\r`` is ignored, ``#`` and ``;`` start a comment, one space or tab after ``=``
is a separator, and a value keeps every other character, trailing spaces included.
"""
from __future__ import annotations

import os
import re
import tempfile
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple

BOM = "\ufeff"
MAIN_BLOCK = 16
# Tables 41-43 are the chat profanity filter, not text the game draws.
PROTECTED_TABLES = frozenset({41, 42, 43})

_DIGITS = re.compile(r"[0-9]+\Z")
_RANGE = re.compile(r"[0-9]+-[0-9]+\Z")
_SIMPLE_ESCAPES = {"n": "\n", "r": "\r", "t": "\t", "\\": "\\", "#": "#", ";": ";"}


def unescape(text: str) -> str:
    """Decode ``\\n \\r \\t \\\\ \\# \\;``. Any other backslash stays as it is."""
    out: List[str] = []
    i = 0
    while i < len(text):
        if text[i] == "\\" and i + 1 < len(text) and text[i + 1] in _SIMPLE_ESCAPES:
            out.append(_SIMPLE_ESCAPES[text[i + 1]])
            i += 2
        else:
            out.append(text[i])
            i += 1
    return "".join(out)


def escape(text: str) -> str:
    """Encode a value so that ``unescape`` returns ``text``."""
    return text.replace("\\", "\\\\").replace("\r", "\\r").replace("\n", "\\n").replace("\t", "\\t")


def _number(text: str) -> Optional[int]:
    if not _DIGITS.match(text):
        return None
    value = int(text)
    return value if value <= 0xFFFFFFFF else None


def _exact_key(key: str) -> Optional[Tuple[int, int]]:
    """``(table, index)`` for a plain ``TABLE:INDEX`` key, else None."""
    if ":" not in key:
        return None
    table_text, index_text = (part.strip() for part in key.split(":", 1))
    table = _number(table_text)
    index = _number(index_text)
    if table is None or index is None or table > 0xFFFF:
        return None
    return table, index


def _is_rule_key(key: str) -> bool:
    """A key with a wildcard or a range (``2:308-382``, ``2:*``, ``*:5``). Kept as written, never edited."""
    if ":" not in key:
        return False
    table_text, index_text = (part.strip() for part in key.split(":", 1))
    table_star = table_text == "*"
    index_star = index_text == "*"
    index_range = _RANGE.match(index_text) is not None
    if not (table_star or _number(table_text) is not None):
        return False
    if not (index_star or index_range or _number(index_text) is not None):
        return False
    return table_star or index_star or index_range


@dataclass
class Entry:
    """One ``TABLE:INDEX = TEXT`` line."""

    block: int
    key: str
    value: str
    table: Optional[int]  # None for range and wildcard keys
    index: Optional[int]
    line: int  # position in LangDocument.lines

    @property
    def editable(self) -> bool:
        """An exact key the game draws. Chat filter tables and entry 0 of a table are left alone."""
        if self.table is None:
            return False
        if self.block == MAIN_BLOCK:
            if self.table in PROTECTED_TABLES or self.index == 0:
                return False
        return True


@dataclass
class _Line:
    ending: str  # "\n" or "" (last line without newline)
    text: str  # everything before the ending, for a line that is not an entry
    prefix: str = ""  # entry lines: text up to the value, separator included
    value_raw: str = ""  # entry lines: the value as written
    tail: str = ""  # entry lines: the trailing "\r" characters
    entry: Optional[Entry] = None

    def render(self) -> str:
        if self.entry is None:
            return self.text + self.ending
        return self.prefix + self.value_raw + self.tail + self.ending


@dataclass
class LangDocument:
    """A parsed ``*.lang`` file. ``serialize`` gives back its text with any edits."""

    bom: bool = False
    lines: List[_Line] = field(default_factory=list)
    language: Optional[str] = None
    name: Optional[str] = None

    @classmethod
    def parse(cls, text: str) -> "LangDocument":
        doc = cls()
        if text.startswith(BOM):
            doc.bom = True
            text = text[1:]
        block = MAIN_BLOCK
        for piece in _split_lf(text):
            ending = "\n" if piece.endswith("\n") else ""
            body_all = piece[: len(piece) - len(ending)]
            body = body_all.rstrip("\r")
            tail = body_all[len(body):]
            line = _Line(ending=ending, text=body_all)
            doc.lines.append(line)
            stripped = body.lstrip(" \t")
            if not stripped or stripped[0] in "#;":
                continue
            if stripped[0] == "[":
                close = stripped.find("]")
                if close < 0:
                    continue
                head = stripped[1:close].strip().split(":", 1)[0].strip()
                if head == "main":
                    block = MAIN_BLOCK
                else:
                    number = _number(head)
                    if number is not None:
                        block = number
                continue
            equals = body.find("=")
            if equals < 0:
                continue
            key = body[:equals].strip(" \t\r\n")
            if key == "language" or key == "name":
                rest = body[equals + 1 :]
                if rest[:1] in (" ", "\t"):
                    rest = rest[1:]
                value = unescape(rest)
                if key == "language":
                    doc.language = value or None
                else:
                    doc.name = value or None
                continue
            exact = _exact_key(key)
            if exact is None and not _is_rule_key(key):
                continue  # Yakumo ignores this line too
            separator = body[equals + 1 : equals + 2] if body[equals + 1 : equals + 2] in (" ", "\t") else ""
            prefix = body[: equals + 1] + separator
            value_raw = body[len(prefix):]
            line.prefix = prefix
            line.value_raw = value_raw
            line.tail = tail
            table, index = exact if exact else (None, None)
            line.entry = Entry(
                block=block,
                key=key,
                value=unescape(value_raw),
                table=table,
                index=index,
                line=len(doc.lines) - 1,
            )
            line.text = ""
        return doc

    def entries(self) -> List[Entry]:
        return [line.entry for line in self.lines if line.entry is not None]

    def set_value(self, entry: Entry, text: str) -> None:
        """Replace one value. The key, the other lines and the line ending stay as they were."""
        line = self.lines[entry.line]
        if line.entry is not entry:
            raise ValueError("the entry does not belong to this document")
        prefix = line.prefix
        # Yakumo drops one space or tab after "=". A value that starts with one needs its own separator.
        if not prefix.endswith((" ", "\t")) and text[:1] in (" ", "\t"):
            prefix += " "
        line.prefix = prefix
        line.value_raw = escape(text)
        entry.value = text

    def serialize(self) -> str:
        text = "".join(line.render() for line in self.lines)
        return BOM + text if self.bom else text


def _split_lf(text: str) -> List[str]:
    """Split on ``\\n`` only, as Yakumo reads lines. A lone ``\\r`` stays inside its line."""
    pieces = text.split("\n")
    out = [piece + "\n" for piece in pieces[:-1]]
    if pieces[-1]:
        out.append(pieces[-1])
    return out


def read_lang(path: str) -> LangDocument:
    """Read a file byte-exactly (no newline translation)."""
    with open(path, "r", encoding="utf-8", newline="") as handle:
        return LangDocument.parse(handle.read())


def write_lang(path: str, doc: LangDocument) -> None:
    """Write through a temporary file in the same folder, then replace (AGENTS rule 9)."""
    folder = os.path.dirname(os.path.abspath(path))
    fd, tmp = tempfile.mkstemp(dir=folder, suffix=".tmp")
    try:
        with os.fdopen(fd, "w", encoding="utf-8", newline="") as handle:
            handle.write(doc.serialize())
        os.replace(tmp, path)
    except BaseException:
        if os.path.exists(tmp):
            os.remove(tmp)
        raise


def to_json_obj(doc: "LangDocument") -> dict:
    """The file as a dict: block name -> {key: value}. Keys keep their written form (TABLE:INDEX)."""
    blocks: Dict[str, Dict[str, str]] = {}
    for entry in doc.entries():
        blocks.setdefault(str(entry.block), {})[entry.key] = entry.value
    return blocks


def from_json_obj(obj: dict, language: str, name: str) -> str:
    """Write a file from the dict form. Values are escaped; blocks keep their order."""
    lines = ["language = %s" % language, "name = %s" % name, ""]
    for block, values in obj.items():
        lines.append("[%s]" % block)
        for key, value in values.items():
            lines.append("%s = %s" % (key, escape(value)))
        lines.append("")
    return "\n".join(lines)
