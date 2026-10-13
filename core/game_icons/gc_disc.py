"""GameCube disc image (raw ISO or GCM): finds ``opening.bnr`` in the root of the file system (FST)."""
from __future__ import annotations

import struct
from typing import Optional, Tuple

from core.game_icons.common import FileSource

GC_MAGIC = b"\xc2\x33\x9f\x3d"     # at 0x1C, big endian
MAGIC_AT, FST_AT_FIELD, FST_SIZE_FIELD = 0x1C, 0x424, 0x428
ENTRY = 12


def _u32(data: bytes, at: int) -> int:
    return struct.unpack_from(">I", data, at)[0]


def is_gamecube(src: FileSource) -> bool:
    return src.size >= 0x430 and src.take(MAGIC_AT, 4) == GC_MAGIC


def find_banner(src: FileSource) -> Optional[Tuple[int, int]]:
    """``(disc offset, size)`` of ``opening.bnr`` in the root directory, or None."""
    if not is_gamecube(src):
        return None
    head = src.take(0, 0x430)
    fst = src.take(_u32(head, FST_AT_FIELD), _u32(head, FST_SIZE_FIELD))
    count = _u32(fst, 8)                       # root entry: number of entries of the whole table
    names_at = count * ENTRY
    index = 1
    while index < count:
        word = _u32(fst, index * ENTRY)
        is_dir, name_at = word >> 24, word & 0xFFFFFF
        end = fst.find(b"\0", names_at + name_at)
        name = fst[names_at + name_at:end].decode("latin-1", "replace").lower()
        if not is_dir and name == "opening.bnr":
            return _u32(fst, index * ENTRY + 4), _u32(fst, index * ENTRY + 8)
        index = _u32(fst, index * ENTRY + 8) if is_dir else index + 1
    return None
