"""Where the text of Final Fantasy Tactics Advance (GBA, USA ``AFXE``) lives in the ROM, how unpack takes it out
and how the build writes it back.

Two kinds of table (``codec`` has the string formats):

- Pointer tables (``ABS_TABLES``): u32 pointers, one per string, strings without a header. An edited string is
  written after the end of the ROM and its pointer changed; the old bytes stay.
- Offset tables: ``u16 offset[n]`` from the table's own start (``offset[0] = 2n``; ``FFFF`` = no string), each string
  a u16 header and its text (``codec``). They are reached through the pointer array ``TABLE_ARRAY``, through
  pointers in the code (``CODE_TABLES``) and through the event tree (``EVENT_BASE``: u32 offsets from that address,
  entry ``EVENT_SUBLIST`` a second list of offsets from the same base). A table with an edited string is rebuilt
  after the end of the ROM and every pointer or offset that reaches it is changed; the old table stays.

An edited string is written plain (without LZSS) and two-byte; the header keeps its window bits. The ROM grows
at most to 32 MiB, the GBA cartridge size. Single-byte strings of the offset tables (all placeholder codes) are not
shown and keep their bytes.
"""
from __future__ import annotations

import struct
from dataclasses import dataclass, field
from typing import Dict, Iterable, List, Optional, Tuple

from core.i18n import tr

from . import codec

GAME_CODE = b"AFXE"
ROM_BASE = 0x08000000
MAX_ROM = 32 * 1024 * 1024
FONT_START, FONT_GLYPHS = 0x433330, 3175          # 16x16 4bpp glyphs (128 bytes), then one width byte a glyph
FONT_END = FONT_START + FONT_GLYPHS * 129
# ponytail: the longest plain string of the game (bytes); the end of the game's buffer at 0x020078B0 is not known,
# so a longer text is refused. Raise it once the buffer size is read from the code.
TEXT_LIMIT = 970

# (file, table, entries, block name)
ABS_TABLES: List[Tuple[str, int, int, str]] = [
    ("system", 0x5567F0, 767, "Menus, commands and abilities"),
    ("system", 0x5668B0, 84, "Menu labels"),
    ("system", 0x557E98, 92, "Law and card names"),
    ("system", 0x569034, 52, "Clan titles"),
    ("items", 0x526680, 753, "Items, jobs, monsters and places"),
    ("names", 0x5516D0, 107, "Character names (CRN)"),
    ("names", 0x5680DC, 725, "Unit names"),
    ("names", 0x565F14, 128, "Clan names"),
    ("names", 0x51BA84, 24, "Names 51BA84"),
    ("missions", 0x55A64C, 512, "Mission names"),
]
TABLE_ARRAY, TABLE_ARRAY_SLOTS = 0x36D67C, 26
# (file, block name) of each slot of TABLE_ARRAY
ARRAY_NAMES: Dict[int, Tuple[str, str]] = {
    0: ("system", "Prompts and questions"), 1: ("system", "Battle setup messages"), 3: ("missions", "Shops"),
    5: ("missions", "Clan descriptions"), 6: ("missions", "Shop descriptions"), 7: ("missions", "Law notes and tutorials"),
    8: ("missions", "Mission information"), 9: ("system", "Field messages"), 10: ("missions", "Mission results"),
    11: ("system", "Table slot 11"), 12: ("system", "Table slot 12"), 13: ("system", "Table slot 13"),
    14: ("system", "Clan member farewells"), 15: ("system", "Battle menu help"), 16: ("items", "Ability descriptions"),
    17: ("items", "Command descriptions"), 18: ("items", "Combo descriptions"), 19: ("items", "Place descriptions"),
    20: ("items", "Item descriptions"), 21: ("items", "Monster and job descriptions"),
    22: ("items", "Law descriptions"), 23: ("items", "Law descriptions"), 24: ("items", "Trophy descriptions"),
    25: ("items", "Unknown item descriptions"),
}
CODE_TABLES: List[Tuple[str, int, str]] = [
    ("system", 0x497418, "Battle messages"),
    ("missions", 0x4A002C, "Mission descriptions 1"),
    ("missions", 0x4AADFC, "Mission descriptions 2"),
    ("missions", 0x4B83A0, "Mission conditions"),
    ("system", 0x4EF3F4, "Table 4EF3F4"),
    ("system", 0x4B64A4, "Table 4B64A4"),
]
EVENT_BASE, EVENT_ENTRIES, EVENT_SUBLIST, EVENT_SUBLIST_ENTRIES = 0x9C1484, 63, 61, 26
FILES = {"system": "System and menus", "items": "Items, abilities and jobs", "names": "Names",
         "missions": "Missions, shops and notices", "events": "Story events and battles"}
