"""No More Heroes file formats: the game's LZ, RMHG resource trees, GDLG text boxes, the Shift-JIS text codec with the
Ukrainian letters, STRIMAGE glyph atlases and the DX archive ``Global\\Global.bin``.

The game keeps everything in RMHG trees (little endian: count, entries of offset/size/kind; a child starts 0x20
aligned, a container ends 0x20 aligned). A text box is a GDLG chunk: dialogs -> pages -> lines, each line an index
into a string table XOR 0x8D (Shift-JIS; Latin letters are one byte). Next to each GDLG an STRIMAGE chunk holds an I4
picture of the glyphs that box uses, with a record per character code.
"""
from __future__ import annotations

import collections
import re
import struct

from core.i18n import tr

from . import gx

ALIGN = 0x20
KEY = 0x8D
UKR = {"Ґ": 0x8492, "Є": 0x8493, "І": 0x8494, "Ї": 0x8495, "ґ": 0x8496, "є": 0x8497, "і": 0x8498, "ї": 0x8499}
UKR_CODES = {v: k for k, v in UKR.items()}
UKR_LETTERS = "АБВГҐДЕЄЖЗИІЇЙКЛМНОПРСТУФХЦЧШЩЬЮЯабвгґдеєжзиіїйклмнопрстуфхцчшщьюя"
TAG = re.compile(r"<\$([0-9A-F]{4})>")


# ---------------------------------------------------------------- the game's LZ

def is_packed(data: bytes) -> bool:
    return len(data) > 9 and struct.unpack_from("<I", data, 4)[0] == len(data)


def lz_decode(src: bytes) -> bytes:
    size, end = struct.unpack_from("<II", src, 0)
    m = src[8]
    out = bytearray()
    pos = 9
    while pos < end:
        b = src[pos]
        if b != m:
            out.append(b)
            pos += 1
            continue
        c = src[pos + 1]
        pos += 2
        if c == m:
            out.append(m)
            continue
        if c > m:
            c -= 1
        length = c >> 3
        if c & 4:
            length |= src[pos] << 5
            pos += 1
        dist = src[pos]
        pos += 1
        if c & 3:
            dist |= src[pos] << 8
            pos += 1
            if c & 3 == 2:
                dist |= src[pos] << 16
                pos += 1
        length += 4
        start = len(out) - dist - 1
        if dist + 1 >= length:
            out += out[start:start + length]
        else:
            for k in range(length):
                out.append(out[start + k])
    if len(out) != size:
        raise ValueError(tr("the game's LZ gives {0} bytes, not {1}", len(out), size))
    return bytes(out)


def lz_encode(data: bytes) -> bytes:
    """Greedy LZ the game reads: matches of 4..8195 bytes up to 16 MiB back (one hash candidate per position)."""
    counts = collections.Counter(data)
    m = min(range(256), key=lambda b: counts.get(b, 0))
    out = bytearray(struct.pack("<II", len(data), 0)) + bytes([m])
    last: dict = {}
    n, pos = len(data), 0
    while pos < n:
        best = 0
        if pos + 4 <= n:
            key = data[pos:pos + 4]
            cand = last.get(key)
            last[key] = pos
            if cand is not None and pos - cand <= 0x1000000:
                limit = min(n - pos, 8195)
                best = 4
                while best < limit and data[cand + best] == data[pos + best]:
                    best += 1
                dist = pos - cand - 1
        if best >= 4:
            length = best - 4
            nbytes = 0 if dist < 0x100 else 1 if dist < 0x10000 else 2
            c = (length & 31) << 3 | (4 if length > 31 else 0) | nbytes
            out += bytes((m, c + 1 if c >= m else c))
            if length > 31:
                out.append(length >> 5)
            out += dist.to_bytes(3, "little")[:nbytes + 1]
            for p in range(pos + 1, min(pos + best, n - 3), 3):
                last[data[p:p + 4]] = p
            pos += best
        else:
            b = data[pos]
            out += bytes((m, m)) if b == m else bytes((b,))
            pos += 1
    struct.pack_into("<I", out, 4, len(out))
    return bytes(out)


