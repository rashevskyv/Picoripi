r"""Skies of Arcadia (GameCube Legends, Dreamcast) message scripts (``*.sct``): the text pages inside a script.

A decoded script holds bytecode with text pages inline. Text escapes are plain bytes: a page starts with ``\h(``
and names its speaker in ``\x81s NAME \x81t`` followed by ``)``. The text runs to ``\c`` (the page ends, the
next page follows) or ``\e`` (the box ends). ``\n`` is a line break and byte ``\x7f`` is a space. Between pages
the bytes are bytecode; this reader does not decode them and never rewrites them.

GameCube scripts are AKLZ files (``core.containers.aklz``); Dreamcast scripts are plain. The page layout is the
same on both, only the bytecode word order differs (big endian on GameCube, little endian on Dreamcast).
"""
from __future__ import annotations

from typing import List, NamedTuple, Optional

HEAD = b"\\h("
PAGE_END = (b"\\c", b"\\e")
SPEAKER_OPEN = b"\x81s"
SPEAKER_CLOSE = b"\x81t"


class Page(NamedTuple):
    start: int          # offset of the page head ``\h(``
    end: int            # offset just past the terminator (``\c`` or ``\e``)
    speaker: Optional[bytes]
    text: bytes         # the text after ``)``, up to the terminator
    terminator: bytes   # b"\c" or b"\e"


def _page_at(body: bytes, start: int) -> Optional[Page]:
    stop = len(body)
    for end_code in PAGE_END:
        pos = body.find(end_code, start + len(HEAD))
        if pos >= 0 and pos < stop:
            stop = pos
    if stop >= len(body):
        return None
    content = body[start + len(HEAD):stop]
    speaker = None
    text = content
    if content.startswith(SPEAKER_OPEN):
        close = content.find(SPEAKER_CLOSE)
        if close >= 0:
            speaker = content[len(SPEAKER_OPEN):close]
            text = content[close + len(SPEAKER_CLOSE):]
            if text.startswith(b")"):
                text = text[1:]
    return Page(start, stop + 2, speaker, text, body[stop:stop + 2])


def pages(body: bytes) -> List[Page]:
    """Every text page of a decoded script, in file order."""
    out: List[Page] = []
    pos = body.find(HEAD)
    while pos >= 0:
        page = _page_at(body, pos)
        if page is None:
            break
        out.append(page)
        pos = body.find(HEAD, page.end)
    return out
