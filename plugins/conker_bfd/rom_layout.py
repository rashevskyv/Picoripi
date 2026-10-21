"""Write changed asset banks into a Conker ROM: contiguous relayout from the first changed bank, outer records only.

Banks are stored in index order. When a bank grows, every bank from it to the last one is copied again, end to
end, from the same start, each padded to eight bytes. Nothing before that start moves. The outer table records of
the moved banks are rewritten; the table's first word and the flag nibbles stay as they are. The ROM keeps its
size: bytes after the new end are set to 0xFF, the padding the cartridge already had.
"""
from __future__ import annotations

import struct
from typing import Dict

from . import n64_archive as na
from .containers import align8

PAD = 0xFF


def _bank_bytes(rom: bytes, bank: na.AssetBank) -> bytes:
    return bytes(rom[bank.start:bank.end])


def relayout_banks(rom: bytes, changed: Dict[int, bytes], table_start: int = na.US_ASSET_TABLE) -> bytes:
    """Return a new ROM with the banks in ``changed`` replaced (index -> new bank bytes)."""
    if not changed:
        return bytes(rom)
    banks = na.parse_banks(rom, table_start)
    if max(changed) >= len(banks) or min(changed) < 0:
        raise na.RomError("a changed bank index is outside the asset table")
    first = min(changed)
    region_start = banks[first].start
    region_end = banks[-1].end
    out = bytearray(rom)
    out[region_start:region_end] = bytes([PAD]) * (region_end - region_start)
    cursor = region_start
    for bank in banks[first:]:
        content = changed.get(bank.index, _bank_bytes(rom, bank))
        if not content:
            raise na.RomError(f"bank {bank.index:02X} would be empty")
        if cursor + len(content) > len(rom):
            raise na.RomError("the edited banks do not fit in the ROM")
        out[cursor:cursor + len(content)] = content
        struct.pack_into(">II", out, table_start + bank.index * 8, cursor - table_start,
                         len(content) | (bank.flags << 28))
        cursor += align8(len(content))
    return bytes(out)
