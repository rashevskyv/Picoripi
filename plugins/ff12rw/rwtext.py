"""Final Fantasy XII: Revenant Wings (DS) text files: every format of the English set (``data/**/E/``).

Text is one byte per character, Windows-1252 (the fonts' encoding), with control bytes: ``02`` breaks the line,
``01`` starts a new page (a new box), other bytes below ``0x20`` switch colours or draw icons. Every format keeps
its strings at offsets; ``parse(name, data)`` returns a ``TextFile`` whose ``strings`` are the raw strings (no
terminator) and whose ``build(strings)`` lays the file out again with the strings it is given, fixing every
offset and size. Building with the parsed strings gives the original bytes.

Formats (little endian; ``pad(n, k)`` = zeros up to a multiple of ``k``):

- ``.btx`` (menus, ``progtext``): u32 count, (u32 id, u32 offset) per string, the strings from ``4 + 8 * count``,
  each ending with ``00 00``.
- ``.btk`` (airship crafting talk): u32 group count, then per group u32 id and ``BTK_SLOTS`` u32 offsets; the
  strings follow, each ending with ``00 00``.
- ``.brt`` (``REPO``: reports, log book, lore, tutorials, facilities): ``REPO``, u16 0, u16 record count, u32
  offset of the first record; a record is ``k`` u32 offsets of its strings and the u32 offset of the next record,
  then the strings (each ``00`` + pad 4). Offsets are from the file start.
- ``.bst`` (the opening scroll): u32 count, then records of 528 bytes: 16 bytes, a 512-byte text field.
- ``.hscd`` (airship conversations): ``HSCD``, u32, u32 count, then records: u32 id, u32 record size, 0x14
  bytes, u32 text field size, u32, u32 name field size, the text, the speaker name (each ``00 00`` + pad 4).
- ``.bch`` / ``.bit`` / ``.bsk`` (characters, items, abilities): magic, u16, u16 count, then (u32 id, u16 offset
  / 8, u16 size / 8) per record; a record is u32 id, u32 name offset, u32 description offset (from the record),
  data, the two strings (``00`` each, or one shared), pad 8.
- ``.bmw`` (world map): a tree of chunks (u16 type, u16 header size, u32 size; a chunk without bit 15 in its
  type has u32 child offset at +8); a type ``0x8100`` chunk is one string (``00`` + pad 4).
- ``.dpk`` packs (``EventPackTxt``, ``HsEventPackTxt``: event dialogue; ``Stage``: mission objectives): u32
  count, (u32 id, u32 offset, u32 size) per member, members 16-byte aligned with ``EE`` filler. An event member:
  u32 1, then triples ending in a pair (``3n + 3`` words), then text records (u32 id, u32 name offset, u32 text
  offset, u32, u32) and the string pool they point into (``00 00`` after each). A stage member (LZ10 packed)
  is ``rw``, u32 section count, section offsets (+8); its first section is 8 bytes and records (u32 type, u32 size, u32,
  payload); a type 6 record holds the objectives (u16 0, u16 text size with ``00``, text, pad 4).
"""
from __future__ import annotations

import re
import struct
from typing import Callable, Dict, List, Optional, Tuple

from core.containers import lz10

BTK_SLOTS = 12
BST_RECORD, BST_HEAD, BST_TEXT = 528, 16, 512
EE = b"\xee"


class FormatError(ValueError):
    """The bytes are not one of the game's text files, or a text cannot be encoded."""


def _pad(data: bytes, unit: int, fill: bytes = b"\x00") -> bytes:
    return data + fill * (-len(data) % unit)


def _cstr(data: bytes, at: int, double: bool = True) -> bytes:
    """The string at ``at`` up to its ``00 00`` (``double``) or ``00``."""
    end = data.find(b"\x00\x00" if double else b"\x00", at)
    if end < 0:
        raise FormatError(f"no string end after {at:#x}")
    return bytes(data[at:end])


class TextFile:
    """The strings of one file and the way back to its bytes."""

    def __init__(self, strings: List[bytes], builder: Callable[[List[bytes]], bytes], labels: Optional[List[str]] = None):
        self.strings = strings
        self._builder = builder
        self.labels = labels or [""] * len(strings)

    def build(self, strings: List[bytes]) -> bytes:
        if len(strings) != len(self.strings):
            raise FormatError("the number of strings changed")
        return self._builder(list(strings))


