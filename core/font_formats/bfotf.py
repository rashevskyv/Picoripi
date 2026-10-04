"""Nintendo Switch scalable fonts (``.bfotf`` / ``.bfttf``): an OpenType font XOR-scrambled with a key.

Layout: u32 magic (``0x18029A7F ^ key``), u32 big-endian size (``^ key``), then the OpenType file with
every 32-bit little-endian word XORed with the key (as Switch shared fonts are, see yuzu
``DecryptSharedFont``). Tears of the Kingdom keeps its fonts this way in ``Font/*.bfarc.zs``.

The editor model renders every mapped character with FreeType (PIL) at ``params["size"]`` pixels; the
advance widths come from ``hmtx`` at that size. A scalable font's outlines and metrics are not edited
here: packing an unedited model gives the original bytes, an edited one is refused with the reason.
"""
from __future__ import annotations

import io
import struct
from typing import Any, Dict, List, Tuple

from PIL import Image, ImageDraw, ImageFont

from core.font_formats import Metadata, Sheets, char_code, grey_sheet, map_entries

_MAGIC = 0x18029A7F
_COLUMNS = 32
DEFAULT_SIZE = 40


def is_bfotf(data: bytes) -> bool:
    """A scrambled font: the first word un-XORs to an OpenType or TrueType header with the derived key."""
    if len(data) < 16:
        return False
    key = struct.unpack_from("<I", data, 0)[0] ^ _MAGIC
    head = struct.unpack_from("<I", data, 8)[0] ^ key
    return struct.pack("<I", head) in (b"OTTO", b"\x00\x01\x00\x00", b"true")


def decrypt(data: bytes) -> Tuple[bytes, int]:
    """``(OpenType bytes, key)`` of a scrambled font."""
    if not is_bfotf(data):
        raise ValueError("Not a Switch scalable font (bfotf/bfttf)")
    key = struct.unpack_from("<I", data, 0)[0] ^ _MAGIC
    words = len(data) // 4
    plain = struct.pack(f"<{words}I", *(word ^ key for word in struct.unpack_from(f"<{words}I", data)))
    size = struct.unpack(">I", plain[4:8])[0]
    return plain[8:8 + size], key


def encrypt(font: bytes, key: int) -> bytes:
    """The scrambled file of an OpenType font (the inverse of ``decrypt``)."""
    body = font + b"\x00" * (-len(font) % 4)
    plain = struct.pack("<I", _MAGIC) + struct.pack(">I", len(font)) + body
    words = len(plain) // 4
    return struct.pack(f"<{words}I", *(word ^ key for word in struct.unpack_from(f"<{words}I", plain)))


class OpenType:
    """The tables of an OpenType font that the editor needs: character map, advances, metrics."""

    def __init__(self, font: bytes):
        self.data = font
        count = struct.unpack_from(">H", font, 4)[0]
        self.tables: Dict[str, Tuple[int, int]] = {}
        for index in range(count):
            tag, _checksum, offset, length = struct.unpack_from(">4sIII", font, 12 + 16 * index)
            self.tables[tag.decode("latin-1")] = (offset, length)
        self.units_per_em = struct.unpack_from(">H", font, self.table("head") + 18)[0]
        hhea = self.table("hhea")
        self.ascender, self.descender = struct.unpack_from(">hh", font, hhea + 4)
        self.long_metrics = struct.unpack_from(">H", font, hhea + 34)[0]
        self.glyph_count = struct.unpack_from(">H", font, self.table("maxp") + 4)[0]

    def table(self, tag: str) -> int:
        if tag not in self.tables:
            raise ValueError(f"The font has no {tag} table")
        return self.tables[tag][0]

    def advance(self, glyph: int) -> int:
        """The advance width of a glyph in font units."""
        index = min(glyph, self.long_metrics - 1)
        return struct.unpack_from(">H", self.data, self.table("hmtx") + 4 * index)[0]

    def cmap(self) -> Dict[int, int]:
        """``{code point: glyph}`` from the Unicode subtables (formats 4 and 12)."""
        base = self.table("cmap")
        data = self.data
        result: Dict[int, int] = {}
        for index in range(struct.unpack_from(">H", data, base + 2)[0]):
            platform, encoding, offset = struct.unpack_from(">HHI", data, base + 4 + 8 * index)
            if (platform, encoding) not in ((0, 3), (0, 4), (3, 1), (3, 10)):
                continue
            at = base + offset
            kind = struct.unpack_from(">H", data, at)[0]
            if kind == 4:
                result.update({c: g for c, g in _format4(data, at).items() if c not in result})
            elif kind == 12:
                for group in range(struct.unpack_from(">I", data, at + 12)[0]):
                    first, last, glyph = struct.unpack_from(">III", data, at + 16 + 12 * group)
                    for code in range(first, last + 1):
                        result.setdefault(code, glyph + code - first)
        return result


