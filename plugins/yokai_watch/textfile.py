"""One Yo-kai Watch text file (``*_en.cfg.bin``) as the rows the editor shows, and back.

A row is one string parameter of an entry: ``TEXT_INFO`` (text id, page number, text, variance) and
``NOUN_INFO`` (noun id, variance, ..., name at 5, plural at 9). Strings the English game never shows stay
out of the editor and are written back as they are: Japanese leftovers (dummy NPC names, debug messages)
and the passwords players type in (``password_text``). The Switch games (``japanese=True``) show the Japanese
lines too: the English fan mods left them untranslated, so they are translated from Japanese.
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Dict, List, Optional, Sequence

from . import tags
from .cfgbin import CfgBin, u32

_JAPANESE = re.compile(r"[぀-ヿ㐀-鿿ｦ-ﾟ]")
_UNTRANSLATED_FILES = ("password_text",)


@dataclass
class Row:
    entry: int
    param: int
    kind: str               # entry name: TEXT_INFO, NOUN_INFO...
    text_id: int            # first parameter of the entry (u32): the id the game asks for
    number: int             # second parameter: page number of a TEXT_INFO, variance of a NOUN_INFO
    text: str               # as stored (game markup)


def is_japanese(text: str) -> bool:
    return bool(_JAPANESE.search(tags.GAME_TAG_RE.sub("", text)))


def shown(text: Optional[str], name: str = "", japanese: bool = False) -> bool:
    if text is None or any(part in name for part in _UNTRANSLATED_FILES):
        return False
    return japanese or not is_japanese(text)


class TextFile:
    """A parsed text file: ``rows`` in file order."""

    def __init__(self, raw: bytes, name: str = "", japanese: bool = False):
        self.table = CfgBin(raw)
        self.name = name
        self.rows: List[Row] = []
        for e, p, text in self.table.strings():
            if not shown(text, name, japanese):
                continue
            entry = self.table.entries[e]
            first = entry.values[0] if entry.values and isinstance(entry.values[0], int) else 0
            second = entry.values[1] if len(entry.values) > 1 and isinstance(entry.values[1], int) else 0
            self.rows.append(Row(e, p, entry.name, u32(first), second, text))

    def japanese_rows(self) -> List[int]:
        """Indices of the rows whose text is Japanese (only shown with ``japanese=True``)."""
        return [i for i, row in enumerate(self.rows) if is_japanese(row.text)]

    def texts(self) -> List[str]:
        return [tags.to_editor(row.text) for row in self.rows]

    def build(self, strings: Sequence[str]) -> bytes:
        """The file with the editor's ``strings`` (one per row; missing ones keep the source text)."""
        changes: Dict[tuple, str] = {}
        for row, text in zip(self.rows, strings):
            if str(text) != tags.to_editor(row.text):   # a debug line of Yo-kai Watch 1 (Switch) has a { } of its own
                changes[(row.entry, row.param)] = tags.from_editor(text)
        # the English fan mod of the Switch game writes repeated strings again: an unedited file stays as it is
        return self.table.build(changes) if changes else self.table.raw
