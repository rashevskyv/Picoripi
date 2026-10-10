"""Static captions inside the Flash / Scaleform movies of Rayman Raving Rabbids TV Party (``.gfx`` files of the
workspace): ``DefineText`` tags (11, 33) whose glyphs come from a font the movie embeds (``DefineFont3``), such as
"NEXT", "OK", "WARNING!" of the minigame intros. The runtime texts (``DefineEditText`` fields) come from
``TextPackages.bin`` and are not here; the movies hold no bitmap pictures (every shape is vector).

A text record: flags (0x08 font id + height, 0x04 colour, 0x02 y, 0x01 x), the fields, u8 glyph count and the
glyphs as (index, advance) bit pairs of the tag's glyph / advance bit widths. The text is the glyph indices
through the font's code table; a saved text is encoded back through the same table (a letter the font lacks
raises ``ValueError``), each glyph advancing by the font's advance scaled to the record's height, and the tag's
bit widths are recomputed. A record that reads back unchanged keeps its bytes. One-glyph records (the
exporter's glyph embedding) are left out.
"""
from __future__ import annotations

import struct
from typing import Dict, List, Tuple

from core.font_formats import swf_font
from core.font_formats.swf_font import _Bits, _Writer, _body, _nbits, _tags, _Font


def is_gfx(raw: bytes) -> bool:
    return bytes(raw[:3]) in (b"GFX", b"CFX", b"FWS", b"CWS")


def _fonts(body: bytes, tags) -> Dict[int, _Font]:
    return {struct.unpack_from("<H", body, a)[0]: _Font(body, a, b) for kind, _t, a, b in tags if kind == 75}


def _skip_rect(body: bytes, at: int) -> int:
    bits = _Bits(body, at)
    n = bits.u(5)
    bits.pos += 4 * n
    return (bits.pos + 7) // 8


def _skip_matrix(body: bytes, at: int) -> int:
    bits = _Bits(body, at)
    for _ in range(2):
        if bits.u(1):
            n = bits.u(5)
            bits.pos += 2 * n
    n = bits.u(5)
    bits.pos += 2 * n
    return (bits.pos + 7) // 8


def _records(body: bytes, kind: int, a: int, b: int) -> Tuple[int, List[dict]]:
    """``(offset of the glyph-bits byte, records)`` of a DefineText tag at ``a``..``b``."""
    at = _skip_matrix(body, _skip_rect(body, a + 2))
    head = at
    gbits, abits = body[at], body[at + 1]
    at += 2
    out, font, height = [], None, 0
    while at < b:
        flags = body[at]
        if flags == 0:
            break
        start = at
        at += 1
        if flags & 8:
            font = struct.unpack_from("<H", body, at)[0]
            at += 2
        if flags & 4:
            at += 4 if kind == 33 else 3
        at += (2 if flags & 1 else 0) + (2 if flags & 2 else 0)
        if flags & 8:
            height = struct.unpack_from("<H", body, at)[0]
            at += 2
        count_at = at
        count = body[at]
        at += 1
        bits = _Bits(body, at)
        glyphs = [(bits.u(gbits), bits.s(abits)) for _ in range(count)]
        at = (bits.pos + 7) // 8
        out.append({"fields": body[start + 1:count_at], "flags": flags, "font": font, "height": height,
                    "glyphs": glyphs})
    return head, out


def texts(raw: bytes) -> List[Tuple[int, int, str]]:
    """``[(tag index, record index, text)]`` of the captions whose font the movie embeds (two glyphs or more)."""
    body = _body(raw)[1]
    tags = _tags(body)
    fonts = _fonts(body, tags)
    out = []
    for i, (kind, _t, a, b) in enumerate(tags):
        if kind not in (11, 33):
            continue
        for j, rec in enumerate(_records(body, kind, a, b)[1]):
            font = fonts.get(rec["font"])
            if font is None or len(rec["glyphs"]) < 2:
                continue
            out.append((i, j, "".join(chr(font.codes[g]) if g < len(font.codes) else "�" for g, _adv in rec["glyphs"])))
    return out


def build(raw: bytes, new: Dict[Tuple[int, int], str]) -> bytes:
    """``raw`` with the captions ``{(tag index, record index): text}`` replaced."""
    head8, body = _body(raw)
    tags = _tags(body)
    fonts = _fonts(body, tags)
    pieces = []
    for i, (kind, t, a, b) in enumerate(tags):
        wanted = {j: s for (ti, j), s in new.items() if ti == i}
        if kind not in (11, 33) or not wanted:
            continue
        glyph_at, recs = _records(body, kind, a, b)
        changed = False
        for j, text in wanted.items():
            rec = recs[j]
            font = fonts[rec["font"]]
            if text == "".join(chr(font.codes[g]) if g < len(font.codes) else "�" for g, _adv in rec["glyphs"]):
                continue
            codes = {c: g for g, c in reversed(list(enumerate(font.codes)))}
            missing = [ch for ch in text if ord(ch) not in codes and ch != " "]
            if missing:
                raise ValueError(f"the movie's font has no glyph for {''.join(sorted(set(missing)))!r}")
            advances = (font.layout or {}).get("advances") or [swf_font.EM // 2] * font.count
            scale = rec["height"] / swf_font.EM * 20          # font units -> twips at this height
            glyphs: List[Tuple[int, int]] = []
            for ch in text:
                if ch == " " and ord(ch) not in codes:          # a space the font lacks: a gap after the last glyph
                    if glyphs:
                        glyphs[-1] = (glyphs[-1][0], glyphs[-1][1] + int(round(rec["height"] * 0.3)))
                    continue
                g = codes[ord(ch)]
                glyphs.append((g, int(round(advances[g] * scale))))
            rec["glyphs"] = glyphs
            changed = True
        if not changed:
            continue
        gbits = max(1, max((g.bit_length() for r in recs for g, _a in r["glyphs"]), default=1))
        abits = max(2, max((_nbits(adv) for r in recs for _g, adv in r["glyphs"]), default=2))
        out = bytearray(body[a:glyph_at]) + bytes((gbits, abits))
        for r in recs:
            out += bytes((r["flags"],)) + r["fields"] + bytes((len(r["glyphs"]),))
            w = _Writer()
            for g, adv in r["glyphs"]:
                w.u(g, gbits)
                w.s(adv, abits)
            out += w.bytes()
        out += b"\0"
        header = struct.pack("<H", (kind << 6) | len(out)) if a - t == 2 and len(out) < 0x3F else \
            struct.pack("<HI", (kind << 6) | 0x3F, len(out))
        pieces.append((t, b, header + bytes(out)))
    if not pieces:
        return bytes(raw)
    new_body, last = bytearray(), 0
    for t, b, data in sorted(pieces):
        new_body += body[last:t] + data
        last = b
    new_body += body[last:]
    head = head8[:4] + struct.pack("<I", len(new_body) + 8)
    import zlib
    return head + (zlib.compress(bytes(new_body), 9) if head[:3] in (b"CFX", b"CWS") else bytes(new_body))