def _format4(data: bytes, at: int) -> Dict[int, int]:
    segments = struct.unpack_from(">H", data, at + 6)[0] // 2
    ends = struct.unpack_from(f">{segments}H", data, at + 14)
    starts = struct.unpack_from(f">{segments}H", data, at + 16 + 2 * segments)
    deltas = struct.unpack_from(f">{segments}h", data, at + 16 + 4 * segments)
    ranges_at = at + 16 + 6 * segments
    ranges = struct.unpack_from(f">{segments}H", data, ranges_at)
    result: Dict[int, int] = {}
    for index in range(segments):
        for code in range(starts[index], ends[index] + 1):
            if code == 0xFFFF:
                continue
            if ranges[index]:
                glyph = struct.unpack_from(">H", data, ranges_at + 2 * index + ranges[index]
                                           + 2 * (code - starts[index]))[0]
                glyph = (glyph + deltas[index]) & 0xFFFF if glyph else 0
            else:
                glyph = (code + deltas[index]) & 0xFFFF
            if glyph:
                result[code] = glyph
    return result


def widths(data: bytes, size: float) -> Dict[str, int]:
    """``{character: advance in pixels}`` of a scrambled font drawn at ``size`` pixels per em."""
    font = OpenType(decrypt(data)[0])
    scale = size / font.units_per_em
    return {chr(code): round(font.advance(glyph) * scale) for code, glyph in sorted(font.cmap().items())}


def extract(data: bytes, params: Dict[str, Any]) -> Tuple[Metadata, Sheets]:
    plain, _key = decrypt(data)
    font = OpenType(plain)
    size = int(params.get("size") or DEFAULT_SIZE)
    scale = size / font.units_per_em
    mapping = font.cmap()
    glyphs = sorted(set(mapping.values()))
    cell_of = {glyph: index for index, glyph in enumerate(glyphs)}
    ascent = round(font.ascender * scale)
    descent = round(-font.descender * scale)
    cell_w, cell_h = size + size // 4, ascent + descent + 2
    rows = max(1, min(_COLUMNS, -(-len(glyphs) // _COLUMNS)))
    per_sheet = _COLUMNS * rows
    sheet_count = max(1, -(-len(glyphs) // per_sheet))
    pil_font = ImageFont.truetype(io.BytesIO(plain), size)
    inks = [Image.new("L", (_COLUMNS * cell_w, rows * cell_h), 0) for _ in range(sheet_count)]
    drawn = set()
    for code, glyph in sorted(mapping.items()):
        if glyph in drawn:
            continue
        drawn.add(glyph)
        cell = cell_of[glyph]
        sheet, slot = divmod(cell, per_sheet)
        row, column = divmod(slot, _COLUMNS)
        ImageDraw.Draw(inks[sheet]).text((column * cell_w + 1, row * cell_h + 1), chr(code), fill=255, font=pil_font)
    packets = [{"kerning": 0, "width": round(font.advance(glyph) * scale)} for glyph in glyphs]
    pairs = [(char_code(chr(code)), cell_of[glyph]) for code, glyph in mapping.items()]
    metadata = {
        "header": {"signature": "BFOTF", "textures_editable": False, "outline": True,
                   "units_per_em": font.units_per_em, "glyph_ids": glyphs},
        "INF1": [{"encoding": 1, "ascent": ascent, "descent": descent, "width": size // 2, "leading": cell_h,
                  "fallback_code": 0x3F, "unk1": 0}],
        "GLY1": [{"start_glyph": 0, "end_glyph": len(glyphs) - 1, "cell_width": cell_w, "cell_height": cell_h,
                  "glyph_horizontal_count": _COLUMNS, "glyph_vertical_count": rows,
                  "texture_width": _COLUMNS * cell_w, "texture_height": rows * cell_h}],
        "MAP1": [map_entries(pairs)],
        "WID1": [{"first_code_included": 0, "last_code_included": len(glyphs), "packets": packets}],
    }
    return metadata, [grey_sheet(ink) for ink in inks]


def pack(metadata: Metadata, sheets: Sheets, original: bytes, params: Dict[str, Any]) -> bytes:
    """The original bytes; a changed width or drawn pixel is refused (outlines are not edited here)."""
    again, again_sheets = extract(original, params)
    if metadata.get("WID1") != again.get("WID1"):
        raise ValueError("The widths of a scalable (OpenType) font are its outlines' metrics and are not "
                         "edited here; edit the font in a font editor (FontForge) instead.")
    if [sheet.convert("RGBA").tobytes() for sheet in sheets] != [sheet.tobytes() for sheet in again_sheets]:
        raise ValueError("The glyphs of a scalable (OpenType) font are outlines and are not drawn here; edit "
                         "the font in a font editor (FontForge) instead.")
    return bytes(original)


def contact_sheet(data: bytes, size: int = 32, columns: int = 32, label: str = "") -> Image.Image:
    """Every mapped character of a font on one white image, for reports (black on white)."""
    metadata, sheets = extract(data, {"size": size})
    pieces: List[Image.Image] = []
    for sheet in sheets:
        pieces.append(Image.eval(sheet.split()[3], lambda value: 255 - value))
    width = max(piece.width for piece in pieces)
    out = Image.new("L", (width, sum(piece.height for piece in pieces) + (20 if label else 0)), 255)
    y = 0
    if label:
        ImageDraw.Draw(out).text((4, 4), label, fill=0)
        y = 20
    for piece in pieces:
        out.paste(piece, (0, y))
        y += piece.height
    return out
