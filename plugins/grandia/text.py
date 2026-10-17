"""Grandia II (Dreamcast) dialogue in the MAP AFS archives: messages to editor text and back, byte for byte.

Facts from the owner's disc (MAP/*.AFS, 90 archives, 91 entries with messages):

* A message starts with the marker ``17 00 02`` and ends where the next marker starts. The message ID follows
  as ``08 <id>`` in most messages (IDs count up inside one archive). A ``17 01`` ends the header; the text
  follows. No length field and no pointer table were found for the messages, so a record joins back to the
  same bytes and a longer text keeps the stream intact (the engine reads the stream in order).
* The text is one byte per character: letters and punctuation are their ASCII codes. Other bytes are codes
  of the engine (``00``, ``01``, ``03``, ``0f``, ``80`` ...). Their meaning is not decoded yet; they are kept
  as tags ``{XX}``, the same way Castlevania (``plugins/castlevania_dxc/text.py``) keeps its codes.

``split`` cuts an entry into its prefix and records, ``header_body`` cuts a record, ``to_text`` and ``from_text``
convert a body. ``{7B}`` and ``{7D}`` stand for the characters ``{`` and ``}``, so a tag never reads as text.
"""
from __future__ import annotations

import re
from typing import List, Optional, Tuple

MARK = b"\x17\x00\x02"
TEXT_START = b"\x17\x01"
TAG_RE = re.compile(r"\{([0-9A-F]{2})\}")


def split(blob: bytes) -> List[bytes]:
    """The pieces of an entry: a prefix (a table, when the entry starts with one) and one record per marker.

    ``b"".join(split(blob)) == blob`` always holds.
    """
    cuts = [0]
    pos = blob.find(MARK)
    while pos >= 0:
        if pos != cuts[-1]:
            cuts.append(pos)
        pos = blob.find(MARK, pos + 1)
    cuts.append(len(blob))
    return [blob[a:b] for a, b in zip(cuts, cuts[1:])]


def header_body(record: bytes) -> Tuple[bytes, bytes]:
    """The header (through ``17 01``) and the body of one record; a record with no ``17 01`` has no text."""
    at = record.find(TEXT_START)
    if at < 0:
        return record, b""
    cut = at + len(TEXT_START)
    return record[:cut], record[cut:]


MAX_HEADER = 40        # a message's header ends within 40 bytes of its marker; a binary table can hold 17 01 far later
MAX_BODY = 4096        # longer bodies are binary data in every archive checked (34 records of 2102)
MIN_PRINTABLE = 0.4    # a message body is mostly ASCII; the records below this are binary with a stray 17 01


def message_parts(piece: bytes) -> Optional[Tuple[bytes, bytes]]:
    """(header, body) of a message record, or None when the record holds no message text."""
    if TEXT_START not in piece:
        return None
    header, body = header_body(piece)
    if len(header) > MAX_HEADER or len(body) > MAX_BODY:
        return None
    printable = sum(1 for code in body if 0x20 <= code < 0x7F)
    if body and printable < MIN_PRINTABLE * len(body):
        return None
    return header, body


def to_text(body: bytes) -> str:
    """Editor text of a body: printable ASCII as itself, every other byte (and ``{`` ``}``) as a ``{XX}`` tag."""
    out = []
    for code in body:
        if 0x20 <= code < 0x7F and code not in (0x7B, 0x7D):
            out.append(chr(code))
        else:
            out.append("{%02X}" % code)
    return "".join(out)


def from_text(text: str) -> bytes:
    """The body bytes of editor text. Raises ValueError for a character that is not ASCII (no glyph yet)."""
    out = bytearray()
    pos = 0
    for match in TAG_RE.finditer(text):
        out.extend(_plain(text[pos:match.start()]))
        out.append(int(match.group(1), 16))
        pos = match.end()
    out.extend(_plain(text[pos:]))
    return bytes(out)


def _plain(chunk: str) -> bytes:
    for char in chunk:
        if not (0x20 <= ord(char) < 0x7F) or char in "{}":
            raise ValueError(f"not an ASCII character of the message font: {char!r}")
    return chunk.encode("ascii")
