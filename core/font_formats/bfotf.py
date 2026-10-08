"""Nintendo Switch scalable fonts (``.bfotf`` / ``.bfttf``): an OpenType font XOR-scrambled with a key.

Layout: u32 magic (``0x18029A7F ^ key``), u32 big-endian size (``^ key``), then the OpenType file with
every 32-bit little-endian word XORed with the key (as Switch shared fonts are, see yuzu
``DecryptSharedFont``). Tears of the Kingdom keeps its fonts this way in ``Font/*.bfarc.zs``.

The editor model renders every mapped character with FreeType (PIL) at ``params["size"]`` pixels; the
advance widths come from ``hmtx`` at that size. Packing an unedited model gives the original bytes. A
changed width becomes the glyph's ``hmtx`` advance; a redrawn cell replaces the glyph's outline with its
ink traced as squares, one rectangle per run of pixels (``core.font_formats.cff`` rebuilds the font): CFF
charstrings in a .bfotf, a simple glyph in the ``glyf`` table of a TrueType .bfttf (Animal Crossing's text
font). A drawn glyph is as blocky as its pixels: a test mark or a draft letter, not a finished outline.
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
_INK = 128          # a drawn pixel at least this opaque is part of the new outline


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
        "header": {"signature": "BFOTF", "textures_editable": True, "units_per_em": font.units_per_em,
                   "glyph_ids": glyphs, "baseline": 1 + pil_font.getmetrics()[0]},
        "INF1": [{"encoding": 1, "ascent": ascent, "descent": descent, "width": size // 2, "leading": cell_h,
                  "fallback_code": 0x3F, "unk1": 0}],
        "GLY1": [{"start_glyph": 0, "end_glyph": len(glyphs) - 1, "cell_width": cell_w, "cell_height": cell_h,
                  "glyph_horizontal_count": _COLUMNS, "glyph_vertical_count": rows,
                  "texture_width": _COLUMNS * cell_w, "texture_height": rows * cell_h}],
        "MAP1": [map_entries(pairs)],
        "WID1": [{"first_code_included": 0, "last_code_included": len(glyphs), "packets": packets}],
    }
    return metadata, [grey_sheet(ink) for ink in inks]


def _cells(metadata: Metadata, sheets: Sheets):
    """``(cell index, box)`` of every glyph cell, sheet by sheet."""
    grid = metadata["GLY1"][0]
    cell_w, cell_h, rows = grid["cell_width"], grid["cell_height"], grid["glyph_vertical_count"]
    for cell in range(len(metadata["header"]["glyph_ids"])):
        sheet, slot = divmod(cell, _COLUMNS * rows)
        row, column = divmod(slot, _COLUMNS)
        yield cell, sheet, (column * cell_w, row * cell_h, (column + 1) * cell_w, (row + 1) * cell_h)


def _traced(ink: Image.Image, baseline: int, scale: float) -> List[list]:
    """Rectangle contours (font units, counter-clockwise) covering the ink of one cell; the pen starts at x = 1."""
    width, height = ink.size
    pixels = ink.load()
    open_runs: Dict[Tuple[int, int], int] = {}      # (x0, x1) -> first row
    boxes = []
    for y in range(height + 1):
        runs, x = set(), 0
        while y < height and x < width:
            if pixels[x, y] >= _INK:
                x0 = x
                while x < width and pixels[x, y] >= _INK:
                    x += 1
                runs.add((x0, x))
            x += 1
        for run in [r for r in open_runs if r not in runs]:
            boxes.append((run[0], open_runs.pop(run), run[1], y))
        for run in runs:
            open_runs.setdefault(run, y)

    def point(px: int, py: int):
        return round((px - 1) / scale), round((baseline - py) / scale)
    return [[("M", point(x0, y1)), ("L", point(x1, y1)), ("L", point(x1, y0)), ("L", point(x0, y0))]
            for x0, y0, x1, y1 in boxes]


def pack(metadata: Metadata, sheets: Sheets, original: bytes, params: Dict[str, Any]) -> bytes:
    """The original bytes when nothing changed; else the font with the changed widths and redrawn glyphs."""
    from core.font_formats import cff as cff_format, coverage
    again, again_sheets = extract(original, params)
    old_widths = [packet["width"] for packet in again["WID1"][0]["packets"]]
    new_widths = [packet["width"] for packet in metadata["WID1"][0]["packets"]]
    drawn = [sheet.convert("RGBA") for sheet in sheets]
    redrawn = [(cell, sheet, box) for cell, sheet, box in _cells(again, again_sheets)
               if sheet < len(drawn) and drawn[sheet].crop(box).tobytes() != again_sheets[sheet].crop(box).tobytes()]
    resized = [cell for cell, (old, new) in enumerate(zip(old_widths, new_widths)) if old != new]
    if not redrawn and not resized:
        return bytes(original)
    plain, key = decrypt(original)
    font = OpenType(plain)
    if "CFF " not in font.tables and "glyf" not in font.tables:
        raise ValueError("The font has neither CFF nor TrueType outlines")
    scale = int(params.get("size") or DEFAULT_SIZE) / font.units_per_em
    glyph_ids = again["header"]["glyph_ids"]
    cff = None
    if "CFF " in font.tables:
        at, length = font.tables["CFF "]
        cff = cff_format.Cff(plain[at:at + length])
    outlines = {}
    hmtx = font.table("hmtx")
    metrics = {}
    for cell in resized:
        glyph = glyph_ids[cell]
        long = font.long_metrics
        lsb_at = hmtx + 4 * glyph + 2 if glyph < long else hmtx + 4 * long + 2 * (glyph - long)
        metrics[glyph] = (round(new_widths[cell] / scale), struct.unpack_from(">h", plain, lsb_at)[0])
    baseline = again["header"]["baseline"]
    for cell, sheet, box in redrawn:
        glyph = glyph_ids[cell]
        contours = _traced(coverage(drawn[sheet].crop(box)), baseline, scale)
        advance = round(new_widths[cell] / scale)
        if cff is not None:
            cff.charstrings[glyph] = cff_format.charstring(advance, cff.widths_x(glyph), contours)
        outlines[glyph] = contours
        metrics[glyph] = (advance, min((p[1][0] for contour in contours for p in contour), default=0))
    replaced = _truetype_glyphs(plain, font, outlines) if cff is None else None
    return encrypt(cff_format.rebuild_font(plain, cff, font.cmap(), [], metrics, replaced), key)


def _simple_glyph(contours: List[list]) -> bytes:
    """A TrueType simple glyph of straight contours (points on the curve, clockwise)."""
    if not contours:
        return b""
    contours = [[point for _op, point in reversed(contour)] for contour in contours]
    points = [point for contour in contours for point in contour]
    xs, ys = [x for x, _y in points], [y for _x, y in points]
    out = bytearray(struct.pack(">h4h", len(contours), min(xs), min(ys), max(xs), max(ys)))
    end = -1
    for contour in contours:
        end += len(contour)
        out += struct.pack(">H", end)
    out += struct.pack(">H", 0) + b"\x01" * len(points)          # no instructions; every point on the curve
    for values in (xs, ys):
        last = 0
        for value in values:
            out += struct.pack(">h", value - last)
            last = value
    return bytes(out + b"\x00" * (-len(out) % 4))


def _truetype_glyphs(plain: bytes, font: "OpenType", outlines: Dict[int, List[list]]) -> Dict[str, bytes]:
    """New ``glyf`` / ``loca`` (long offsets), ``head`` and ``maxp`` with ``outlines`` replacing those glyphs."""
    head = bytearray(plain[font.table("head"):font.table("head") + font.tables["head"][1]])
    long_offsets = struct.unpack_from(">h", head, 50)[0] == 1
    loca_at, glyf_at = font.table("loca"), font.table("glyf")
    count = font.glyph_count
    starts = (struct.unpack_from(f">{count + 1}I", plain, loca_at) if long_offsets
              else [2 * v for v in struct.unpack_from(f">{count + 1}H", plain, loca_at)])
    glyf, offsets = bytearray(), []
    for glyph in range(count):
        offsets.append(len(glyf))
        data = (_simple_glyph(outlines[glyph]) if glyph in outlines
                else plain[glyf_at + starts[glyph]:glyf_at + starts[glyph + 1]])
        glyf += data + b"\x00" * (-len(data) % 4)
    offsets.append(len(glyf))
    struct.pack_into(">h", head, 50, 1)
    maxp = bytearray(plain[font.table("maxp"):font.table("maxp") + font.tables["maxp"][1]])
    if len(maxp) >= 10:
        points = max((sum(len(c) for c in contours) for contours in outlines.values()), default=0)
        struct.pack_into(">HH", maxp, 6, max(struct.unpack_from(">H", maxp, 6)[0], points),
                         max(struct.unpack_from(">H", maxp, 8)[0], max(map(len, outlines.values()), default=0)))
    return {"glyf": bytes(glyf), "loca": struct.pack(f">{count + 1}I", *offsets), "head": bytes(head),
            "maxp": bytes(maxp)}


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
