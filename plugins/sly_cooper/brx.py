"""Sly Cooper and the Thievius Raccoonus (ProjectCane PC/Switch port): level .brx files, their text spans.

Facts from the ProjectCane source (Sly1-Release): a level file on disk is raw data (the extractor writes it
decompressed, transition.cpp opens it without decoding). Text is a u16 little-endian length followed by that many
bytes, with no terminator (CBinaryInputStream::ReadStringSw). Texture offsets are relative to the stream position
taken at load time (shd.cpp textureDataStart), but that position comes from Align(0x10) counted from the file start
(sw.cpp). So the texture block only stays aligned when every length change is a multiple of 16. replace_spans pads
a new text with trailing spaces to keep that: the port draws them as blank space.

This module finds candidate text spans and replaces them. It does not decode the object tree: a span is text only
when its bytes pass ``is_text``. Spans that are not text are never reported, so they are never edited.
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from typing import List, Sequence, Tuple

MIN_LENGTH = 4
MAX_LENGTH = 600
ALIGNMENT = 16  # sw.cpp: pbis->Align(0x10) before the texture block
_PRINTABLE = re.compile(rb"[\x20-\x7e]+")
_IDENTIFIER = re.compile(rb"[a-z0-9_]+")
_LONG_RUN = re.compile(rb"([^ ])\1\1\1")  # a run of spaces is alignment padding, not noise
_VOWEL = re.compile(rb"[aeiouyAEIOUY]")


@dataclass(frozen=True)
class TextSpan:
    """One length-prefixed text span: ``offset`` is the position of the u16 length, ``text`` the bytes after it."""

    offset: int
    text: str

    @property
    def length(self) -> int:
        return len(self.text.encode("ascii"))


def is_text(raw: bytes) -> bool:
    """True when the bytes read like game text (sentences, names, credit lines), not pixels or identifiers."""
    if len(raw) < MIN_LENGTH or not all(0x20 <= b <= 0x7E for b in raw):
        return False
    if _IDENTIFIER.fullmatch(raw):
        return False  # event and file names such as from_hub: editing one breaks the level
    letters = sum(1 for b in raw if (0x41 <= b <= 0x5A) or (0x61 <= b <= 0x7A))
    if letters < 3 or letters * 2 < len(raw):
        return False
    if _LONG_RUN.search(raw):
        return False  # pixel noise such as zzzzzzzz
    if not _VOWEL.search(raw):
        return False  # pixel noise such as GDGD
    # A sentence has a space. A short line must end in punctuation, such as "Really?" or "Sly!".
    return b" " in raw or (raw[-1:] in (b".", b"!", b"?") and sum(1 for b in raw if 0x61 <= b <= 0x7A) >= 3)


def scan_text(data: bytes) -> List[TextSpan]:
    """Every text span in ``data``, in file order, without overlaps."""
    spans: List[TextSpan] = []
    free_from = 0  # first byte after the last accepted span; a span lies inside one printable run
    for run in _PRINTABLE.finditer(data):
        position = max(run.start(), free_from + 2)
        while position < run.end():
            length = int.from_bytes(data[position - 2:position], "little")
            if MIN_LENGTH <= length <= MAX_LENGTH and position + length <= run.end():
                raw = data[position:position + length]
                if is_text(raw):
                    spans.append(TextSpan(position - 2, raw.decode("ascii")))
                    free_from = position + length
                    position = free_from + 2
                    continue
            position += 1
    return spans


def replace_spans(data: bytes, edits: Sequence[Tuple[TextSpan, str]]) -> bytes:
    """Return ``data`` with each span's text replaced by the new text. The u16 length is rewritten to match.

    The new text gets trailing spaces so that its length differs from the old one by a multiple of 16: the
    texture block after the text stays on its 16-byte alignment (see the module docstring).
    Raises ValueError when a new text is not printable ASCII or is longer than MAX_LENGTH. Every edit is checked
    against the span it replaces: the stored bytes must still be the original text."""
    out = bytearray()
    cursor = 0
    for span, new_text in sorted(edits, key=lambda item: item[0].offset):
        raw_old = span.text.encode("ascii")
        at = span.offset
        if at < cursor or data[at + 2:at + 2 + len(raw_old)] != raw_old:
            raise ValueError(f"span at {at:#x} does not match the file")
        if int.from_bytes(data[at:at + 2], "little") != len(raw_old):
            raise ValueError(f"span at {at:#x} has a different length prefix")
        raw_new = new_text.encode("ascii")  # UnicodeEncodeError is a ValueError
        if not (1 <= len(raw_new) <= MAX_LENGTH) or not all(0x20 <= b <= 0x7E for b in raw_new):
            raise ValueError(f"new text at {at:#x} is not printable ASCII of 1..{MAX_LENGTH} bytes")
        padded_length = len(raw_new) + (len(raw_old) - len(raw_new)) % ALIGNMENT
        if padded_length > MAX_LENGTH:
            raise ValueError(f"new text at {at:#x} is too long after alignment padding")
        raw_new = raw_new.ljust(padded_length, b" ")
        out += data[cursor:at]
        out += len(raw_new).to_bytes(2, "little") + raw_new
        cursor = at + 2 + len(raw_old)
    out += data[cursor:]
    return bytes(out)