def load_game_file(raw: bytes) -> tuple:
    """``(packed, tree, trailer)`` of a disc file, or ``(packed, None, data)`` for a file that is not an RMHG tree."""
    packed = is_packed(raw)
    data = lz_decode(raw) if packed else raw
    if data[:4] != b"RMHG":
        return packed, None, data
    tree, trailer = rmhg_file(data)
    return packed, tree, trailer


# ---------------------------------------------------------------- RMHG trees

def rmhg_parse(data: bytes, base: int = 0) -> list:
    """``[header, [[entry, child], ...]]``; a child is a node (container), an embedded RSL file
    (``{"tree", "trailer"}``: a chunk that is a whole RMHG file of its own), bytes (a chunk) or None (empty)."""
    count, hsize = struct.unpack_from("<II", data, base + 4)
    ents = []
    for i in range(count):
        e = data[base + hsize + 0x20 * i:base + hsize + 0x20 * (i + 1)]
        off, size, kind = struct.unpack_from("<III", e)
        child = None
        if size:
            blob = data[base + off:base + off + size]
            if blob[:4] == b"RMHG" and kind == 1:
                child = rmhg_parse(data, base + off)
            elif blob[:4] == b"RMHG" and 0x20 <= struct.unpack_from("<I", blob, 0x10)[0] <= len(blob):
                tree, trailer = rmhg_file(blob)
                child = {"tree": tree, "trailer": trailer} if rmhg_save(tree, trailer) == blob else blob
            else:
                child = blob
        ents.append([e, child])
    return [data[base:base + hsize], ents]


def rmhg_build(node: list) -> bytes:
    head, ents = node
    out = bytearray(head) + bytes(0x20 * len(ents))
    for i, (e, child) in enumerate(ents):
        e = bytearray(e)
        if child is not None:
            blob = rmhg_build(child) if isinstance(child, list) else \
                rmhg_save(child["tree"], child["trailer"]) if isinstance(child, dict) else child
            out += bytes(-len(out) % ALIGN)
            struct.pack_into("<II", e, 0, len(out), len(blob))
            out += blob
        out[len(head) + 0x20 * i:len(head) + 0x20 * (i + 1)] = e
    out += bytes(-len(out) % ALIGN)
    return bytes(out)


def rmhg_file(data: bytes) -> tuple:
    """``(tree, trailer)`` of a whole (unpacked) RSL file."""
    total = struct.unpack_from("<I", data, 0x10)[0]
    return rmhg_parse(data[:total]), data[total:]


def rmhg_save(tree: list, trailer: bytes) -> bytes:
    out = bytearray(rmhg_build(tree))
    struct.pack_into("<I", out, 0x10, len(out))
    return bytes(out) + trailer


def _node(child):
    return child["tree"] if isinstance(child, dict) else child


def leaves(node: list, path: str = ""):
    """``(path, chunk)`` of every chunk, depth first (path like ``/2/1/0``)."""
    for i, (_e, child) in enumerate(node[1]):
        if isinstance(child, (list, dict)):
            yield from leaves(_node(child), f"{path}/{i}")
        elif child is not None:
            yield f"{path}/{i}", child


def get(node: list, path: str) -> bytes:
    for part in path.strip("/").split("/"):
        node = _node(node)[1][int(part)][1]
    return node


def put(node: list, path: str, blob: bytes) -> None:
    parts = [int(p) for p in path.strip("/").split("/")]
    for part in parts[:-1]:
        node = _node(node[1][part][1])
    node[1][parts[-1]][1] = blob


# ---------------------------------------------------------------- GDLG text boxes and the text codec

def gdlg_strings(blob: bytes) -> list:
    count = struct.unpack_from("<H", blob, 0xA)[0]
    area, table = struct.unpack_from("<II", blob, 0x14)
    raw = bytes(b ^ KEY for b in blob[area:])
    out = []
    for off in struct.unpack_from(f"<{count}I", blob, table):
        out.append(raw[off:raw.index(0, off)] if 0 in raw[off:] else raw[off:])
    return out


