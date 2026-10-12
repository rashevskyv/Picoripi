"""Identity and dialog table layout of Link's Awakening DX (Game Boy Color, English v1.0, 1 MB).

Offsets are file offsets into the ROM image. Facts checked against the public LADX-Disassembly
(src/code/home/dialog.asm, src/text/dialog_*.asm) and against the ROM bytes:

- The dialog pointer table starts at GB 0x4001 of bank 0x1C (file 0x70001). Index n has a 16-bit
  little-endian pointer at 0x70001 + 2 * n.
- A bank table follows at GB 0x4741 (file 0x70741): one byte per index. The game masks it with
  0x3F, so the code keeps the raw byte and only reads the low six bits.
- Index n is the dialog ``Dialog<n in hex, 3 digits>``. Indices 0x000-0x2AF are dialogs. Entries
  after that do not resolve to text and are not read.
"""
from __future__ import annotations

import hashlib
from dataclasses import dataclass

ROM_SIZE = 0x100000
BANK_SIZE = 0x4000
SWITCHABLE_BASE = 0x4000

# English v1.0 (LADX-Disassembly ladx.md5: azle.gbc).
DX_EN_V1_0_SHA1 = "d90ac17e9bf17b6c61624ad9f05447bdb5efc01a"

POINTER_TABLE = 0x70001  # GB 0x4001 in bank 0x1C
BANK_TABLE = 0x70741  # GB 0x4741 in bank 0x1C
DIALOG_COUNT = 0x2B0  # indices 0x000-0x2AF


class UnknownRom(ValueError):
    """The bytes are not the English v1.0 Link's Awakening DX ROM."""


def dialog_name(index: int) -> str:
    """The disassembly label of a dialog index, e.g. ``Dialog24E``."""
    return f"Dialog{index:03X}"


@dataclass(frozen=True)
class DialogRef:
    """Where one dialog index lives in the ROM."""

    index: int
    pointer: int  # GB address in 0x4000-0x7FFF
    bank_byte: int  # raw byte from the bank table
    rom: int  # file offset of the first byte of text

    @property
    def bank(self) -> int:
        return self.bank_byte & 0x3F

    @property
    def name(self) -> str:
        return dialog_name(self.index)


def sha1_hex(rom: bytes) -> str:
    return hashlib.sha1(rom).hexdigest()


def identify(rom: bytes) -> None:
    """Raise UnknownRom unless the bytes are the English v1.0 DX ROM."""
    if len(rom) != ROM_SIZE:
        raise UnknownRom(f"ROM has {len(rom)} bytes, expected {ROM_SIZE}")
    if sha1_hex(rom) != DX_EN_V1_0_SHA1:
        raise UnknownRom("ROM is not Link's Awakening DX English v1.0 (SHA-1 mismatch)")


def read_dialog_refs(rom: bytes) -> list[DialogRef]:
    """Resolve every dialog index to its file offset. Pure function over the ROM bytes."""
    refs = []
    for index in range(DIALOG_COUNT):
        at = POINTER_TABLE + 2 * index
        pointer = rom[at] | (rom[at + 1] << 8)
        if not SWITCHABLE_BASE <= pointer < 2 * SWITCHABLE_BASE:
            raise ValueError(f"{dialog_name(index)}: pointer 0x{pointer:04X} is outside the switchable bank")
        bank_byte = rom[BANK_TABLE + index]
        offset = (bank_byte & 0x3F) * BANK_SIZE + (pointer - SWITCHABLE_BASE)
        refs.append(DialogRef(index=index, pointer=pointer, bank_byte=bank_byte, rom=offset))
    return refs
