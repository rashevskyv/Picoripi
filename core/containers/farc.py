"""FARC version 5 packs (Spike Chunsoft's archive, Pokémon Mystery Dungeon 3DS): a member list and the member data.

Layout (zt ``pmd3ds.py``): ``FARC``, then five u32 words from 0x20: the version (5), the file table offset, its length,
the data offset and its length. The file table starts with a u32 offset (relative to the table) of a header that holds
the member count and the member list offset; each member is 12 bytes: name hash, data offset (from the data offset)
and length. A member's name hash is the CRC-32 of its UTF-16 name (see ``name_hash``).

``replace`` writes the pack again with some members changed: the members keep their order, each member is padded to
16 bytes, and the table offsets follow the new data. It never changes the member list.
"""
from __future__ import annotations

import struct
import zlib
from pathlib import PurePosixPath
from typing import Dict, List, Tuple

VERSION = 5
_ENTRY = 12


class FarcError(ValueError):
    """The bytes are not a FARC version 5 pack, or a member does not fit the pack."""


def name_hash(name: str) -> int:
    """The hash of a member name: its CRC-32 over the UTF-16 name, or the hex hash of a ``#<hash>`` placeholder name."""
    if name.startswith("#"):
        return int(PurePosixPath(name).stem[1:], 16)
    return zlib.crc32(name.encode("utf-16-le"))


def _layout(data: bytes) -> Tuple[int, int, int, int, List[Tuple[int, int, int]]]:
    """``(fat offset, fat length, data offset, table offset, [(hash, offset, length)])`` of a pack."""
    if len(data) < 0x34 or data[:4] != b"FARC":
        raise FarcError("not a FARC pack")
    version, fat_off, fat_len, data_off, _data_len = struct.unpack_from("<5I", data, 0x20)
    if version != VERSION:
        raise FarcError(f"a FARC pack of version {version}, not {VERSION}")
    if fat_off + 8 > len(data) or data_off > len(data):
        raise FarcError("the FARC file table lies outside the pack")
    header = fat_off + struct.unpack_from("<I", data, fat_off + 4)[0]
    if header + 8 > len(data):
        raise FarcError("the FARC header lies outside the pack")
    table, count = struct.unpack_from("<II", data, header)
    start = fat_off + table
    if start + count * _ENTRY > len(data):
        raise FarcError("the FARC member list lies outside the pack")
    entries = []
    for i in range(count):
        h, offset, length = struct.unpack_from("<III", data, start + i * _ENTRY)
        if data_off + offset + length > len(data):
            raise FarcError("a FARC member lies outside the pack")
        entries.append((h, data_off + offset, length))
    return fat_off, fat_len, data_off, table, entries


def members(data: bytes) -> List[Tuple[int, int, int]]:
    """``[(name hash, offset in data, length)]`` of the members, in file table order."""
    return _layout(data)[4]


def member_bytes(data: bytes) -> Dict[int, bytes]:
    """``{name hash: bytes}`` of every member of the pack."""
    return {h: data[offset:offset + length] for h, offset, length in members(data)}


def replace(data: bytes, replacements: Dict[int, bytes]) -> bytes:
    """The pack with the members of the hashes in ``replacements`` changed. The rest keep their bytes. A hash the pack
    does not hold raises FarcError."""
    fat_off, fat_len, data_off, table, entries = _layout(data)
    missing = set(replacements) - {h for h, _o, _n in entries}
    if missing:
        raise FarcError("the pack holds no member with the hash " + ", ".join(f"{h:08X}" for h in sorted(missing)))
    head = bytearray(data[:data_off])
    body = bytearray()
    for index, (h, offset, length) in sorted(enumerate(entries), key=lambda e: e[1][1]):
        blob = replacements.get(h, data[offset:offset + length])
        blob += bytes(-len(blob) % 16)
        struct.pack_into("<II", head, fat_off + table + index * _ENTRY + 4, len(body), len(blob))
        body += blob
    struct.pack_into("<I", head, 0x30, len(head) + len(body) - fat_off - fat_len)
    return bytes(head) + bytes(body)
