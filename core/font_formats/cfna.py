"""3DS archived fonts (``CFNA``, ``.bcfna``; NintendoWare ArchiveFont): a CFNT whose sheets are compressed one by one,
with a ``GLGR`` block that groups sheets and character tables (Senran Kagura Burst's ``font.bcfna``,
``hudemoji.bcfna``, ``number_NN.bcfna``). It is ``brfna`` (the Wii RFNA) in little endian with a 0x14-byte header.

Layout: ``CFNA``, BOM, u16 header size 0x14, u32 version, u32 file size, u16 block count (GLGR included), ``GLGR``
(u32 sheet size, u16 glyphs per sheet, u16 set count, u16 sheet count, u16 CWDH count, u16 CMAP count, the set name
offsets, then on 4 bytes the stored size of every sheet, CWDH and CMAP block, the bit lists and names), ``FINF``,
``TGLP`` (sheet format with bit 15 set = compressed; each sheet is u32 size + a CX Huffman stream), the CWDH and
CMAP chains.

The model is the CFNT this file holds (``core.font_formats.bcfnt``): extracting decompresses the sheets into a CFNT;
packing compresses again only the sheets whose pixels changed and writes their sizes into GLGR. Glyph pixels and
widths can be edited; new characters cannot be added. An unedited model packs to the original bytes.
"""
from __future__ import annotations

import struct
from typing import Any, Dict, List, Tuple

from core.font_formats import Metadata, Sheets, bcfnt
from core.font_formats.brfna import huffman_decode, huffman_encode

ADDS_GLYPHS = False
E = "<"


def is_cfna(data: bytes) -> bool:
    return bytes(data[:4]) == b"CFNA"


def _blocks(data: bytes) -> List[Tuple[bytes, int, int]]:
    at, out = struct.unpack_from(E + "H", data, 0x06)[0], []
    for _ in range(struct.unpack_from(E + "H", data, 0x10)[0]):
        magic, size = bytes(data[at:at + 4]), struct.unpack_from(E + "I", data, at + 4)[0]
        out.append((magic, at, size))
        at += size
    return out


def _parts(data: bytes) -> Dict[str, Any]:
    if not is_cfna(data):
        raise ValueError("Not a 3DS archived font (CFNA)")
    blocks = _blocks(data)
    by = {m: (a, s) for m, a, s in blocks}
    glgr_at, glgr_size = by[b"GLGR"]
    sets, sheets = struct.unpack_from(E + "HH", data, glgr_at + 8 + 6)
    sizes_at = glgr_at + 8 + 14 + sets * 2
    sizes_at += -sizes_at % 4
    tglp_at = by[b"TGLP"][0]
    image = struct.unpack_from(E + "I", data, tglp_at + 8 + 0x14)[0]
    chunks, at = [], image
    for _ in range(sheets):
        size = struct.unpack_from(E + "I", data, at)[0]
        chunks.append(bytes(data[at + 4:at + 4 + size]))
        at += 4 + size
    finf_at, finf_size = by[b"FINF"]
    return {"glgr": bytes(data[glgr_at:glgr_at + glgr_size]), "sizes": sizes_at - glgr_at,
            "finf": bytes(data[finf_at:finf_at + finf_size]), "tglp": bytes(data[tglp_at:tglp_at + 8 + 0x18]),
            "pad": image - (tglp_at + 8 + 0x18), "chunks": chunks,
            "tables": [bytes(data[a:a + s]) for m, a, s in blocks if m in (b"CWDH", b"CMAP")]}