# -- .btx ---------------------------------------------------------------------------------------------------

def parse_btx(data: bytes) -> TextFile:
    count = struct.unpack_from("<I", data, 0)[0]
    base = 4 + 8 * count
    pairs = [struct.unpack_from("<II", data, 4 + 8 * i) for i in range(count)]
    if base > len(data) or any(base + off > len(data) for _id, off in pairs):
        raise FormatError("not a .btx table")
    strings = [_cstr(data, base + off) for _id, off in pairs]
    if _btx(pairs, strings) != data:
        raise FormatError(".btx layout not understood")
    return TextFile(strings, lambda new: _btx(pairs, new))


def _btx(pairs, strings: List[bytes]) -> bytes:
    head, body = bytearray(struct.pack("<I", len(pairs))), bytearray()
    for (ident, _off), raw in zip(pairs, strings):
        head += struct.pack("<II", ident, len(body))
        body += raw + b"\x00\x00"
    return bytes(head + body)


# -- .btk ---------------------------------------------------------------------------------------------------

def parse_btk(data: bytes) -> TextFile:
    groups = struct.unpack_from("<I", data, 0)[0]
    width = 1 + BTK_SLOTS
    base = 4 + 4 * width * groups
    rows = [struct.unpack_from(f"<{width}I", data, 4 + 4 * width * g) for g in range(groups)]
    strings = [_cstr(data, base + off) for row in rows for off in row[1:]]
    if _btk(rows, strings) != data:
        raise FormatError(".btk layout not understood")
    return TextFile(strings, lambda new: _btk(rows, new))


def _btk(rows, strings: List[bytes]) -> bytes:
    head, body, at = bytearray(struct.pack("<I", len(rows))), bytearray(), 0
    for row in rows:
        head += struct.pack("<I", row[0])
        for _slot in row[1:]:
            head += struct.pack("<I", len(body))
            body += strings[at] + b"\x00\x00"
            at += 1
    return bytes(head + body)


# -- .brt (REPO) --------------------------------------------------------------------------------------------

def parse_repo(data: bytes) -> TextFile:
    if data[:4] != b"REPO":
        raise FormatError("not a REPO file")
    count = struct.unpack_from("<H", data, 6)[0]
    first = struct.unpack_from("<I", data, 8)[0]
    shapes, strings, at = [], [], first
    for _ in range(count):
        p0 = struct.unpack_from("<I", data, at)[0]
        k = (p0 - at) // 4 - 1
        ptrs = struct.unpack_from(f"<{k + 1}I", data, at)
        shapes.append(k)
        strings += [_cstr(data, p, double=False) for p in ptrs[:k]]
        at = ptrs[k]
    built = _repo(data[:8], first, shapes, strings, data[at:])
    if built != data:
        raise FormatError("REPO layout not understood")
    tail = bytes(data[at:])
    return TextFile(strings, lambda new: _repo(data[:8], first, shapes, new, tail))


def _repo(head: bytes, first: int, shapes, strings: List[bytes], tail: bytes) -> bytes:
    out = bytearray(head) + struct.pack("<I", first)
    out += bytes(first - len(out))
    at = 0
    for k in shapes:
        rec = len(out)
        pieces, pos = [], rec + 4 * (k + 1)
        for raw in strings[at:at + k]:
            piece = _pad(raw + b"\x00", 4)
            pieces.append((pos, piece))
            pos += len(piece)
        out += struct.pack(f"<{k + 1}I", *[p for p, _piece in pieces], pos)
        for _p, piece in pieces:
            out += piece
        at += k
    return bytes(out) + tail


# -- .bst (scroll) ------------------------------------------------------------------------------------------

def parse_bst(data: bytes) -> TextFile:
    count = struct.unpack_from("<I", data, 0)[0]
    if 4 + count * BST_RECORD != len(data):
        raise FormatError("not a .bst scroll")
    strings = [_cstr(data, 4 + i * BST_RECORD + BST_HEAD, double=False) for i in range(count)]

    def build(new: List[bytes]) -> bytes:
        out = bytearray(data)
        for i, raw in enumerate(new):
            if len(raw) >= BST_TEXT:
                raise FormatError(f"scroll line {i}: at most {BST_TEXT - 1} bytes")
            at = 4 + i * BST_RECORD + BST_HEAD
            old = _cstr(data, at, double=False)
            if raw != old:
                out[at:at + BST_TEXT] = raw + bytes(BST_TEXT - len(raw))
        return bytes(out)
    return TextFile(strings, build)


