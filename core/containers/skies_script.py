r"""Skies of Arcadia message scripts (``*.sct``): the label table, the branch operands and the writer for text pages.

Layout of a decoded script (the same on GameCube, big endian, and Dreamcast, little endian):

  0    16 bytes  header; u32 at 8 is the label count
  16   20 bytes  per label: 16-byte NUL padded name, then a u32 target
  16+20*count    code stream (``cs``): 32-bit words, with text pages inline (see ``core.containers.skies_sct``)

A label target is code-relative: the label sits at ``cs + target``. Every label that is not ``loops`` (a
known odd entry) sits right after a ``0x09`` word, and no label points inside a text page.

Branch operands (found by the scan in ``branch_sites``; the rule holds for both byte orders):

  - a word ``0x0b`` (goto; also a call id ``1d 0b``) is followed by one operand word;
  - a word ``0x90`` (dispatch table entry) is followed by a relative operand, then a mask word.

An operand is relative to the word after it: ``target = operand_position + 4 + signed(operand)``, both as
absolute file offsets. The rule is applied only when the target is inside the code and the word before it is
``0x09``. On the Dreamcast and GameCube field scripts 98 to 99.7 percent of operands after these words pass
that test; a random operand passes about 1 percent of the time.

Not decoded: the rest of the instruction set (the ``0x0a`` operand does not fit the rule, and the arity of
the call ids is unknown). A script is therefore not fully decoded, and growing it is an unproven move.
"""
from __future__ import annotations

import bisect
import struct
from typing import Dict, List, NamedTuple, Sequence, Tuple

from core.containers import skies_sct

HEADER_SIZE = 16
LABEL_SIZE = 20
NAME_SIZE = 16
BRANCH_WORDS = (0x0B, 0x90)   # the word before a branch operand
MARK_BEFORE_TARGET = 0x09     # the word before every label target (except ``loops``)


class Label(NamedTuple):
    name: bytes
    target: int   # code-relative: the label sits at code_start + target


def _unpack_u32(body: bytes, at: int, big: bool) -> int:
    return struct.unpack_from(">I" if big else "<I", body, at)[0]


def _pack_u32(value: int, big: bool) -> bytes:
    return struct.pack(">I" if big else "<I", value & 0xFFFFFFFF)


def label_count(body: bytes, big: bool) -> int:
    return _unpack_u32(body, 8, big)


def code_start(body: bytes, big: bool) -> int:
    return HEADER_SIZE + LABEL_SIZE * label_count(body, big)


def read_labels(body: bytes, big: bool) -> List[Label]:
    count = label_count(body, big)
    labels: List[Label] = []
    for i in range(count):
        at = HEADER_SIZE + LABEL_SIZE * i
        name = body[at:at + NAME_SIZE].split(b"\x00", 1)[0]
        labels.append(Label(name, _unpack_u32(body, at + NAME_SIZE, big)))
    return labels


def page_bytes(page: skies_sct.Page) -> bytes:
    """The bytes of one page's head, speaker and terminator, with the given text (inverse of ``skies_sct.pages``)."""
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


def _text_span(page: skies_sct.Page) -> Tuple[int, int]:
    head = len(page_bytes(skies_sct.Page(page.start, page.end, page.speaker, b"", b"")))
    return page.start + head, page.end - len(page.terminator)


def text_segments(body: bytes, big: bool) -> List[Tuple[int, int, int]]:
    """Each page's text split at the labels inside it: (page index, start, end) with absolute offsets.

    A label strictly inside the text starts a new segment. The labels of a script never sit inside a text (checked on
    the field scripts), so a page is one segment in practice. Segments cover the text, without the head and terminator.
    """
    cs = code_start(body, big)
    labels = [cs + label.target for label in read_labels(body, big)]
    out: List[Tuple[int, int, int]] = []
    for index, page in enumerate(skies_sct.pages(body)):
        a, b = _text_span(page)
        cuts = sorted({at for at in labels if a < at < b})
        bounds = [a] + cuts + [b]
        for lo, hi in zip(bounds, bounds[1:]):
            if hi > lo:
                out.append((index, lo, hi))
    return out


