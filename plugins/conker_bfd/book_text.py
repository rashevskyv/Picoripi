"""Editable text of Conker's Bad Fur Day: instruction-book pages (bank 0x1A) and menu sub-tables (bank 0x1C).

Each bank 0x1A entry is a container of page records; each page holds one text region, a code list and a header
(see ``book_pages``). Each bank 0x1C holder is a container of four sub-tables. A sub-table is one list of strings
that are separated by NUL bytes; every string is one editable unit, empty strings included.

``extract`` reads a ROM and returns one ``Table`` per entry and per sub-table. ``table_to_json`` and
``table_from_json`` move a table to and from the editor's JSON. ``rebuild`` applies edited tables to the ROM's
banks and returns the new bytes of the changed banks. Only the structure above is read; no text is guessed.
"""
from __future__ import annotations

import binascii
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from . import book_pages, containers, n64_archive as na, text_blocks
from .containers import Slot

FORMAT_ID = "conker-bfd-text/3"
BOOK_BANK = 0x1A
SUB_HOLDER_BANK = 0x1C

KIND_PAGE = "page"
KIND_STRING = "string"
KIND_RAW = "raw"
KIND_EMPTY = "empty"


@dataclass
class Item:
    kind: str
    flags: int = 0
    slot: int = -1
    text: bytes = b""       # page body (no trailing NULs) or one string
    nul: int = 0            # trailing NUL bytes of a page text, kept for an exact rebuild
    codes: bytes = b""      # page code list
    raw: bytes = b""        # bytes of a raw slot


@dataclass
class Table:
    name: str               # e.g. "bank_1A/entry_0000" or "bank_1C/sub_0002"
    layout: str             # "pages" or "strings"
    items: List[Item] = field(default_factory=list)
    slot_count: int = 0     # slots in the container (pages layout only)


def _entry_table(bank_index: int, entry_index: int, container: bytes) -> Table:
    table = Table(name=f"bank_{bank_index:02X}/entry_{entry_index:04d}", layout="pages",
                  slot_count=len(containers.parse_container(container)))
    for index, slot in enumerate(containers.parse_container(container)):
        if slot.empty:
            table.items.append(Item(kind=KIND_EMPTY, flags=slot.flags, slot=index))
            continue
        payload = slot.payload()
        page = book_pages.parse_page(payload)
        if page is None:
            table.items.append(Item(kind=KIND_RAW, flags=slot.flags, slot=index, raw=payload))
            continue
        body = book_pages.page_text(page.text)
        table.items.append(Item(kind=KIND_PAGE, flags=slot.flags, slot=index, text=body,
                                nul=len(page.text) - len(body), codes=page.codes))
    return table


def _sub_table(holder_index: int, sub_index: int, payload: bytes, flags: int) -> Table:
    table = Table(name=f"bank_{holder_index:02X}/sub_{sub_index:04d}", layout="strings")
    for piece in payload.split(b"\x00"):
        table.items.append(Item(kind=KIND_STRING, flags=flags, slot=sub_index, text=piece))
    return table


def extract(rom: bytes) -> List[Table]:
    """Every editable table of the ROM, in bank order."""
    banks = {bank.index: bank for bank in na.parse_banks(rom)}
    out: List[Table] = []
    book = bytes(rom[banks[BOOK_BANK].start:banks[BOOK_BANK].end])
    for entry_index, slot in enumerate(containers.parse_container(book)):
        if slot.empty:
            continue
        out.append(_entry_table(BOOK_BANK, entry_index, slot.stored))
    holder_bank = bytes(rom[banks[SUB_HOLDER_BANK].start:banks[SUB_HOLDER_BANK].end])
    holder = containers.parse_container(holder_bank)[0]
    for sub_index, sub in enumerate(containers.parse_container(holder.stored)):
        if sub.empty:
            continue
        out.append(_sub_table(SUB_HOLDER_BANK, sub_index, sub.payload(), sub.flags))
    return out


