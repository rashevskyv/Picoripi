"""Nintendo Switch bitmap fonts (BFFNT 4.x, little endian): glyph sheets, advance widths, character map.

Layout: ``FFNT`` header, ``FINF`` (metrics and the offsets of the other blocks), ``TGLP`` (cell
grid; the sheets are a BNTX texture array inside it), chains of ``CWDH`` (left, glyph width,
advance per glyph) and ``CMAP`` (code -> glyph), optional ``KRNG``. A BNTX texture is stored
block-linear (Tegra X1 GOBs of 512 bytes, ``2^layout`` GOBs per block) and the sheet is upside
down; cells are ``cell + 1`` pixels apart.

Editing: advances and left offsets are written back in place; sheet pixels are written back for
BC4 textures (the common font format), only for the 4x4 blocks that changed. Other texture formats
open with empty sheets and keep their texture. Wii U (big-endian) fonts are the ``bffnt_wiiu`` format
(``bcfnt.py``).

New characters: the font source's ``min_sheets`` param opens a BC4 font with blank sheets up to that
count, so a font without room (a Latin-only font that needs Cyrillic) gets free cells. On save, a
blank sheet that got ink or a character becomes a new layer of the BNTX texture array (inserted
before its relocation table; every offset behind it is moved), its glyphs get a new CWDH block, and
a changed character map becomes a new CMAP block put first in the chain: it holds the final mapping
of every code between the lowest and the highest changed code, so it wins over the old blocks.
Nothing is added when nothing changed: an unedited font packs back byte for byte.
"""
from __future__ import annotations

import struct
from typing import Any, Dict, List, Tuple

from PIL import Image

from core.font_formats import Metadata, Sheets, char_code, char_map, code_char, coverage, grey_sheet, map_entries

ADDS_GLYPHS = True  # a typed character gets its own code in a new CMAP block (an empty or ``min_sheets`` cell)

BC4 = 0x1D


def _finf(data: bytes) -> Dict[str, int]:
    if data[:4] != b"FFNT":
        raise ValueError("Not a BFFNT font")
    if data[4:6] != b"\xff\xfe":
        raise ValueError("Big-endian (Wii U) BFFNT fonts are not supported; Switch and 3DS fonts are")
    at = struct.unpack_from("<H", data, 6)[0]
    if data[at:at + 4] != b"FINF":
        raise ValueError("BFFNT without FINF")
    (_kind, height, width, ascent, line_feed, alter, left, glyph_w, char_w, _enc,
     tglp, cwdh, cmap) = struct.unpack_from("<BBBBHHbBBBIII", data, at + 8)
    return {"height": height, "width": width, "ascent": ascent, "line_feed": line_feed, "alter": alter,
            "left": left, "glyph_width": glyph_w, "char_width": char_w,
            "tglp": tglp - 8, "cwdh": cwdh - 8 if cwdh else 0, "cmap": cmap - 8 if cmap else 0}


def _tglp(data: bytes, at: int) -> Dict[str, int]:
    if data[at:at + 4] != b"TGLP":
        raise ValueError("BFFNT without TGLP")
    size = struct.unpack_from("<I", data, at + 4)[0]
    (cell_w, cell_h, sheets, _max_w, _sheet_size, _base, fmt, columns, rows, sheet_w, sheet_h,
     sheet_at) = struct.unpack_from("<BBBBIHHHHHHI", data, at + 8)
    return {"cell_width": cell_w, "cell_height": cell_h, "sheets": sheets, "format": fmt, "columns": columns,
            "rows": rows, "sheet_width": sheet_w, "sheet_height": sheet_h, "data": sheet_at, "end": at + size}


def _cwdh_blocks(data: bytes, at: int) -> List[Tuple[int, int, int]]:
    """``(entries offset, first glyph, last glyph)`` of every CWDH block in the chain."""
    blocks, seen = [], set()
    while at and at not in seen and data[at:at + 4] == b"CWDH":
        seen.add(at)
        first, last, following = struct.unpack_from("<HHI", data, at + 8)
        blocks.append((at + 16, first, last))
        at = following - 8 if following else 0
    return blocks


