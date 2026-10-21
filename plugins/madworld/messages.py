"""MadWorld message tables (MSD), glyph atlases (MTD), the text <-> words mapping and the containers around them.

A message table keeps each message as 16-bit words: 0x1000 + n is glyph n of its atlas, 0x8000 a new line, 0x8001 a
space, 0x8002 the end, and 0x8010 / 0x8073 / 0x8093 / 0x8095 / 0x8F00 / 0x8F01 take one argument word. The atlas next
to it has a texture rectangle and a size per glyph, and a C4 picture (IA8 palette) of just the glyphs the table uses.
Glyph characters come from the glyph pictures themselves (``glyph_labels.json``: a picture's key -> character and font).
"""
from __future__ import annotations

import hashlib
import json
import re
import struct
from pathlib import Path
from typing import Dict, List, Optional, Tuple

from . import gx

NEWLINE, SPACE, END = 0x8000, 0x8001, 0x8002
ARGS = (0x8010, 0x8073, 0x8093, 0x8095, 0x8F00, 0x8F01)
LABELS = Path(__file__).with_name("glyph_labels.json")
TAG = re.compile(r"<([0-9A-F]{4})(?::([0-9A-F]{4}))?>|<(?:G:|#)([0-9A-F]{4})>")


# ---------------------------------------------------------------- message tables (MSD)

def msd_parse(body: bytes) -> Tuple[int, List[Tuple[int, List[int]]]]:
    """``(flag, [(id, words)])``."""
    count, flag = struct.unpack_from(">II", body, 0)
    out = []
    for i in range(count):
        ident, off, size = struct.unpack_from(">III", body, 8 + 12 * i)
        out.append((ident, list(struct.unpack_from(f">{size // 2}H", body, off))))
    return flag, out


def msd_build(flag: int, msgs: List[Tuple[int, List[int]]], size: int = 0) -> bytes:
    """The table, padded with zeros to ``size`` when it is shorter."""
    head = bytearray(struct.pack(">II", len(msgs), flag)) + bytes(12 * len(msgs))
    data = bytearray()
    for i, (ident, words) in enumerate(msgs):
        struct.pack_into(">III", head, 8 + 12 * i, ident, len(head) + len(data), 2 * len(words))
        data += struct.pack(f">{len(words)}H", *words)
    out = bytes(head + data)
    return out + bytes(max(0, size - len(out)))


# ---------------------------------------------------------------- atlases (MTD)

def glyph_key(w: int, h: int, alpha: bytes) -> str:
    """A glyph picture's identity: its ink (alpha) cut to the ink box, with the cell height."""
    rows = [alpha[y * w:(y + 1) * w] for y in range(h)]
    ys = [y for y in range(h) if any(rows[y])]
    xs = [x for x in range(w) if any(r[x] for r in rows)]
    trim = b"".join(bytes(r[xs[0]:xs[-1] + 1]) for y, r in enumerate(rows) if ys and ys[0] <= y <= ys[-1]) if xs else b""
    return hashlib.md5(bytes((len(xs), len(ys), h)) + trim).hexdigest()[:10]


def mtd_parse(body: bytes) -> dict:
    """Records, sizes and pictures of an atlas; glyphs ``{index: (w, h, palette indices, adv, height, page)}``."""
    size, first, count = struct.unpack_from(">III", body, 0)
    recs = [struct.unpack_from(">HHffff", body, 12 + 20 * k) for k in range(count)]
    wcount, wa, wb = struct.unpack_from(">III", body, size)
    widths = {}
    for k in range(wcount):
        idx, _page, w, h = struct.unpack_from(">HHff", body, size + 12 + 12 * k)
        widths[idx] = (w, h)
    tpl_at = (size + 12 + 12 * wcount + 0xFFF) & ~0xFFF
    tpl = body[tpl_at:]
    pages = []
    n = struct.unpack_from(">I", tpl, 4)[0]
    for k in range(n):
        image, palette = struct.unpack_from(">II", tpl, 0xC + 8 * k)
        h, w, fmt, data_at = struct.unpack_from(">HHII", tpl, image)
        pn, _u, _p, pfmt, pal_at = struct.unpack_from(">HBBII", tpl, palette)
        if fmt != gx.C4 or pfmt != 0:
            raise ValueError(f"atlas: GX format {fmt} / palette {pfmt}, expected C4 with an IA8 palette")
        pages.append((w, h, gx.c4_decode(tpl[data_at:], w, h), tpl[pal_at:pal_at + 2 * pn]))
    glyphs = {}
    for idx, page, u0, v0, u1, v1 in recs:
        w, h, px, _pal = pages[page]
        x0, y0, x1, y1 = round(u0 * w), round(v0 * h), round(u1 * w), round(v1 * h)
        adv, height = widths.get(idx, (x1 - x0, y1 - y0))
        glyphs[idx] = (x1 - x0, y1 - y0, gx.crop(px, w, x0, y0, x1 - x0, y1 - y0), adv, height, page)
    return {"first": first, "glyphs": glyphs, "pages": pages, "whead": (wa, wb), "size": len(body)}


