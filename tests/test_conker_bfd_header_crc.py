"""Conker's Bad Fur Day N64 header checksum (CIC-6105): round trip, range, boot-table term. Synthetic bytes only."""
import random

import pytest

from plugins.conker_bfd import header_crc as hc, n64_archive as na

SIZE = 0x101000 + 0x1000


def _rom(seed=1):
    rng = random.Random(seed)
    rom = bytearray(rng.getrandbits(8) for _ in range(SIZE))
    return bytes(rom)


def test_fix_makes_the_header_valid_and_is_idempotent():
    rom = _rom()
    assert not hc.is_valid(rom)
    fixed = hc.fix(rom)
    assert hc.is_valid(fixed)
    assert hc.fix(fixed) == fixed


def test_a_byte_inside_the_range_changes_the_checksum_and_outside_does_not():
    rom = _rom()
    base = hc.compute(rom)
    inside = bytearray(rom)
    inside[0x1000 + 0x100] ^= 0x5A
    assert hc.compute(bytes(inside)) != base
    outside = bytearray(rom)
    outside[0x101000 + 0x100] ^= 0x5A          # past the checksummed range: the sums do not change
    assert hc.compute(bytes(outside)) == base


def test_the_boot_table_word_is_part_of_the_checksum():
    rom = _rom()
    base = hc.compute(rom)
    table = bytearray(rom)
    table[0x750 + 0x10] ^= 0xFF                 # a boot-code table byte read by the 6105 term
    assert hc.compute(bytes(table)) != base


def test_a_short_rom_is_refused():
    with pytest.raises(na.RomError):
        hc.compute(b"\x00" * 0x1000)
