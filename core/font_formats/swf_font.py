"""Vector fonts of Flash / Scaleform movies (``DefineFont3`` in a ``.gfx`` / ``.swf`` file; Rayman Raving Rabbids
TV Party keeps its fonts in ``fonts_en`` and ``gfxfontlib``), shown in the bitmap font editor.

File: ``GFX`` / ``FWS`` (plain) or ``CFX`` / ``CWS`` (zlib after the 8-byte header), u32 length, frame RECT, frame
rate, frame count, then tags (u16 code << 6 | length, length 0x3F = u32 after). ``DefineFont3`` (75): u16 font id,
u8 flags (0x80 layout, 0x08 wide offsets, 0x04 wide codes), u8 language, the name, u16 glyph count, the offset
table (u16 / u32) and the code-table offset, one SHAPE per glyph (bit-packed records: style change = move,
straight and curved edges; units are 1/20480 of the em), the code table (u16 per glyph), then with layout
ascent, descent, leading, an s16 advance per glyph, a RECT of bounds per glyph and the kerning records.

``params``: ``font`` -- the font name (or id) when the movie has several. The model draws every glyph (even-odd
fill, curves flattened) into a cell of a 16-column grid, the baseline at the font's ascent; the width is the
glyph's advance. Packing replaces the shapes of the cells that changed: every row run of ink becomes a
rectangle (runs repeated on the next rows join into one), with the advance from the width and new bounds;
the other glyphs keep their bytes, so an unedited model packs to the original file. Glyphs cannot be added
(other movies place glyphs by index): a new letter is drawn over a glyph the text does not use.
"""
from __future__ import annotations

import struct
import zlib
from typing import Any, Dict, List, Tuple

from PIL import Image, ImageChops, ImageDraw

from core.font_formats import Metadata, Sheets, char_code, map_entries

ADDS_GLYPHS = False
COLUMNS = 16
EM = 20480.0
CELL_EM = 56          # model pixels per em


# ---------------------------------------------------------------- movie and tags

def _body(data: bytes) -> Tuple[bytes, bytes]:
    """``(8-byte header, uncompressed body)``."""
    if data[:3] in (b"GFX", b"FWS"):
        return bytes(data[:8]), bytes(data[8:])
    if data[:3] in (b"CFX", b"CWS"):
        return bytes(data[:8]), zlib.decompress(bytes(data[8:]))
    raise ValueError("Not a Flash / Scaleform movie")


def _tags(body: bytes) -> List[Tuple[int, int, int, int]]:
    """``[(code, tag start, data start, data end)]``."""
    at = (5 + 4 * (body[0] >> 3) + 7) // 8 + 4
    out = []
    while at < len(body):
        code = struct.unpack_from("<H", body, at)[0]
        kind, size, data = code >> 6, code & 0x3F, at + 2
        if size == 0x3F:
            size, data = struct.unpack_from("<I", body, at + 2)[0], at + 6
        out.append((kind, at, data, data + size))
        at = data + size
        if kind == 0:
            break
    return out


def fonts(data: bytes) -> List[Dict[str, Any]]:
    """Every DefineFont3 of a movie: id, name, glyph count."""
    _head, body = _body(data)
    out = []
    for kind, _t, a, _b in _tags(body):
        if kind == 75:
            font_id, _flags, _lang, length = struct.unpack_from("<HBBB", body, a)
            name = body[a + 5:a + 5 + length].split(b"\0")[0].decode("latin-1")
            out.append({"id": font_id, "name": name, "glyphs": struct.unpack_from("<H", body, a + 5 + length)[0]})
    return out


# ---------------------------------------------------------------- bits

class _Bits:
    def __init__(self, data: bytes, at: int = 0):
        self.data, self.pos = data, at * 8

    def u(self, n: int) -> int:
        value = 0
        for _ in range(n):
            value = (value << 1) | ((self.data[self.pos >> 3] >> (7 - (self.pos & 7))) & 1)
            self.pos += 1
        return value

    def s(self, n: int) -> int:
        value = self.u(n)
        return value - (1 << n) if n and value >> (n - 1) else value


