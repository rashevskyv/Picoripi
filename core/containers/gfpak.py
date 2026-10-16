"""Game Freak ``GFLXPACK`` packs (Legends: Arceus ``*.gfpak``): the file table, the decoded files and their names.

Header: ``GFLXPACK``, u32 version, u32 relocated, i32 file count, i32 folder count, u64 file table offset, u64 path
hash table offset. The file table holds 24 bytes per file: u16 level, u16 compression (0 stored, 3 Oodle), u32 size,
u32 packed size, u32 padding, u64 data offset. The path hash table holds one u64 per file (FNV-1a 64 with Game Freak's
offset basis). Decoding needs an Oodle decompressor, passed in by the caller; nothing here loads a library.
"""
from __future__ import annotations

import re
import struct
from typing import Callable, List, NamedTuple, Sequence

from core.containers.game_freak import path_hash

MAGIC = b"GFLXPACK"
KIND_STORED = 0
KIND_OODLE = 3
_BLYT = re.compile(rb"blyt/([A-Za-z0-9_]+)\.bflyt")


class GfpakError(ValueError):
    """The bytes are not a GFLXPACK pack, or hold a compression this reader does not know."""


class Entry(NamedTuple):
    path_hash: int
    kind: int
    size: int
    packed: bytes


def read_entries(data: bytes) -> List[Entry]:
    """The files of a pack as they are stored (still compressed)."""
    if data[:8] != MAGIC:
        raise GfpakError("not a GFLXPACK pack")
    count, table, hashes = struct.unpack_from("<i4xQQ", data, 0x10)
    entries = []
    for index in range(count):
        kind, size, packed_size, offset = struct.unpack_from("<2xHII4xQ", data, table + 24 * index)
        if kind not in (KIND_STORED, KIND_OODLE):
            raise GfpakError(f"unknown compression {kind} in a GFLXPACK pack")
        path_value = struct.unpack_from("<Q", data, hashes + 8 * index)[0]
        entries.append(Entry(path_value, kind, size, data[offset:offset + packed_size]))
    return entries


def decode(data: bytes, decompress: Callable[[bytes, int], bytes]) -> List[bytes]:
    """Every file of the pack, decoded. ``decompress(packed, size)`` decodes an Oodle block."""
    return [entry.packed if entry.kind == KIND_STORED else decompress(entry.packed, entry.size)
            for entry in read_entries(data)]


def file_names(files: Sequence[bytes], hashes: Sequence[int]) -> List[str]:
    """Names for unpacked files: ``NN_<layout>.arc`` for a layout archive (its real name when the path hash is the
    bin/appli/<folder>/bin/<layout>[_eng].arc of a layout inside), ``NN_<layout>.arc`` otherwise, ``NN.bin`` for the rest."""
    names = []
    for index, (raw, wanted) in enumerate(zip(files, hashes)):
        layouts = [m.decode() for m in _BLYT.findall(raw[:65536])] if raw[:4] == b"SARC" else []
        real = next((f"{layout}{suffix}" for layout in layouts for k in range(1, layout.count("_") + 1)
                     for suffix in ("_eng.arc", ".arc")
                     if path_hash(f"bin/appli/{layout.rsplit('_', k)[0]}/bin/{layout}{suffix}") == wanted), None)
        names.append(f"{index:02}_{real or layouts[0] + '.arc'}" if layouts else f"{index:02}.bin")
    return names
