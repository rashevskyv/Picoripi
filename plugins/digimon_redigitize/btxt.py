"""Digimon World Re:Digitize Decode text files: ``BTX `` string tables inside ``KCAP`` containers.

``KCAP`` (little endian): ``"KCAP"``, u32 1, u32 total size, u32 0x10000, u32 item count, u32 0, u32 0x20, u32 0, then
u32 offset of item 0 and, per item, ``u32 size`` followed by the offset of the next item (the last item has only its
size). Items follow each other, every one starting at a multiple of 0x10; an item is raw data or another ``KCAP``.

``BTX `` table: ``"BTX "``, u32 1, u32 header size (0x10 or 0x0C), the header's remaining bytes, u32 1, u32 count,
``count`` x (u32 id, u32 offset) and the heap of ``count`` UTF-16 strings, each ending with one or two NUL units. The
offset of string ``i`` is counted from the start of its own (id, offset) pair. The game finds a string by this offset,
so a string that changes its length moves the ones behind it and their offsets are written again.
In the second kind of item (the story texts) a u32 with the size of the table up to the end of the heap comes before
``"BTX "``.

Text is shown as it is; a line break is a real new line; any other control unit (below 0x20, private use area) is a
``{c:XXXX}`` tag.
"""
from __future__ import annotations

import re
import struct
from dataclasses import dataclass, field
from typing import List, Optional, Tuple

TAG_RE = re.compile(r"\{c:[0-9a-f]{4}\}")
_MAX_DEPTH = 8


class FormatError(ValueError):
    """Not a Digimon text file, or an edit that the file cannot take."""


