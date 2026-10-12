"""Parse and write Link's Awakening DX HD language files (``KEY VALUE`` lines).

The game reads ``Data/Languages/*.lng`` with ``Language.LoadFile``: a line is ``KEY`` + one space + ``VALUE``;
lines without a space and lines that start with ``//`` are skipped. Everything the loader skips is kept here as
it is, so a file that is read and written again comes back byte for byte.

Rules that matter for the game:

* The loader uses ``Dictionary.Add``. A key that appears twice in one language (both ``eng.lng`` and
  ``dialog_eng.lng`` count) stops the game at start-up. ``duplicate_keys`` finds them.
* A lone carriage return inside a line splits the line in the game (``ReadLine``). ``parse`` refuses it.
* Text escapes ``\\n`` and ``\\f`` are two characters in the file. The game turns them into line breaks.
* Square-bracket tags such as ``[NAME]`` are replaced at run time (player name, or a save variable).
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Dict, Iterable, List, Optional, Sequence

KIND_ENTRY = "entry"
KIND_COMMENT = "comment"
KIND_BLANK = "blank"
KIND_OTHER = "other"

# Square-bracket tag as the game writes it: [NAME], [itemShopItem]. Found in dialog_eng.lng.
TAG_RE = re.compile(r"\[[A-Za-z][A-Za-z0-9_]*\]")
# Two-character escapes the text box turns into a line break (\n) or a page break (\f).
ESCAPE_RE = re.compile(r"\\[nf]")
# Regex used by the editor to keep tags and escapes out of spell checking.
IGNORE_PATTERN = r"\[[A-Za-z][A-Za-z0-9_]*\]|\\[nf]"


@dataclass
class Line:
    """One physical line of a file. ``eol`` is ``"\\r\\n"``, ``"\\n"`` or ``""`` (last line, no newline)."""

    kind: str
    text: str = ""          # raw text of a non-entry line (no EOL)
    key: str = ""           # entry only
    value: str = ""         # entry only: everything after the first space
    eol: str = "\r\n"


@dataclass
class LangFile:
    """A parsed language file: the lines in order, and whether it began with a UTF-8 byte order mark."""

    lines: List[Line] = field(default_factory=list)
    bom: bool = False

    def entries(self) -> List[Line]:
        """The ``KEY VALUE`` lines, in file order."""
        return [line for line in self.lines if line.kind == KIND_ENTRY]


def _classify(chunk: str, eol: str) -> Line:
    if "\r" in chunk:
        raise ValueError("a lone carriage return inside a line: the game would split this line")
    if chunk.strip() == "":
        return Line(KIND_BLANK, text=chunk, eol=eol)
    if chunk.startswith("//"):
        return Line(KIND_COMMENT, text=chunk, eol=eol)
    space = chunk.find(" ")
    if space < 0:
        return Line(KIND_OTHER, text=chunk, eol=eol)
    return Line(KIND_ENTRY, key=chunk[:space], value=chunk[space + 1:], eol=eol)


def parse_text(text: str) -> LangFile:
    """Parse the decoded text of a language file. A leading BOM character is recorded and not kept as text."""
    bom = text.startswith("﻿")
    if bom:
        text = text[1:]
    lines: List[Line] = []
    pos = 0
    while pos < len(text):
        newline = text.find("\n", pos)
        if newline < 0:
            chunk, eol, pos = text[pos:], "", len(text)
        else:
            chunk, eol, pos = text[pos:newline], "\n", newline + 1
            if chunk.endswith("\r"):
                chunk, eol = chunk[:-1], "\r\n"
        lines.append(_classify(chunk, eol))
    return LangFile(lines=lines, bom=bom)


def parse(raw: bytes) -> LangFile:
    """Parse the bytes of a language file (UTF-8, optional BOM)."""
    return parse_text(raw.decode("utf-8"))


def serialize(lang: LangFile, values: Optional[Sequence[str]] = None) -> str:
    """Write the file back as text. ``values`` replaces the value of each entry, in entry order.

    Entries keep their key, their line ending and their position. Comments, blank lines and skipped lines
    are written as they were read.
    """
    if values is not None and len(values) != len(lang.entries()):
        raise ValueError(f"{len(values)} values for {len(lang.entries())} entries")
    out: List[str] = ["﻿"] if lang.bom else []
    index = 0
    for line in lang.lines:
        if line.kind == KIND_ENTRY:
            value = line.value
            if values is not None:
                value = values[index]
            index += 1
            out.append(f"{line.key} {value}{line.eol}")
        else:
            out.append(f"{line.text}{line.eol}")
    return "".join(out)


def serialize_bytes(lang: LangFile, values: Optional[Sequence[str]] = None) -> bytes:
    """``serialize`` encoded as UTF-8."""
    return serialize(lang, values).encode("utf-8")


def duplicate_keys(files: Iterable[LangFile]) -> List[str]:
    """Keys that the game would see twice in one language (all files given count as one language)."""
    seen: Dict[str, int] = {}
    for lang in files:
        for entry in lang.entries():
            seen[entry.key] = seen.get(entry.key, 0) + 1
    return sorted(key for key, count in seen.items() if count > 1)


def tags(value: str) -> List[str]:
    """Square-bracket tags of a value, in order."""
    return TAG_RE.findall(value)


def escapes(value: str) -> List[str]:
    """Line-break and page-break escapes of a value, in order."""
    return ESCAPE_RE.findall(value)


def missing_characters(value: str, charset: Iterable[str]) -> List[str]:
    """Characters of ``value`` the font has no glyph for (each once, in order of appearance)."""
    have = set(charset)
    missing: List[str] = []
    for ch in value:
        if ch not in have and ch not in missing and ch not in "\r\n":
            missing.append(ch)
    return missing
