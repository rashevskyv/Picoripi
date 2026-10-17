r"""Skies of Arcadia message scripts (``*.sct``): the label table and the writer for text pages.

Layout of a decoded script (the same on GameCube, big endian, and Dreamcast, little endian):

  0    16 bytes  header; u32 at 8 is the label count
  16   20 bytes  per label: 16-byte NUL padded name, then a 32-bit offset (the label's instruction word)
  16+20*count    code stream: bytecode with text pages inline (see ``core.containers.skies_sct``)

Hypothesis tested here (not proven for every opcode): branches name labels by index, so the only absolute offsets
are the label offsets and the header. Growing a text page by N bytes (a multiple of 4) moves only the code after
it; every label offset at or after the insertion point grows by N.
"""
from __future__ import annotations

import struct
from typing import List, NamedTuple, Sequence, Tuple

from core.containers import skies_sct

HEADER_SIZE = 16
LABEL_SIZE = 20
NAME_SIZE = 16


class Label(NamedTuple):
    name: bytes
    target: int


def _unpack_u32(body: bytes, at: int, big: bool) -> int:
    return struct.unpack_from(">I" if big else "<I", body, at)[0]


def _pack_u32(value: int, big: bool) -> bytes:
    return struct.pack(">I" if big else "<I", value)


def label_count(body: bytes, big: bool) -> int:
    return _unpack_u32(body, 8, big)


def read_labels(body: bytes, big: bool) -> List[Label]:
    count = label_count(body, big)
    labels: List[Label] = []
    for i in range(count):
        at = HEADER_SIZE + LABEL_SIZE * i
        name = body[at:at + NAME_SIZE].split(b"\x00", 1)[0]
        labels.append(Label(name, _unpack_u32(body, at + NAME_SIZE, big)))
    return labels


def code_start(body: bytes, big: bool) -> int:
    return HEADER_SIZE + LABEL_SIZE * label_count(body, big)


def write_labels(body: bytearray, labels: Sequence[Label], big: bool) -> None:
    for i, label in enumerate(labels):
        at = HEADER_SIZE + LABEL_SIZE * i + NAME_SIZE
        body[at:at + 4] = _pack_u32(label.target, big)


def page_bytes(page: skies_sct.Page) -> bytes:
    """The bytes of one page as the script holds them (inverse of ``skies_sct.pages``)."""
    head = skies_sct.HEAD
    if page.speaker is not None:
        head += skies_sct.SPEAKER_OPEN + page.speaker + skies_sct.SPEAKER_CLOSE + b")"
    return head + page.text + page.terminator


def rebuild_pages(body: bytes) -> bytes:
    """The body with every page re-assembled from its parts. Byte-exact for an unchanged script."""
    out = bytearray()
    cursor = 0
    for page in skies_sct.pages(body):
        out += body[cursor:page.start]
        out += page_bytes(page)
        cursor = page.end
    out += body[cursor:]
    return bytes(out)


def grow_page(body: bytes, page_index: int, new_text: bytes, big: bool) -> Tuple[bytes, int]:
    """Replace the text of one page. The page length changes; the code after it moves by ``delta`` bytes.

    ``delta`` is the change in length rounded up to a multiple of 4, so every later word keeps its alignment.
    Padding is zero bytes. Every aligned 32-bit word whose value is at or after the old end of the page is an
    absolute offset (label targets and the operands that point into the code); it grows by ``delta``. Words
    below that point are not changed. Returns (new body, delta).
    """
    pages = skies_sct.pages(body)
    page = pages[page_index]
    replaced = skies_sct.Page(page.start, page.end, page.speaker, new_text, page.terminator)
    old_len = page.end - page.start
    new_block = page_bytes(replaced)
    delta = _round4(len(new_block)) - _round4(old_len)
    new_block = new_block + b"\x00" * (_round4(len(new_block)) - len(new_block))
    old_block_end = page.end + (_round4(old_len) - old_len)
    old_tail = body[page.end:old_block_end]
    if old_tail.strip(b"\x00"):
        raise ValueError("the bytes after the page are not padding; cannot grow it safely")
    labels = read_labels(body, big)
    if any(page.start < label.target < old_block_end for label in labels):
        raise ValueError("a label points inside the grown page")
    out = bytearray(body[:page.start] + new_block + body[old_block_end:])
    limit = len(body)
    fmt = ">I" if big else "<I"
    relocated = 0
    block_end_new = page.start + len(new_block)
    label_fields = {HEADER_SIZE + LABEL_SIZE * i + NAME_SIZE for i in range(len(labels))}
    for at in range(0, len(out) - 3, 4):
        if page.start <= at < block_end_new or at in label_fields:
            continue
        value = struct.unpack_from(fmt, out, at)[0]
        if old_block_end <= value < limit and value % 4 == 0:
            struct.pack_into(fmt, out, at, value + delta)
            relocated += 1
    moved = [Label(label.name, label.target + delta if label.target >= old_block_end else label.target)
             for label in labels]
    write_labels(out, moved, big)
    grow_page.last_relocated = relocated
    return bytes(out), delta


def _round4(n: int) -> int:
    return (n + 3) & ~3
