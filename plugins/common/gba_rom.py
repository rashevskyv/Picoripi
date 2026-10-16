"""GBA cartridge helpers: the header complement, the pointer index and the relocation of data into free space.

A GBA ROM maps its file at 0x08000000. A pointer is the 4-byte little-endian address. The index finds every
4-byte value that points into the ROM, at any byte offset, because bytecode can hold unaligned pointers.
"""
from __future__ import annotations

import re
from typing import Dict, List, Tuple

from core.i18n import tr

ROM_BASE = 0x08000000
MAX_ROM = 0x02000000          # 32 MB, the largest GBA cartridge; a relocated text may grow the file up to it
COMPLEMENT_AT = 0xBD

class RomError(ValueError):
    """A ROM cannot take the change: no room, or a pointer that cannot be rewritten."""

def header_complement(rom: bytes) -> int:
    """The value the BIOS checks at 0xBD: ``-(sum(0xA0..0xBC) + 0x19) & 0xFF``."""
    total = sum(rom[0xA0:0xBD])
    return (-(total + 0x19)) & 0xFF

def fix_header(rom: bytearray) -> None:
    """Write the header complement. An unchanged header gives the same byte (checked by the tests)."""
    rom[COMPLEMENT_AT] = header_complement(rom)

def pointer_index(rom: bytes) -> Dict[int, List[int]]:
    """Every 4-byte value in the ROM range, at any offset, that is a ROM address: ``value -> offsets``."""
    index: Dict[int, List[int]] = {}
    # A ROM pointer ends, in little-endian order, with the byte 0x08 or 0x09: only those bytes need a look.
    for match in re.finditer(rb"[\x08\x09]", rom):
        at = match.start()
        if at < 3:
            continue
        value = int.from_bytes(rom[at - 3:at + 1], "little")
        if ROM_BASE <= value < ROM_BASE + MAX_ROM:
            index.setdefault(value, []).append(at - 3)
    return index

def free_start(rom_end_address: int) -> int:
    """The first free file offset after the linked data (an absolute address), aligned to 4 bytes."""
    return ((rom_end_address - ROM_BASE) + 3) & ~3

class Relocator:
    """Places new bytes in free space and rewrites the pointers that point at a moved block.

    ``rom`` is a bytearray that the caller owns; ``index`` comes from ``pointer_index`` on the ROM before any change.
    ``floor`` is the file offset where free space starts (``free_start`` of the linked data).
    """

    def __init__(self, rom: bytearray, index: Dict[int, List[int]], floor: int) -> None:
        self.rom = rom
        self.index = index
        self.cursor = floor
        self.moved: List[Tuple[int, int, int]] = []    # (old offset, new offset, size)

    def _grow(self, end: int) -> None:
        if end > MAX_ROM:
            raise RomError(tr("The ROM has no free space left for the longer text."))
        if end > len(self.rom):
            self.rom.extend(b"\xff" * (end - len(self.rom)))

    def place(self, data: bytes) -> int:
        """Copy ``data`` to the next free 4-byte aligned place and return its file offset."""
        start = (self.cursor + 3) & ~3
        self._grow(start + len(data))
        self.rom[start:start + len(data)] = data
        self.cursor = start + len(data)
        return start

    def move(self, old: int, old_size: int, data: bytes) -> int:
        """Move a block of ``old_size`` bytes at file offset ``old`` to a new place holding ``data``.

        Pointers to the old address are rewritten to the new one. The old bytes become 0xFF.
        """
        old_address = ROM_BASE + old
        pointers = self.index.get(old_address, [])
        if not pointers:
            # Nothing points at this block, so a moved copy could never be read: refuse instead of losing the text.
            raise RomError(tr("This message is not used through a pointer, so it cannot move. Keep it within its original length."))
        new = self.place(data)
        new_address = ROM_BASE + new
        for at in pointers:
            self.rom[at:at + 4] = new_address.to_bytes(4, "little")
        self.rom[old:old + old_size] = b"\xff" * old_size
        self.moved.append((old, new, old_size))
        return new

def write_in_place(rom: bytearray, offset: int, old_size: int, data: bytes) -> None:
    """Write ``data`` over a block of ``old_size`` bytes; the rest of the block becomes 0xFF."""
    if len(data) > old_size:
        raise RomError("The text does not fit in place.")
    rom[offset:offset + old_size] = data + b"\xff" * (old_size - len(data))