def _assemble(head: bytes, blocks: List[bytes], tglp_head: bytes, pad: int, sheets: bytes, tables: List[bytes],
              compressed: bool) -> bytes:
    out = bytearray(head[:0x14])
    for block in blocks:
        out += block
    finf_at = len(out) - len(blocks[-1])
    tglp_at = len(out)
    body = bytearray(tglp_head) + bytes(pad) + sheets
    struct.pack_into(E + "I", body, 4, len(body))
    fmt = struct.unpack_from(E + "H", body, 8 + 0x0A)[0]
    struct.pack_into(E + "H", body, 8 + 0x0A, (fmt | 0x8000) if compressed else (fmt & 0x7FFF))
    struct.pack_into(E + "I", body, 8 + 0x14, tglp_at + len(tglp_head) + pad)
    out += body
    starts = {b"CWDH": [], b"CMAP": []}
    for table in tables:
        starts[table[:4]].append(len(out))
        out += table
    for magic, field, nxt in ((b"CWDH", 8 + 12, 8 + 4), (b"CMAP", 8 + 16, 8 + 8)):
        at = starts[magic]
        struct.pack_into(E + "I", out, finf_at + field, at[0] + 8 if at else 0)
        for k, block_at in enumerate(at):
            struct.pack_into(E + "I", out, block_at + nxt, at[k + 1] + 8 if k + 1 < len(at) else 0)
    struct.pack_into(E + "I", out, finf_at + 8 + 8, tglp_at + 8)
    struct.pack_into(E + "I", out, 0x0C, len(out))
    struct.pack_into(E + "H", out, 0x10, len(blocks) + 1 + len(tables))
    return bytes(out)


def to_cfnt(data: bytes) -> bytes:
    """The CFNT this archived font holds (sheets decompressed, 0x80 aligned like a plain 3DS font)."""
    parts = _parts(data)
    head = b"CFNT" + bytes(data[4:0x14])
    pad = -(0x14 + len(parts["finf"]) + len(parts["tglp"])) % 0x80
    sheets = b"".join(huffman_decode(c) for c in parts["chunks"])
    return _assemble(head, [parts["finf"]], parts["tglp"], pad, sheets, parts["tables"], False)


def extract(data: bytes, params: Dict[str, Any]) -> Tuple[Metadata, Sheets]:
    return bcfnt.extract(to_cfnt(data), params)


def pack(metadata: Metadata, sheets: Sheets, original: bytes, params: Dict[str, Any]) -> bytes:
    cfnt = to_cfnt(original)
    new = bcfnt.pack(metadata, sheets, cfnt, params)
    if new == cfnt:
        return bytes(original)
    parts = _parts(original)
    old_info, new_info = bcfnt._info(cfnt), bcfnt._info(new)
    tables = [new[a:a + s] for m, a, s in _blocks(new) if m in (b"CWDH", b"CMAP")]
    before = [cfnt[a:a + s] for m, a, s in _blocks(cfnt) if m in (b"CWDH", b"CMAP")]
    if new_info["sheets"] != old_info["sheets"] or [len(t) for t in tables] != [len(t) for t in before] \
            or [t for t in tables if t[:4] == b"CMAP"] != [t for t in before if t[:4] == b"CMAP"]:
        raise ValueError("an archived font (.bcfna) cannot get new characters: draw over a glyph the text does "
                         "not use and map the letter to it in the translation map")
    glgr = bytearray(parts["glgr"])
    size, stored = old_info["sheet_size"], bytearray()
    for i, chunk in enumerate(parts["chunks"]):
        old_sheet = cfnt[old_info["data"] + i * size:][:size]
        new_sheet = new[new_info["data"] + i * size:][:size]
        if old_sheet != new_sheet:
            chunk = huffman_encode(new_sheet)
            chunk += bytes(-len(chunk) % 4)
            struct.pack_into(E + "I", glgr, parts["sizes"] + i * 4, len(chunk))
        stored += struct.pack(E + "I", len(chunk)) + chunk
    finf = next(new[a:a + s] for m, a, s in _blocks(new) if m == b"FINF")
    tglp = next(new[a:a + 8 + 0x18] for m, a, _s in _blocks(new) if m == b"TGLP")
    return _assemble(original, [bytes(glgr), finf], tglp, parts["pad"], bytes(stored), tables, True)
