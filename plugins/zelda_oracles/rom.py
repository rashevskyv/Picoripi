"""ROM identity and the data layout of Oracle of Ages and Oracle of Seasons (USA, 1 MB).

Only the USA release is supported: the Oracles PC port accepts only the USA SHA-1 values, and the
other ROMs on disk (EU 2 MB, hacks) have different layouts.

Offsets are file offsets into the ROM image. The text pointer tables and their index split follow
the public disassembly (text/info.txt, tools/dump/dumpText.py); the message font is 256 glyph cells
of 16 bytes each, found at 0x70720 for Ages (the disassembly places gfx_font at 0x70800 after 14
blank glyphs).
"""
from __future__ import annotations

import hashlib
from typing import Optional
from dataclasses import dataclass

ROM_SIZE = 0x100000
BANK_SIZE = 0x4000


@dataclass(frozen=True)
class GameLayout:
    """Where one game keeps its text pointer tables and its message font."""

    key: str
    sha1: str
    # Three-byte bank pointers (16-bit pointer, then bank) to the two text base addresses.
    text_base1_table: int
    text_base2_table: int
    # Reversed three-byte pointer (16-bit pointer, then bank) to the text index table.
    language_table: int
    # Index (high byte) where the second text base starts.
    text_base2_index_start: int
    # Size of the last index group, which the disassembly hard-codes.
    last_group_size: int
    # Glyph cell 0 of the message font (cell n = 16 bytes at font_offset + 16 * n); None when not checked.
    font_offset: Optional[int]
    # European (and Russian-hack) ROMs have a third text base. Language k uses the pointer entries
    # at table + 4 * k (bases) and language_table + 3 * k (index table).
    text_base3_table: Optional[int] = None
    text_base3_index_start: Optional[int] = None


AGES_US = GameLayout(
    key="ages",
    sha1="880374fb978b18af4aa529e2e32f7ffb4d7dd2f4",
    text_base1_table=0xFCFB3,
    text_base2_table=0xFCFCB,
    language_table=0xFCFE3,
    text_base2_index_start=0x2C,
    last_group_size=0x16,
    font_offset=0x70720,
)

SEASONS_US = GameLayout(
    key="seasons",
    sha1="ba1268290fb2b1b70505d2d7b5825fc8a4816a4b",
    text_base1_table=0xFCFE2,
    text_base2_table=0xFCFFA,
    language_table=0xFD012,
    text_base2_index_start=0x2C,
    last_group_size=0x1D,
    font_offset=0x70720,
)

# European ROMs (2 MB, region 'P'), reference only: the port does not accept them.
AGES_EU = GameLayout(
    key="ages-eu",
    sha1="9f2dff3c46406839f839a8d535353dfc1e3e8670",
    text_base1_table=0xFCFD9,
    text_base2_table=0xFCFED,
    language_table=0xFD015,
    text_base2_index_start=0x1A,
    last_group_size=0x16,
    font_offset=None,
    text_base3_table=0xFD001,
    text_base3_index_start=0x34,
)

SEASONS_EU = GameLayout(
    key="seasons-eu",
    sha1="360b9408e569ba826212eac1ebea1b09573cb48c",
    text_base1_table=0xFD008,
    text_base2_table=0xFD01C,
    language_table=0xFD044,
    text_base2_index_start=0x1A,
    last_group_size=0x1D,
    font_offset=None,
    text_base3_table=0xFD030,
    text_base3_index_start=0x34,
)

LAYOUTS = {layout.sha1: layout for layout in (AGES_US, SEASONS_US)}
REFERENCE_LAYOUTS = {layout.sha1: layout for layout in (AGES_EU, SEASONS_EU)}

# Hacks of the Russian translation (ZELDA64RUS, 2 MB): the English slot (language 0) is unchanged,
# and languages 1-4 carry the Russian text. Their layout is the European one.
RUSSIAN_HACK_SHA1 = {
    "0a701aae2ea2": AGES_EU,
    "eaaba63fefd9": SEASONS_EU,
}


def identify_reference(rom: bytes) -> GameLayout:
    """Layout of an EU ROM or a Russian hack (2 MB), for reference columns only."""
    if len(rom) != 2 * ROM_SIZE:
        raise UnknownRom(f"reference ROM has {len(rom)} bytes, expected {2 * ROM_SIZE}")
    digest = sha1_hex(rom)
    layout = REFERENCE_LAYOUTS.get(digest)
    if layout is None:
        layout = RUSSIAN_HACK_SHA1.get(digest[:12])
    if layout is None:
        raise UnknownRom("ROM is not an Oracle of Ages / Seasons EU or Russian-hack reference")
    return layout


class UnknownRom(ValueError):
    """The bytes are not a USA Oracle of Ages or Oracle of Seasons ROM."""


def sha1_hex(rom: bytes) -> str:
    return hashlib.sha1(rom).hexdigest()


def identify(rom: bytes) -> GameLayout:
    """Return the layout of a USA Oracle ROM, or raise UnknownRom."""
    if len(rom) != ROM_SIZE:
        raise UnknownRom(f"ROM has {len(rom)} bytes, expected {ROM_SIZE}")
    layout = LAYOUTS.get(sha1_hex(rom))
    if layout is None:
        raise UnknownRom("ROM is not the USA Oracle of Ages or Oracle of Seasons (SHA-1 mismatch)")
    return layout


def read16(rom: bytes, index: int) -> int:
    return rom[index] | (rom[index + 1] << 8)


def banked_address(bank: int, pos: int) -> int:
    return bank * BANK_SIZE + (pos & 0x3FFF)


def read_bank_pointer(rom: bytes, index: int) -> int:
    """Bank byte first, then the 16-bit pointer."""
    return banked_address(rom[index], read16(rom, index + 1))


def read_reversed_bank_pointer(rom: bytes, index: int) -> int:
    """16-bit pointer first, then the bank byte."""
    return banked_address(rom[index + 2], read16(rom, index))
