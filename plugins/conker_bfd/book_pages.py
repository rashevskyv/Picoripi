"""Text pages of the instruction book (bank 0x1A entries): a four-word header, the text, and a code list.

Layout of one decoded page (big-endian words):
- word 0: always 0x10, the start of the text;
- word 1: the text length in bytes, NUL terminators included;
- word 2: the code list offset, 0x10 + the text length rounded up to eight;
- word 3: 0x80000000 | the code list length in bytes.
The text runs from 0x10 to 0x10 + word 1. Zero bytes fill up to word 2. The code list holds u16 values. The
page is padded with zeros to eight bytes. Pages are addressed by their slot in the entry's table, so an empty
slot stays empty.
"""
from __future__ import annotations

import struct
from dataclasses import dataclass
from typing import Optional

from .containers import align8
from .n64_archive import RomError

HEADER_SIZE = 0x10
_TEXT_START = 0x10
_CODE_FLAG = 0x80000000


@dataclass(frozen=True)
class Page:
    text: bytes   # the text region, NUL terminators included (its length is word 1)
    codes: bytes  # the code list as stored

    def payload(self) -> bytes:
        """The page bytes as the game reads them."""
        head = struct.pack(">IIII", _TEXT_START, len(self.text), HEADER_SIZE + align8(len(self.text)),
                           _CODE_FLAG | len(self.codes))
        body = bytearray(head)
        body += self.text
        body += b"\x00" * (align8(len(self.text)) - len(self.text))
        body += self.codes
        body += b"\x00" * (align8(len(body)) - len(body))
        return bytes(body)


def parse_page(payload: bytes) -> Optional[Page]:
    """The page in ``payload``, or None when the bytes do not follow the page layout."""
    if len(payload) < HEADER_SIZE:
        return None
    start, text_len, code_at, code_word = struct.unpack_from(">IIII", payload, 0)
    code_len = code_word & ~_CODE_FLAG
    if start != _TEXT_START or not code_word & _CODE_FLAG or text_len == 0:
        return None
    if code_at != HEADER_SIZE + align8(text_len) or code_len % 2:
        return None
    if code_at + code_len > len(payload) or len(payload) != align8(code_at + code_len):
        return None
    text = bytes(payload[HEADER_SIZE:HEADER_SIZE + text_len])
    if text[-1] != 0:
        return None
    if any(payload[HEADER_SIZE + text_len:code_at]) or any(payload[code_at + code_len:]):
        return None
    return Page(text=text, codes=bytes(payload[code_at:code_at + code_len]))


def page_text(text: bytes) -> bytes:
    """The text without trailing NUL terminators (the editor shows these as a count)."""
    return text.rstrip(b"\x00")


def page_from_body(body: bytes, terminators: int) -> bytes:
    """Rebuild the text region from an edited body and the original count of trailing NUL bytes."""
    if terminators < 1:
        raise RomError("a page text needs at least one NUL terminator")
    return body + b"\x00" * terminators