def alpha_of(glyph: tuple, palette: bytes) -> bytes:
    return bytes(palette[2 * i] for i in glyph[2])


def inten_of(glyph: tuple, palette: bytes) -> bytes:
    return bytes(palette[2 * i + 1] for i in glyph[2])


def quantize(alpha: bytes, inten: bytes, palette: bytes) -> bytes:
    """Palette indices of the nearest (alpha, intensity) entries of ``palette``."""
    pal = [(palette[2 * k], palette[2 * k + 1]) for k in range(len(palette) // 2)]
    cache: Dict[tuple, int] = {}
    out = bytearray()
    for a, i in zip(alpha, inten):
        if (a, i) not in cache:
            cache[(a, i)] = min(range(len(pal)), key=lambda k: (pal[k][0] - a) ** 2 + (pal[k][1] - i) ** 2)
        out.append(cache[(a, i)])
    return bytes(out)


def mtd_build(old: dict, glyphs: Dict[int, tuple]) -> bytes:
    """A one-picture atlas of ``glyphs`` {index: (w, h, palette indices, adv, height)} with the old palette."""
    w0, _h0, _px, palette = old["pages"][0]
    order = sorted(glyphs)
    sizes = [(glyphs[i][0], glyphs[i][1]) for i in order]
    width = max(w0, gx.pow2(max((w for w, _h in sizes), default=8) + 2))
    places, used = gx.pack(sizes, width, gap=2)
    height = gx.pow2(used + 2)
    px = bytearray(width * height)
    recs, wtab = bytearray(), bytearray()
    for i, (x, y) in zip(order, places):
        gw, gh, cell, adv, gheight = glyphs[i][:5]
        for r in range(gh):
            px[(y + r) * width + x:(y + r) * width + x + gw] = cell[r * gw:(r + 1) * gw]
        recs += struct.pack(">HHffff", i, 0, x / width, y / height, (x + gw) / width, (y + gh) / height)
        wtab += struct.pack(">HHff", i, 0, adv, gheight)
    table = struct.pack(">III", 12 + len(recs), old["first"], len(order)) + recs
    table += struct.pack(">III", len(order), *old["whead"]) + wtab
    table += bytes(-len(table) % 0x1000)
    tpl = gx.tpl(gx.C4, width, height, gx.c4_encode(px, width, height), palette=palette, pal_fmt=0)
    body = table + tpl
    body += bytes(-len(body) % 0x20)
    return body + bytes(max(0, old["size"] - len(body)))


# ---------------------------------------------------------------- text <-> words

def labels() -> Dict[str, list]:
    """``{glyph key: [character, font]}`` read once off the English atlases."""
    return json.loads(LABELS.read_text(encoding="utf-8")) if LABELS.is_file() else {}


def atlas_chars(atlas: dict, table: dict) -> Dict[int, Tuple[str, str]]:
    """``{index: (character, font)}`` of an atlas; glyphs without a label are left out."""
    palette = atlas["pages"][0][3]
    out = {}
    for idx, g in atlas["glyphs"].items():
        pal = atlas["pages"][g[5]][3] if g[5] < len(atlas["pages"]) else palette
        key = glyph_key(g[0], g[1], alpha_of(g, pal))
        if key in table:
            out[idx] = tuple(table[key])
    return out


def words_to_text(words: List[int], first: int, chars: Dict[int, tuple]) -> Tuple[str, bool]:
    """``(text, ends)``: the message as text (tags for the codes), and whether it ends with the end word."""
    ends = bool(words) and words[-1] == END
    if ends:
        words = words[:-1]
    out, k = [], 0
    while k < len(words):
        w = words[k]
        if w == NEWLINE:
            out.append("\n")
        elif w == SPACE:
            out.append(" ")
        elif w in ARGS and k + 1 < len(words):
            out.append(f"<{w:04X}:{words[k + 1]:04X}>")
            k += 1
        elif w >= 0x8000:
            out.append(f"<{w:04X}>")
        elif w < first:
            out.append(f"<#{w:04X}>")                 # an argument or number of a code before it
        elif w - first in chars:
            out.append(chars[w - first][0])
        else:
            out.append(f"<G:{w:04X}>")
        k += 1
    return "".join(out), ends


def text_to_words(text: str, ends: bool, glyph_of) -> List[int]:
    """Words of ``text``; ``glyph_of(char)`` gives the word of a character (it may add a glyph)."""
    out, pos = [], 0
    for m in list(TAG.finditer(text)) + [None]:
        plain = text[pos:m.start() if m else len(text)]
        for ch in plain:
            out.append(NEWLINE if ch == "\n" else SPACE if ch == " " else glyph_of(ch))
        if m:
            if m.group(3):
                out.append(int(m.group(3), 16))
            else:
                out.append(int(m.group(1), 16))
                if m.group(2):
                    out.append(int(m.group(2), 16))
            pos = m.end()
    return out + ([END] if ends else [])


# ---------------------------------------------------------------- containers

def idpac_sections(data: bytes) -> List[list]:
    """``[[tag, body]]`` of a stage package: a 0x20 header, then sections of tag, size, 0x18 zeros and body."""
    out, at = [], 0x20
    while at + 8 <= len(data):
        tag = data[at:at + 4]
        size = struct.unpack_from(">I", data, at + 4)[0]
        out.append([tag, data[at + 0x20:at + 0x20 + size]])
        at += 0x20 + size
    return out


def idpac_build(head: bytes, sections: List[list]) -> bytes:
    out = bytearray(head[:0x20])
    for tag, body in sections:
        out += tag + struct.pack(">I", len(body)) + bytes(0x18) + body
    return bytes(out)


def evnt_mess(data: bytes) -> Optional[dict]:
    """Where the message table and atlas of an event file are (the MESS chunk: MSD, MTD, more)."""
    at = 8
    while at + 8 <= len(data):
        tag, size = data[at:at + 4], struct.unpack_from(">I", data, at + 4)[0]
        if tag == b"MESS":
            inner, end, parts = at + 8, at + 8 + size, {}
            while inner + 8 <= end:
                t, s = data[inner:inner + 4], struct.unpack_from(">I", data, inner + 4)[0]
                parts[t] = (inner, s)
                inner += 8 + s
            if b"MSD " not in parts or b"MTD " not in parts:
                return None
            return {"mess": at, "end": end, "parts": parts}
        at += 8 + size
    return None


def _body(data: bytes, chunk: tuple) -> bytes:
    at, size = chunk
    start = (at + 8 + 0x1F) & ~0x1F
    return data[start:at + 8 + size]


def evnt_bodies(data: bytes) -> Tuple[bytes, bytes]:
    m = evnt_mess(data)
    return _body(data, m["parts"][b"MSD "]), _body(data, m["parts"][b"MTD "])


def evnt_build(data: bytes, msd: bytes, mtd: bytes) -> bytes:
    """``data`` (an event file) with a new message table and atlas; what follows the MESS chunk moves by a
    multiple of 0x20."""
    m = evnt_mess(data)
    msd_at, _ = m["parts"][b"MSD "]
    mtd_at, mtd_size = m["parts"][b"MTD "]
    rest = data[mtd_at + 8 + mtd_size:m["end"]]
    out = bytearray(data[:msd_at])
    for tag, body in ((b"MSD ", msd), (b"MTD ", mtd)):
        at = len(out)
        pad = ((at + 8 + 0x1F) & ~0x1F) - (at + 8)
        if tag == b"MTD ":                     # keep everything after MESS on its 0x20 alignment
            body += bytes(-(at + 8 + pad + len(body) + len(rest) - m["end"]) % 0x20)
        out += tag + struct.pack(">I", pad + len(body)) + bytes(pad) + body
    out += rest
    struct.pack_into(">I", out, m["mess"] + 4, len(out) - m["mess"] - 8)
    out += data[m["end"]:]
    struct.pack_into(">I", out, 4, len(out) - 8)
    return bytes(out)


# ---------------------------------------------------------------- the disc's English message units

def text_files(names: set) -> List[Tuple[str, str, Optional[str]]]:
    """``[(file, kind, atlas)]`` of the English message units: subtitles, missions and system messages."""
    out = []
    for rel in sorted(names):
        name = rel.rsplit("/", 1)[-1]
        if rel.startswith("subscr/") and name.endswith("_us.msd"):
            mtd = "subscr/" + name.replace("MessSubscr", "subscr").replace("Messnl", "nl")[:-4] + ".mtd"
            if mtd in names:
                out.append((rel, "msd", mtd))
        elif rel.startswith("event/") and name.endswith("_us.dat"):
            out.append((rel, "evnt", None))
        elif re.match(r"(case\w+|etc)/idpac_\w+_us\.dat$", rel):
            out.append((rel, "idpac", None))
    return out


def load_unit(read, rel: str, kind: str, mtd: Optional[str]):
    """``(raw parts, msd body, mtd body)`` of a text unit, or None when it has no messages.

    ``read(path)`` gives the bytes of a disc file.
    """
    data = read(rel)
    if kind == "msd":
        return (data, read(mtd)), data, read(mtd)
    if kind == "evnt":
        if data[:4] != b"EVNT" or evnt_mess(data) is None:
            return None
        msd, mtd_body = evnt_bodies(data)
        return (data,), msd, mtd_body
    tags = {t: b for t, b in idpac_sections(data)}
    if b"MSD\0" not in tags or b"MTD\0" not in tags:
        return None
    return (data,), tags[b"MSD\0"], tags[b"MTD\0"]


def save_unit(kind: str, raw: tuple, msd: bytes, mtd: bytes) -> List[Tuple[int, bytes]]:
    """``[(part index, new bytes)]``: index 0 is the unit's file, 1 the separate atlas file (kind msd)."""
    if kind == "msd":
        return [(0, msd), (1, mtd)]
    if kind == "evnt":
        return [(0, evnt_build(raw[0], msd, mtd))]
    secs = idpac_sections(raw[0])
    for sec in secs:
        if sec[0] == b"MSD\0":
            sec[1] = msd
        elif sec[0] == b"MTD\0":
            sec[1] = mtd
    return [(0, idpac_build(raw[0], secs))]


def ui_files(names: set) -> List[str]:
    """The disc files that hold 2D pictures with English text (TPL files or archives of TPLs)."""
    out = []
    for rel in sorted(names):
        name = rel.rsplit("/", 1)[-1]
        if rel.startswith("subscr/") and name.endswith("_us.idd"):
            out.append(rel)
        elif rel in ("etc/core_us.idd", "etc/core2_us.dat"):
            out.append(rel)
        elif re.match(r"(case\w+|etc)/idpac_\w+_us\.dat$", rel) or (rel.startswith("event/") and name.endswith("_us.dat")):
            out.append(rel)
        elif rel.startswith("banner/") or re.match(r"strap/strap_.*_eu\.tpl$", rel):
            out.append(rel)
    return out


def pictures(data: bytes) -> List[Tuple[int, int]]:
    """``[(offset, size)]`` of the TPL pictures in ``data``: the file itself, or each ``TEX\\0`` chunk's TPL."""
    size = gx.tpl_size(data)
    if size:
        return [(0, size)]
    out = []
    for m in re.finditer(rb"TEX\x00", data):
        at = m.start() + 0x10
        size = gx.tpl_size(data, at)
        if size:
            out.append((at, size))
    return out
