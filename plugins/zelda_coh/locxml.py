"""Cadence of Hyrule's ``localization.xml``: every UI, dialogue and item string, 11 languages per entry.

The file is UTF-8 XML written by the game's tools: ``<text description="key" id="N">`` holds one
``<string lang="xx">`` per language (``en ja de fr es it sc tc kr cafr uses``). Line endings are mixed
(CRLF and LF) and a few strings end in a raw line break, so the file is never re-serialised: it is
read as text, the English strings are located by their spans, and saving splices only the strings
that changed. An unedited file is written back byte for byte.
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Dict, List, Optional, Sequence

LANG = "en"
_TEXT_RE = re.compile(r'<text description="([^"]*)" id="(\d+)">(.*?)</text>', re.S)
_ESCAPES = {"&amp;": "&", "&lt;": "<", "&gt;": ">", "&quot;": '"', "&apos;": "'"}
_ESCAPE_RE = re.compile("|".join(map(re.escape, _ESCAPES)) + r"|&#(\d+);|&#x([0-9A-Fa-f]+);")


class FormatError(ValueError):
    """Not a Cadence of Hyrule localization file."""


@dataclass
class Entry:
    """One ``<text>`` element: its key, id and the English string (unescaped)."""

    id: int
    description: str
    text: str
    start: int          # span of what is replaced on save (string content, or a self-closing tag)
    end: int
    self_closing: bool


def unescape(raw: str) -> str:
    def one(match):
        if match.group(1):
            return chr(int(match.group(1)))
        if match.group(2):
            return chr(int(match.group(2), 16))
        return _ESCAPES[match.group(0)]
    return _ESCAPE_RE.sub(one, raw)


def escape(text: str) -> str:
    return text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


class LocalizationFile:
    """The parsed file; ``entries`` in file order (one per ``<text>`` with an English string)."""

    def __init__(self, data: bytes, lang: str = LANG):
        if b"<strings>" not in data[:400] or b"<text " not in data:
            raise FormatError("not a localization.xml (no <strings> root)")
        try:
            self.document = bytes(data).decode("utf-8")
        except UnicodeDecodeError as error:
            raise FormatError(f"not UTF-8: {error}") from error
        string_re = re.compile(r'<string lang="%s"(?: */>|>(.*?)</string>)' % re.escape(lang), re.S)
        self.entries: List[Entry] = []
        for match in _TEXT_RE.finditer(self.document):
            string = string_re.search(match.group(3))
            if string is None:
                continue
            base = match.start(3)
            if string.group(1) is None:
                start, end, text, closing = base + string.start(), base + string.end(), "", True
            else:
                start, end, text, closing = base + string.start(1), base + string.end(1), unescape(string.group(1)), False
            self.entries.append(Entry(int(match.group(2)), match.group(1), text, start, end, closing))
        if not self.entries:
            raise FormatError(f"no <string lang=\"{lang}\"> entries")
        self.by_id: Dict[int, Entry] = {entry.id: entry for entry in self.entries}

    def build(self, texts: Sequence[Optional[str]], lang: str = LANG) -> bytes:
        """The file with ``texts[i]`` as the string of ``entries[i]``; None or an equal text keeps it."""
        parts, position = [], 0
        for entry, text in zip(self.entries, texts):
            if text is None or text == entry.text:
                continue
            parts.append(self.document[position:entry.start])
            if entry.self_closing:
                parts.append(f'<string lang="{lang}">{escape(text)}</string>' if text else
                             self.document[entry.start:entry.end])
            else:
                parts.append(escape(text))
            position = entry.end
        parts.append(self.document[position:])
        return "".join(parts).encode("utf-8")
