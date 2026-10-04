"""N64 ROMs of the Zelda 64 engine (OoT, MM): byte order, the dmadata file table, file swap, header CRC.

A replaced file keeps its place when it still fits, else it is appended after
the last used byte; only its dmadata entry changes, nothing else moves.  The
boot CRC covers 0x1000-0x101000, which holds dmadata, so it is recomputed.
"""
from __future__ import annotations

import struct
import zlib
from typing import Dict, List, Optional, Tuple

from core.containers import yaz0

_MASK = 0xFFFFFFFF
_DMADATA_START = bytes.fromhex("00000000000010600000000000000000")
# CIC chip, found by the CRC32 of the boot code -> CRC seed.
_CIC_BY_BOOT_CRC = {0x6170A4A1: 6101, 0x90BB6CB5: 6102, 0x0B050EE0: 6103, 0x98BC2C86: 6105, 0xACC8580A: 6106}
_CIC_SEED = {6101: 0xF8CA4DDC, 6102: 0xF8CA4DDC, 6103: 0xA3886759, 6105: 0xDF26F436, 6106: 0x1FEA617A}

DmaEntry = Tuple[int, int, int, int]  # vrom start, vrom end, rom start, rom end (0 = uncompressed)


def to_big_endian(data: bytes) -> bytes:
    """Return a .z64 (big-endian) image from a .z64, .v64 (byte-swapped) or .n64 (little-endian) one."""
    magic = data[:4]
    if magic == b"\x80\x37\x12\x40":
        return bytes(data)
    out = bytearray(data)
    if magic == b"\x37\x80\x40\x12":
        out[0::2], out[1::2] = data[1::2], data[0::2]
        return bytes(out)
    if magic == b"\x40\x12\x37\x80":
        for i in range(4):
            out[i::4] = data[3 - i::4]
        return bytes(out)
    raise ValueError("Not an N64 ROM image")


def _rol(value: int, bits: int) -> int:
    return ((value << bits) | (value >> (32 - bits))) & _MASK


def compute_crc(rom: bytes) -> Tuple[int, int]:
    """The two header checksums (offsets 0x10 and 0x14) the boot code verifies."""
    cic = _CIC_BY_BOOT_CRC.get(zlib.crc32(rom[0x40:0x1000]), 6102)
    t1 = t2 = t3 = t4 = t5 = t6 = _CIC_SEED[cic]
    words = struct.unpack_from(">262144I", rom, 0x1000)
    boot = rom[0x750:0x850]
    for index, d in enumerate(words):
        if (t6 + d) & _MASK < t6:
            t4 = (t4 + 1) & _MASK
        t6 = (t6 + d) & _MASK
        t3 ^= d
        r = _rol(d, d & 0x1F)
        t5 = (t5 + r) & _MASK
        t2 = t2 ^ r if t2 > d else t2 ^ t6 ^ d
        if cic == 6105:
            k = (index * 4) & 0xFF
            t1 = (t1 + (struct.unpack_from(">I", boot, k)[0] ^ d)) & _MASK
        else:
            t1 = (t1 + (t5 ^ d)) & _MASK
    if cic == 6103:
        return ((t6 ^ t4) + t3) & _MASK, ((t5 ^ t2) + t1) & _MASK
    if cic == 6106:
        return ((t6 * t4) + t3) & _MASK, ((t5 * t2) + t1) & _MASK
    return t6 ^ t4 ^ t3, t5 ^ t2 ^ t1


def retarget_constant(code: bytes, old: int, new: int, expected: int) -> bytes:
    """Rewrite every ``lui`` + ``addiu``/``ori`` pair that builds ``old`` so it builds ``new``.

    MIPS code loads a 32-bit address in two halves; ``addiu`` sign-extends its
    half, so the upper half is rounded.  Refuses unless exactly ``expected``
    pairs are found, so a different build cannot be patched blindly.
    """
    out = bytearray(code)
    old_hi, old_lo = ((old + 0x8000) >> 16) & 0xFFFF, old & 0xFFFF
    count = len(code) // 4
    found = 0
    for i in range(count):
        word = struct.unpack_from(">I", code, i * 4)[0]
        if word >> 26 != 0x0F:
            continue
        rt = (word >> 16) & 0x1F
        for j in range(i + 1, min(i + 16, count)):
            low = struct.unpack_from(">I", code, j * 4)[0]
            op = low >> 26
            if op in (0x09, 0x0D) and (low >> 21) & 0x1F == rt and low & 0xFFFF == old_lo:
                hi_old = old_hi if op == 0x09 else old >> 16
                if word & 0xFFFF != hi_old:
                    break
                hi_new = ((new + 0x8000) >> 16) & 0xFFFF if op == 0x09 else new >> 16
                struct.pack_into(">I", out, i * 4, (word & 0xFFFF0000) | hi_new)
                struct.pack_into(">I", out, j * 4, (low & 0xFFFF0000) | (new & 0xFFFF))
                found += 1
                break
    if found != expected:
        raise ValueError(f"Found {found} references to {old:#x}, expected {expected}")
    return bytes(out)