class _Writer:
    def __init__(self):
        self.bits: List[int] = []

    def u(self, value: int, n: int) -> None:
        self.bits += [(value >> (n - 1 - i)) & 1 for i in range(n)]

    def s(self, value: int, n: int) -> None:
        self.u(value & ((1 << n) - 1), n)

    def bytes(self) -> bytes:
        bits = self.bits + [0] * (-len(self.bits) % 8)
        return bytes(int("".join(map(str, bits[i:i + 8])), 2) for i in range(0, len(bits), 8))


def _nbits(*values: int) -> int:
    """Signed bit count for all values."""
    return max([2] + [max(v, ~v).bit_length() + 1 for v in values])


def _rect(data: bytes, at: int) -> Tuple[Tuple[int, int, int, int], int]:
    bits = _Bits(data, at)
    n = bits.u(5)
    rect = (bits.s(n), bits.s(n), bits.s(n), bits.s(n))      # xmin, xmax, ymin, ymax
    return rect, (bits.pos + 7) // 8


def _rect_bytes(xmin: int, xmax: int, ymin: int, ymax: int) -> bytes:
    n = _nbits(xmin, xmax, ymin, ymax)
    w = _Writer()
    w.u(n, 5)
    for v in (xmin, xmax, ymin, ymax):
        w.s(v, n)
    return w.bytes()


# ---------------------------------------------------------------- DefineFont3

class _Font:
    def __init__(self, body: bytes, a: int, b: int):
        self.a, self.b = a, b
        d = body[a:b]
        self.raw = d
        self.flags = d[2]
        length = d[4]
        at = 5 + length
        self.head_end = at
        self.count = struct.unpack_from("<H", d, at)[0]
        at += 2
        self.wide = bool(self.flags & 0x08)
        fmt = "I" if self.wide else "H"
        self.table_at = at
        offsets = list(struct.unpack_from(f"<{self.count}{fmt}", d, at))
        code_off = struct.unpack_from("<" + fmt, d, at + self.count * (4 if self.wide else 2))[0]
        self.shapes = [d[at + o:at + e] for o, e in zip(offsets, offsets[1:] + [code_off])]
        self.codes = list(struct.unpack_from(f"<{self.count}H", d, at + code_off))
        self.layout = None
        tail = at + code_off + 2 * self.count
        if self.flags & 0x80:
            ascent, descent, leading = struct.unpack_from("<HHh", d, tail)
            p = tail + 6
            advances = list(struct.unpack_from(f"<{self.count}h", d, p))
            p += 2 * self.count
            bounds = []
            for _ in range(self.count):
                rect, p = _rect(d, p)
                bounds.append(rect)
            self.layout = {"ascent": ascent, "descent": descent, "leading": leading, "advances": advances,
                           "bounds": bounds, "rest": d[p:]}
        else:
            self.rest = d[tail:]

    def build(self) -> bytes:
        fmt = "I" if self.wide else "H"
        size = 4 if self.wide else 2
        offsets, pos = [], (self.count + 1) * size
        for shape in self.shapes:
            offsets.append(pos)
            pos += len(shape)
        out = bytearray(self.raw[:self.table_at])
        out += struct.pack(f"<{self.count}{fmt}", *offsets) + struct.pack("<" + fmt, pos)
        out += b"".join(self.shapes) + struct.pack(f"<{self.count}H", *self.codes)
        if self.layout:
            lay = self.layout
            out += struct.pack("<HHh", lay["ascent"], lay["descent"], lay["leading"])
            out += struct.pack(f"<{self.count}h", *lay["advances"])
            out += b"".join(_rect_bytes(*r) for r in lay["bounds"]) + lay["rest"]
        else:
            out += self.rest
        return bytes(out)


