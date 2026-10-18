"""Conker's Bad Fur Day (N64, USA) ROM access: byte order, asset banks and RZIP entries.

Clean-room from the layout notes in the community decompilation's docs (MIT, read only; no code copied):
an RZIP entry is a big-endian u32 decoded length followed by a raw deflate stream. The asset table at a
fixed ROM offset holds 8-byte records (start relative to the table, size with a 4-bit flag nibble). Each
bank starts with an inner table of 8-byte records (start relative to the bank, length, type byte). Bit 0x10
of the type byte marks an RZIP entry; other entries are stored raw.
"""
from __future__ import annotations

import hashlib
import struct
import zlib
from dataclasses import dataclass
from typing import List, Tuple

US_SHA1 = "4cbadd3c4e0729dec46af64ad018050eada4f47a"
US_ASSET_TABLE = 0xAB1950
US_FONT_START = 0x40F10
US_FONT_END = 0x42450
US_GAME_DATA_START = 0x188328  # one RZIP entry: the game's data section
US_GAME_DATA_SIZE = 189088
US_GLYPH_MAP_OFFSET = 0x2E10  # 95 input-byte codes inside the decoded data section (RAM 0x80085930)
US_TITLE = b"CONKER BFD"  # internal name at header offset 0x20

_Z64 = b"\x80\x37\x12\x40"
_V64 = b"\x37\x80\x40\x12"
_N64 = b"\x40\x12\x37\x80"
_RZIP_FLAG = 0x10


class RomError(ValueError):
    """The file is not a ROM this module can read."""


def normalize_rom(data: bytes) -> bytes:
    """Return big-endian (z64) bytes. Accepts z64, v64 (byte swapped) and n64 (word swapped)."""
    magic = data[:4]
    if magic == _Z64:
        return data
    if magic == _V64:
        if len(data) % 2:
            raise RomError("byte-swapped ROM has an odd length")
        out = bytearray(len(data))
        out[0::2] = data[1::2]
        out[1::2] = data[0::2]
        return bytes(out)
    if magic == _N64:
        if len(data) % 4:
            raise RomError("word-swapped ROM length is not a multiple of four")
        out = bytearray(len(data))
        for pos in range(0, len(data), 4):
            out[pos:pos + 4] = data[pos:pos + 4][::-1]
        return bytes(out)
    raise RomError("not an N64 ROM (unknown byte order)")


def is_us_rom(normalized: bytes) -> bool:
    """True for the US retail ROM: internal title and the pinned SHA-1."""
    if normalized[0x20:0x2A] != US_TITLE:
        return False
    return hashlib.sha1(normalized).hexdigest() == US_SHA1


def decode_rzip(blob: bytes) -> Tuple[bytes, int]:
    """Decode one RZIP entry at the start of ``blob``. Returns (payload, bytes consumed)."""
    if len(blob) < 5:
        raise RomError("RZIP entry is shorter than its header")
    declared = struct.unpack_from(">I", blob, 0)[0]
    decoder = zlib.decompressobj(wbits=-15)
    payload = decoder.decompress(blob[4:]) + decoder.flush()
    if not decoder.eof:
        raise RomError("RZIP deflate stream is truncated")
    if len(payload) != declared:
        raise RomError(f"RZIP length mismatch: header {declared}, decoded {len(payload)}")
    consumed = len(blob) - len(decoder.unused_data)
    return payload, consumed


def encode_rzip(payload: bytes) -> bytes:
    """One RZIP entry: big-endian u32 decoded length, then a raw deflate stream (zlib level 9, RFC 1951)."""
    deflater = zlib.compressobj(9, zlib.DEFLATED, -15)
    return struct.pack(">I", len(payload)) + deflater.compress(payload) + deflater.flush()


@dataclass(frozen=True)
class AssetBank:
    index: int
    start: int
    end: int
    flags: int  # non-zero: raw block without an inner index (not a bank of entries)


