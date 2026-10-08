r"""Spore Hero text files: the localisation package and the system messages of ``main.dol``.

``game/localization/localization/ENG_US.rpk`` (``1_unpack`` writes it decompressed) is an EA ``STRM`` stream:
groups (``AGRP``) of a header (``GHDR``) and asset records (``ASET``: hash, type hash, ..., u32 data offset, u32
data size, u32 name offset -- offsets from the start of the stream), the strings (``STRS``) and the data
(``DATA``, the last chunk). It holds two ``LOCBIN`` assets (little endian inside):

- ``LANGUAGE_English_Global.BIN``: u32 0x39000, u32 size (of what follows), u32 string count, u32 table offset,
  u32 pool offset (both from byte 8), a 16-byte name, the table (u32 key hash, u32 pool offset) sorted by hash,
  then the pool of zero-terminated 8-bit strings, padded to 4 bytes;
- ``LANGUAGE_English_HISTOGRAM.BIN``: u32 0x39001, u32 size, u32 256, then u16 per byte value: the Unicode
  character the game draws for a byte from 0x81 up (0 = not used; bytes below 0x80 are ASCII; the entry of
  0x80 is not a character and stays as it is).

The editor shows the strings in pool order (the order they were written in). Saving encodes each character as
its byte: ASCII, a byte the table already maps to it, else a free byte (its own Latin-1 value when free) whose
table entry is set -- so any letter, Cyrillic too, gets a byte; the fonts must have its glyph. With a
translation map (letter -> font slot, written by the Font Editor) a letter is written as its slot's character. The game reads
the package as a stream: the assets stay packed one after another at their group's alignment.

``main.dol`` keeps the disc and Wii memory messages of every language (cp1252, ``\n`` written as two
characters); the two English sets are edited in place, each message within its own bytes.
"""
from __future__ import annotations

import struct
from typing import Dict, List, Tuple

TEXT_ID, MAP_ID = 0x39000, 0x39001
FIRST_FREE = 0x81
DOL_SETS = ((0x5721E8, 0x5726F9, "System messages (disc, Wii memory)"),
            (0x5726F9, 0x572B33, "System messages, second English set"))
DOL_PROBE = b"Please insert the\0"


# -- STRM ------------------------------------------------------------------------------------------------------

def assets(strm: bytes) -> List[Dict]:
    """``[{type, name, at (ASET record), off, size, align}]`` of a decompressed package."""
    if strm[:4] != b"STRM":
        raise ValueError("Not an EA STRM package")
    out, at = [], 8
    while at < len(strm):
        tag, size = strm[at:at + 4], struct.unpack_from(">I", strm, at + 4)[0]
        if size < 8:
            raise ValueError("Broken STRM chunk")
        if tag == b"AGRP":
            inner, kind, align = at + 8, "", 4
            while inner < at + size:
                tag2, size2 = strm[inner:inner + 4], struct.unpack_from(">I", strm, inner + 4)[0]
                if tag2 == b"GHDR":
                    kind = _cstr(strm, struct.unpack_from(">I", strm, inner + 12)[0])
                    align = max(1, struct.unpack_from(">I", strm, inner + 16)[0])
                elif tag2 == b"ASET":
                    off, length, name = struct.unpack_from(">III", strm, inner + 24)
                    out.append({"type": kind, "name": _cstr(strm, name), "at": inner, "off": off, "size": length,
                                "align": align})
                inner += max(8, size2)
        at += size
    return out


def _cstr(data: bytes, at: int) -> str:
    return data[at:data.index(b"\0", at)].decode("latin-1")


def _data_chunk(strm: bytes) -> int:
    at = 8
    while at < len(strm):
        if strm[at:at + 4] == b"DATA":
            return at
        at += struct.unpack_from(">I", strm, at + 4)[0]
    raise ValueError("STRM without DATA")


