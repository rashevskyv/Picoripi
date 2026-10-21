"""Talk-bubble dialogue of Conker's Bad Fur Day: bank 0x06, nested containers, text leaves.

Bank 0x06 is a bank of raw entries. Each entry is a container; each of its slots is a container of leaves; a leaf
is one talk exchange. A text leaf holds pages separated by 0xBD (one bubble each) and ends with NUL padding. Other
leaves are binary and stay as they are.

``extract`` reads a ROM and returns one ``Table`` per entry. A table item is one page of a text leaf; ``nul`` is the
count of trailing NUL bytes of its leaf (kept for an exact rebuild). ``rebuild`` applies the edited pages to the
original ROM bytes and returns the new bank. Containers are rebuilt bottom-up; unchanged slots keep their bytes.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple

from . import containers, n64_archive as na, text_blocks
from .containers import Slot

FORMAT_ID = "conker-bfd-dialogue/1"
BANK = 0x06
PAGE_SEPARATOR = 0x0BD
MAX_DEPTH = 4
_LETTER = re.compile(rb"[A-Za-z]")


@dataclass
class Page:
    path: Tuple[int, ...]   # slot path of the leaf inside the entry
    index: int              # page number inside the leaf
    nul: int                # trailing NUL bytes of the leaf (same for every page of the leaf)
    text: bytes             # page bytes (no separator)


@dataclass
class Table:
    name: str               # "bank_06/entry_0041"
    pages: List[Page] = field(default_factory=list)


def is_text_leaf(body: bytes) -> bool:
    """A leaf is dialogue when it has letters, no NUL inside, mostly plain bytes and a space or line break."""
    if len(body) < 4 or b"\x00" in body:
        return False
    if len(_LETTER.findall(body)) < 4 or not (b" " in body or b"\n" in body):
        return False
    plain = sum(1 for b in body if 0x20 <= b <= 0x7E or b in (0x0A, PAGE_SEPARATOR))
    return plain * 10 >= len(body) * 7


def _leaves(data: bytes, path: Tuple[int, ...], depth: int, out: List[Tuple[Tuple[int, ...], bytes]]) -> None:
    """Walk containers; every leaf is (path, bytes). A container is a slot table with at least one slot."""
    if depth < MAX_DEPTH:
        try:
            slots = containers.parse_container(data)
        except na.RomError:
            slots = None
        if slots is not None and any(not s.empty for s in slots):
            for index, slot in enumerate(slots):
                if not slot.empty:
                    _leaves(slot.payload(), path + (index,), depth + 1, out)
            return
    out.append((path, data))


def leaves_of(entry: bytes) -> List[Tuple[Tuple[int, ...], bytes]]:
    out: List[Tuple[Tuple[int, ...], bytes]] = []
    _leaves(entry, (), 0, out)
    return out


def _split_text(data: bytes) -> Optional[Tuple[int, List[bytes]]]:
    """(trailing NUL count, page texts) for a text leaf, or None for a binary leaf."""
    body = data.rstrip(b"\x00")
    if not is_text_leaf(body):
        return None
    return len(data) - len(body), body.split(bytes([PAGE_SEPARATOR]))


def extract(rom: bytes) -> List[Table]:
    """One table per non-empty bank 0x06 entry. Items keep the order of the leaves and their pages."""
    bank = {b.index: b for b in na.parse_banks(rom)}[BANK]
    out: List[Table] = []
    for entry in na.parse_entries(rom, bank):
        raw = na.read_entry(rom, entry)
        table = Table(name=f"bank_{BANK:02X}/entry_{entry.index:04d}")
        for path, data in leaves_of(raw):
            split = _split_text(data)
            if split is None:
                continue
            nul, texts = split
            for index, text in enumerate(texts):
                table.pages.append(Page(path=path, index=index, nul=nul, text=text))
        if table.pages:
            out.append(table)
    return out


def table_to_json(table: Table, font_block: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    out: Dict[str, Any] = {"format": FORMAT_ID, "source": table.name,
                           "items": [{"path": ".".join(str(i) for i in p.path), "page": p.index, "nul": p.nul,
                                      "text": text_blocks.bytes_to_string(p.text)} for p in table.pages]}
    if font_block is not None:
        out["font"] = font_block
    return out


def page_error(text: bytes) -> bool:
    """True when a page holds a NUL or the page separator: either would split the leaf on rebuild."""
    return b"\x00" in text or bytes([PAGE_SEPARATOR]) in text


def table_from_json(obj: Dict[str, Any]) -> Table:
    if obj.get("format") != FORMAT_ID:
        raise ValueError("not a Conker dialogue table of this version")
    table = Table(name=obj["source"])
    for row in obj["items"]:
        path = tuple(int(part) for part in str(row["path"]).split(".") if part != "")
        table.pages.append(Page(path=path, index=int(row["page"]), nul=int(row["nul"]),
                                text=text_blocks.string_to_bytes(row["text"])))
    return table


def _rebuild_entry(data: bytes, table: Table) -> Optional[bytes]:
    """The entry with its edited pages, or None when no page changed."""
    edited: Dict[Tuple[int, ...], Dict[int, bytes]] = {}
    for page in table.pages:
        edited.setdefault(page.path, {})[page.index] = page.text
    if not edited:
        return None
    rebuilt = _rebuild_node(data, (), edited, 0)
    return rebuilt if rebuilt != data else None


def _rebuild_node(data: bytes, path: Tuple[int, ...], edited: Dict[Tuple[int, ...], Dict[int, bytes]],
                  depth: int) -> bytes:
    if depth < MAX_DEPTH and not _is_leaf(data, depth):
        slots = containers.parse_container(data)
        new_slots: List[Slot] = list(slots)
        changed = False
        for index, slot in enumerate(slots):
            if slot.empty:
                continue
            child_path = path + (index,)
            child = slot.payload()
            new_child = _rebuild_node(child, child_path, edited, depth + 1)
            if new_child != child:
                new_slots[index] = _slot_for(slot, new_child)
                changed = True
        return containers.build_container(new_slots) if changed else data
    if path in edited:
        split = _split_text(data)
        if split is None:
            raise ValueError(f"leaf {path} is not dialogue text")
        nul, texts = split
        pages = edited[path]
        new_texts = [pages.get(index, text) for index, text in enumerate(texts)]
        if any(page_error(text) for text in new_texts):
            raise ValueError(f"leaf {path} has a NUL or a separator inside a page")
        body = bytes([PAGE_SEPARATOR]).join(new_texts)
        return body + b"\x00" * nul
    return data


def _is_leaf(data: bytes, depth: int) -> bool:
    try:
        slots = containers.parse_container(data)
    except na.RomError:
        return True
    return not any(not s.empty for s in slots)


def _fit(new: Slot, old: Slot) -> Slot:
    """Pad a rebuilt blob with zeros to the old stored length when it fits, so later offsets do not move.

    A saved game keeps the old offsets in RAM; a longer blob moves every blob after it. The zeros after a deflate
    stream are ignored by the container reader (same rule as the code chunks). Longer blobs grow the bank.
    """
    if len(new.stored) <= len(old.stored):
        return Slot(flags=new.flags, stored=new.stored + b"\x00" * (len(old.stored) - len(new.stored)))
    return new


def _slot_for(old: Slot, payload: bytes) -> Slot:
    """A slot that holds ``payload`` with the old flags. An RZIP slot is encoded again (level 9)."""
    new = containers.rzip_slot(payload, old.flags) if old.rzip else containers.raw_slot(payload, old.flags)
    return _fit(new, old)


def rebuild(rom: bytes, tables: List[Table]) -> Dict[int, bytes]:
    """New bytes of bank 0x06 when an edited table changes it. Empty when nothing changed."""
    bank_info = {b.index: b for b in na.parse_banks(rom)}[BANK]
    slots = containers.parse_container(bytes(rom[bank_info.start:bank_info.end]))
    changed = False
    new_slots = list(slots)
    for table in tables:
        if not table.name.startswith(f"bank_{BANK:02X}/entry_"):
            continue
        index = int(table.name.rsplit("_", 1)[1])
        old = slots[index]
        rebuilt = _rebuild_entry(old.stored, table)
        if rebuilt is None:
            continue
        new_slots[index] = _fit(Slot(flags=old.flags, stored=rebuilt), old)
        changed = True
    return {BANK: containers.build_container(new_slots)} if changed else {}
