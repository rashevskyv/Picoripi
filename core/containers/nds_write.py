"""Writes a Nintendo DS cartridge image with changed NitroFS files (the rebuild of zt/twewy.py, in core).

The NitroFS files named in the file name table are laid out again in their old order, each 0x200 aligned and padded
with 0xFF. The file allocation table, the used ROM size (0x80), the capacity (0x14) and the header CRC (0x15E) are
written again. Overlays and everything before the first NitroFS file stay where they are. Nothing replaced gives the
same image back, byte for byte.
"""
from __future__ import annotations

import struct
from typing import Dict

from core.containers.nds import HEADER_SIZE, walk_fnt

ALIGN = 0x200
FILLER = 0xFF
CAPACITY_UNIT = 0x20000
USED_SIZE_AT = 0x80
CAPACITY_AT = 0x14
HEADER_CRC_AT = 0x15E


class NdsWriteError(ValueError):
    """The image cannot be rebuilt: an unknown file, or a layout this writer does not handle."""


def crc16(data: bytes) -> int:
    """CRC-16 (Modbus, poly 0xA001, start 0xFFFF): the DS header CRC."""
    crc = 0xFFFF
    for byte in data:
        crc ^= byte
        for _ in range(8):
            crc = (crc >> 1) ^ 0xA001 if crc & 1 else crc >> 1
    return crc


def header_crc(rom: bytes) -> int:
    return crc16(bytes(rom[:HEADER_CRC_AT]))


def nitro_ids(rom: bytes) -> Dict[str, int]:
    """``{path: file id}`` of the NitroFS of a cartridge image."""
    if len(rom) < HEADER_SIZE:
        raise NdsWriteError("the image is shorter than a DS header")
    fnt_at, fnt_size = struct.unpack_from("<II", rom, 0x40)
    if fnt_at + fnt_size > len(rom):
        raise NdsWriteError("the file name table lies outside the image")
    return walk_fnt(bytes(rom[fnt_at:fnt_at + fnt_size]))


def _spans(rom: bytes) -> list:
    fat_at, fat_size = struct.unpack_from("<II", rom, 0x48)
    if fat_at + fat_size > len(rom):
        raise NdsWriteError("the file allocation table lies outside the image")
    spans = [struct.unpack_from("<II", rom, fat_at + 8 * i) for i in range(fat_size // 8)]
    for start, end in spans:
        if end < start or end > len(rom):
            raise NdsWriteError("a file span lies outside the image")
    return spans


def nitro_files(rom: bytes) -> Dict[str, bytes]:
    """``{path: data}`` of every NitroFS file."""
    spans = _spans(rom)
    out = {}
    for path, file_id in nitro_ids(rom).items():
        if file_id >= len(spans):
            raise NdsWriteError(f"the file allocation table has no entry for {path}")
        start, end = spans[file_id]
        out[path] = bytes(rom[start:end])
    return out


def rebuild_nds(rom: bytes, replace: Dict[str, bytes]) -> bytes:
    """``rom`` with the NitroFS files of ``replace`` ({path: data}) swapped in, the tables and the CRC written again.

    Nothing to change (or every replacement equal to the file it replaces) returns ``rom`` unchanged.
    """
    rom = bytes(rom)
    ids = nitro_ids(rom)
    unknown = sorted(set(replace) - set(ids))
    if unknown:
        raise NdsWriteError(f"the image has no such NitroFS files: {', '.join(unknown)}")
    spans = _spans(rom)
    if any(file_id >= len(spans) for file_id in ids.values()):
        raise NdsWriteError("the file allocation table has no entry for a NitroFS file")
    by_id = {ids[path]: bytes(data) for path, data in replace.items()}
    if all(rom[spans[fid][0]:spans[fid][1]] == data for fid, data in by_id.items()):
        return rom
    movable = sorted(ids.values(), key=lambda fid: spans[fid][0])
    if not movable:
        raise NdsWriteError("the image has no NitroFS files")
    start = spans[movable[0]][0]
    moved = set(movable)
    for file_id, (_s, end) in enumerate(spans):
        if file_id not in moved and end > start:
            raise NdsWriteError("an overlay or other file lies after the first NitroFS file: layout not handled")

    fat_at = struct.unpack_from("<I", rom, 0x48)[0]
    out = bytearray(rom[:start])
    new_span = {}
    for file_id in movable:
        data = by_id.get(file_id)
        if data is None:
            data = rom[spans[file_id][0]:spans[file_id][1]]
        out += bytes([FILLER]) * (-len(out) % ALIGN)
        new_span[file_id] = (len(out), len(out) + len(data))
        out += data
    used = len(out)
    capacity = rom[CAPACITY_AT]
    while (CAPACITY_UNIT << capacity) < used:
        capacity += 1
    out[CAPACITY_AT] = capacity
    out += bytes([FILLER]) * ((CAPACITY_UNIT << capacity) - used)
    struct.pack_into("<I", out, USED_SIZE_AT, used)
    for file_id, (a, b) in new_span.items():
        struct.pack_into("<II", out, fat_at + 8 * file_id, a, b)
    struct.pack_into("<H", out, HEADER_CRC_AT, header_crc(out))
    return bytes(out)


def check_header(rom: bytes) -> None:
    """Raise NdsWriteError when the header CRC is wrong."""
    if header_crc(rom) != struct.unpack_from("<H", rom, HEADER_CRC_AT)[0]:
        raise NdsWriteError("the header CRC does not match")
