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

import bisect
import struct
from typing import Dict, List, NamedTuple, Sequence, Tuple

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


def grow_pages(body: bytes, texts: Dict[int, bytes], big: bool, relocate_words: bool = True) -> Tuple[bytes, int]:
    """Replace the text of several pages in one pass. ``texts`` maps a page index to its new text.

    Each edited page moves the code after it by its own ``delta`` (its length change rounded up to 4, zero padded).
    Every old offset maps to ``offset + sum(deltas of the edited pages that end at or before it)``. Absolute words
    (aligned, pointing into the script) and label entries (any alignment) are mapped this way. Labels inside a page's
    text or terminator are refused. Returns (new body, total delta).
    """
    pages = skies_sct.pages(body)
    fmt = ">I" if big else "<I"
    limit = len(body)
    edits = []
    for index in sorted(texts):
        page = pages[index]
        old_len = page.end - page.start
        old_block_end = page.end + (_round4(old_len) - old_len)
        if body[page.end:old_block_end].strip(b"\x00"):
            raise ValueError("the bytes after the page are not padding; cannot grow it safely")
        new_block = page_bytes(skies_sct.Page(page.start, page.end, page.speaker, texts[index], page.terminator))
        delta = _round4(len(new_block)) - _round4(old_len)
        new_block += b"\x00" * (_round4(len(new_block)) - len(new_block))
        prefix_len = len(page_bytes(skies_sct.Page(page.start, page.end, page.speaker, b"", b"")))
        edits.append((page.start, page.start + prefix_len, old_block_end, new_block, delta))
    labels = read_labels(body, big)
    for start, prefix_end, end, _, _ in edits:
        if any(prefix_end < label.target < end for label in labels):
            raise ValueError("a label points inside the text of a grown page")
    ends = [end for _, _, end, _, _ in edits]
    cumulative = []
    running = 0
    for _, _, _, _, delta in edits:
        running += delta
        cumulative.append(running)

    def shift(old: int) -> int:
        k = bisect.bisect_right(ends, old)
        return cumulative[k - 1] if k else 0

    out = bytearray()
    cursor = 0
    for start, _, end, new_block, _ in edits:
        out += body[cursor:start] + new_block
        cursor = end
    out += body[cursor:]
    label_fields = {HEADER_SIZE + LABEL_SIZE * i + NAME_SIZE: i for i in range(len(labels))}
    relocated = 0
    for old in range(0, limit - 3, 4):
        if old in label_fields:
            continue
        if any(start <= old < end for start, _, end, _, _ in edits):
            continue
        if not relocate_words:
            break
        value = struct.unpack_from(fmt, body, old)[0]
        if ends and ends[0] <= value < limit and value % 4 == 0:
            new_value = value + shift(value)
            struct.pack_into(fmt, out, old + shift(old), new_value)
            relocated += 1
    moved = []
    for label in labels:
        target = label.target + shift(label.target)
        moved.append(Label(label.name, target))
    for i, label in enumerate(labels):
        at = HEADER_SIZE + LABEL_SIZE * i + NAME_SIZE
        struct.pack_into(fmt, out, at + shift(at), moved[i].target)
    grow_pages.last_relocated = relocated
    return bytes(out), running


def grow_page(body: bytes, page_index: int, new_text: bytes, big: bool) -> Tuple[bytes, int]:
    """Replace the text of one page. See ``grow_pages``. Returns (new body, delta)."""
    return grow_pages(body, {page_index: new_text}, big)


def _round4(n: int) -> int:
    return (n + 3) & ~3
