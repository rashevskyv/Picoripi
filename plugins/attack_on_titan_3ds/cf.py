"""``_catfiles_lists/system.cf`` of Attack on Titan: Humanity in Chains (3DS): the game's text.

The file is a memory image (little endian) of about 670 KB that Spike Chunsoft's engine loads as it is: a header
whose u32 words at 0x14..0x20 are section end offsets (the last one is the file size), data tables, a table of
2,684 u32 offsets at 0x38774 and, from 0x3B164 to the end of the first section (0xA5280), the strings: UTF-16LE,
each ended by a NUL unit, one after another (5,501 of them, 5,379 not empty; line breaks are ``\\n``, a page ends
with ``@``; the characters U+FF61..U+FF9F are button and icon glyphs of the game's font).

The strings are referenced by position (tables and scripts keep absolute offsets that are not decoded), so a text
is written back in place: it must fit in the room of the original string (its length up to the NUL unit); a
shorter text is padded with spaces (the NUL units between strings stay where they are). Nothing else of the
file changes.
"""
from __future__ import annotations

import struct
from typing import List, Sequence, Tuple

FILE_SIZE = 0xA7D80
TEXT_START = 0x3B164
TEXT_END = 0xA5280


class FormatError(ValueError):
    pass


class SystemCf:
    def __init__(self, raw: bytes):
        raw = bytes(raw)
        if len(raw) != FILE_SIZE or struct.unpack_from("<I", raw, 0x20)[0] != FILE_SIZE:
            raise FormatError("not the Attack on Titan system.cf")
        if struct.unpack_from("<I", raw, 0x14)[0] != TEXT_END:
            raise FormatError("unexpected section table")
        self.raw = raw
        self.spans: List[Tuple[int, int]] = []   # (offset, byte length up to the NUL unit)
        at = TEXT_START
        while at < TEXT_END:
            end = at
            while end + 1 < len(raw) and raw[end:end + 2] != b"\0\0":
                end += 2
            self.spans.append((at, end - at))
            at = end + 2
        self.texts = [raw[a:a + n].decode("utf-16-le", "surrogatepass") for a, n in self.spans]

    def build(self, texts: Sequence[str]) -> bytes:
        if len(texts) != len(self.spans):
            raise FormatError(f"{len(texts)} strings for {len(self.spans)} entries")
        out = bytearray(self.raw)
        for index, ((at, room), old, new) in enumerate(zip(self.spans, self.texts, texts)):
            if str(new) == old:
                continue
            blob = str(new).encode("utf-16-le", "surrogatepass")
            if len(blob) > room:
                raise FormatError(f"string {index + 1}: {len(blob) // 2} characters, the original has room for "
                                  f"{room // 2}: {str(new)[:40]!r}")
            out[at:at + room] = blob + b" \x00" * ((room - len(blob)) // 2)   # spaces keep the NUL count of the region
        return bytes(out)

    def capacity(self, index: int) -> int:
        """The number of UTF-16 characters string ``index`` may have."""
        return self.spans[index][1] // 2