TEXT_FORMAT = "ffta-gba-text"


class BuildError(ValueError):
    """The translation cannot be written into the ROM."""


@dataclass
class Table:
    """One offset table: where it is, what reaches it, its entries."""
    file: str
    address: int
    name: str
    abs_refs: List[int] = field(default_factory=list)      # ROM offsets of u32 pointers to it
    rel_refs: List[int] = field(default_factory=list)      # ROM offsets of u32 offsets from EVENT_BASE


def u16(data: bytes, at: int) -> int:
    return struct.unpack_from("<H", data, at)[0]


def u32(data: bytes, at: int) -> int:
    return struct.unpack_from("<I", data, at)[0]


def pointer(data: bytes, at: int) -> Optional[int]:
    value = u32(data, at)
    return value - ROM_BASE if ROM_BASE <= value < ROM_BASE + len(data) else None


def is_ffta(data: bytes) -> bool:
    return bytes(data[0xAC:0xB0]) == GAME_CODE and len(data) > FONT_END


# -- the tables -----------------------------------------------------------------------------------------------

def offset_tables(data: bytes) -> List[Table]:
    """Every offset table, once each, with what reaches it (event tables after the others)."""
    found: Dict[int, Table] = {}

    def add(file: str, address: int, name: str) -> Table:
        return found.setdefault(address, Table(file, address, name))

    for slot in range(TABLE_ARRAY_SLOTS):
        address = pointer(data, TABLE_ARRAY + 4 * slot)
        if address is not None:
            file, name = ARRAY_NAMES.get(slot, ("system", f"Table slot {slot}"))
            add(file, address, name)
    for file, address, name in CODE_TABLES:
        add(file, address, name)
    for k in range(EVENT_ENTRIES):
        at = EVENT_BASE + 4 * k
        if k == EVENT_SUBLIST:
            sub = EVENT_BASE + u32(data, at)
            for j in range(EVENT_SUBLIST_ENTRIES):
                add("events", EVENT_BASE + u32(data, sub + 4 * j), f"Battle scene {j:02d}").rel_refs.append(sub + 4 * j)
        else:
            add("events", EVENT_BASE + u32(data, at), f"Event scene {k:02d}").rel_refs.append(at)
    for table in found.values():
        table.abs_refs = find_u32(data, ROM_BASE + table.address)
    return sorted(found.values(), key=lambda t: (t.file == "events", t.address))


def find_u32(data: bytes, value: int) -> List[int]:
    """Aligned ROM offsets that hold ``value``."""
    needle, hits, at = struct.pack("<I", value), [], 0
    while (at := data.find(needle, at)) >= 0:
        if at % 4 == 0:
            hits.append(at)
        at += 1
    return hits


def table_entries(data: bytes, address: int) -> List[int]:
    """The u16 offsets of an offset table."""
    count = u16(data, address) // 2
    return list(struct.unpack_from(f"<{count}H", data, address))


def string_slices(data: bytes, address: int) -> Dict[int, bytes]:
    """Offset -> the bytes of that string of an offset table: up to the next string; the last one by its format."""
    offsets = sorted({o for o in table_entries(data, address) if o != 0xFFFF})
    out: Dict[int, bytes] = {}
    for i, offset in enumerate(offsets):
        at = address + offset
        if i + 1 < len(offsets):
            out[offset] = bytes(data[at:address + offsets[i + 1]])
        else:
            out[offset] = bytes(data[at:at + tbl_length(data, at)])
    return out


