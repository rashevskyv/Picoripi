"""Wii archived fonts (``RFNA``, ``.brfna``; NW4R ArchiveFont): an RFNT whose sheets are compressed one by one,
with a ``GLGR`` block that groups sheets and character tables for partial loading (the Wii system fonts
``wbf1.brfna`` / ``wbf2.brfna`` that the Raving Rabbids Party Collection menu draws with).

Layout (big endian): an RFNT-like header (``RFNA``; the block count includes GLGR), ``GLGR`` (u32 sheet size,
u16 glyphs per sheet, u16 set count, u16 sheet count, u16 CWDH count, u16 CMAP count, the set name offsets,
then on 4 bytes the stored size of every sheet, CWDH and CMAP block, then per set the bit lists of what it
uses, then the names), ``FINF``, ``TGLP`` (sheet format with bit 15 set = compressed), the CWDH and CMAP chains.
Each sheet in TGLP is u32 size + a CX stream (little-endian header: 0x28 = Huffman over bytes, 0x24 = over
nibbles; the size in the upper 24 bits; bits read MSB first from little-endian words).

The model is the RFNT this file holds (``core.font_formats.bcfnt``): extracting decompresses the sheets into an
RFNT; packing compresses again only the sheets whose pixels changed (Huffman over bytes, over nibbles when the
tree does not fit the format's 6-bit offsets) and writes their sizes into GLGR. Glyph pixels and widths can be
edited; new characters cannot be added (they would need new CMAP entries in every group). An unedited model
packs to the original bytes.
"""
from __future__ import annotations

import heapq
import struct
from typing import Any, Dict, List, Tuple

from core.font_formats import Metadata, Sheets, bcfnt

ADDS_GLYPHS = False


# ---------------------------------------------------------------- CX Huffman

def huffman_decode(src: bytes) -> bytes:
    head = struct.unpack_from("<I", src)[0]
    bits, size = head & 15, head >> 8
    root, pos = 5, 4 + (src[4] + 1) * 2
    out, node, half = bytearray(), root, None
    while len(out) < size:
        word = struct.unpack_from("<I", src, pos)[0]
        pos += 4
        for shift in range(31, -1, -1):
            bit = (word >> shift) & 1
            value = src[node]
            child = (node & ~1) + (value & 0x3F) * 2 + 2 + bit
            if not value & (0x80 >> bit):
                node = child
                continue
            if bits == 8:
                out.append(src[child])
            elif half is None:
                half = src[child]
            else:
                out.append(half | (src[child] << 4))
                half = None
            node = root
            if len(out) >= size:
                break
    return bytes(out)


def _tree(counts: Dict[int, int]):
    """A Huffman tree as nested pairs (a leaf is its symbol)."""
    heap = [(n, i, s) for i, (s, n) in enumerate(sorted(counts.items()))]
    if len(heap) == 1:
        heap.append((0, 1, (heap[0][2] + 1) & 0xFF))
    heapq.heapify(heap)
    tick = len(heap)
    while len(heap) > 1:
        a, b = heapq.heappop(heap), heapq.heappop(heap)
        heapq.heappush(heap, (a[0] + b[0], tick, (a[2], b[2])))
        tick += 1
    return heap[0][2]


