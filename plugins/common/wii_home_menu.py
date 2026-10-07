"""Wii HOME Menu messages (``HomeButton2/home.csv``, ``home_nosave.csv``): UTF-16 with a BOM, one message a row,
one quoted cell a language separated by tabs (Japanese, English, German, French, Spanish, Italian, Dutch,
Chinese, English again, Korean). A plugin edits the English cell; every other byte stays as it is. Shared by
the Wii plugins (Skyward Sword HD, Super Paper Mario, Metroid: Other M)."""
import re
from typing import List, Tuple

ENGLISH = 1
_CELL = re.compile(r'"((?:[^"]|"")*)"')
_BOMS = {b"\xfe\xff": "utf-16-be", b"\xff\xfe": "utf-16-le"}


def is_home_csv(raw: bytes) -> bool:
    return bytes(raw[:2]) in _BOMS and bytes(raw[2:4]) in (b'\x00"', b'"\x00')


class HomeCsv:
    """The file's text and the spans of its English cells."""

    def __init__(self, raw: bytes):
        if not is_home_csv(raw):
            raise ValueError("Not a HOME Menu message table")
        self.bom, self.codec = bytes(raw[:2]), _BOMS[bytes(raw[:2])]
        self.text = bytes(raw[2:]).decode(self.codec)
        self.spans: List[Tuple[int, int]] = []
        column, at = 0, 0
        for match in _CELL.finditer(self.text):
            if self.text[at:match.start()].count("\n"):
                column = 0
            if column == ENGLISH:
                self.spans.append(match.span(1))
            column, at = column + 1, match.end()

    @property
    def messages(self) -> List[str]:
        return [self.text[a:b].replace('""', '"').replace("\r\n", "\n") for a, b in self.spans]

    def build(self, messages: List[str]) -> bytes:
        text = self.text
        for (start, end), new in sorted(zip(self.spans, messages), reverse=True):
            text = text[:start] + new.replace("\r\n", "\n").replace("\n", "\r\n").replace('"', '""') + text[end:]
        return self.bom + text.encode(self.codec)