def _cmap(data: bytes, at: int) -> Dict[int, int]:
    """``{code: glyph}`` from the CMAP chain (NX: 32-bit codes)."""
    glyphs: Dict[int, int] = {}
    seen = set()
    while at and at not in seen and data[at:at + 4] == b"CMAP":
        seen.add(at)
        begin, end, method, _reserved, following = struct.unpack_from("<IIHHI", data, at + 8)
        position = at + 24
        if method == 0:
            offset = struct.unpack_from("<H", data, position)[0]
            for code in range(begin, end + 1):
                glyphs.setdefault(code, code - begin + offset)
        elif method == 1:
            for code in range(begin, end + 1):
                index = struct.unpack_from("<h", data, position)[0]
                position += 2
                if index != -1:
                    glyphs.setdefault(code, index)
        elif method == 2:
            count = struct.unpack_from("<H", data, position)[0]
            position += 4
            for _ in range(count):
                code, index = struct.unpack_from("<Ih", data, position)
                position += 8
                if index != -1:
                    glyphs.setdefault(code, index)
        else:
            raise ValueError(f"Unknown CMAP mapping method {method}")
        at = following - 8 if following else 0
    return glyphs


# -- BNTX texture array ----------------------------------------------------------------


def _bntx(data: bytes, tglp: Dict[str, int]) -> Dict[str, int]:
    base = tglp["data"]
    if data[base:base + 4] != b"BNTX":
        raise ValueError("The BFFNT sheets are not a BNTX texture")
    count, info = struct.unpack_from("<IQ", data, base + 0x24)
    if count < 1:
        raise ValueError("BNTX without textures")
    brti = base + struct.unpack_from("<Q", data, base + info)[0]
    fmt = struct.unpack_from("<I", data, brti + 0x1C)[0]
    width, height, _depth, layers, layout = struct.unpack_from("<iiiii", data, brti + 0x24)
    image_size = struct.unpack_from("<I", data, brti + 0x50)[0]
    mips = base + struct.unpack_from("<Q", data, brti + 0x70)[0]
    start = base + struct.unpack_from("<Q", data, mips)[0]
    return {"format": fmt >> 8, "width": width, "height": height, "layers": max(1, layers),
            "block_height": 1 << (layout & 7), "start": start, "layer_size": image_size // max(1, layers)}


def _block_addresses(blocks_wide: int, blocks_high: int, bpp: int, block_height: int) -> List[int]:
    """Byte offset of every 4x4 block (row by row) in a block-linear surface (Tegra X1 GOBs)."""
    gobs_wide = (blocks_wide * bpp + 63) // 64
    rows_per_block = 8 * block_height
    out = []
    for y in range(blocks_high):
        row_base = (y // rows_per_block) * 512 * block_height * gobs_wide + (y % rows_per_block // 8) * 512
        row_in_gob = ((y % 8) // 2) * 64 + (y % 2) * 16
        for x in range(blocks_wide):
            xb = x * bpp
            out.append(row_base + (xb // 64) * 512 * block_height + ((xb % 64) // 32) * 256
                       + ((xb % 32) // 16) * 32 + row_in_gob + (xb % 16))
    return out


def _layer_bc4(data: bytes, texture: Dict[str, int], layer: int, addresses: List[int]) -> bytes:
    """Linear BC4 blocks of one layer."""
    at = texture["start"] + layer * texture["layer_size"]
    return b"".join(data[at + a:at + a + 8] for a in addresses)


def _texture_images(data: bytes, texture: Dict[str, int]) -> List[Image.Image]:
    """One channel per layer, in texture orientation (upside down)."""
    w, h = texture["width"], texture["height"]
    addresses = _block_addresses((w + 3) // 4, (h + 3) // 4, 8, texture["block_height"])
    return [Image.frombytes("L", (w, h), _layer_bc4(data, texture, layer, addresses), "bcn", 4)
            for layer in range(texture["layers"])]


def extract(data: bytes, params: Dict[str, Any]) -> Tuple[Metadata, Sheets]:
    finf = _finf(data)
    tglp = _tglp(data, finf["tglp"])
    cell_w, cell_h = tglp["cell_width"] + 1, tglp["cell_height"] + 1
    count = tglp["columns"] * tglp["rows"] * tglp["sheets"]
    size = (tglp["sheet_width"], tglp["sheet_height"])

    texture = _bntx(data, tglp)
    editable = texture["format"] == BC4
    if editable:
        sheets = [grey_sheet(layer.transpose(Image.Transpose.FLIP_TOP_BOTTOM))
                  for layer in _texture_images(data, texture)]
        sheets += [Image.new("RGBA", size, (0, 0, 0, 0))
                   for _ in range(int(params.get("min_sheets", 0)) - len(sheets))]
    else:
        sheets = [Image.new("RGBA", size, (0, 0, 0, 0)) for _ in range(tglp["sheets"])]
    file_count, count = count, tglp["columns"] * tglp["rows"] * len(sheets)

    packets = [{"kerning": -finf["left"], "width": finf["char_width"]} for _ in range(file_count)]
    packets += [{"kerning": 0, "width": finf["char_width"]} for _ in range(count - file_count)]
    glyph_widths = [finf["glyph_width"]] * file_count + [tglp["cell_width"]] * (count - file_count)
    for entries, first, last in _cwdh_blocks(data, finf["cwdh"]):
        for index in range(first, min(last, count - 1) + 1):
            left, glyph_w, char_w = struct.unpack_from("<bBB", data, entries + (index - first) * 3)
            packets[index] = {"kerning": -left, "width": char_w}
            glyph_widths[index] = glyph_w

    pairs = [(char_code(chr(code)), glyph) for code, glyph in _cmap(data, finf["cmap"]).items() if glyph < file_count]
    metadata = {
        "header": {"signature": "FFNT", "num_chunks": 4, "textures_editable": editable,
                   "texture_format": texture["format"]},
        "INF1": [{"encoding": 1, "ascent": finf["ascent"], "descent": max(0, finf["height"] - finf["ascent"]),
                  "width": finf["char_width"], "leading": finf["line_feed"], "fallback_code": 0x3F, "unk1": 0}],
        "GLY1": [{"start_glyph": 0, "end_glyph": count - 1, "cell_width": cell_w, "cell_height": cell_h,
                  "page_data_size": texture["layer_size"], "texture_format": texture["format"],
                  "glyph_horizontal_count": tglp["columns"], "glyph_vertical_count": tglp["rows"],
                  "texture_width": size[0], "texture_height": size[1]}],
        "MAP1": [map_entries(pairs)],
        "WID1": [{"first_code_included": 0, "last_code_included": count, "packets": packets,
                  "glyph_widths": glyph_widths}],
    }
    return metadata, sheets


def pack(metadata: Metadata, sheets: Sheets, original: bytes, params: Dict[str, Any]) -> bytes:
    finf = _finf(original)
    tglp = _tglp(original, finf["tglp"])
    out = bytearray(original)
    per_sheet = tglp["columns"] * tglp["rows"]
    count = per_sheet * tglp["sheets"]

    packets = metadata["WID1"][0]["packets"]
    for entries, first, last in _cwdh_blocks(original, finf["cwdh"]):
        for index in range(first, min(last, len(packets) - 1) + 1):
            at = entries + (index - first) * 3
            left = max(-128, min(127, -int(packets[index]["kerning"])))
            width = max(0, min(255, int(packets[index]["width"])))
            struct.pack_into("<bB", out, at, left, out[at + 1])
            out[at + 2] = width

    texture = _bntx(original, tglp)
    editable = texture["format"] == BC4 and metadata.get("header", {}).get("textures_editable", True)
    if editable:
        _write_pixels(out, original, texture, sheets)

    mapping = {ord(char): glyph for char, glyph in char_map(metadata).items()}
    if editable:
        inked = [index for index in range(tglp["sheets"], len(sheets)) if coverage(sheets[index]).getbbox()]
        top = max([tglp["sheets"] - 1, *inked, *(glyph // per_sheet for glyph in mapping.values())])
        if top >= tglp["sheets"]:
            out = _add_layers(out, texture, sheets[tglp["sheets"]:top + 1])
    new_count = per_sheet * _tglp(bytes(out), finf["tglp"])["sheets"]
    if new_count > count:
        widths = metadata["WID1"][0].get("glyph_widths") or []
        default = {"kerning": 0, "width": finf["char_width"]}
        _append_cwdh(out, count, [(packets[i] if i < len(packets) else default,
                                   widths[i] if i < len(widths) else tglp["cell_width"])
                                  for i in range(count, new_count)])
    mapping = {code: glyph for code, glyph in mapping.items() if glyph < new_count}
    before = {ord(code_char(char_code(chr(code)))): glyph
              for code, glyph in _cmap(original, finf["cmap"]).items() if glyph < count}
    if mapping != before:
        _prepend_cmap(out, mapping, before)
    return bytes(out)


def _write_pixels(out: bytearray, original: bytes, texture: Dict[str, int], sheets: Sheets) -> None:
    """Sheet pixels of the layers the file has, only the 4x4 blocks that changed."""
    w, h = texture["width"], texture["height"]
    blocks_wide, blocks_high = (w + 3) // 4, (h + 3) // 4
    addresses = _block_addresses(blocks_wide, blocks_high, 8, texture["block_height"])
    for layer, old_image in enumerate(_texture_images(original, texture)):
        if layer >= len(sheets):
            break
        new_image = coverage(sheets[layer]).transpose(Image.Transpose.FLIP_TOP_BOTTOM)
        if new_image.size != (w, h):
            raise ValueError(f"Sheet {layer} is {new_image.size}, the texture {w}x{h}")
        old, new = old_image.tobytes(), new_image.tobytes()
        base = texture["start"] + layer * texture["layer_size"]
        for by in range(blocks_high):
            band = slice(by * 4 * w, (by * 4 + 4) * w)
            if old[band] == new[band]:
                continue
            for bx in range(blocks_wide):
                if all(old[(by * 4 + y) * w + bx * 4:(by * 4 + y) * w + bx * 4 + 4]
                       == new[(by * 4 + y) * w + bx * 4:(by * 4 + y) * w + bx * 4 + 4] for y in range(4)):
                    continue
                ink = new_image.crop((bx * 4, by * 4, bx * 4 + 4, by * 4 + 4))
                white = Image.new("L", (4, 4), 255)
                block = Image.merge("RGBA", (white, white, white, ink)).tobytes("bcn", 3)[:8]  # BC3 alpha = BC4
                at = base + addresses[by * blocks_wide + bx]
                out[at:at + 8] = block


# -- growing the file ---------------------------------------------------------------
# Offsets in FINF and the CWDH/CMAP "next" fields point 8 bytes into a block (past its header).


def _add(out: bytearray, fmt: str, at: int, delta: int) -> None:
    struct.pack_into(fmt, out, at, struct.unpack_from(fmt, out, at)[0] + delta)


def _shift(out: bytearray, at: int, after: int, delta: int) -> None:
    """Add ``delta`` to the 32-bit offset stored at ``at`` when it points past ``after``."""
    if struct.unpack_from("<I", out, at)[0] > after:
        _add(out, "<I", at, delta)


def _chain_links(data: bytes, at: int, magic: bytes, next_field: int) -> List[int]:
    """Positions of the "next" fields of a CWDH (+12) or CMAP (+20) chain starting at block ``at``."""
    links, seen = [], set()
    while at and at not in seen and data[at:at + 4] == magic:
        seen.add(at)
        links.append(at + next_field)
        following = struct.unpack_from("<I", data, at + next_field)[0]
        at = following - 8 if following else 0
    return links


def _add_layers(out: bytearray, texture: Dict[str, int], new_sheets: Sheets) -> bytearray:
    """Append layers to the BNTX texture array: their data goes right before the BNTX's ``_RLT``."""
    finf_at = struct.unpack_from("<H", out, 6)[0]
    finf = _finf(bytes(out))
    tglp_at = finf["tglp"]
    bntx = _tglp(bytes(out), tglp_at)["data"]
    rlt = bntx + struct.unpack_from("<I", out, bntx + 0x18)[0]
    layers, layer_size = texture["layers"], texture["layer_size"]
    insert_at = texture["start"] + layers * layer_size
    if insert_at != rlt or out[rlt:rlt + 4] != b"_RLT":
        raise ValueError("Cannot add sheets: the BNTX texture data does not end at its relocation table")
    w, h = texture["width"], texture["height"]
    addresses = _block_addresses((w + 3) // 4, (h + 3) // 4, 8, texture["block_height"])
    data = bytearray()
    for sheet in new_sheets:
        ink = coverage(sheet).transpose(Image.Transpose.FLIP_TOP_BOTTOM)
        white = Image.new("L", ink.size, 255)
        linear = Image.merge("RGBA", (white, white, white, ink)).tobytes("bcn", 3)  # BC3 alpha halves = BC4
        layer = bytearray(layer_size)
        for index, address in enumerate(addresses):
            layer[address:address + 8] = linear[index * 16:index * 16 + 8]
        data += layer
    delta = len(data)

    links = (_chain_links(bytes(out), finf["cwdh"], b"CWDH", 12)
             + _chain_links(bytes(out), finf["cmap"], b"CMAP", 20))
    for at in links + [finf_at + 8 + 16, finf_at + 8 + 20]:     # chains and FINF -> CWDH / CMAP
        _shift(out, at, insert_at, delta)
    _add(out, "<I", 0x0C, delta)                                 # FFNT file size
    _add(out, "<I", tglp_at + 4, delta)                          # TGLP block size
    out[tglp_at + 10] = layers + len(new_sheets)                 # TGLP sheet count
    _add(out, "<I", tglp_at + 12, delta)                         # TGLP sheet data size (= the BNTX)
    _add(out, "<I", bntx + 0x18, delta)                          # BNTX -> _RLT
    _add(out, "<I", bntx + 0x1C, delta)                          # BNTX file size
    _add(out, "<Q", bntx + struct.unpack_from("<Q", out, bntx + 0x30)[0] + 8, delta)   # BRTD size
    brti = bntx + struct.unpack_from("<Q", out, bntx + struct.unpack_from("<Q", out, bntx + 0x28)[0])[0]
    struct.pack_into("<I", out, brti + 0x30, layers + len(new_sheets))                # array layers
    _add(out, "<I", brti + 0x50, delta)                          # image size
    out[insert_at:insert_at] = data
    rlt += delta
    _add(out, "<I", rlt + 4, delta)                              # _RLT's own offset
    inserted = insert_at - bntx
    for section in range(struct.unpack_from("<I", out, rlt + 8)[0]):
        entry = rlt + 0x10 + section * 0x18
        offset, size = struct.unpack_from("<II", out, entry + 8)
        if offset < inserted <= offset + size:                   # the section that holds the texture
            struct.pack_into("<I", out, entry + 12, size + delta)
        elif offset >= inserted:
            struct.pack_into("<I", out, entry + 8, offset + delta)
    return out


def _append_block(out: bytearray, block: bytes) -> int:
    """Append a block at the end (4-byte aligned) and count it in the header; returns its offset."""
    out += b"\0" * (-len(out) % 4)
    at = len(out)
    out += block
    struct.pack_into("<I", out, 0x0C, len(out))
    _add(out, "<H", 0x10, 1)
    return at


def _append_cwdh(out: bytearray, first: int, glyphs: List[Tuple[Dict[str, int], int]]) -> None:
    """A CWDH block for new glyphs ``first...``, linked at the end of the chain."""
    links = _chain_links(bytes(out), _finf(bytes(out))["cwdh"], b"CWDH", 12)
    body = bytearray()
    for packet, glyph_width in glyphs:
        body += struct.pack("<bBB", max(-128, min(127, -int(packet["kerning"]))),
                            max(0, min(255, int(glyph_width))), max(0, min(255, int(packet["width"]))))
    body += b"\0" * (-len(body) % 4)
    at = _append_block(out, struct.pack("<4sIHHI", b"CWDH", 16 + len(body), first, first + len(glyphs) - 1, 0)
                       + bytes(body))
    struct.pack_into("<I", out, links[-1], at + 8)


def _prepend_cmap(out: bytearray, mapping: Dict[int, int], before: Dict[int, int]) -> None:
    """A scan CMAP block with the final mapping of every code in the changed range, first in the chain."""
    changed = [code for code in set(mapping) | set(before) if mapping.get(code) != before.get(code)]
    low, high = min(changed), max(changed)
    pairs = sorted((code, glyph) for code, glyph in mapping.items() if low <= code <= high)
    finf_at = struct.unpack_from("<H", out, 6)[0]
    old_head = struct.unpack_from("<I", out, finf_at + 8 + 20)[0]
    body = struct.pack("<HH", len(pairs), 0) + b"".join(struct.pack("<IhH", code, glyph, 0) for code, glyph in pairs)
    at = _append_block(out, struct.pack("<4sIIIHHI", b"CMAP", 24 + len(body), low, high, 2, 0, old_head) + body)
    struct.pack_into("<I", out, finf_at + 8 + 20, at + 8)