def _table(tree) -> bytes:
    """The tree table (size byte, root at 1, every node a 6-bit offset to its child pair); child pairs are placed
    earliest-deadline first. ValueError when a pair cannot be placed within 63 pairs of its parent."""
    out, pending, order = [0, 0], [], 0

    def node(slot: int, item) -> None:
        nonlocal order
        if isinstance(item, tuple):
            heapq.heappush(pending, (slot // 2 + 63, order, slot, item))
            order += 1
        else:
            out[slot] = item

    node(1, tree)
    while pending:
        _deadline, _o, parent, pair = heapq.heappop(pending)
        offset = len(out) // 2 - parent // 2 - 1
        if offset > 63:
            raise ValueError("Huffman tree too wide for 6-bit offsets")
        out[parent] = (0x80 if not isinstance(pair[0], tuple) else 0) | \
            (0x40 if not isinstance(pair[1], tuple) else 0) | offset
        at = len(out)
        out += [0, 0]
        node(at, pair[0])
        node(at + 1, pair[1])
    out += [0] * (-len(out) % 4)
    out[0] = len(out) // 2 - 1
    return bytes(out)


def _paths(tree, prefix: str = "") -> Dict[int, str]:
    if not isinstance(tree, tuple):
        return {tree: prefix or "0"}
    return {**_paths(tree[0], prefix + "0"), **_paths(tree[1], prefix + "1")}


def huffman_encode(data: bytes) -> bytes:
    """A CX Huffman stream of ``data``: over bytes, else over nibbles."""
    for bits in (8, 4):
        symbols = list(data) if bits == 8 else [v for b in data for v in (b & 15, b >> 4)]
        counts: Dict[int, int] = {}
        for s in symbols:
            counts[s] = counts.get(s, 0) + 1
        tree = _tree(counts)
        try:
            table = _table(tree)
        except ValueError:
            continue
        paths = _paths(tree)
        stream = "".join(paths[s] for s in symbols)
        stream += "0" * (-len(stream) % 32)
        words = b"".join(struct.pack("<I", int(stream[i:i + 32], 2)) for i in range(0, len(stream), 32))
        return struct.pack("<I", (len(data) << 8) | 0x20 | bits) + table + words
    raise ValueError("Huffman: no tree layout fits")


# ---------------------------------------------------------------- RFNA <-> RFNT

def _blocks(data: bytes) -> List[Tuple[bytes, int, int]]:
    """``[(magic, offset, size)]`` of the blocks after the header."""
    at, out = struct.unpack_from(">H", data, 0x0C)[0], []
    for _ in range(struct.unpack_from(">H", data, 0x0E)[0]):
        magic, size = bytes(data[at:at + 4]), struct.unpack_from(">I", data, at + 4)[0]
        out.append((magic, at, size))
        at += size
    return out


def _parts(data: bytes) -> Dict[str, Any]:
    """GLGR, FINF and TGLP of an RFNA with its compressed sheets and its CWDH / CMAP blocks."""
    if data[:4] != b"RFNA":
        raise ValueError("Not a Wii archived font (RFNA)")
    blocks = _blocks(data)
    by = {m: (a, s) for m, a, s in blocks}
    glgr_at, glgr_size = by[b"GLGR"]
    sets, sheets = struct.unpack_from(">HH", data, glgr_at + 8 + 6)
    sizes_at = glgr_at + 8 + 14 + sets * 2
    sizes_at += -sizes_at % 4
    tglp_at = by[b"TGLP"][0]
    image = struct.unpack_from(">I", data, tglp_at + 8 + 0x14)[0]
    chunks, at = [], image
    for _ in range(sheets):
        size = struct.unpack_from(">I", data, at)[0]
        chunks.append(bytes(data[at + 4:at + 4 + size]))
        at += 4 + size
    finf_at, finf_size = by[b"FINF"]
    return {"glgr": bytes(data[glgr_at:glgr_at + glgr_size]), "sizes": sizes_at - glgr_at,
            "finf": bytes(data[finf_at:finf_at + finf_size]), "tglp": bytes(data[tglp_at:tglp_at + 8 + 0x18]),
            "pad": image - (tglp_at + 8 + 0x18), "chunks": chunks,
            "tables": [bytes(data[a:a + s]) for m, a, s in blocks if m in (b"CWDH", b"CMAP")]}


def _assemble(head: bytes, blocks: List[bytes], tglp_head: bytes, pad: int, sheets: bytes, tables: List[bytes],
              compressed: bool) -> bytes:
    """A font file: header, ``blocks`` (GLGR?, FINF), TGLP with ``sheets``, then the tables; pointers set."""
    out = bytearray(head[:0x10])
    for block in blocks:
        out += block
    finf_at = len(out) - len(blocks[-1])
    tglp_at = len(out)
    body = bytearray(tglp_head) + bytes(pad) + sheets
    struct.pack_into(">I", body, 4, len(body))
    fmt = struct.unpack_from(">H", body, 8 + 0x0A)[0]
    struct.pack_into(">H", body, 8 + 0x0A, (fmt | 0x8000) if compressed else (fmt & 0x7FFF))
    struct.pack_into(">I", body, 8 + 0x14, tglp_at + len(tglp_head) + pad)
    out += body
    starts = {b"CWDH": [], b"CMAP": []}
    for table in tables:
        starts[table[:4]].append(len(out))
        out += table
    for magic, field, nxt in ((b"CWDH", 8 + 12, 8 + 4), (b"CMAP", 8 + 16, 8 + 8)):
        at = starts[magic]
        struct.pack_into(">I", out, finf_at + field, at[0] + 8 if at else 0)
        for k, block_at in enumerate(at):
            struct.pack_into(">I", out, block_at + nxt, at[k + 1] + 8 if k + 1 < len(at) else 0)
    struct.pack_into(">I", out, finf_at + 8 + 8, tglp_at + 8)
    struct.pack_into(">I", out, 0x08, len(out))
    struct.pack_into(">H", out, 0x0E, len(blocks) + 1 + len(tables))
    return bytes(out)


def to_rfnt(data: bytes) -> bytes:
    """The RFNT this archived font holds (sheets decompressed, 0x20 aligned)."""
    parts = _parts(data)
    head = b"RFNT" + bytes(data[4:0x10])
    pad = -(0x10 + len(parts["finf"]) + len(parts["tglp"])) % 0x20
    sheets = b"".join(huffman_decode(c) for c in parts["chunks"])
    return _assemble(head, [parts["finf"]], parts["tglp"], pad, sheets, parts["tables"], False)


def extract(data: bytes, params: Dict[str, Any]) -> Tuple[Metadata, Sheets]:
    return bcfnt.extract(to_rfnt(data), params)


def pack(metadata: Metadata, sheets: Sheets, original: bytes, params: Dict[str, Any]) -> bytes:
    rfnt = to_rfnt(original)
    new = bcfnt.pack(metadata, sheets, rfnt, params)
    if new == rfnt:
        return bytes(original)
    parts = _parts(original)
    old_info, new_info = bcfnt._info(rfnt), bcfnt._info(new)
    tables = [new[a:a + s] for m, a, s in _blocks(new) if m in (b"CWDH", b"CMAP")]
    before = [rfnt[a:a + s] for m, a, s in _blocks(rfnt) if m in (b"CWDH", b"CMAP")]
    if new_info["sheets"] != old_info["sheets"] or [len(t) for t in tables] != [len(t) for t in before] \
            or [t for t in tables if t[:4] == b"CMAP"] != [t for t in before if t[:4] == b"CMAP"]:
        raise ValueError("an archived font (.brfna) cannot get new characters: draw over a glyph the text does "
                         "not use and map the letter to it in the translation map")
    glgr = bytearray(parts["glgr"])
    size, stored = old_info["sheet_size"], bytearray()
    for i, chunk in enumerate(parts["chunks"]):
        old_sheet = rfnt[old_info["data"] + i * size:][:size]
        new_sheet = new[new_info["data"] + i * size:][:size]
        if old_sheet != new_sheet:
            chunk = huffman_encode(new_sheet)
            chunk += bytes(-len(chunk) % 4)
            struct.pack_into(">I", glgr, parts["sizes"] + i * 4, len(chunk))
        stored += struct.pack(">I", len(chunk)) + chunk
    finf = next(new[a:a + s] for m, a, s in _blocks(new) if m == b"FINF")
    tglp = next(new[a:a + 8 + 0x18] for m, a, _s in _blocks(new) if m == b"TGLP")
    return _assemble(original, [bytes(glgr), finf], tglp, parts["pad"], bytes(stored), tables, True)