class N64Rom:
    """A big-endian Zelda 64 ROM with its dmadata table."""

    def __init__(self, data: bytes):
        self.data = bytearray(to_big_endian(data))
        self.dmadata_offset = self.data.find(_DMADATA_START)
        if self.dmadata_offset < 0:
            raise ValueError("No dmadata table: not a Zelda 64 ROM")
        self.files: List[DmaEntry] = []
        offset = self.dmadata_offset
        while True:
            entry = struct.unpack_from(">IIII", self.data, offset)
            if not any(entry):
                break
            self.files.append(entry)
            offset += 16

    def read_file(self, index: int) -> bytes:
        """The decompressed contents of dmadata file ``index``."""
        vstart, vend, pstart, pend = self.files[index]
        if pstart == _MASK:
            raise ValueError(f"File {index} is not present in this ROM")
        if pend == 0:
            return bytes(self.data[pstart:pstart + (vend - vstart)])
        return yaz0.decompress(bytes(self.data[pstart:pend]))

    def free_vrom(self) -> int:
        """The first virtual address after every file: room for a file that outgrew its range."""
        return (max(entry[1] for entry in self.files) + 0xF) & ~0xF

    def file_capacity(self, index: int) -> int:
        """Bytes file ``index`` may grow to without overlapping the next file's virtual range."""
        vstart = self.files[index][0]
        later = [entry[0] for entry in self.files if entry[0] > vstart]
        return (min(later) if later else self.files[index][1]) - vstart

    def replace_files(self, contents: Dict[int, bytes], new_vrom: Optional[Dict[int, int]] = None) -> bytes:
        """A new ROM image with these files replaced; CRC updated.

        A file that was Yaz0-compressed is compressed again.  It stays where it
        was if it still fits there; otherwise it goes after the last used byte.
        ``new_vrom`` gives a file a new virtual start (``free_vrom()``); the
        caller patches the code that addresses it (``retarget_constant``).
        """
        new_vrom = new_vrom or {}
        rom = bytearray(self.data)
        used = max(entry[3] or entry[2] + (entry[1] - entry[0])
                   for entry in self.files if entry[2] != _MASK)
        cursor = (used + 0xF) & ~0xF
        for index, payload in sorted(contents.items()):
            vstart, vend, pstart, pend = self.files[index]
            slot = (pend or pstart + (vend - vstart)) - pstart
            if index in new_vrom:
                if new_vrom[index] < self.free_vrom():
                    raise ValueError(f"New virtual start {new_vrom[index]:#x} overlaps other files")
                vstart = new_vrom[index]
            elif len(payload) > self.file_capacity(index):
                raise ValueError(f"File {index} is {len(payload):#x} bytes; it has room for "
                                 f"{self.file_capacity(index):#x}")
            stored = yaz0.compress(payload) if pend else payload
            if len(stored) <= slot:
                start = pstart
                rom[start:start + slot] = stored + b"\0" * (slot - len(stored))
            else:
                start = cursor
                cursor = (start + len(stored) + 0xF) & ~0xF
                if start + len(stored) > len(rom):
                    rom.extend(b"\0" * (start + len(stored) - len(rom)))
                rom[start:start + len(stored)] = stored
            struct.pack_into(">IIII", rom, self.dmadata_offset + index * 16,
                             vstart, vstart + len(payload), start, start + len(stored) if pend else 0)
        # Cartridge sizes are powers of two in practice; pad up to the next one.
        size = 1 << max(len(rom) - 1, 1).bit_length()
        rom.extend(b"\xff" * (size - len(rom)))
        struct.pack_into(">II", rom, 0x10, *compute_crc(bytes(rom)))
        return bytes(rom)
