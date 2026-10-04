"""Nintendo 3DS and Wii U bitmap fonts: BCFNT (``CFNT``), the 3DS flavour of BFFNT 4.0 (``FFNT``, little
endian, raw sheets) and Wii U BFFNT 3.0 (``FFNT``, big endian, GX2 sheets; format id ``bffnt_wiiu``).

Layout: header, ``FINF`` (metrics and the offsets of the other blocks), ``TGLP`` (cell grid; the sheets
are raw PICA textures), chains of ``CWDH`` (left, glyph width, advance per glyph) and ``CMAP`` (16-bit
code -> glyph: direct range, table or scan list). A sheet is stored in 8x8 tiles, top row first, Morton
order inside a tile (A4 / L4: low nibble first). Cells are ``cell + 1`` pixels apart, the spare row and
column on the top and left; the model shows the cells without them, so cell pixel 0 is glyph pixel 0.

Wii U: the same blocks in big endian; a sheet is a GX2 surface (BC4, ``2D_TILED_THIN1``, see ``gx2``)
stored upside down. Only the 4x4 blocks of a redrawn cell are encoded again, so the rest of the sheet
keeps its bytes. RGBA8 sheets (the button-icon font) open for viewing; editing their pixels is refused.

Editing: cell pixels, left offsets and advances are written in place; a redrawn glyph's glyph width is
measured from its ink. New characters are added: a glyph after the last ``CWDH`` range gets a new
``CWDH`` block; a new code goes into a ``CMAP`` table that covers it, else into a scan list (the one
covering it is rewritten at the end of the file, or a new one is linked at the end of the chain).
Changing or removing a code the file already has is refused.
"""
from __future__ import annotations

import struct
from functools import lru_cache
from typing import Any, Dict, List, Optional, Tuple

from PIL import Image, ImageChops

from core.font_formats import Metadata, Sheets, char_map, coverage, grey_sheet, map_entries, char_code
from core.texture_formats import gx2

ADDS_GLYPHS = True  # a typed character gets its own CMAP code (an empty cell, a new CWDH block)

LA8, L8, A8, LA4, L4, A4 = 5, 7, 8, 9, 10, 11
FORMATS = {LA8: "LA8", L8: "L8", A8: "A8", LA4: "LA4", L4: "L4", A4: "A4"}
_BITS = {LA8: 16, L8: 8, A8: 8, LA4: 8, L4: 4, A4: 4}
_NO_GLYPH = 0xFFFF

# Wii U (NW4F) sheet formats
CAFE_RGBA8, CAFE_BC4, CAFE_RGBA8_SRGB = 0, 12, 14
CAFE_FORMATS = {CAFE_RGBA8: "RGBA8", CAFE_BC4: "BC4", CAFE_RGBA8_SRGB: "RGBA8_SRGB"}


def _endian(data: bytes) -> str:
    return ">" if data[4:6] == b"\xfe\xff" else "<"


# -- PICA textures (also used by the GZF backend) ------------------------------------------


@lru_cache(maxsize=8)
def _order(width: int, height: int) -> Tuple[int, ...]:
    """The pixel index (``y * width + x``) of every texel in storage order."""
    tile = [(((i >> 1) & 1) | ((i >> 2) & 2) | ((i >> 3) & 4), (i & 1) | ((i >> 1) & 2) | ((i >> 2) & 4))
            for i in range(64)]
    return tuple((ty + y) * width + tx + x for ty in range(0, height, 8) for tx in range(0, width, 8)
                 for y, x in tile)


def _nibbles(raw: bytes) -> bytes:
    """Two texels per byte, low nibble first, each scaled to 0..255."""
    out = bytearray(len(raw) * 2)
    out[0::2] = raw.translate(bytes((b & 15) * 17 for b in range(256)))
    out[1::2] = raw.translate(bytes((b >> 4) * 17 for b in range(256)))
    return bytes(out)


def _unswizzle(texels: bytes, width: int, height: int) -> bytes:
    pixels = bytearray(width * height)
    for texel, pixel in zip(texels, _order(width, height)):
        pixels[pixel] = texel
    return bytes(pixels)


def _swizzle(pixels: bytes, width: int, height: int) -> bytes:
    return bytes(pixels[pixel] for pixel in _order(width, height))