def decode(raw: bytes) -> str:
    out: List[str] = []
    for (unit,) in struct.iter_unpack("<H", raw[:len(raw) // 2 * 2]):
        if unit == 0x0A:
            out.append("\n")
        elif unit < 0x20 or 0xD800 <= unit < 0xF900:
            out.append("{c:%04x}" % unit)
        else:
            out.append(chr(unit))
    return "".join(out)


def encode(text: str) -> bytes:
    units: List[int] = []
    pos = 0
    while pos < len(text):
        tag = TAG_RE.match(text, pos)
        if tag:
            units.append(int(tag.group()[3:-1], 16))
            pos = tag.end()
            continue
        raw = text[pos].encode("utf-16-le", "surrogatepass")
        units.extend(struct.unpack(f"<{len(raw) // 2}H", raw))
        pos += 1
    return struct.pack(f"<{len(units)}H", *units)


@dataclass
class Block:
    """One ``BTX `` table: where it sits and its strings."""

    item_at: int               # start of the item (for the second kind: the size field before "BTX ")
    item_end: int              # end of the item, from the KCAP size table
    btx_at: int
    count: int
    heap_at: int
    heap_end: int              # end of the last string's terminator
    prefixed: bool             # a size field comes before "BTX "
    ent_at: int = 0            # start of the (id, offset) pairs
    raw: List[bytes] = field(default_factory=list)
    texts: List[str] = field(default_factory=list)
    gaps: List[bytes] = field(default_factory=list)      # the NUL units (and padding) behind each string


def _btx(data: bytes, at: int, item_at: int, item_end: int) -> Optional[Block]:
    if data[at:at + 4] != b"BTX " or at + 0x14 > len(data):
        return None
    version, header = struct.unpack_from("<II", data, at + 4)
    if version != 1 or header not in (0x0C, 0x10):
        return None
    count = struct.unpack_from("<I", data, at + header + 4)[0]
    ent_at = at + header + 8
    heap_at = ent_at + 8 * count
    if not 0 < count <= 100000 or heap_at > item_end:
        return None
    starts = [ent_at + 8 * i + struct.unpack_from("<I", data, ent_at + 8 * i + 4)[0] for i in range(count)]
    if starts[0] != heap_at or any(a % 2 or b < a for a, b in zip(starts, starts[1:])) or starts[-1] >= item_end:
        return None
    raw, gaps = [], []
    for i, start in enumerate(starts):
        end = start
        while end + 2 <= item_end and data[end:end + 2] != b"\0\0":
            end += 2
        if end + 2 > item_end:
            return None
        if i + 1 < count:
            stop = starts[i + 1]
            if stop < end + 2:
                return None
        else:                                                # the last string: one or two NUL units
            stop = end + 4 if data[end + 2:end + 4] == b"\0\0" and end + 4 <= item_end else end + 2
        raw.append(data[start:end])
        gaps.append(data[end:stop])
    return Block(item_at, item_end, at, count, heap_at, starts[-1] + len(raw[-1]) + len(gaps[-1]), item_at != at, ent_at,
                 raw, [decode(r) for r in raw], gaps)


def _walk(data: bytes, base: int, end: int, depth: int, blocks: List[Block]) -> None:
    if depth > _MAX_DEPTH or base + 0x28 > len(data) or data[base:base + 4] != b"KCAP":
        return
    n = struct.unpack_from("<I", data, base + 0x10)[0]
    if not 0 < n <= 20000 or base + 0x24 + 8 * n > len(data):
        return
    first = struct.unpack_from("<I", data, base + 0x20)[0]
    vals = struct.unpack_from(f"<{2 * n - 1}I", data, base + 0x24)
    off = first
    for i in range(n):
        size = vals[2 * i]
        a = base + off
        if size and a > base and a + size <= len(data) and a >= base + 0x24:
            head = data[a:a + 4]
            if head == b"KCAP":
                _walk(data, a, a + size, depth + 1, blocks)
            elif head == b"BTX ":
                block = _btx(data, a, a, a + size)
                if block:
                    blocks.append(block)
            elif size > 8 and data[a + 4:a + 8] == b"BTX ":
                block = _btx(data, a + 4, a, a + size)
                if block:
                    blocks.append(block)
        if i + 1 < n:
            off = vals[2 * i + 1]


def find_blocks(data: bytes) -> List[Block]:
    blocks: List[Block] = []
    _walk(data, 0, len(data), 0, blocks)
    blocks.sort(key=lambda b: b.item_at)
    return blocks


class DigiText:
    """A text file: ``blocks`` (one per BTX table, each with ``texts``) and ``build``."""

    def __init__(self, data: bytes):
        self.data = bytes(data)
        if self.data[:4] != b"KCAP":
            raise FormatError("not a KCAP container")
        self.blocks = find_blocks(self.data)
        if not self.blocks:
            raise FormatError("no BTX table in the file")
        self.exact = [encode(t) == r for b in self.blocks for t, r in zip(b.texts, b.raw)]

    @property
    def strings(self) -> List[List[str]]:
        return [list(b.texts) for b in self.blocks]

    def build(self, texts: List[List[str]]) -> bytes:
        if len(texts) != len(self.blocks) or any(len(t) != b.count for t, b in zip(texts, self.blocks)):
            raise FormatError("the number of blocks or strings changed")
        out = bytearray(self.data)
        grown = []
        for block, new in zip(self.blocks, texts):
            if new == block.texts:
                continue
            raws = [block.raw[i] if t == block.texts[i] else encode(t) for i, t in enumerate(new)]
            heap = b"".join(r + g for r, g in zip(raws, block.gaps))
            offsets, pos = [], 8 * block.count
            for i, (r, g) in enumerate(zip(raws, block.gaps)):
                offsets.append(pos - 8 * i)
                pos += len(r) + len(g)
            if len(heap) == block.heap_end - block.heap_at:
                out[block.heap_at:block.heap_end] = heap
                for i, off in enumerate(offsets):
                    struct.pack_into("<I", out, block.ent_at + 8 * i + 4, off)
            else:
                grown.append((block, heap, offsets))
        if grown:
            out = bytearray(_rebuild(bytes(out), grown))
        return bytes(out)


# ---------------------------------------------------------------- rebuilding a KCAP tree with changed item sizes

def _align(value: int, to: int = 0x10) -> int:
    return (value + to - 1) // to * to


def _alignment(offset: int) -> int:
    """The alignment (a power of two up to 0x10) an item offset has: the container pads to it."""
    for to in (0x10, 8, 4, 2):
        if offset % to == 0:
            return to
    return 1


def _rebuild(data: bytes, grown: List[Tuple[Block, bytes, List[int]]]) -> bytes:
    """``data`` with the heaps of the BTX tables in ``grown`` replaced by longer or shorter ones. Every KCAP on the way
    gets its size table and later items moved; the file must be a regular tree (items back to back, every one at the
    next multiple of 0x10) that fills the file."""
    total = struct.unpack_from("<I", data, 8)[0]
    if total != len(data) and data[total:].strip(b"\0"):
        raise FormatError("the file has data behind the container; a text that changes its size is not supported")
    edits = {b.item_at: (b, h, o) for b, h, o in grown}
    out = _build_node(data, 0, len(data), edits, 0)
    if out is None:
        raise FormatError("the container is not a regular tree; a text that changes its size is not supported")
    if total != len(data):
        out += bytes(len(data) - total)
    return out


def _build_node(data: bytes, base: int, end: int, edits: dict, depth: int) -> Optional[bytes]:
    """The KCAP at ``base`` rebuilt (bytes), or None when its layout is not the regular one."""
    if depth > _MAX_DEPTH:
        return None
    n = struct.unpack_from("<I", data, base + 0x10)[0]
    first = struct.unpack_from("<I", data, base + 0x20)[0]
    vals = struct.unpack_from(f"<{2 * n - 1}I", data, base + 0x24)
    sizes = [vals[2 * i] for i in range(n)]
    offs = [first] + [vals[2 * i + 1] for i in range(n - 1)]
    # the container pads an item to the alignment its offset has; a container that does not follow this rule on
    # its original sizes is not rebuilt
    for i in range(n - 1):
        if offs[i + 1] != _align(offs[i] + sizes[i], _alignment(offs[i + 1])):
            return None
    pos = first
    parts: List[bytes] = []
    new_sizes: List[int] = []
    new_offs: List[int] = []
    for i in range(n):
        a, size = base + offs[i], sizes[i]
        item = data[a:a + size]
        if size and data[a:a + 4] == b"KCAP":
            sub = _build_node(data, a, a + size, edits, depth + 1)
            if sub is None:
                return None
            item = sub
        elif a in edits:
            block, heap, offsets = edits[a]
            head = bytearray(data[a:block.heap_at])
            for k, off in enumerate(offsets):
                struct.pack_into("<I", head, block.ent_at - a + 8 * k + 4, off)
            tail = data[block.heap_end:a + size]
            item = bytes(head) + heap + tail
            if block.prefixed:                                    # the size field before "BTX " follows the heap
                field = struct.unpack_from("<I", data, a)[0] + len(heap) - (block.heap_end - block.heap_at)
                item = struct.pack("<I", field) + item[4:]
        new_offs.append(pos)
        new_sizes.append(len(item))
        parts.append(item)
        if i + 1 < n:
            pos = _align(pos + len(item), _alignment(offs[i + 1]))
        else:
            pos += len(item)
    head = bytearray(data[base:base + first])
    for i in range(n):
        struct.pack_into("<I", head, 0x24 + 8 * i, new_sizes[i])
        if i + 1 < n:
            struct.pack_into("<I", head, 0x28 + 8 * i, new_offs[i + 1])
    out = bytearray(head)
    for i, part in enumerate(parts):
        out += bytes(new_offs[i] - len(out))
        out += part
    struct.pack_into("<I", out, 8, len(out))
    return bytes(out)