def gdlg_lines(blob: bytes) -> list:
    """Indices of the strings the boxes show (page lines), in order, each once."""
    dialogs = struct.unpack_from("<H", blob, 8)[0]
    count = struct.unpack_from("<H", blob, 0xA)[0]
    section, table = struct.unpack_from("<II", blob, 0xC)
    seen: list = []
    for off in struct.unpack_from(f"<{dialogs}I", blob, table):
        at = section + off
        pages = struct.unpack_from("<I", blob, at + 4)[0]
        for poff in struct.unpack_from(f"<{pages}I", blob, at + 0x20):
            page = at + poff
            lines = struct.unpack_from("<H", blob, page + 2)[0]
            for loff in struct.unpack_from(f"<{lines}I", blob, page + 0x20):
                idx = struct.unpack_from("<I", blob, page + loff)[0]
                if idx < count and idx not in seen:
                    seen.append(idx)
    return seen


def gdlg_with(blob: bytes, strings: list) -> bytes:
    """``blob`` with its string table set to ``strings`` (bytes each; the same count)."""
    area, table = struct.unpack_from("<II", blob, 0x14)
    out = bytearray(blob[:area])
    pool = bytearray()
    for i, s in enumerate(strings):
        struct.pack_into("<I", out, table + 4 * i, len(pool))
        pool += s + b"\0"
    old = gdlg_strings(blob)
    used = area + sum(len(s) + 1 for s in old)
    filler = blob[-1:] if len(blob) > used else bytes((KEY,))       # the padding as the original tool wrote it
    return bytes(out) + bytes(b ^ KEY for b in pool) + filler * (-(area + len(pool)) % 0x10)


def decode_text(raw: bytes) -> str:
    out, i = [], 0
    while i < len(raw):
        b = raw[i]
        if b < 0x80 or 0xA0 <= b < 0xE0:
            out.append(chr(b) if b < 0x80 else raw[i:i + 1].decode("cp932", "replace"))
            i += 1
            continue
        code = int.from_bytes(raw[i:i + 2], "big")
        if code in UKR_CODES:
            out.append(UKR_CODES[code])
        else:
            try:
                out.append(raw[i:i + 2].decode("cp932"))
            except UnicodeDecodeError:
                out.append(f"<${code:04X}>")
        i += 2
    return "".join(out)


def encode_text(text: str, missing: set | None = None) -> bytes:
    out = bytearray()
    pos = 0
    for m in TAG.finditer(text):
        out += _encode_plain(text[pos:m.start()], missing)
        out += int(m.group(1), 16).to_bytes(2, "big")
        pos = m.end()
    return bytes(out + _encode_plain(text[pos:], missing))


def _encode_plain(text: str, missing) -> bytes:
    out = bytearray()
    for ch in text.replace("ʼ", "'"):
        if ch in UKR:
            out += UKR[ch].to_bytes(2, "big")
            continue
        try:
            out += ch.encode("cp932")
        except UnicodeEncodeError:
            if missing is not None:
                missing.add(ch)
            out += b"?"
    return bytes(out)


def codes_of(raw: bytes) -> list:
    out, i = [], 0
    while i < len(raw):
        b = raw[i]
        if b < 0x80 or 0xA0 <= b < 0xE0:
            out.append(b)
            i += 1
        else:
            out.append(int.from_bytes(raw[i:i + 2], "big"))
            i += 2
    return out


def code_char(code: int) -> str:
    if code < 0x100:
        return chr(code) if code < 0x80 else bytes([code]).decode("cp932", "replace")
    if code in UKR_CODES:
        return UKR_CODES[code]
    try:
        return code.to_bytes(2, "big").decode("cp932")
    except UnicodeDecodeError:
        return "�"


def char_code(ch: str) -> int:
    if ch in UKR:
        return UKR[ch]
    return int.from_bytes(ch.encode("cp932"), "big")


# ---------------------------------------------------------------- STRIMAGE glyph atlases