def _four_bit(value: int) -> int:
    return min(15, (value + 8) // 17)


def texture_size(fmt: int, width: int, height: int) -> int:
    """Bytes of a sheet."""
    if fmt not in _BITS:
        raise ValueError(f"3DS texture format {fmt} is not supported (A4, L4, A8, L8, LA4, LA8 are)")
    return width * height * _BITS[fmt] // 8


def decode(raw: bytes, fmt: int, width: int, height: int) -> Image.Image:
    """An RGBA image of a PICA texture: alpha and luminance formats as grey ink, LA as grey + alpha."""
    raw = bytes(raw[:texture_size(fmt, width, height)])
    size = (width, height)
    if fmt in (A4, L4):
        return grey_sheet(Image.frombytes("L", size, _unswizzle(_nibbles(raw), width, height)))
    if fmt in (A8, L8):
        return grey_sheet(Image.frombytes("L", size, _unswizzle(raw, width, height)))
    if fmt == LA4:
        lum = _unswizzle(raw.translate(bytes((b >> 4) * 17 for b in range(256))), width, height)
        alpha = _unswizzle(raw.translate(bytes((b & 15) * 17 for b in range(256))), width, height)
    else:  # LA8: alpha byte, then luminance
        alpha, lum = _unswizzle(raw[0::2], width, height), _unswizzle(raw[1::2], width, height)
    lum_image = Image.frombytes("L", size, lum)
    return Image.merge("RGBA", (lum_image, lum_image, lum_image, Image.frombytes("L", size, alpha)))


def encode(image: Image.Image, fmt: int) -> bytes:
    """The PICA texture of an RGBA image (the inverse of ``decode``)."""
    width, height = image.size
    texture_size(fmt, width, height)
    if fmt in (A4, L4, A8, L8):
        texels = _swizzle(coverage(image).tobytes(), width, height)
        if fmt in (A8, L8):
            return texels
        quantized = texels.translate(bytes(_four_bit(v) for v in range(256)))
        return bytes(low | high << 4 for low, high in zip(quantized[0::2], quantized[1::2]))
    red, green, blue, alpha = image.convert("RGBA").split()
    lum = _swizzle(ImageChops.lighter(ImageChops.lighter(red, green), blue).tobytes(), width, height)
    alpha_texels = _swizzle(alpha.tobytes(), width, height)
    if fmt == LA4:
        return bytes(_four_bit(l_value) << 4 | _four_bit(a_value) for l_value, a_value in zip(lum, alpha_texels))
    out = bytearray(len(lum) * 2)
    out[0::2], out[1::2] = alpha_texels, lum
    return bytes(out)


# -- font blocks -------------------------------------------------------------------------------


def is_ctr_font(data: bytes) -> bool:
    """A 3DS font: ``CFNT``, or a little-endian ``FFNT`` whose sheets are not a Switch BNTX."""
    if data[:4] == b"CFNT":
        return True
    if data[:6] != b"FFNT\xff\xfe":
        return False
    try:
        info = _info(data)
    except (ValueError, struct.error):
        return False
    return data[info["data"]:info["data"] + 4] != b"BNTX"


def _info(data: bytes) -> Dict[str, Any]:
    """FINF and TGLP fields (offsets are block starts, not the +8 pointers); ``e`` is the byte order."""
    magic = bytes(data[:4])
    cafe = magic == b"FFNT" and data[4:6] == b"\xfe\xff"
    if magic not in (b"CFNT", b"FFNT") or not (cafe or data[4:6] == b"\xff\xfe"):
        raise ValueError("Not a 3DS (CFNT / FFNT) or Wii U (FFNT) font")
    e = ">" if cafe else "<"
    at = struct.unpack_from(e + "H", data, 6)[0]
    if data[at:at + 4] != b"FINF":
        raise ValueError("Font without FINF")
    if magic == b"CFNT":
        (_kind, line_feed, _alter, left, glyph_w, char_w, _enc, tglp, cwdh, cmap, height, _width,
         ascent, _pad) = struct.unpack_from("<BbHbBBBIIIBBBB", data, at + 8)
        t = tglp - 8
        (cell_w, cell_h, baseline, _max_w, sheet_size, sheets, fmt, columns, rows, sheet_w, sheet_h,
         sheet_at) = struct.unpack_from("<BBbBIHHHHHHI", data, t + 8)
    else:
        (_kind, height, _width, ascent, line_feed, _alter, left, glyph_w, char_w, _enc,
         tglp, cwdh, cmap) = struct.unpack_from(e + "BBBBHHbBBBIII", data, at + 8)
        t = tglp - 8
        (cell_w, cell_h, sheets, _max_w, sheet_size, baseline, fmt, columns, rows, sheet_w, sheet_h,
         sheet_at) = struct.unpack_from(e + "BBBBIHHHHHHI", data, t + 8)
    if data[t:t + 4] != b"TGLP":
        raise ValueError("Font without TGLP")
    return {"e": e, "cafe": cafe, "height": height, "ascent": ascent, "line_feed": line_feed, "left": left,
            "glyph_width": glyph_w, "char_width": char_w, "cwdh": cwdh - 8 if cwdh else 0,
            "cmap": cmap - 8 if cmap else 0, "finf": at, "cell_width": cell_w, "cell_height": cell_h,
            "baseline": baseline, "sheet_size": sheet_size, "sheets": sheets, "format": fmt & 0x7FFF,
            "columns": columns, "rows": rows, "sheet_width": sheet_w, "sheet_height": sheet_h, "data": sheet_at}


def _chain(data: bytes, at: int, magic: bytes, next_at: int) -> List[int]:
    """Block offsets of a ``CWDH`` / ``CMAP`` chain (``next_at``: where the next pointer is)."""
    blocks, seen = [], set()
    while at and at not in seen and at + 8 <= len(data) and data[at:at + 4] == magic:
        seen.add(at)
        blocks.append(at)
        following = struct.unpack_from(_endian(data) + "I", data, at + next_at)[0]
        at = following - 8 if following else 0
    return blocks


def _widths(data: bytes, info: Dict[str, int]) -> Dict[int, Tuple[int, int, int]]:
    """``{glyph: (left, glyph width, advance)}`` from the CWDH chain."""
    result: Dict[int, Tuple[int, int, int]] = {}
    e = info["e"]
    for at in _chain(data, info["cwdh"], b"CWDH", 12):
        first, last = struct.unpack_from(e + "HH", data, at + 8)
        for index in range(first, last + 1):
            result.setdefault(index, struct.unpack_from("bBB", data, at + 16 + (index - first) * 3))
    return result


def _cmap_blocks(data: bytes, info: Dict[str, int]) -> List[Dict[str, Any]]:
    """Every CMAP block: ``at``, ``begin``, ``end``, ``method`` and ``codes`` ``{code: glyph}``."""
    blocks, e = [], info["e"]
    for at in _chain(data, info["cmap"], b"CMAP", 16):
        begin, end, method = struct.unpack_from(e + "HHH", data, at + 8)
        position, codes = at + 20, {}
        if method == 0:
            offset = struct.unpack_from(e + "H", data, position)[0]
            codes = {code: code - begin + offset for code in range(begin, end + 1)}
        elif method == 1:
            for code in range(begin, end + 1):
                glyph = struct.unpack_from(e + "H", data, position + 2 * (code - begin))[0]
                if glyph != _NO_GLYPH:
                    codes[code] = glyph
        elif method == 2:
            count = struct.unpack_from(e + "H", data, position)[0]
            for index in range(count):
                code, glyph = struct.unpack_from(e + "HH", data, position + 2 + 4 * index)
                if glyph != _NO_GLYPH:
                    codes[code] = glyph
        else:
            raise ValueError(f"Unknown CMAP mapping method {method}")
        blocks.append({"at": at, "begin": begin, "end": end, "method": method, "codes": codes})
    return blocks


def _codes(blocks: List[Dict[str, Any]]) -> Dict[int, int]:
    result: Dict[int, int] = {}
    for block in blocks:
        for code, glyph in block["codes"].items():
            result.setdefault(code, glyph)
    return result


# -- model ------------------------------------------------------------------------------------


def _cell_box(info: Dict[str, int], cell: int) -> Tuple[int, int, int, int]:
    """Where cell ``cell`` (of its sheet) is in the texture."""
    column, row = cell % info["columns"], cell // info["columns"]
    x, y = column * (info["cell_width"] + 1) + 1, row * (info["cell_height"] + 1) + 1
    return x, y, x + info["cell_width"], y + info["cell_height"]


def _model_box(info: Dict[str, int], cell: int) -> Tuple[int, int, int, int]:
    column, row = cell % info["columns"], cell // info["columns"]
    x, y = column * info["cell_width"], row * info["cell_height"]
    return x, y, x + info["cell_width"], y + info["cell_height"]


def _textures(data: bytes, info: Dict[str, int]) -> List[Image.Image]:
    if info["cafe"]:
        return [_cafe_decode(data, info, index) for index in range(info["sheets"])]
    size = texture_size(info["format"], info["sheet_width"], info["sheet_height"])
    return [decode(data[info["data"] + index * info["sheet_size"]:][:size], info["format"],
                   info["sheet_width"], info["sheet_height"]) for index in range(info["sheets"])]


# -- Wii U (GX2) sheets ------------------------------------------------------------------------


def _cafe_layout(info: Dict[str, Any], index: int) -> Tuple[int, int, int, Tuple[int, ...]]:
    """``(elements wide, elements high, bytes per element, element offsets)`` of Wii U sheet ``index``
    (the sheets are the layers of one texture array)."""
    fmt, w, h = info["format"], info["sheet_width"], info["sheet_height"]
    if fmt == CAFE_BC4:
        wide, high, size = (w + 3) // 4, (h + 3) // 4, 8
    elif fmt in (CAFE_RGBA8, CAFE_RGBA8_SRGB):
        wide, high, size = w, h, 4
    else:
        raise ValueError(f"Wii U font sheet format {fmt} is not supported (BC4 and RGBA8 are)")
    return wide, high, size, gx2.element_offsets(wide, high, size * 8, slice_index=index)


def _cafe_decode(data: bytes, info: Dict[str, Any], index: int) -> Image.Image:
    """An RGBA image of sheet ``index``, right side up: BC4 as grey ink, RGBA8 as is."""
    _wide, _high, size, offsets = _cafe_layout(info, index)
    raw = data[info["data"] + index * info["sheet_size"]:][:info["sheet_size"]]
    linear = b"".join(raw[offset:offset + size] for offset in offsets)
    dimensions = (info["sheet_width"], info["sheet_height"])
    if info["format"] == CAFE_BC4:
        image = grey_sheet(Image.frombytes("L", dimensions, linear, "bcn", 4))
    else:
        image = Image.frombytes("RGBA", dimensions, linear)
    return image.transpose(Image.Transpose.FLIP_TOP_BOTTOM)


def _cafe_write(out: bytearray, info: Dict[str, Any], index: int, old: Image.Image, new: Image.Image) -> None:
    """Encode again only the 4x4 blocks of sheet ``index`` whose ink changed (BC4)."""
    if info["format"] != CAFE_BC4:
        raise ValueError("Only BC4 sheets of a Wii U font can be redrawn")
    wide, high, _size, offsets = _cafe_layout(info, index)
    old_ink = coverage(old).transpose(Image.Transpose.FLIP_TOP_BOTTOM)
    new_ink = coverage(new).transpose(Image.Transpose.FLIP_TOP_BOTTOM)
    width = info["sheet_width"]
    before, after = old_ink.tobytes(), new_ink.tobytes()
    base = info["data"] + index * info["sheet_size"]
    white = Image.new("L", (4, 4), 255)
    for by in range(high):
        band = slice(by * 4 * width, (by * 4 + 4) * width)
        if before[band] == after[band]:
            continue
        for bx in range(wide):
            if all(before[(by * 4 + y) * width + bx * 4:(by * 4 + y) * width + bx * 4 + 4]
                   == after[(by * 4 + y) * width + bx * 4:(by * 4 + y) * width + bx * 4 + 4] for y in range(4)):
                continue
            ink = new_ink.crop((bx * 4, by * 4, bx * 4 + 4, by * 4 + 4))
            block = Image.merge("RGBA", (white, white, white, ink)).tobytes("bcn", 3)[:8]  # BC3 alpha = BC4
            at = base + offsets[by * wide + bx]
            out[at:at + 8] = block


def _model_sheets(info: Dict[str, int], textures: List[Image.Image]) -> List[Image.Image]:
    per_sheet = info["columns"] * info["rows"]
    sheets = []
    for texture in textures:
        sheet = Image.new("RGBA", (info["columns"] * info["cell_width"], info["rows"] * info["cell_height"]))
        for cell in range(per_sheet):
            sheet.paste(texture.crop(_cell_box(info, cell)), _model_box(info, cell)[:2])
        sheets.append(sheet)
    return sheets


def extract(data: bytes, params: Dict[str, Any]) -> Tuple[Metadata, Sheets]:
    info = _info(data)
    sheets = _model_sheets(info, _textures(data, info))
    if info["cafe"] and info["format"] == CAFE_BC4:   # blank sheets for new glyphs (``min_sheets``)
        size = (info["columns"] * info["cell_width"], info["rows"] * info["cell_height"])
        sheets += [Image.new("RGBA", size) for _ in range(int(params.get("min_sheets", 0)) - len(sheets))]
    count = info["columns"] * info["rows"] * len(sheets)
    widths = _widths(data, info)
    packets = [{"kerning": -info["left"], "width": info["char_width"]} for _ in range(count)]
    glyph_widths = [info["glyph_width"]] * count
    for glyph, (left, glyph_w, advance) in widths.items():
        if glyph < count:
            packets[glyph] = {"kerning": -left, "width": advance}
            glyph_widths[glyph] = glyph_w
    pairs = [(char_code(chr(code)), glyph) for code, glyph in _codes(_cmap_blocks(data, info)).items()
             if glyph < count]
    metadata = {
        "header": {"signature": bytes(data[:4]).decode("ascii"), "num_chunks": 4,
                   "texture_format": (CAFE_FORMATS if info["cafe"] else FORMATS).get(info["format"], info["format"])},
        "INF1": [{"encoding": 1, "ascent": info["baseline"], "descent": max(0, info["height"] - info["ascent"]),
                  "width": info["char_width"], "leading": info["line_feed"], "fallback_code": 0x3F, "unk1": 0}],
        "GLY1": [{"start_glyph": 0, "end_glyph": count - 1, "cell_width": info["cell_width"],
                  "cell_height": info["cell_height"], "page_data_size": info["sheet_size"],
                  "texture_format": info["format"], "glyph_horizontal_count": info["columns"],
                  "glyph_vertical_count": info["rows"], "texture_width": sheets[0].width if sheets else 0,
                  "texture_height": sheets[0].height if sheets else 0}],
        "MAP1": [map_entries(pairs)],
        "WID1": [{"first_code_included": 0, "last_code_included": count, "packets": packets,
                  "glyph_widths": glyph_widths}],
    }
    return metadata, sheets


# -- pack -------------------------------------------------------------------------------------


def _ink_width(cell: Image.Image) -> int:
    bounds = cell.getchannel("A").getbbox()
    return bounds[2] if bounds else 0


def _clamp(value: int, low: int, high: int) -> int:
    return max(low, min(high, int(value)))


def _set_pointer(out: bytearray, holder: Optional[int], offset_in_block: int, target: int, info) -> None:
    """Point ``holder``'s next field (or FINF's first pointer when ``holder`` is None) at block ``target``."""
    if holder is None:
        struct.pack_into(info["e"] + "I", out, info["finf"] + offset_in_block, target + 8)
    else:
        struct.pack_into(info["e"] + "I", out, holder + offset_in_block, target + 8)


def _append_block(out: bytearray, block: bytes) -> int:
    out += bytes(-len(out) % 4)
    at = len(out)
    out += block + bytes(-len(block) % 4)
    return at


def _scan_block(begin: int, end: int, codes: Dict[int, int], e: str = "<") -> bytes:
    body = struct.pack(e + "HHHHI", begin, end, 2, 0, 0) + struct.pack(e + "H", len(codes))
    body += b"".join(struct.pack(e + "HH", code, glyph) for code, glyph in sorted(codes.items()))
    body += bytes(-(len(body) + 8) % 4)
    return b"CMAP" + struct.pack(e + "I", len(body) + 8) + body


def _cwdh_block(first: int, entries: List[Tuple[int, int, int]], e: str = "<") -> bytes:
    body = struct.pack(e + "HHI", first, first + len(entries) - 1, 0)
    body += b"".join(struct.pack("bBB", *entry) for entry in entries)
    body += bytes(-(len(body) + 8) % 4)
    return b"CWDH" + struct.pack(e + "I", len(body) + 8) + body


def _finf_pointer_offsets(data: bytes) -> Tuple[int, int]:
    """Offsets in FINF of the CWDH and CMAP pointers."""
    return (0x14, 0x18) if data[:4] == b"CFNT" else (0x18, 0x1C)


def _cafe_add_sheets(data: bytes, info: Dict[str, Any], extra: int) -> bytes:
    """``data`` with ``extra`` blank sheets after the last one (inside TGLP); every offset behind them moves."""
    e, finf = info["e"], info["finf"]
    tglp = struct.unpack_from(e + "I", data, finf + 0x14)[0] - 8
    insert_at = info["data"] + info["sheets"] * info["sheet_size"]
    if tglp + struct.unpack_from(e + "I", data, tglp + 4)[0] != insert_at:
        raise ValueError("Cannot add sheets: the font's sheet data does not end its TGLP block")
    delta = extra * info["sheet_size"]
    links = ([at + 12 for at in _chain(data, info["cwdh"], b"CWDH", 12)]
             + [at + 16 for at in _chain(data, info["cmap"], b"CMAP", 16)])
    out = bytearray(data[:insert_at]) + bytes(delta) + bytearray(data[insert_at:])
    for at in [finf + 0x18, finf + 0x1C] + [link + delta for link in links]:
        pointer = struct.unpack_from(e + "I", out, at)[0]
        if pointer > insert_at:
            struct.pack_into(e + "I", out, at, pointer + delta)
    struct.pack_into(e + "I", out, tglp + 4, insert_at + delta - tglp)
    out[tglp + 10] += extra
    struct.pack_into(e + "I", out, 0x0C, len(out))
    return bytes(out)


def pack(metadata: Metadata, sheets: Sheets, original: bytes, params: Dict[str, Any]) -> bytes:
    info = _info(original)
    e = info["e"]
    if info["cafe"] and len(sheets) > info["sheets"]:
        # Blank sheets (``min_sheets``) become part of the file only when they got ink or a character.
        per_sheet = info["columns"] * info["rows"]
        inked = [index for index in range(info["sheets"], len(sheets)) if coverage(sheets[index]).getbbox()]
        top = max([info["sheets"] - 1, *inked, *(glyph // per_sheet for glyph in char_map(metadata).values())])
        if top >= info["sheets"]:
            original = _cafe_add_sheets(original, info, top + 1 - info["sheets"])
            info = _info(original)
        sheets = sheets[:info["sheets"]]
    out = bytearray(original)
    count = info["columns"] * info["rows"] * info["sheets"]
    per_sheet = info["columns"] * info["rows"]
    packets = metadata["WID1"][0]["packets"]

    # Pixels: only the cells that changed; their glyph width follows the ink.
    textures = _textures(original, info)
    old_sheets = _model_sheets(info, textures)
    redrawn = set()
    for index, (texture, old, new) in enumerate(zip(textures, old_sheets, sheets)):
        if new.size != old.size:
            raise ValueError(f"Sheet {index} is {new.size[0]}x{new.size[1]}, the font's {old.size[0]}x{old.size[1]}")
        new = new.convert("RGBA")
        if new.tobytes() == old.tobytes():
            continue
        before = texture.copy()
        for cell in range(per_sheet):
            box = _model_box(info, cell)
            piece = new.crop(box)
            if piece.tobytes() != old.crop(box).tobytes():
                texture.paste(piece, _cell_box(info, cell)[:2])
                redrawn.add(index * per_sheet + cell)
        if info["cafe"]:
            _cafe_write(out, info, index, before, texture)
            continue
        start = info["data"] + index * info["sheet_size"]
        raw = encode(texture, info["format"])
        out[start:start + len(raw)] = raw

    def entry(glyph: int, glyph_width: int) -> Tuple[int, int, int]:
        if glyph in redrawn:
            sheet, cell = divmod(glyph, per_sheet)
            glyph_width = _ink_width(sheets[sheet].crop(_model_box(info, cell)))
        packet = packets[glyph] if glyph < len(packets) else {"kerning": -info["left"], "width": info["char_width"]}
        return (_clamp(-int(packet["kerning"]), -128, 127), _clamp(glyph_width, 0, 255),
                _clamp(packet["width"], 0, 255))

    # Widths of the glyphs the file has.
    widths = _widths(original, info)
    for at in _chain(original, info["cwdh"], b"CWDH", 12):
        first, last = struct.unpack_from(e + "HH", original, at + 8)
        for glyph in range(first, last + 1):
            struct.pack_into("bBB", out, at + 16 + (glyph - first) * 3, *entry(glyph, widths[glyph][1]))

    # Characters: the codes the file has must stay; new ones are added.
    blocks = _cmap_blocks(original, info)
    existing = _codes(blocks)
    wanted: Dict[int, int] = {}
    for char, glyph in char_map(metadata).items():
        wanted[ord(char)] = glyph
    changed = [code for code, glyph in existing.items() if glyph < count and wanted.get(code) != glyph]
    if changed:
        raise ValueError("This font keeps the characters it has; changed or removed: "
                         + " ".join(f"U+{code:04X}" for code in sorted(changed)[:10]))
    new = {code: glyph for code, glyph in wanted.items() if code not in existing}
    if not new:
        return bytes(out)
    if max(new) > 0xFFFF:
        raise ValueError("3DS fonts map 16-bit character codes only")
    if max(new.values()) >= count:
        raise ValueError(f"Glyph {max(new.values())} is beyond the font's {count} cells")

    cwdh_ptr, cmap_ptr = _finf_pointer_offsets(original)
    added_blocks = 0

    # New codes: into a table that covers them, else into a scan list.
    scan_extra: Dict[int, Dict[int, int]] = {}
    loose: Dict[int, int] = {}
    for code, glyph in sorted(new.items()):
        block = next((b for b in blocks if b["begin"] <= code <= b["end"] and b["method"] in (1, 2)), None)
        if block is None:
            loose[code] = glyph
        elif block["method"] == 1:
            struct.pack_into(e + "H", out, block["at"] + 20 + 2 * (code - block["begin"]), glyph)
        else:
            scan_extra.setdefault(block["at"], {})[code] = glyph
    for at, extra in scan_extra.items():
        block = next(b for b in blocks if b["at"] == at)
        size = struct.unpack_from(e + "I", original, at + 4)[0]
        following = struct.unpack_from(e + "I", original, at + 16)[0]
        rebuilt = bytearray(_scan_block(block["begin"], block["end"], {**block["codes"], **extra}, e))
        struct.pack_into(e + "I", rebuilt, 16, following)
        if at + size == len(out):           # the last block of the file is rewritten where it is
            del out[at:]
            added_blocks -= 1
        index = blocks.index(block)
        new_at = _append_block(out, bytes(rebuilt))
        _set_pointer(out, blocks[index - 1]["at"] if index else None, 16 if index else cmap_ptr, new_at, info)
        block["at"] = new_at
        added_blocks += 1
    if loose:
        last = blocks[-1]["at"] if blocks else None
        at = _append_block(out, _scan_block(min(loose), max(loose), loose, e))
        _set_pointer(out, last, 16 if last is not None else cmap_ptr, at, info)
        added_blocks += 1

    # New glyphs after the last width range get one CWDH block (after the CMAP work, which may cut the file end).
    known = max(widths) + 1 if widths else 0
    last_glyph = max(new.values())
    if last_glyph >= known:
        default = info["glyph_width"]
        entries = [entry(glyph, _ink_width(sheets[glyph // per_sheet].crop(_model_box(info, glyph % per_sheet)))
                         if glyph in new.values() else default) for glyph in range(known, last_glyph + 1)]
        chain = _chain(original, info["cwdh"], b"CWDH", 12)
        at = _append_block(out, _cwdh_block(known, entries, e))
        _set_pointer(out, chain[-1] if chain else None, 12 if chain else cwdh_ptr, at, info)
        added_blocks += 1

    struct.pack_into(e + "I", out, 0x0C, len(out))
    struct.pack_into(e + "H", out, 0x10, struct.unpack_from(e + "H", original, 0x10)[0] + added_blocks)
    return bytes(out)