def tbl_length(data: bytes, at: int) -> int:
    """Bytes of the offset-table string at ``at`` (header and end included)."""
    header = u16(data, at)
    if header & 2:
        return 2 + codec.lzss_decode(data, at + 2)[1]
    if header & 1:
        return data.index(b"\xff", at + 2) + 1 - at
    return 2 + codec.plain_length(data, at + 2)


def tbl_body(raw: bytes) -> bytes:
    """The two-byte text of an offset-table string (``raw`` = header + data), without its ``00``."""
    header = u16(raw, 0)
    if header & 1:
        raise ValueError("a single-byte string")
    data = codec.lzss_decode(raw, 2)[0] if header & 2 else raw[2:]
    return data[:codec.plain_length(data + b"\0", 0) - 1]


def tbl_text(raw: bytes) -> str:
    """Editor text of an offset-table string; ValueError when it does not read back byte for byte."""
    body = tbl_body(raw)
    text = codec.decode_db(body)
    if codec.encode_db(text) != body:
        raise ValueError("the text does not encode back to the same bytes")
    return text


def tbl_encode(text: str, raw: bytes) -> bytes:
    """A new offset-table string for ``text``: the old header without single-byte and LZSS, two-byte text."""
    body = codec.encode_db(text)
    if len(body) + 1 > TEXT_LIMIT:
        raise codec.EncodeError(tr("The text takes {0} bytes; the longest the game is known to show is {1}",
                                   len(body) + 1, TEXT_LIMIT))
    return struct.pack("<H", u16(raw, 0) & ~3) + body + b"\0"


def abs_text(raw: bytes) -> str:
    text = codec.decode_plain(raw)
    if codec.encode_plain(text, raw[:1] == b"\x01") != raw:
        raise ValueError("the text does not encode back to the same bytes")
    return text


def abs_encode(text: str, raw: bytes) -> bytes:
    new = codec.encode_plain(text, raw[:1] == b"\x01")
    if len(new) > TEXT_LIMIT:
        raise codec.EncodeError(tr("The text takes {0} bytes; the longest the game is known to show is {1}",
                                   len(new), TEXT_LIMIT))
    return new


# -- unpack ---------------------------------------------------------------------------------------------------

def extract(data: bytes) -> Dict[str, dict]:
    """``{file key: bank}``: every string the editor can show, by table. A bank is
    ``{"format", "file", "blocks": [{"id", "name", "strings": [{"id", "raw"}]}]}`` (``raw``: the string's bytes as
    the ROM has them, hex)."""
    banks = {key: {"format": TEXT_FORMAT, "file": key, "title": title, "blocks": []} for key, title in FILES.items()}
    for file, table, count, name in ABS_TABLES:
        strings, seen = [], set()
        for i in range(count):
            at = pointer(data, table + 4 * i)
            if at is None or at in seen:
                continue
            seen.add(at)
            try:
                raw = bytes(data[at:at + codec.plain_length(data, at)])
                abs_text(raw)
            except (ValueError, IndexError):
                continue
            strings.append({"id": f"{table:06X}-{i}", "raw": raw.hex()})
        banks[file]["blocks"].append({"id": f"{table:06X}", "kind": "pointers", "name": name, "strings": strings})
    for table in offset_tables(data):
        slices = string_slices(data, table.address)
        strings, seen = [], set()
        for i, offset in enumerate(table_entries(data, table.address)):
            if offset == 0xFFFF or offset in seen:
                continue
            seen.add(offset)
            raw = slices[offset]
            try:
                tbl_text(raw)
            except (ValueError, IndexError, struct.error):
                continue
            strings.append({"id": f"{table.address:06X}-{i}", "raw": raw.hex()})
        if strings:
            banks[table.file]["blocks"].append({"id": f"{table.address:06X}", "kind": "offsets",
                                                "name": table.name, "strings": strings})
    return banks