def _contours(shape: bytes) -> List[List[Tuple[float, float]]]:
    """Closed outlines of a glyph SHAPE (curves flattened), in font units."""
    bits = _Bits(shape)
    fill_bits, line_bits = bits.u(4), bits.u(4)
    x = y = 0
    paths: List[List[Tuple[float, float]]] = []
    current: List[Tuple[float, float]] = []
    while True:
        if bits.u(1) == 0:
            flags = bits.u(5)
            if flags == 0:
                break
            if flags & 1:
                n = bits.u(5)
                x, y = bits.s(n), bits.s(n)
                if current:
                    paths.append(current)
                current = [(x, y)]
            if flags & 2:
                bits.u(fill_bits)
            if flags & 4:
                bits.u(fill_bits)
            if flags & 8:
                bits.u(line_bits)
            if flags & 16:          # new styles: not used by font glyphs
                break
        elif bits.u(1) == 1:
            n = bits.u(4) + 2
            if bits.u(1):
                dx, dy = bits.s(n), bits.s(n)
            elif bits.u(1):
                dx, dy = 0, bits.s(n)
            else:
                dx, dy = bits.s(n), 0
            x, y = x + dx, y + dy
            current.append((x, y))
        else:
            n = bits.u(4) + 2
            cx, cy = x + bits.s(n), y + bits.s(n)
            ax, ay = cx + bits.s(n), cy + bits.s(n)
            for t in (0.25, 0.5, 0.75, 1.0):
                u = 1 - t
                current.append((u * u * x + 2 * u * t * cx + t * t * ax, u * u * y + 2 * u * t * cy + t * t * ay))
            x, y = ax, ay
    if current:
        paths.append(current)
    return [p for p in paths if len(p) > 2]


def _rectangles_shape(rects: List[Tuple[int, int, int, int]]) -> bytes:
    """A glyph SHAPE of rectangles (x0, y0, x1, y1 in font units): clockwise, fill style 1."""
    w = _Writer()
    w.u(1, 4)
    w.u(0, 4)
    for x0, y0, x1, y1 in rects:
        w.u(0, 1)
        w.u(0b00101, 5)                  # fill style 1 + move to
        n = _nbits(x0, y0)
        w.u(n, 5)
        w.s(x0, n)
        w.s(y0, n)
        w.u(1, 1)
        for dx, dy in ((x1 - x0, 0), (0, y1 - y0), (x0 - x1, 0), (0, y0 - y1)):
            w.u(1, 1)
            w.u(1, 1)
            n = _nbits(dx, dy)
            w.u(n - 2, 4)
            w.u(0, 1)                    # not general: vertical or horizontal
            w.u(1 if dx == 0 else 0, 1)
            w.s(dy if dx == 0 else dx, n)
    w.u(0, 6)                            # end of shape
    return w.bytes()


# ---------------------------------------------------------------- the model

def _pick(body: bytes, params: Dict[str, Any]) -> _Font:
    wanted = params.get("font")
    found = [(a, b) for kind, _t, a, b in _tags(body) if kind == 75]
    if not found:
        raise ValueError("The movie has no DefineFont3 font")
    for a, b in found:
        font_id, _f, _l, length = struct.unpack_from("<HBBB", body, a)
        name = body[a + 5:a + 5 + length].split(b"\0")[0].decode("latin-1")
        if wanted in (None, name, font_id, str(font_id)):
            return _Font(body, a, b)
    raise ValueError(f"The movie has no font {wanted!r}")