def replace_assets(strm: bytes, new: Dict[int, bytes]) -> bytes:
    """The package with assets ``{index: bytes}`` replaced. The game reads the data as a stream: every asset
    follows the one before it at the next multiple of its group's alignment, and the package ends on 4 bytes."""
    items = assets(strm)
    data_at = _data_chunk(strm)
    head = bytearray(strm[:data_at + 8])
    body = bytearray()
    pos = data_at + 8
    for i in sorted(range(len(items)), key=lambda i: items[i]["off"]):
        item = items[i]
        blob = new[i] if i in new else strm[item["off"]:item["off"] + item["size"]]
        at = -(-pos // item["align"]) * item["align"]
        body += bytes(at - pos) + blob
        struct.pack_into(">II", head, item["at"] + 24, at, len(blob))
        pos = at + len(blob)
    out = head + body + bytes(-pos % 4)
    struct.pack_into(">I", out, 4, len(out))
    struct.pack_into(">I", out, data_at + 4, len(out) - data_at)
    return bytes(out)


def is_package(raw: bytes) -> bool:
    try:
        return len(_parts(raw)) == 2
    except (ValueError, struct.error):
        return False


def _parts(strm: bytes) -> Dict[int, Tuple[int, bytes]]:
    """``{chunk id: (asset index, asset bytes)}`` of the LOCBIN assets."""
    out = {}
    for index, item in enumerate(assets(strm)):
        blob = strm[item["off"]:item["off"] + item["size"]]
        if item["type"] == "LOCBIN" and len(blob) >= 12:
            out[struct.unpack_from("<I", blob)[0]] = (index, blob)
    if TEXT_ID not in out or MAP_ID not in out:
        raise ValueError("No LOCBIN text and histogram in the package")
    return out


def strings(blob: bytes) -> List[Tuple[int, bytes]]:
    """``[(key hash, bytes)]`` of the text asset, in pool order."""
    count, table, pool = struct.unpack_from("<III", blob, 8)
    entries = [struct.unpack_from("<II", blob, 8 + table + 8 * i) for i in range(count)]
    base = 8 + pool
    return [(key, blob[base + off:blob.index(b"\0", base + off)]) for key, off in sorted(entries, key=lambda e: e[1])]


def build_strings(blob: bytes, items: List[Tuple[int, bytes]]) -> bytes:
    """The text asset with ``items`` (pool order) as its strings."""
    count, table, pool = struct.unpack_from("<III", blob, 8)
    if len(items) != count:
        raise ValueError(f"The text has {count} strings, not {len(items)}")
    body, offsets = bytearray(), {}
    for key, text in items:
        offsets[key] = len(body)
        body += text + b"\0"
    body += bytes(-(8 + pool + len(body)) % 4)
    out = bytearray(blob[:8 + pool])
    for i, key in enumerate(sorted(offsets)):
        struct.pack_into("<II", out, 8 + table + 8 * i, key, offsets[key])
    out += body
    struct.pack_into("<I", out, 4, len(out) - 8)
    return bytes(out)


def char_table(blob: bytes) -> List[int]:
    """The histogram: the character of every byte value (0 = none)."""
    return list(struct.unpack_from("<256H", blob, 12))


def decode(text: bytes, table: List[int]) -> str:
    return "".join(chr(b) if b < 0x80 or not table[b] or b == 0x80 else chr(table[b]) for b in text)


def encode(text: str, table: List[int], reserved: frozenset = frozenset()) -> bytes:
    """``text`` as bytes; a character without a byte gets a free one (``table`` is updated; ``reserved``
    bytes, used by other strings, are never given out)."""
    reverse = {code: b for b, code in enumerate(table) if code and b >= FIRST_FREE}
    out = bytearray()
    for char in text:
        code = ord(char)
        if code < 0x80:
            out.append(code)
            continue
        byte = reverse.get(code)
        if byte is None:
            free = [b for b in range(FIRST_FREE, 256) if not table[b] and b not in reserved]
            if not free:
                raise ValueError(f"No free byte left for {char!r}: the game has 127 characters above ASCII")
            byte = code if code in free else free[0]
            table[byte] = code
            reverse[code] = byte
        out.append(byte)
    return bytes(out)


def _swap(text: str, mapping: Dict[str, str]) -> str:
    return "".join(mapping.get(char, char) for char in text) if mapping else text


def texts(strm: bytes, shown: Dict[str, str] = None) -> List[str]:
    """The strings; ``shown`` (font slot -> letter, the reverse of a translation map) turns slots into letters."""
    parts = _parts(strm)
    table = char_table(parts[MAP_ID][1])
    return [_swap(decode(text, table), shown) for _key, text in strings(parts[TEXT_ID][1])]


def build(strm: bytes, new: List[str], slots: Dict[str, str] = None, shown: Dict[str, str] = None) -> bytes:
    """The package with the strings ``new`` (pool order); unchanged strings keep their bytes. ``slots`` (letter ->
    font slot, the Font Editor's translation map) writes a letter as the character whose glyph draws it."""
    parts = _parts(strm)
    (text_index, text_blob), (map_index, map_blob) = parts[TEXT_ID], parts[MAP_ID]
    table = char_table(map_blob)
    old = strings(text_blob)
    if len(new) != len(old):
        raise ValueError(f"The text has {len(old)} strings, the project {len(new)}")
    used = frozenset(b for _key, raw in old for b in raw if b >= 0x80)
    items = [(key, raw if _swap(decode(raw, table), shown) == text else encode(_swap(text, slots), table, used))
             for (key, raw), text in zip(old, new)]
    changes = {}
    text_new = build_strings(text_blob, items)
    if text_new != text_blob:
        changes[text_index] = text_new
    if table != char_table(map_blob):
        changes[map_index] = map_blob[:12] + struct.pack("<256H", *table) + map_blob[12 + 512:]
    return replace_assets(strm, changes) if changes else strm


# -- main.dol --------------------------------------------------------------------------------------------------

def is_dol(raw: bytes) -> bool:
    start = DOL_SETS[0][0]
    return raw[start:start + len(DOL_PROBE)] == DOL_PROBE


def dol_slots(raw: bytes, start: int, end: int) -> List[Tuple[int, int]]:
    """``(offset, room)`` of every message between ``start`` and ``end`` (room: its bytes and the zeros after)."""
    out, at = [], start
    while at < end:
        stop = raw.index(b"\0", at)
        nxt = stop
        while nxt < end and raw[nxt] == 0:
            nxt += 1
        out.append((at, nxt - at - 1))
        at = nxt
    return out


def dol_texts(raw: bytes) -> List[List[str]]:
    return [[raw[at:raw.index(b"\0", at)].decode("cp1252") for at, _room in dol_slots(raw, start, end)]
            for start, end, _name in DOL_SETS]


def build_dol(raw: bytes, groups: List[List[str]]) -> bytes:
    out = bytearray(raw)
    for (start, end, name), texts_ in zip(DOL_SETS, groups):
        slots = dol_slots(raw, start, end)
        if len(texts_) != len(slots):
            raise ValueError(f"{name}: {len(slots)} messages, the project {len(texts_)}")
        for (at, room), text in zip(slots, texts_):
            data = text.encode("cp1252")
            if len(data) > room:
                raise ValueError(f"main.dol message is {len(data)} bytes, its place {room}: {text[:40]!r}")
            if data != raw[at:raw.index(b"\0", at)]:
                out[at:at + room + 1] = data + bytes(room + 1 - len(data))
    return bytes(out)
