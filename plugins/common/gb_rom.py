"""Game Boy ROM layout shared by the GB and GBC plugins: banks, header checksums and free space for moved blocks.

Bank 0 is the fixed window (file offsets 0x0000-0x3FFF). Bank N >= 1 is the switchable window: file offsets
N*0x4000 .. N*0x4000+0x3FFF, CPU addresses 0x4000-0x7FFF.
"""
from __future__ import annotations

from typing import Iterable, List, Optional, Sequence

BANK_SIZE = 0x4000
HEADER_SUM_RANGE = (0x134, 0x14D)       # the header checksum covers 0x134..0x14C
HEADER_SUM_AT = 0x14D
GLOBAL_SUM_AT = 0x14E                   # two bytes, big-endian, sum of every other byte


def offset_of(bank: int, cpu: int) -> int:
    """The file offset of a CPU address in a bank."""
    return cpu if bank == 0 else bank * BANK_SIZE + (cpu - BANK_SIZE)


def bank_of(offset: int) -> int:
    return offset // BANK_SIZE


def cpu_of(offset: int) -> int:
    """The CPU address of a file offset, in the window it is visible through."""
    return offset if offset < BANK_SIZE else BANK_SIZE + offset % BANK_SIZE


def fix_checksums(rom: bytearray) -> None:
    """Write the header checksum and the global checksum after a change."""
    total = 0
    for byte in rom[HEADER_SUM_RANGE[0]:HEADER_SUM_RANGE[1]]:
        total = (total - byte - 1) & 0xFF
    rom[HEADER_SUM_AT] = total
    rom[GLOBAL_SUM_AT] = rom[GLOBAL_SUM_AT + 1] = 0
    total = sum(rom) & 0xFFFF
    rom[GLOBAL_SUM_AT] = total >> 8
    rom[GLOBAL_SUM_AT + 1] = total & 0xFF


class FreeSpace:
    """Free runs ``[bank, start, end)`` of a ROM. ``take`` cuts the first run that fits and returns its start."""

    def __init__(self, runs: Iterable[Sequence[int]]) -> None:
        self.runs: List[List[int]] = [[int(bank), int(start), int(end)] for bank, start, end, *_ in runs]

    def take(self, size: int, banks: Optional[Sequence[int]] = None) -> Optional[int]:
        for run in self.runs:
            bank, start, end = run
            if banks is not None and bank not in banks:
                continue
            if end - start >= size:
                run[1] = start + size
                return start
        return None
