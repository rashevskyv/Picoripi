"""NitroFS of the Nintendo DS cartridges of The Legend of Zelda: Phantom Hourglass and Spirit Tracks.

``rebuild`` writes changed files into the ROM. Every file keeps the gap that followed it in the original (its bytes
are copied), so a ROM with nothing changed comes back byte for byte: the USA dumps pack their files tightly (4-byte
alignment, zero filler), and some dumps 0x200-align them (0xFF filler). A file that grows moves the files after it;
the FAT, the used size and the header CRC are written again. The bytes after the used size (padding up to the cart
size) are kept.
"""
from __future__ import annotations

import struct
from typing import Dict


class RomError(ValueError):
    """The ROM is not laid out the way this module expects, or a file is not in it."""


def _crc16(data: bytes) -> int:
    crc = 0xFFFF
    for byte in data:
        crc ^= byte
        for _ in range(8):
            crc = (crc >> 1) ^ 0xA001 if crc & 1 else crc >> 1
    return crc


def nitro_ids(rom: bytes) -> Dict[str, int]:
    """``{path: file id}`` of the NitroFS (the file name table at the header's FNT offset)."""
    fnt = struct.unpack_from("<I", rom, 0x40)[0]
    found: Dict[str, int] = {}

    def walk(dir_id: int, prefix: str) -> None:
        sub, first = struct.unpack_from("<IH", rom, fnt + (dir_id & 0xFFF) * 8)
        at, file_id = fnt + sub, first
        while rom[at]:
            length = rom[at] & 0x7F
            name = rom[at + 1:at + 1 + length].decode("ascii", "replace")
            if rom[at] & 0x80:
                walk(struct.unpack_from("<H", rom, at + 1 + length)[0], prefix + name + "/")
                at += 3 + length
            else:
                found[prefix + name] = file_id
                file_id += 1
                at += 1 + length

    walk(0xF000, "")
    return found


def nitro_files(rom: bytes) -> Dict[str, bytes]:
    fat = struct.unpack_from("<I", rom, 0x48)[0]
    out = {}
    for path, file_id in nitro_ids(rom).items():
        start, end = struct.unpack_from("<II", rom, fat + 8 * file_id)
        out[path] = rom[start:end]
    return out


def rebuild(rom: bytes, replace: Dict[str, bytes]) -> bytes:
    """``rom`` with the NitroFS files of ``replace`` ({path: new bytes}) swapped in; nothing to replace = same bytes."""
    ids = nitro_ids(rom)
    unknown = sorted(set(replace) - set(ids))
    if unknown:
        raise RomError("the game has no such file: " + ", ".join(unknown))
    fat, fat_size = struct.unpack_from("<II", rom, 0x48)
    overlays = struct.unpack_from("<I", rom, 0x54)[0] // 32
    spans = [struct.unpack_from("<II", rom, fat + 8 * i) for i in range(fat_size // 8)]
    order = sorted(range(overlays, len(spans)), key=lambda i: spans[i][0])
    by_id = {ids[path]: data for path, data in replace.items()}
    start = spans[order[0]][0]
    if any(spans[i][1] > start for i in range(overlays)):
        raise RomError("unusual ROM: overlays lie after the NitroFS files")
    aligned = all(spans[i][0] % 0x200 == 0 for i in order)
    align, filler = (0x200, b"\xff") if aligned else (4, b"\x00")
    out = bytearray(rom[:start])
    previous_end = None
    for file_id in order:
        s, e = spans[file_id]
        if previous_end is not None:
            out += rom[previous_end:s]          # the gap the original kept after the file before
        out += filler * (-len(out) % align)
        data = by_id.get(file_id, rom[s:e])
        struct.pack_into("<II", out, fat + 8 * file_id, len(out), len(out) + len(data))
        out += data
        previous_end = e
    used = len(out)
    struct.pack_into("<I", out, 0x80, used)
    out += rom[previous_end:]                   # padding up to the cart size stays as it was
    cap = out[0x14]
    while (0x20000 << cap) < used:
        cap += 1
    out[0x14] = cap
    struct.pack_into("<H", out, 0x15E, _crc16(bytes(out[:0x15E])))
    return bytes(out)
