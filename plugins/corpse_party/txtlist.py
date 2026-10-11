"""Corpse Party (3DS) text lists in ``data\\*.txt``: comma separated rows with quoted strings.

``itemdatalist.txt`` (item names and descriptions), ``deaddatalist.txt`` (the victims' notes), ``endinglist.txt``
(ending names), ``playersettinglist.txt`` (character names). The game reads these files as they are (Shift-JIS);
a string is one quoted value, ``/n`` inside it is a line break (shown as ``\\n``). Quotes inside comments (``//``)
are not strings. Other lists of the folder (BGM, bitmap, face lists) hold names of files and no English text.
"""
from __future__ import annotations

import re
from typing import List, Tuple

_QUOTED = re.compile(r'"([^"\r\n]*)"')


class ListError(ValueError):
    pass


def is_list(raw: bytes) -> bool:
    return not raw.startswith((b"table", b"FFNT", b"CTPK", b"SARC")) and bool(_strings(raw))


def _decode(raw: bytes) -> str:
    return raw.decode("cp932", "surrogateescape")


def _spans(text: str) -> List[Tuple[int, int]]:
    spans = []
    for line_start, line in _lines(text):
        cut = line.find("//")
        for m in _QUOTED.finditer(line if cut < 0 else line[:cut]):
            spans.append((line_start + m.start(1), line_start + m.end(1)))
    return spans


def _lines(text: str):
    pos = 0
    for line in text.split("\n"):
        yield pos, line
        pos += len(line) + 1


def _strings(raw: bytes) -> List[str]:
    text = _decode(raw)
    return [text[a:b] for a, b in _spans(text)]


def texts(raw: bytes) -> List[str]:
    return [s.replace("/n", "\n") for s in _strings(raw)]


def rebuild(raw: bytes, new: List[str]) -> bytes:
    text = _decode(raw)
    spans = _spans(text)
    if len(new) != len(spans):
        raise ListError(f"{len(new)} strings for {len(spans)} in the list")
    out, last = [], 0
    for (a, b), value in zip(spans, new):
        out.append(text[last:a])
        out.append(value.replace("\n", "/n"))
        last = b
    out.append(text[last:])
    result = "".join(out)
    try:
        return result.encode("cp932", "surrogateescape")
    except UnicodeEncodeError as error:
        raise ListError(f"cannot write {result[error.start:error.end]!r} (Shift-JIS)") from None