# -- .hscd --------------------------------------------------------------------------------------------------

def parse_hscd(data: bytes) -> TextFile:
    if data[:4] != b"HSCD":
        raise FormatError("not an HSCD file")
    count = struct.unpack_from("<I", data, 8)[0]
    records, strings, labels, at = [], [], [], 12
    for _ in range(count):
        ident, size = struct.unpack_from("<II", data, at)
        heads, pos = [], at + 8
        while pos < at + size:
            text_size, _value, name_size = struct.unpack_from("<III", data, pos + 0x10)
            text_at, name_at = pos + 0x1C, pos + 0x1C + text_size
            heads.append((bytes(data[pos:text_at]), bytes(data[text_at:name_at]),
                          bytes(data[name_at:name_at + name_size])))
            strings += [_fstr(heads[-1][1]), _fstr(heads[-1][2])]
            labels += ["text", "speaker"]
            pos += 0x1C + text_size + name_size
        if pos != at + size:
            raise FormatError("HSCD record sizes do not add up")
        records.append((ident, heads))
        at += size
    tail = bytes(data[at:])
    if _hscd(data[:12], records, strings, tail) != data:
        raise FormatError("HSCD layout not understood")
    return TextFile(strings, lambda new: _hscd(data[:12], records, new, tail), labels)


def _fstr(field: bytes) -> bytes:
    """The string of a fixed field: up to its ``00 00`` (or its zero filler)."""
    end = field.find(b"\x00\x00")
    return bytes(field[:end]) if end >= 0 else bytes(field.rstrip(b"\x00"))


def _field(raw: bytes, old: bytes) -> bytes:
    """A text field: the old bytes while the text is the same, else the text, ``00 00`` and pad 4."""
    if _fstr(old) == raw:
        return old
    return _pad(raw + b"\x00\x00", 4)


def _hscd(head: bytes, records, strings: List[bytes], tail: bytes) -> bytes:
    out, at = bytearray(head), 0
    for ident, heads in records:
        body = bytearray()
        for entry, old_text, old_name in heads:
            text, name = _field(strings[at], old_text), _field(strings[at + 1], old_name)
            entry = bytearray(entry)
            struct.pack_into("<I", entry, 0x10, len(text))
            struct.pack_into("<I", entry, 0x18, len(name))
            body += entry + text + name
            at += 2
        out += struct.pack("<II", ident, 8 + len(body)) + body
    return bytes(out) + tail


# -- .bch / .bit / .bsk -------------------------------------------------------------------------------------

