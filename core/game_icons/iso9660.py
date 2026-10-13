"""ISO 9660 disc image (PSP UMD dumps): reads one file by its path, e.g. ``PSP_GAME/ICON0.PNG``."""
from __future__ import annotations

import struct
from typing import List, Optional, Tuple

from core.game_icons.common import FileSource

SECTOR = 2048
PVD_SECTOR = 16
ROOT_RECORD_AT = 156
DIR_FLAG = 2


def _record(data: bytes, at: int) -> Tuple[str, int, int, bool]:
    """``(name, first sector, size, is directory)`` of the directory record at ``at``."""
    extent = struct.unpack_from("<I", data, at + 2)[0]     # little endian copy; the big endian one follows
    size = struct.unpack_from("<I", data, at + 10)[0]
    name_len = data[at + 32]
    name = data[at + 33:at + 33 + name_len].decode("latin-1").split(";")[0]
    return name, extent, size, bool(data[at + 25] & DIR_FLAG)


def find(src: FileSource, parts: List[str]) -> Optional[bytes]:
    """The bytes of the file at ``parts`` (case-insensitive names), or None."""
    pvd = src.take(PVD_SECTOR * SECTOR, SECTOR)
    if pvd[1:6] != b"CD001":
        return None
    _name, extent, size, _is_dir = _record(pvd, ROOT_RECORD_AT)
    for index, wanted in enumerate(parts):
        listing = src.take(extent * SECTOR, size)
        at, found = 0, None
        while at < len(listing):
            if listing[at] == 0:                   # records do not cross sectors: skip the padding
                at = (at // SECTOR + 1) * SECTOR
                continue
            name, rec_extent, rec_size, is_dir = _record(listing, at)
            if name.upper() == wanted.upper():
                found = (rec_extent, rec_size, is_dir)
                break
            at += listing[at]
        if found is None:
            return None
        extent, size, is_dir = found
        if index == len(parts) - 1:
            return None if is_dir else src.take(extent * SECTOR, size)
        if not is_dir:
            return None
    return None
