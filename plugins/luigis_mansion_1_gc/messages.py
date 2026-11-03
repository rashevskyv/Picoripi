"""The message table of Luigi's Mansion (GameCube): one ``message/messageNN.csv`` member of an event archive.

The file is Shift-JIS text (the English slot is ASCII; a few messages are Japanese). A record ends with CRLF, so
``<SPEAK>(n)`` in the event script reads record n. An LF inside a record is a line break within the message. Tags
are ``<TAG>`` or ``<TAG>(n)``. A file that does not decode as Shift-JIS is not a message table.
"""
from __future__ import annotations

import re
import unicodedata
import warnings
from typing import List, Sequence, Tuple

from core.i18n import tr

ENCODING = "cp932"
RECORD_END = "\r\n"
TAG_NAME = re.compile(r"<([A-Z][A-Z0-9_]*)>")
# Ukrainian letters that Shift-JIS lacks: the game's font draws them in unused cp932 Cyrillic slots (char_map.json).
SLOT_OF = {"Ґ": "Ё", "Є": "Э", "І": "Ы", "Ї": "Ъ", "ґ": "ё", "є": "э", "і": "ы", "ї": "ъ"}
TO_SLOT = str.maketrans(SLOT_OF)
FROM_SLOT = str.maketrans({slot: letter for letter, slot in SLOT_OF.items()})
# Typographic marks with no Shift-JIS code: the nearest Shift-JIS mark is written instead.
PUNCT_FALLBACK = str.maketrans({"—": "―", "«": "“", "»": "”"})


def _game_text(text: str) -> Tuple[str, List[Tuple[str, str]]]:
    """``text`` as the game can code it, and the (character, written) pairs of the characters that had no code.

    A character with no Shift-JIS code (a Latin accent such as è, the dialogue font has no glyph for it) is written as
    its base letter (è -> e). A character with no base letter (for example Serbian dje) is written as "?".
    """
    out: List[str] = []
    replaced: List[Tuple[str, str]] = []
    for char in text.translate(TO_SLOT).translate(PUNCT_FALLBACK):
        try:
            char.encode(ENCODING)
        except UnicodeEncodeError:
            base = unicodedata.normalize("NFKD", char)[:1]
            written = base if base.isascii() and base.isalpha() else "?"
            replaced.append((char, written))
            char = written
        out.append(char)
    return "".join(out), replaced


def encode(text: str) -> bytes:
    """``text`` in the game's encoding (Ukrainian letters and the marks of PUNCT_FALLBACK included; see _game_text)."""
    return _game_text(text)[0].encode(ENCODING)


class Table:
    """One message file. ``build`` returns the original bytes while no record changed."""

    def __init__(self, raw: bytes):
        self.raw = bytes(raw)
        text = self.raw.decode(ENCODING).translate(FROM_SLOT)   # ValueError (UnicodeDecodeError) for a file that is not Shift-JIS
        # A message table uses only <COLOR> tags. An event script (text/eventNN.txt) uses command tags such as <END>.
        # ponytail: a tag list, checked on the real discs; a new message tag needs it here.
        if any(tag != "COLOR" for tag in TAG_NAME.findall(text)):
            raise ValueError("event script, not a message table")
        self.tail = text.endswith(RECORD_END)
        body = text[:-len(RECORD_END)] if self.tail else text
        self._texts: List[str] = body.split(RECORD_END) if text else []

    def texts(self) -> List[str]:
        return list(self._texts)

    def ids(self) -> List[str]:
        return [str(i + 1) for i in range(len(self._texts))]

    def build(self, texts: Sequence[str]) -> bytes:
        if list(texts) == self._texts:
            return self.raw
        if len(texts) != len(self._texts):
            raise ValueError(tr("the message file holds {0} records, {1} were given", len(self._texts), len(texts)))
        records: List[str] = []
        for number, text in enumerate(texts, 1):
            if RECORD_END in text:
                raise ValueError(tr("record {0}: a record break (CRLF) is not allowed inside a message", number))
            game, replaced = _game_text(text)
            for char, written in replaced:   # a warning, not an error: the import keeps the line (see translation_import)
                warnings.warn(tr("record {0}: the character {1} has no Shift-JIS code; written as {2}",
                                 number, repr(char), repr(written)), stacklevel=2)
            records.append(game)
        body = RECORD_END.join(records)
        return (body + RECORD_END if self.tail else body).encode(ENCODING)
