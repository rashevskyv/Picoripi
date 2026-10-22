"""Hades text: the strings of a SJSON file and of a subtitle CSV, one row per string, and the same file written back.

SJSON: a row is the content of one DisplayName or Description string, as the file holds it (escapes and the
triple-quoted raw strings are kept). Other keys (Id, Speaker, flags) are not rows. A row that does not change keeps
its bytes; a changed row is written over its span. A quote mark inside a plain string is escaped. A row with a line
break goes into a triple-quoted raw string; a row that cannot be written that way keeps its original text and is
reported.

CSV: a row is the Line column (index 7) of each record after the header line. The file is rewritten by csv only when
a row changed. The files use CRLF line endings; the CSV writer keeps them.
"""
from __future__ import annotations

import csv
import io
import re
from typing import List, Optional, Tuple

STRING = re.compile(rb'(?P<key>DisplayName|Description)(?P<gap>[ \t]*=[ \t]*)'
                    rb'(?P<raw>"""[\s\S]*?"""|"(?:[^"\\\r\n]|\\.)*")')
LINE_COLUMN = 7
TRIPLE = b'"""'
UNESCAPED_QUOTE = re.compile(rb'(?<!\\)"')


def _inner(raw: bytes) -> bytes:
    return raw[3:-3] if raw.startswith(TRIPLE) else raw[1:-1]


def _literal(text: str) -> Optional[bytes]:
    """The literal of the file for ``text``, or None when the text cannot be written as one.

    A row without a line break is a plain string: its unescaped quote marks get a backslash. A row with a line break is
    a triple-quoted raw string; it cannot end with a quote mark or hold three quote marks in a row.
    """
    data = text.encode("utf-8")
    if b"\r" in data or b"\n" in data:
        if data.endswith(b'"') or TRIPLE in data:
            return None
        return TRIPLE + data + TRIPLE
    if data.endswith(b"\\"):
        return None
    return b'"' + UNESCAPED_QUOTE.sub(rb'\\"', data) + b'"'


def read_sjson(data: bytes) -> List[str]:
    """The text of every DisplayName and Description string, in file order."""
    return [_inner(match.group("raw")).decode("utf-8") for match in STRING.finditer(data)]


def write_sjson(data: bytes, rows: List[str]) -> Tuple[bytes, List[str]]:
    """The bytes of the file with ``rows`` written over its strings. Returns (bytes, warnings).

    ``rows`` must have one row per string; otherwise the file is returned unchanged with a warning. A row that cannot be
    written keeps its original string and adds a warning.
    """
    matches = list(STRING.finditer(data))
    if len(rows) != len(matches):
        return data, [f"row count changed ({len(rows)} for {len(matches)}); file not saved"]
    out = bytearray()
    cursor = 0
    warnings: List[str] = []
    for match, row in zip(matches, rows):
        original = match.group("raw")
        if row == _inner(original).decode("utf-8"):
            continue
        literal = _literal(row)
        if literal is None:
            warnings.append(f"a row cannot be written as a string literal, kept as it was: {row[:40]!r}")
            continue
        if literal == original:
            continue
        out += data[cursor:match.start("raw")]
        out += literal
        cursor = match.end("raw")
    out += data[cursor:]
    return bytes(out), warnings


def read_csv(data: bytes) -> List[str]:
    """The Line cell of each record after the header line (a record without that column gives an empty row)."""
    records = list(csv.reader(io.StringIO(data.decode("utf-8-sig"), newline="")))
    return [record[LINE_COLUMN] if len(record) > LINE_COLUMN else "" for record in records[1:]]


def write_csv(data: bytes, rows: List[str]) -> Tuple[bytes, List[str]]:
    """The bytes of the file with ``rows`` as the Line cells of its records. Unchanged files keep their bytes."""
    text_value = data.decode("utf-8-sig")
    records = list(csv.reader(io.StringIO(text_value, newline="")))
    if len(rows) != len(records) - 1:
        return data, [f"row count changed ({len(rows)} for {len(records) - 1}); file not saved"]
    changed = False
    for record, row in zip(records[1:], rows):
        if len(record) > LINE_COLUMN and record[LINE_COLUMN] != row:
            record[LINE_COLUMN] = row
            changed = True
    if not changed:
        return data, []
    buffer = io.StringIO(newline="")
    csv.writer(buffer, lineterminator="\r\n").writerows(records)
    body = buffer.getvalue()
    if not text_value.endswith("\r\n") and body.endswith("\r\n"):
        body = body[:-2]   # the file has no line break after its last record: keep it that way
    prefix = b"\xef\xbb\xbf" if data.startswith(b"\xef\xbb\xbf") else b""
    return prefix + body.encode("utf-8"), []