def table_to_json(table: Table, font_block: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    items: List[Dict[str, Any]] = []
    for item in table.items:
        row: Dict[str, Any] = {"kind": item.kind, "flags": item.flags}
        if table.layout == "pages":
            row["slot"] = item.slot
        if item.kind == KIND_PAGE:
            row["text"] = text_blocks.bytes_to_string(item.text)
            row["nul"] = item.nul
            row["codes"] = binascii.hexlify(item.codes).decode("ascii")
        elif item.kind == KIND_STRING:
            row["text"] = text_blocks.bytes_to_string(item.text)
        elif item.kind == KIND_RAW:
            row["hex"] = binascii.hexlify(item.raw).decode("ascii")
        items.append(row)
    out: Dict[str, Any] = {"format": FORMAT_ID, "source": table.name, "layout": table.layout,
                           "slot_count": table.slot_count, "items": items}
    if font_block is not None:
        out["font"] = font_block
    return out


def table_from_json(obj: Dict[str, Any]) -> Table:
    if obj.get("format") != FORMAT_ID:
        raise ValueError("not a Conker text table of this version")
    layout = obj["layout"]
    table = Table(name=obj["source"], layout=layout, slot_count=int(obj.get("slot_count", 0)))
    for row in obj["items"]:
        kind = row["kind"]
        slot = int(row.get("slot", -1))
        flags = int(row.get("flags", 0))
        if kind == KIND_PAGE:
            table.items.append(Item(kind=kind, flags=flags, slot=slot,
                                    text=text_blocks.string_to_bytes(row["text"]),
                                    nul=int(row["nul"]), codes=binascii.unhexlify(row["codes"])))
        elif kind == KIND_STRING:
            table.items.append(Item(kind=kind, flags=flags, slot=slot,
                                    text=text_blocks.string_to_bytes(row["text"])))
        elif kind == KIND_RAW:
            table.items.append(Item(kind=kind, flags=flags, slot=slot, raw=binascii.unhexlify(row["hex"])))
        elif kind == KIND_EMPTY:
            table.items.append(Item(kind=kind, flags=flags, slot=slot))
        else:
            raise ValueError(f"unknown item kind {kind!r}")
    return table


def text_items(table: Table) -> List[Item]:
    """The items a translator edits, in order."""
    return [item for item in table.items if item.kind in (KIND_PAGE, KIND_STRING)]


def _page_payload(item: Item) -> bytes:
    text = item.text + b"\x00" * max(item.nul, 1)
    return book_pages.Page(text=text, codes=item.codes).payload()


def _entry_container(original: bytes, table: Table) -> Optional[bytes]:
    """The rebuilt entry container, or None when no page changed."""
    slots = containers.parse_container(original)
    if len(slots) != table.slot_count:
        raise ValueError(f"{table.name} has {len(slots)} slots, the table has {table.slot_count}")
    changed = False
    new_slots: List[Slot] = list(slots)
    for item in table.items:
        if item.kind != KIND_PAGE:
            continue
        old = slots[item.slot]
        payload = _page_payload(item)
        if payload == old.payload():
            continue
        new_slots[item.slot] = containers.raw_slot(payload, old.flags)
        changed = True
    return containers.build_container(new_slots) if changed else None


def _holder_container(original: bytes, table: Table, sub_index: int) -> Optional[bytes]:
    """The rebuilt holder container for one changed sub-table, or None when that sub-table did not change."""
    subs = containers.parse_container(original)
    old = subs[sub_index]
    pieces = [item.text for item in table.items if item.kind == KIND_STRING]
    if any(b"\x00" in piece for piece in pieces):
        raise ValueError(f"{table.name} has a NUL byte inside a string")
    strings = b"\x00".join(pieces)
    if strings == old.payload():
        return None
    new_subs = list(subs)
    new_subs[sub_index] = containers.raw_slot(strings, old.flags)
    return containers.build_container(new_subs)


def rebuild(rom: bytes, tables: List[Table]) -> Dict[int, bytes]:
    """New bytes of each bank that an edited table changes. The caller relays the banks out with ``rom_layout``."""
    banks = {bank.index: bank for bank in na.parse_banks(rom)}
    book_bank = bytes(rom[banks[BOOK_BANK].start:banks[BOOK_BANK].end])
    holder_bank = bytes(rom[banks[SUB_HOLDER_BANK].start:banks[SUB_HOLDER_BANK].end])
    book_slots = containers.parse_container(book_bank)
    holder_slot = containers.parse_container(holder_bank)[0]
    book_current = {index: slot.stored for index, slot in enumerate(book_slots)}
    holder_current = holder_slot.stored
    book_changed: set = set()
    holder_changed = False
    for table in tables:
        if table.name.startswith(f"bank_{BOOK_BANK:02X}/entry_"):
            entry = int(table.name.rsplit("_", 1)[1])
            rebuilt = _entry_container(book_current[entry], table)
            if rebuilt is not None:
                book_current[entry] = rebuilt
                book_changed.add(entry)
        elif table.name.startswith(f"bank_{SUB_HOLDER_BANK:02X}/sub_"):
            sub = int(table.name.rsplit("_", 1)[1])
            rebuilt = _holder_container(holder_current, table, sub)
            if rebuilt is not None:
                holder_current = rebuilt
                holder_changed = True
    out: Dict[int, bytes] = {}
    if book_changed:
        out[BOOK_BANK] = containers.build_container([
            containers.raw_slot(book_current[i], slot.flags) if i in book_changed else slot
            for i, slot in enumerate(book_slots)])
    if holder_changed:
        holder_new = containers.raw_slot(holder_current, holder_slot.flags)
        out[SUB_HOLDER_BANK] = containers.build_container(
            [holder_new] + containers.parse_container(holder_bank)[1:])
    return out