def _geometry(font: _Font) -> Tuple[float, int, int, int]:
    """``(pixels per unit, ascent px, cell width, cell height)``."""
    scale = CELL_EM / EM
    lay = font.layout or {"ascent": int(EM * 0.8), "descent": int(EM * 0.2), "advances": [int(EM)] * font.count}
    ascent = int(round(lay["ascent"] * scale))
    height = ascent + int(round(lay["descent"] * scale)) + 2
    width = max([int(a * scale) + 2 for a in lay["advances"]] + [CELL_EM // 2])
    if font.layout:
        width = max([width] + [int(r[1] * scale) + 2 for r in font.layout["bounds"]])
    return scale, ascent, min(width, CELL_EM * 2), height


def _draw(font: _Font, index: int, scale: float, ascent: int, size: Tuple[int, int]) -> Image.Image:
    mask = Image.new("1", size, 0)
    for contour in _contours(font.shapes[index]):
        layer = Image.new("1", size, 0)
        ImageDraw.Draw(layer).polygon([(x * scale, y * scale + ascent) for x, y in contour], fill=1)
        mask = ImageChops.logical_xor(mask, layer)
    cell = Image.new("RGBA", size, (255, 255, 255, 0))
    cell.putalpha(mask.convert("L"))
    return cell


def extract(data: bytes, params: Dict[str, Any]) -> Tuple[Metadata, Sheets]:
    _head, body = _body(data)
    font = _pick(body, params)
    scale, ascent, cell_w, cell_h = _geometry(font)
    rows = max(1, -(-font.count // COLUMNS))
    sheet = Image.new("RGBA", (COLUMNS * cell_w, rows * cell_h))
    for i in range(font.count):
        sheet.alpha_composite(_draw(font, i, scale, ascent, (cell_w, cell_h)),
                              ((i % COLUMNS) * cell_w, (i // COLUMNS) * cell_h))
    advances = (font.layout or {}).get("advances") or [int(EM / 2)] * font.count
    packets = [{"kerning": 0, "width": max(1, int(round(a * scale)))} for a in advances]
    metadata = {
        "header": {"signature": "DefineFont3", "num_chunks": 4},
        "INF1": [{"encoding": 1, "ascent": ascent, "descent": cell_h - ascent, "width": packets[0]["width"],
                  "leading": cell_h, "fallback_code": 0x3F, "unk1": 0}],
        "GLY1": [{"start_glyph": 0, "end_glyph": rows * COLUMNS - 1, "cell_width": cell_w, "cell_height": cell_h,
                  "glyph_horizontal_count": COLUMNS, "glyph_vertical_count": rows,
                  "texture_width": sheet.width, "texture_height": sheet.height}],
        "MAP1": [map_entries([(char_code(chr(c)), i) for i, c in enumerate(font.codes)])],
        "WID1": [{"first_code_included": 0, "last_code_included": font.count, "packets": packets}],
    }
    return metadata, [sheet]


def _runs(cell: Image.Image, scale: float, ascent: int) -> List[Tuple[int, int, int, int]]:
    """Ink of a cell as rectangles in font units (row runs; equal runs on following rows joined)."""
    alpha = cell.getchannel("A").point(lambda v: 255 if v >= 128 else 0)
    width, height = cell.size
    px = alpha.load()
    open_runs: Dict[Tuple[int, int], int] = {}
    rects = []
    for y in range(height + 1):
        runs, x = set(), 0
        while y < height and x < width:
            if px[x, y]:
                start = x
                while x < width and px[x, y]:
                    x += 1
                runs.add((start, x))
            x += 1
        for run in list(open_runs):
            if run not in runs:
                rects.append((run[0], open_runs.pop(run), run[1], y))
        for run in runs:
            open_runs.setdefault(run, y)
    to_units = lambda v: int(round(v / scale))          # noqa: E731 - one formula, two axes
    return [(to_units(x0), to_units(y0 - ascent), to_units(x1), to_units(y1 - ascent)) for x0, y0, x1, y1 in rects]


def pack(metadata: Metadata, sheets: Sheets, original: bytes, params: Dict[str, Any]) -> bytes:
    head, body = _body(original)
    font = _pick(body, params)
    scale, ascent, cell_w, cell_h = _geometry(font)
    packets = (metadata.get("WID1") or [{}])[0].get("packets", [])
    sheet = sheets[0].convert("RGBA") if sheets else None
    changed = False
    for i in range(font.count):
        x, y = (i % COLUMNS) * cell_w, (i // COLUMNS) * cell_h
        if sheet is not None and y + cell_h <= sheet.height:
            cell = sheet.crop((x, y, x + cell_w, y + cell_h))
            if cell.getchannel("A").tobytes() != _draw(font, i, scale, ascent, (cell_w, cell_h)).getchannel("A").tobytes():
                rects = _runs(cell, scale, ascent)
                font.shapes[i] = _rectangles_shape(rects)
                if font.layout:
                    xs = [r[0] for r in rects] + [r[2] for r in rects] or [0]
                    ys = [r[1] for r in rects] + [r[3] for r in rects] or [0]
                    font.layout["bounds"][i] = (min(xs), max(xs), min(ys), max(ys))
                changed = True
        if font.layout and i < len(packets):
            width = int(packets[i]["width"])
            if width != max(1, int(round(font.layout["advances"][i] * scale))):
                font.layout["advances"][i] = max(-32768, min(32767, int(round(width / scale))))
                changed = True
    if not changed:
        return bytes(original)
    new_tag = font.build()
    tag_start = next(t for kind, t, a, _b in _tags(body) if a == font.a)
    new_body = body[:tag_start] + struct.pack("<HI", (75 << 6) | 0x3F, len(new_tag)) + new_tag + body[font.b:]
    head = head[:4] + struct.pack("<I", len(new_body) + 8)
    if head[:3] in (b"CFX", b"CWS"):
        return head + zlib.compress(new_body, 9)
    return head + new_body
