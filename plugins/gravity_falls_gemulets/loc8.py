"""UbiArt ``.loc8`` localisation files as the 3DS build of Gravity Falls: Legend of the Gnome Gemulets stores them.

The file holds one section per language (English, French, German, Spanish, Italian here). A section is

- ``count`` simple records ``u32 id, u32 length, UTF-8 text`` (menu and system strings), then
- complex records ``u32 speaker hash, u32 id, u32 length, UTF-8 text, u32 0xFFFFFFFF, u32 variant, u32 next hash``
  (dialogue, quest texts, animation names) until the next section's header.

Everything between and around the records (hash tables, section headers) is kept as it is; no offset or size in the
file points into the records, so a text may change its length. All numbers are big endian.
"""
from __future__ import annotations

import struct
from typing import List, Optional, Sequence, Tuple

END = 0xFFFFFFFF
MAX_TEXT = 4000
LANGUAGE_NAMES = {0: "English", 1: "French", 2: "Japanese", 3: "German", 4: "Spanish", 5: "Italian"}


class FormatError(ValueError):
    pass


def _text(raw: bytes, at: int, length: int) -> Optional[str]:
    if length > MAX_TEXT or at + length > len(raw):
        return None
    chunk = raw[at:at + length]
    if any(b < 0x20 and b != 0x0A for b in chunk):
        return None
    try:
        return chunk.decode("utf-8")
    except UnicodeDecodeError:
        return None


def _simple_run(raw: bytes, at: int, count: int) -> Optional[Tuple[int, List[Tuple[int, str]]]]:
    records = []
    for _ in range(count):
        if at + 8 > len(raw):
            return None
        ident, length = struct.unpack_from(">II", raw, at)
        text = _text(raw, at + 8, length)
        if text is None or ident > 0xFFFFFF:
            return None
        records.append((ident, text))
        at += 8 + length
    return at, records


def _complex_run(raw: bytes, at: int) -> Tuple[int, List[Tuple[int, int, str, int, int]]]:
    records = []
    while at + 12 <= len(raw):
        speaker, ident, length = struct.unpack_from(">III", raw, at)
        text = _text(raw, at + 12, length)
        if text is None or at + 24 + length > len(raw):
            break
        marker, variant, following = struct.unpack_from(">III", raw, at + 12 + length)
        if marker != END or ident > 0xFFFFFF:
            break
        records.append((speaker, ident, text, variant, following))
        at += 24 + length
    return at, records


class Section:
    """One language: the simple records and the complex ones with the byte ranges they occupy."""

    def __init__(self, start: int, simple_end: int, end: int, language: int,
                 simple: List[Tuple[int, str]], complex_: List[Tuple[int, int, str, int, int]]):
        self.start, self.simple_end, self.end, self.language = start, simple_end, end, language
        self.simple, self.complex = simple, complex_

    @property
    def name(self) -> str:
        return LANGUAGE_NAMES.get(self.language, f"Language {self.language}")

    def texts(self) -> List[str]:
        return [text for _ident, text in self.simple] + [record[2] for record in self.complex]

    def ids(self) -> List[int]:
        return [ident for ident, _text in self.simple] + [record[1] for record in self.complex]

    def serialise(self, texts: Sequence[str]) -> bytes:
        if len(texts) != len(self.simple) + len(self.complex):
            raise FormatError(f"{len(texts)} strings for {len(self.simple) + len(self.complex)} records")
        out = bytearray()
        for (ident, _old), text in zip(self.simple, texts):
            blob = text.encode("utf-8")
            out += struct.pack(">II", ident, len(blob)) + blob
        for (speaker, ident, _old, variant, following), text in zip(self.complex, texts[len(self.simple):]):
            blob = text.encode("utf-8")
            out += struct.pack(">III", speaker, ident, len(blob)) + blob + struct.pack(">III", END, variant, following)
        return bytes(out)


class Loc8:
    """A parsed file: ``sections`` in file order; ``build(texts_per_section)`` writes the file again."""

    def __init__(self, raw: bytes):
        self.raw = bytes(raw)
        self.sections: List[Section] = []
        at = 8
        while at < len(self.raw) - 8:
            found = self._section_at(at)
            if found is None:
                at += 1
                continue
            self.sections.append(found)
            at = found.end
        if not self.sections:
            raise FormatError("no localisation section found")

    def _section_at(self, at: int) -> Optional[Section]:
        raw = self.raw
        count = struct.unpack_from(">I", raw, at - 4)[0]
        if not 2 <= count <= 20000 or at + 8 > len(raw):
            return None
        ident, length = struct.unpack_from(">II", raw, at)
        if length > MAX_TEXT or ident > 0xFFFF or length == 0:
            return None
        run = _simple_run(raw, at, count)
        if run is None:
            return None
        simple_end, simple = run
        end, complex_ = _complex_run(raw, simple_end)
        if not complex_:
            return None
        language = struct.unpack_from(">I", raw, at - 8)[0]
        return Section(at, simple_end, end, language if language < 16 else 0, simple, complex_)

    def texts(self) -> List[List[str]]:
        return [section.texts() for section in self.sections]

    def build(self, texts: Sequence[Sequence[str]]) -> bytes:
        if len(texts) != len(self.sections):
            raise FormatError(f"{len(texts)} languages for {len(self.sections)} sections")
        if [list(t) for t in texts] == self.texts():
            return self.raw
        out = bytearray()
        at = 0
        for section, new in zip(self.sections, texts):
            out += self.raw[at:section.start]
            out += section.serialise([str(t) for t in new])
            at = section.end
        out += self.raw[at:]
        return bytes(out)