def parse_records(data: bytes) -> TextFile:
    count = struct.unpack_from("<H", data, 6)[0]
    table = [struct.unpack_from("<IHH", data, 8 + 8 * i) for i in range(count)]
    shapes, strings = [], []
    for _ident, unit, size in table:
        rec = data[unit * 8:(unit + size) * 8]
        name_off, desc_off = struct.unpack_from("<II", rec, 4)
        name, desc = _cstr(rec, name_off, double=False), _cstr(rec, desc_off, double=False)
        end = max(name_off + len(name), desc_off + len(desc)) + 1
        # Skill records keep more data after the strings (4-byte aligned); the record is padded to 8.
        trailing = bytes(rec[-(-end // 4) * 4:])
        if len(trailing) % 8 == 4 and not any(trailing[-4:]):
            trailing = trailing[:-4]
        shapes.append((bytes(rec[:min(name_off, desc_off)]), (name_off, desc_off), trailing))
        strings += [name, desc]
    head = bytes(data[:8])
    first = table[0][1] * 8 if table else len(data)
    last = (table[-1][1] + table[-1][2]) * 8 if table else len(data)
    tail = bytes(data[last:])
    if _records(head, table, shapes, strings, first, tail) != data:
        raise FormatError("record layout not understood")
    labels = ["name", "description"] * count
    return TextFile(strings, lambda new: _records(head, table, shapes, new, first, tail), labels)


def _records(head: bytes, table, shapes, strings: List[bytes], first: int, tail: bytes) -> bytes:
    body = bytearray()
    entries = []
    for i, (ident, _unit, _size) in enumerate(table):
        name, desc = strings[2 * i], strings[2 * i + 1]
        fixed, (old_name, old_desc), trailing = shapes[i]
        rec = bytearray(fixed)
        name_at = len(rec)
        if old_name == old_desc and name == desc:
            desc_at = name_at
            rec += name + b"\x00"
        elif old_desc < old_name:
            desc_at = name_at
            rec += desc + b"\x00"
            name_at = len(rec)
            rec += name + b"\x00"
        else:
            rec += name + b"\x00"
            desc_at = len(rec)
            rec += desc + b"\x00"
        struct.pack_into("<II", rec, 4, name_at, desc_at)
        rec = _pad(_pad(bytes(rec), 4) + trailing, 8)
        entries.append((ident, (first + len(body)) // 8, len(rec) // 8))
        body += rec
    out = bytearray(head)
    for ident, unit, size in entries:
        if unit > 0xFFFF or size > 0xFFFF:
            raise FormatError("the data file grew beyond its 16-bit offsets")
        out += struct.pack("<IHH", ident, unit, size)
    out += bytes(first - len(out))
    return bytes(out + body) + tail


# -- .bmw ---------------------------------------------------------------------------------------------------

STRING_CHUNK = 0x8100


def _chunk(data: bytes, at: int, strings: List[bytes]):
    """A chunk as a tree: (header bytes, data bytes, children or None, string index or None)."""
    kind, head, size = struct.unpack_from("<HHI", data, at)
    if kind == STRING_CHUNK:
        strings.append(_cstr(data, at + head, double=False))
        return (bytes(data[at:at + head]), None, None, len(strings) - 1)
    if kind & 0x8000 or head < 12:
        return (bytes(data[at:at + head]), bytes(data[at + head:at + size]), None, None)
    child = struct.unpack_from("<I", data, at + 8)[0]
    children, pos = [], at + child
    while pos < at + size:
        children.append(_chunk(data, pos, strings))
        pos += struct.unpack_from("<I", data, pos + 4)[0]
    if pos != at + size:
        raise FormatError("chunk children overrun")
    return (bytes(data[at:at + head]), bytes(data[at + head:at + child]), children, None)


def _emit(node, strings: List[bytes]) -> bytes:
    head, payload, children, index = node
    if index is not None:
        body = _pad(strings[index] + b"\x00", 4)
        out = bytearray(head) + body
    elif children is None:
        return bytes(head) + payload
    else:
        out = bytearray(head) + payload + b"".join(_emit(child, strings) for child in children)
    struct.pack_into("<I", out, 4, len(out))
    return bytes(out)


def parse_bmw(data: bytes) -> TextFile:
    if data[:4] != b"bwm\x00":
        raise FormatError("not a world map file")
    strings: List[bytes] = []
    root = _chunk(data, 8, strings)
    end = 8 + struct.unpack_from("<I", data, 12)[0]
    head, tail = bytes(data[:8]), bytes(data[end:])
    if head + _emit(root, strings) + tail != data:
        raise FormatError("world map layout not understood")
    return TextFile(strings, lambda new: head + _emit(root, new) + tail)


# -- .dpk packs ---------------------------------------------------------------------------------------------

def dpk_members(data: bytes) -> List[Tuple[int, bytes]]:
    count = struct.unpack_from("<I", data, 0)[0]
    out = []
    for i in range(count):
        ident, at, size = struct.unpack_from("<III", data, 4 + 12 * i)
        out.append((ident, bytes(data[at:at + size])))
    return out


def dpk_pack(members: List[Tuple[int, bytes]], head_fill: bytes = EE) -> bytes:
    """A DPK of ``members`` (each 16-byte aligned with ``EE`` filler, like the game's)."""
    head = 4 + 12 * len(members)
    at = head + (-head % 16)
    table, body = bytearray(struct.pack("<I", len(members))), bytearray()
    for ident, member in members:
        table += struct.pack("<III", ident, at + len(body), len(member))
        body += _pad(member, 16, EE)
    table += head_fill * (-len(table) % 16)
    return bytes(table + body)


def _pool_offsets(pool: bytes) -> Optional[List[int]]:
    """Where the strings of a pool start (each ends with ``00 00``), or None when it is not such a pool."""
    offsets, at = [], 0
    while at < len(pool):
        end = pool.find(b"\x00\x00", at)
        if end < 0:
            return None
        offsets.append(at)
        at = end + 2
    return offsets


def _event_member(member: bytes):
    """``(script, records, pool, filler)`` of an event text member, or None when it holds no text.

    The script is u32 1 and triples ending in a pair: ``12 * (n + 1)`` bytes; the text records follow (the first
    one's name is at pool offset 0) and the pool takes the rest; every pool string is some record's name or text.
    """
    plain = member.rstrip(EE)
    filler = len(member) - len(plain)
    if not plain:
        return None
    for start in range(12, len(plain) + 1, 12):
        if start == len(plain):
            return None
        if start + 20 > len(plain) or struct.unpack_from("<I", plain, start + 4)[0] != 0:
            continue
        for count in range(1, (len(plain) - start) // 20 + 1):
            pool = plain[start + 20 * count:]
            records = [struct.unpack_from("<5I", plain, start + 20 * i) for i in range(count)]
            wanted = sorted({r[1] for r in records} | {r[2] for r in records})
            if wanted[-1] >= len(pool) + 2:
                continue
            if _pool_offsets(pool) == wanted:
                return plain[:start], records, pool, filler
    raise FormatError("event text member not understood")


def parse_event_pack(data: bytes) -> TextFile:
    members = dpk_members(data)
    layout, strings, labels = [], [], []
    for ident, member in members:
        found = _event_member(member)
        if found is None:
            layout.append((ident, member, None))
            continue
        script, records, pool, _filler = found
        order = sorted({r[1] for r in records} | {r[2] for r in records})
        texts = [_cstr(pool, off) for off in order]
        layout.append((ident, member, (script, records, order, len(strings))))
        strings += texts
        labels += [f"{ident}" for _ in texts]
    head_fill = data[4 + 12 * len(members):(4 + 12 * len(members) + 15) // 16 * 16][-1:] or EE

    def build(new: List[bytes]) -> bytes:
        out = []
        for ident, member, info in layout:
            if info is None:
                out.append((ident, member))
                continue
            script, records, order, first = info
            mine = new[first:first + len(order)]
            if mine == strings[first:first + len(order)]:
                out.append((ident, member))
                continue
            where, body = {}, bytearray()
            for off, raw in zip(order, mine):
                where[off] = len(body)
                body += raw + b"\x00\x00"
            recs = b"".join(struct.pack("<5I", r[0], where[r[1]], where[r[2]], r[3], r[4]) for r in records)
            plain = script + recs + bytes(body)
            out.append((ident, _pad(plain, 16, EE)))
        return dpk_pack(out, head_fill)

    if build(list(strings)) != data:
        raise FormatError("event pack layout not understood")
    return TextFile(strings, build, labels)


def _stage(member: bytes):
    """``(plain, (section offsets), text records [(at, size)])`` of a Stage member (LZ10)."""
    plain = lz10.decompress(member)[0]
    if plain[:4] != b"rw\x00\x00":
        raise FormatError("not a stage member")
    count = struct.unpack_from("<I", plain, 4)[0]
    sections = list(struct.unpack_from(f"<{count}I", plain, 8))
    # The first section: 8 bytes, then the records.
    start, end = sections[0] + 16, (sections[1] + 8 if count > 1 else len(plain))
    texts, at = [], start
    while at < end:
        kind, size = struct.unpack_from("<II", plain, at)
        if kind == 6:
            texts.append(at)
        at += 12 + size
    if at != end:
        raise FormatError("stage records overrun")
    return plain, sections, texts


def parse_stage_pack(data: bytes) -> TextFile:
    members = dpk_members(data)
    layout, strings, labels = [], [], []
    for ident, member in members:
        plain, sections, texts = _stage(member)
        mine = []
        for at in texts:
            length = struct.unpack_from("<H", plain, at + 14)[0]
            mine.append(bytes(plain[at + 16:at + 16 + length - 1]))
        layout.append((ident, member, plain, sections, texts, len(strings)))
        strings += mine
        labels += [f"stage {ident}"] * len(mine)
    head_fill = EE

    def build(new: List[bytes]) -> bytes:
        out = []
        for ident, member, plain, sections, texts, first in layout:
            mine = new[first:first + len(texts)]
            if mine == strings[first:first + len(texts)]:
                out.append((ident, member))
                continue
            buf = bytearray(plain)
            for at, raw in sorted(zip(texts, mine), reverse=True):
                kind, size, extra = struct.unpack_from("<III", buf, at)
                payload = _pad(struct.pack("<HH", 0, len(raw) + 1) + raw + b"\x00", 4)
                buf[at:at + 12 + size] = struct.pack("<III", kind, len(payload), extra) + payload
                grow = len(payload) - size
                for k in range(1, len(sections)):
                    if sections[k] + 8 > at:
                        struct.pack_into("<I", buf, 8 + 4 * k, struct.unpack_from("<I", buf, 8 + 4 * k)[0] + grow)
            out.append((ident, lz10.compress(bytes(buf))))
        return dpk_pack(out, head_fill)

    if build(list(strings)) != data:
        raise FormatError("stage pack layout not understood")
    return TextFile(strings, build, labels)


# -- dispatch -----------------------------------------------------------------------------------------------

PARSERS: Dict[str, Callable[[bytes], TextFile]] = {
    ".btx": parse_btx, ".btk": parse_btk, ".brt": parse_repo, ".bst": parse_bst, ".hscd": parse_hscd,
    ".bch": parse_records, ".bit": parse_records, ".bsk": parse_records, ".bmw": parse_bmw,
}
TEXT_PACKS = {"EventPackTxt.dpk": parse_event_pack, "HsEventPackTxt.dpk": parse_event_pack,
              "Stage.dpk": parse_stage_pack}


def parser_for(name: str) -> Optional[Callable[[bytes], TextFile]]:
    base = re.split(r"[\\/]", str(name))[-1]
    if base in TEXT_PACKS:
        return TEXT_PACKS[base]
    ext = "." + base.rsplit(".", 1)[-1].lower() if "." in base else ""
    return PARSERS.get(ext)


def parse(name: str, data: bytes) -> TextFile:
    """The text of a game file (by its name), or ``FormatError``."""
    parser = parser_for(name)
    if parser is None:
        raise FormatError(f"{name}: not a text file of the game")
    try:
        return parser(bytes(data))
    except (struct.error, IndexError) as error:
        raise FormatError(f"{name}: {error}") from None


def detect(data: bytes) -> Optional[Callable[[bytes], TextFile]]:
    """The parser that reads ``data`` byte-exactly (for a file whose name is not known)."""
    head = bytes(data[:4])
    for magic, parser in ((b"REPO", parse_repo), (b"HSCD", parse_hscd), (b"bwm\x00", parse_bmw),
                          (b"CHAR", parse_records), (b"ITEM", parse_records), (b"SKIL", parse_records)):
        if head == magic:
            return parser
    for parser in (parse_event_pack, parse_stage_pack, parse_btk, parse_btx, parse_bst):
        try:
            parser(bytes(data))
            return parser
        except (FormatError, struct.error, IndexError, ValueError):
            continue
    return None


# -- editor text --------------------------------------------------------------------------------------------

NEWLINE, PAGE = 0x02, 0x01
TAG_RE = re.compile(r"\[(?:page|x[0-9A-F]{2})\]")
_LOW = {NEWLINE: "\n", PAGE: "[page]"}


def to_editor(raw: bytes) -> str:
    parts = []
    for byte in raw:
        if byte in _LOW:
            parts.append(_LOW[byte])
        elif byte < 0x20 or byte in (0x5B, 0x5D) or 0x7F <= byte < 0xA0 and byte not in _CP1252_PRINTABLE:
            parts.append(f"[x{byte:02X}]")
        else:
            parts.append(bytes([byte]).decode("cp1252"))
    return "".join(parts)


_CP1252_PRINTABLE = {b for b in range(0x80, 0xA0) if b not in (0x81, 0x8D, 0x8F, 0x90, 0x9D)}


def from_editor(text: str) -> bytes:
    out = bytearray()
    text = str(text).replace("\r\n", "\n")
    at = 0
    for match in list(TAG_RE.finditer(text)) + [None]:
        for char in text[at:match.start() if match else len(text)]:
            if char == "\n":
                out.append(NEWLINE)
                continue
            try:
                encoded = char.encode("cp1252")
            except UnicodeEncodeError:
                raise FormatError(f"The game's fonts have no character {char!r} (U+{ord(char):04X})") from None
            out += encoded
        if match is None:
            break
        tag = match.group()
        out.append(PAGE if tag == "[page]" else int(tag[2:4], 16))
        at = match.end()
    if b"\x00" in out:
        raise FormatError("a text cannot hold the byte 00")
    return bytes(out)


def describe(tag: str) -> str:
    if tag == "[page]":
        return "New page (the next box)"
    if TAG_RE.fullmatch(tag):
        return f"Control byte {tag[2:4]} (colour or icon)"
    return ""