def branch_sites(body: bytes, big: bool) -> List[Tuple[int, int]]:
    """(operand offset, target offset) of each branch operand, both absolute, in file order.

    Scans the code words. A word in ``BRANCH_WORDS`` marks the next word as an operand. The operand is kept only when
    its target lies in the code and the word before the target is ``0x09`` (see the module docstring).
    """
    cs = code_start(body, big)
    fmt = ">I" if big else "<I"
    sites: List[Tuple[int, int]] = []
    for at in range(cs, len(body) - 7, 4):
        if _unpack_u32(body, at, big) not in BRANCH_WORDS:
            continue
        operand = at + 4
        raw = struct.unpack_from(fmt, body, operand)[0]
        signed = raw - (1 << 32) if raw & 0x80000000 else raw
        target = operand + 4 + signed
        if cs <= target < len(body) - 3 and target % 4 == cs % 4 and \
                _unpack_u32(body, target - 4, big) == MARK_BEFORE_TARGET:
            sites.append((operand, target))
    return sites


def _shift_fn(edits: Sequence[Tuple[int, int, bytes, int]]):
    """A function that maps an old absolute offset to its new offset (edits end at or before it add their delta)."""
    ends = [end for _, end, _, _ in edits]
    cumulative = []
    running = 0
    for _, _, _, delta in edits:
        running += delta
        cumulative.append(running)

    def shift(old: int) -> int:
        k = bisect.bisect_right(ends, old)
        return cumulative[k - 1] if k else 0

    return shift


def grow_regions(body: bytes, replacements: Dict[Tuple[int, int], bytes], big: bool,
                 net_zero: bool = False) -> Tuple[bytes, int]:
    """Replace byte regions ``[start, end)`` by new bytes. Each region's length changes; the bytes after it move.

    The new bytes are padded with spaces (0x7f) so every region's length change is a multiple of 4, so the code stays
    word aligned. Every label and every branch operand (``branch_sites``) is moved to the new place of its target,
    and each relative operand is recomputed from the new positions. Labels inside a region are refused. Returns
    (new body, total delta). Raises ValueError when a region holds a label or a branch.
    """
    fmt = ">I" if big else "<I"
    cs = code_start(body, big)
    labels = read_labels(body, big)
    edits = []
    for (start, end), new in sorted(replacements.items()):
        if any(start < cs + label.target < end for label in labels):
            raise ValueError("a label points inside a replaced region")
        block = new + b"\x7f" * ((-(len(new) - (end - start))) % 4)
        edits.append((start, end, block, len(block) - (end - start)))
    for prev, cur in zip(edits, edits[1:]):
        if cur[0] < prev[1]:
            raise ValueError("replaced regions overlap")
    if net_zero and edits:
        # The script keeps its total length: the last edit (before the tail) absorbs the difference in spaces.
        # Everything after the last edit keeps its offset (the tail).
        total = sum(delta for *_, delta in edits)
        if total > 0:
            raise ValueError("the script's text is longer than its budget")
        if total < 0:
            start, end, block, delta = edits[-1]
            edits[-1] = (start, end, block + b"\x7f" * (-total), delta - total)
    edited = [(start, end) for start, end, _, _ in edits]

    def in_edit(at: int) -> bool:
        return any(start <= at < end for start, end in edited)

    sites = [(op, tgt) for op, tgt in branch_sites(body, big) if not in_edit(op)]   # text holds no code
    if any(in_edit(target) for _, target in sites):
        raise ValueError("a branch points inside a replaced region")
    shift = _shift_fn(edits)
    out = bytearray()
    cursor = 0
    for start, end, block, _ in edits:
        out += body[cursor:start] + block
        cursor = end
    out += body[cursor:]
    for i, label in enumerate(labels):
        at = HEADER_SIZE + LABEL_SIZE * i + NAME_SIZE
        target = cs + label.target
        struct.pack_into(fmt, out, at + shift(at), (label.target + shift(target)) & 0xFFFFFFFF)
    for operand, target in sites:
        new_operand = operand + shift(operand)
        new_value = (target + shift(target)) - (new_operand + 4)
        struct.pack_into(fmt, out, new_operand, new_value & 0xFFFFFFFF)
    return bytes(out), sum(delta for *_, delta in edits)