# -- build ----------------------------------------------------------------------------------------------------

def _changes(data: bytes, banks: Iterable[dict]) -> Dict[str, bytes]:
    """String id -> new bytes, for every string whose bytes differ from the ROM's."""
    original = {s["id"]: s["raw"] for bank in extract(data).values() for b in bank["blocks"] for s in b["strings"]}
    changes = {}
    for bank in banks:
        for block in bank.get("blocks") or []:
            for string in block.get("strings") or []:
                sid, raw = string.get("id"), string.get("raw")
                if sid in original and raw != original[sid]:
                    changes[sid] = bytes.fromhex(raw)
    return changes


def _append(rom: bytearray, payload: bytes, align: int = 4) -> int:
    rom += bytes(-len(rom) % align)
    at = len(rom)
    rom += payload
    if len(rom) > MAX_ROM:
        raise BuildError(tr("The translated ROM would be {0} bytes; a GBA cartridge holds {1}.", len(rom), MAX_ROM))
    return at


def _rebuild_table(data: bytes, address: int, new: Dict[int, bytes]) -> bytes:
    """An offset table with the strings of ``new`` (entry index -> bytes) replaced, every string at an even offset."""
    entries = table_entries(data, address)
    slices = string_slices(data, address)
    by_offset = {entries[i]: raw for i, raw in new.items()}
    head = 2 * len(entries)
    body, placed = bytearray(), {}
    for offset in entries:
        if offset == 0xFFFF or offset in placed:
            continue
        placed[offset] = head + len(body)
        body += by_offset.get(offset, slices[offset])
        body += bytes(len(body) % 2)
    if head + len(body) > 0xFFFF:
        raise BuildError(tr("Table {0} would take {1} bytes; its offsets reach 65535.", f"{address:06X}",
                            head + len(body)))
    return struct.pack(f"<{len(entries)}H", *(0xFFFF if o == 0xFFFF else placed[o] for o in entries)) + bytes(body)


def build(data: bytes, banks: Iterable[dict], font: Optional[bytes] = None) -> bytes:
    """The ROM with the banks' edited strings and ``font`` (the bytes of ``FONT_START:FONT_END``) written in."""
    data = bytes(data)
    if not is_ffta(data):
        raise BuildError(tr("The source is not Final Fantasy Tactics Advance (USA, AFXE)."))
    rom = bytearray(data)
    if font is not None:
        if len(font) != FONT_END - FONT_START:
            raise BuildError(tr("The font file has {0} bytes; the game's font has {1}.", len(font),
                                FONT_END - FONT_START))
        rom[FONT_START:FONT_END] = font
    changes = _changes(data, banks)
    if not changes:
        return bytes(rom)
    for _file, table, count, _name in ABS_TABLES:
        for sid in [s for s in changes if s.startswith(f"{table:06X}-")]:
            target = pointer(data, table + 4 * int(sid.split("-")[1]))
            at = _append(rom, changes[sid], 2)
            for i in range(count):                  # every pointer of the table to that string follows it
                if pointer(data, table + 4 * i) == target:
                    struct.pack_into("<I", rom, table + 4 * i, ROM_BASE + at)
    for table in offset_tables(data):
        prefix = f"{table.address:06X}-"
        new = {int(sid.split("-")[1]): raw for sid, raw in changes.items() if sid.startswith(prefix)}
        if not new:
            continue
        if not (table.abs_refs or table.rel_refs):
            raise BuildError(tr("Table {0} ({1}) has no pointer the build can move.", f"{table.address:06X}",
                                table.name))
        at = _append(rom, _rebuild_table(data, table.address, new))
        for ref in table.abs_refs:
            struct.pack_into("<I", rom, ref, ROM_BASE + at)
        for ref in table.rel_refs:
            struct.pack_into("<I", rom, ref, at - EVENT_BASE)
    rom += bytes(-len(rom) % 16)
    return bytes(rom)
