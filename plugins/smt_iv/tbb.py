"""Atlus ``FBIN`` / ``TBB1`` containers of Strange Journey Redux (3DS) around the ``MSG2`` text tables of ``mbm``.

The game keeps its text in ``.mbm`` files (a ``TBB1`` block that holds one or more ``MSG2`` tables) and in
``Event/EventMessage*.bin`` files (an ``FBIN`` of ``TBB1`` blocks). A table that is a bare ``MSG2`` (SMT IV, the
SJR keyboard file) is a bundle of one table.

``TBB1`` (little endian): ``TBB1``, u32 0x10, u32 count, u32 total size, then ``count`` u32 block offsets from the
start of the ``TBB1``; every block starts at a multiple of 0x10. ``FBIN``: ``FBIN``, u32 count, u32 offset of the
first member, ``count`` u32 member sizes, padding to 0x10; the members follow one after another.

``Bundle.texts()`` is the entries of every table one after the other; ``build`` writes them back and lays the
containers out again. A bundle whose texts did not change is returned as the original bytes.
"""
from __future__ import annotations

import struct
from typing import List, Optional, Sequence

from . import mbm

ALIGN = 0x10


def _pad(size: int) -> int:
    return (size + ALIGN - 1) // ALIGN * ALIGN


class _Node:
    """One block: ``kind`` is ``fbin``, ``tbb1``, ``msg2`` or ``raw``; ``kids`` for the containers."""

    def __init__(self, kind: str, raw: bytes, kids: Optional[List["_Node"]] = None, table: Optional[mbm.Table] = None):
        self.kind, self.raw, self.kids, self.table = kind, raw, kids or [], table

    def tables(self) -> List[mbm.Table]:
        if self.kind == "msg2":
            return [self.table]
        return [t for kid in self.kids for t in kid.tables()]


def _parse(raw: bytes) -> _Node:
    magic = raw[:4]
    if magic == b"FBIN":
        count, first = struct.unpack_from("<II", raw, 4)
        sizes = struct.unpack_from(f"<{count}I", raw, 12)
        kids, at = [], first
        for size in sizes:
            kids.append(_parse(raw[at:at + size]))
            at += size
        if at > len(raw) or not any(k.tables() for k in kids):
            raise mbm.FormatError("FBIN without text tables")
        return _Node("fbin", raw, kids)
    if magic == b"TBB1":
        header, count, total = struct.unpack_from("<III", raw, 4)
        if header != 0x10 or total > len(raw) or not count:
            raise mbm.FormatError("bad TBB1 header")
        offsets = list(struct.unpack_from(f"<{count}I", raw, header)) + [total]
        kids = [_parse(raw[a:b]) for a, b in zip(offsets, offsets[1:])]
        return _Node("tbb1", raw, kids)
    if raw[4:8] == b"MSG2":
        return _Node("msg2", raw, table=mbm.Table(raw))
    return _Node("raw", raw)


def _lay_out(node: _Node, texts: List[str], used: List[int]) -> bytes:
    """The node's bytes with the (already consumed ``used[0]``) texts of its tables written in."""
    if node.kind == "msg2":
        n = node.table.count
        part = texts[used[0]:used[0] + n]
        used[0] += n
        return node.table.build(part) if part != node.table.texts() else node.raw
    if node.kind == "raw":
        return node.raw
    blocks = [_lay_out(kid, texts, used) for kid in node.kids]
    if node.kind == "tbb1":
        start = _pad(0x10 + 4 * len(blocks))
        offsets, at = [], start
        for block in blocks:
            offsets.append(at)
            at += _pad(len(block))
        head = b"TBB1" + struct.pack("<III", 0x10, len(blocks), at) + struct.pack(f"<{len(blocks)}I", *offsets)
        out = bytearray(head.ljust(start, b"\0"))
        for block in blocks:
            out += block.ljust(_pad(len(block)), b"\0")
        return bytes(out)
    first = _pad(12 + 4 * len(blocks))
    sizes = [_pad(len(b)) for b in blocks]
    head = b"FBIN" + struct.pack("<II", len(blocks), first) + struct.pack(f"<{len(blocks)}I", *sizes)
    return head.ljust(first, b"\0") + b"".join(b.ljust(s, b"\0") for b, s in zip(blocks, sizes))


class Bundle:
    """A parsed text file: ``tables`` in file order and the ``ids`` of every entry."""

    def __init__(self, raw: bytes):
        self.raw = bytes(raw)
        self.root = _parse(self.raw)
        self.tables = self.root.tables()
        if not self.tables:
            raise mbm.FormatError("no MSG2 table")
        # one table: its entry ids; several: (table index, entry id)
        self.ids: list = ([i for table in self.tables for i in table.ids] if len(self.tables) == 1
                          else [(t, i) for t, table in enumerate(self.tables) for i in table.ids])

    def texts(self) -> List[str]:
        return [text for table in self.tables for text in table.texts()]

    def build(self, texts: Sequence[str]) -> bytes:
        if len(texts) != len(self.ids):
            raise mbm.FormatError(f"{len(texts)} strings for {len(self.ids)} entries")
        listed = [str(t) for t in texts]
        if listed == self.texts():
            return self.raw
        return _lay_out(self.root, listed, [0])


def is_bundle(raw: bytes) -> bool:
    return raw[:4] in (b"FBIN", b"TBB1") or raw[4:8] == b"MSG2"