@dataclass(frozen=True)
class AssetEntry:
    bank: int
    index: int
    start: int
    end: int
    rzip: bool


def parse_banks(rom: bytes, table_start: int = US_ASSET_TABLE) -> List[AssetBank]:
    """Read the outer table. Every bank must lie after the previous one and inside the ROM."""
    table_size = struct.unpack_from(">I", rom, table_start)[0]
    if table_size == 0 or table_size % 8 or table_start + table_size > len(rom):
        raise RomError("asset table has no valid eight-byte span")
    banks: List[AssetBank] = []
    previous_end = table_start + table_size
    for index in range(table_size // 8):
        rel, size_flags = struct.unpack_from(">II", rom, table_start + index * 8)
        start = table_start + rel
        size = size_flags & 0x0FFFFFFF
        end = start + size
        if size == 0 or start < previous_end or end > len(rom):
            raise RomError(f"asset bank {index:02X} has an invalid range")
        banks.append(AssetBank(index=index, start=start, end=end, flags=size_flags >> 28))
        previous_end = end
    return banks


def parse_entries(rom: bytes, bank: AssetBank) -> List[AssetEntry]:
    """Read one bank's inner table. Zero-length slots are empty and are skipped; their index is kept."""
    if bank.flags:
        return []
    first = struct.unpack_from(">I", rom, bank.start)[0]
    if first == 0 or first % 8 or bank.start + first > bank.end:
        raise RomError(f"asset bank {bank.index:02X} has an invalid inner table")
    entries: List[AssetEntry] = []
    previous_end = bank.start + first
    for index in range(first // 8):
        rel, length_flags = struct.unpack_from(">II", rom, bank.start + index * 8)
        length = length_flags & 0x0FFFFFFF
        if length == 0:
            continue
        start = bank.start + rel
        end = start + length
        if start < previous_end or end > bank.end:
            raise RomError(f"asset bank {bank.index:02X} entry {index} has an invalid range")
        entries.append(AssetEntry(bank=bank.index, index=index, start=start, end=end,
                                  rzip=bool((length_flags >> 24) & _RZIP_FLAG)))
        previous_end = end
    return entries


def read_text_sources(rom: bytes) -> List[Tuple[str, str, bytes]]:
    """Decoded text tables as (folder, name, bytes).

    Bank 0x1A: each entry is a text table (the catapult instruction book). Bank 0x1C holds one raw entry that is
    an inner index of four sub-tables: menu options, pause menu, chapter names and credits.
    """
    banks = {bank.index: bank for bank in parse_banks(rom)}
    sources: List[Tuple[str, str, bytes]] = []
    for entry in parse_entries(rom, banks[0x1A]):
        sources.append(("bank_1A", f"entry_{entry.index:04d}", read_entry(rom, entry)))
    holder = parse_entries(rom, banks[0x1C])[0]
    inner = AssetBank(index=0x1C, start=holder.start, end=holder.end, flags=0)
    for sub in parse_entries(rom, inner):
        sources.append(("bank_1C", f"sub_{sub.index:04d}", read_entry(rom, sub)))
    return sources


def read_game_data(rom: bytes) -> bytes:
    """Decode the game's data section (one RZIP entry) and check its size."""
    payload, _ = decode_rzip(rom[US_GAME_DATA_START:US_GAME_DATA_START + 0x1B000])
    if len(payload) != US_GAME_DATA_SIZE:
        raise RomError("game data section has an unexpected size")
    return payload


def read_entry(rom: bytes, entry: AssetEntry) -> bytes:
    """Return the decoded bytes of one entry (RZIP decoded, raw copied)."""
    blob = rom[entry.start:entry.end]
    if not entry.rzip:
        return bytes(blob)
    payload, consumed = decode_rzip(blob)
    if consumed != len(blob):
        raise RomError(f"entry {entry.bank:02X}:{entry.index} has {len(blob) - consumed} unused bytes")
    return payload