def stri_parse(blob: bytes) -> dict | None:
    """The glyph records and I4 picture of an STRIMAGE chunk; None for the kinds the build never rewrites."""
    v2 = blob[:8] == b"STRIMAG2"
    count = struct.unpack_from(">I", blob, 0x18)[0]
    mode = struct.unpack_from(">H", blob, 0x1C)[0]
    rec = 0xA0 if v2 else 0x20
    gct = (rec + 20 * count + 0x1F) & ~0x1F
    if mode or blob[gct:gct + 4] != b"GCT0" or struct.unpack_from(">I", blob, gct + 4)[0] != gx.I4:
        return None
    w, h = struct.unpack_from(">HH", blob, gct + 8)
    data_at = gct + struct.unpack_from(">I", blob, gct + 0x10)[0]
    px = gx.i4_decode(blob[data_at:], w, h)
    glyphs = {}
    for k in range(count):
        code, x, y, gw, gh, bx, by, adv = struct.unpack_from(">HHHHHhhH", blob, rec + 20 * k)
        cell = gx.crop(px, w, x, y, gw, gh) if gw and gh and x + gw <= w and y + gh <= h else b""
        glyphs[code] = (gw, gh, bx, by, adv, cell)
    return {"v2": v2, "size": struct.unpack_from(">I", blob, 0xC)[0],
            "font": blob[0x20:0x40].split(b"\0")[0].decode("cp932", "replace") if v2 else "",
            "rec": rec, "gct": gct, "width": w, "height": h, "glyphs": glyphs}


def stri_build(blob: bytes, glyphs: dict) -> bytes:
    """``blob`` (an STRIMAGE) with a new picture and records for ``glyphs`` {code: (w, h, bx, by, adv, pixels)}."""
    old = stri_parse(blob)
    codes = list(glyphs)
    width = old["width"]
    sizes = [(glyphs[c][0], glyphs[c][1]) for c in codes]
    width = max(width, gx.pow2(max((w for w, _h in sizes), default=8)))
    places, used = gx.pack(sizes, width)
    height = max(8, gx.pow2(used))
    px = bytearray(width * height)
    recs = bytearray()
    for code, (x, y) in zip(codes, places):
        gw, gh, bx, by, adv, cell = glyphs[code]
        for r in range(gh):
            px[(y + r) * width + x:(y + r) * width + x + gw] = cell[r * gw:(r + 1) * gw]
        recs += struct.pack(">HHHHHhhH", code, x, y, gw, gh, bx, by, adv) + b"\x01\x00" + struct.pack("<H", code)
    head = bytearray(blob[:old["rec"]])
    struct.pack_into(">I", head, 0x18, len(codes))
    body = head + recs
    body += bytes(-len(body) % 0x20)
    gct = bytearray(blob[old["gct"]:old["gct"] + 0x40])
    struct.pack_into(">HH", gct, 8, width, height)
    return bytes(body + gct + gx.i4_encode(px, width, height))


# ---------------------------------------------------------------- Global.bin (a DX archive, version 3, plain)

def dxa_replace(arc: bytes, swaps: list) -> bytes:
    """``arc`` with every member whose bytes equal an ``old`` of ``swaps`` [(old, new)] set to ``new``. A member that
    grew moves to the end of the data; the header block (names, files, folders) follows the data."""
    _head, version, size, start, table, files, folders = struct.unpack_from("<HHIIIII", arc, 0)
    if arc[:2] != b"DX" or version != 3:
        raise ValueError(tr("Global.bin is not the DX archive it should be"))
    head = bytearray(arc[table:table + size])
    data = bytearray(arc[start:table])
    found = 0
    for at in range(files, folders, 44):
        attr = struct.unpack_from("<I", head, at + 4)[0]
        addr, length = struct.unpack_from("<II", head, at + 32)
        if attr & 0x10:
            continue
        member = bytes(data[addr:addr + length])
        for old, new in swaps:
            if member == old:
                if len(new) <= length:
                    data[addr:addr + len(new)] = new
                else:
                    data += bytes(-len(data) % 0x10)
                    addr = len(data)
                    data += new
                struct.pack_into("<II", head, at + 32, addr, len(new))
                found += 1
                break
    if found < len(swaps):
        raise ValueError(tr("Global.bin does not hold every changed Global\\Global file"))
    out = bytearray(arc[:start]) + data
    struct.pack_into("<I", out, 12, len(out))
    return bytes(out + head)
