"""Zone of the Enders: The 2nd Runner (PlayStation 2, USA): the disc, found by path, and the STAGE.DAT file on it.

The ISO 9660 reader is the one of the Okami plugin; this module adds the path walk (STAGE.DAT is in ``ZOE2/``) and the
write of a file's extent. A disc image is read in place.
"""
from __future__ import annotations

from typing import BinaryIO, Optional, Tuple

from plugins.okami_ps2 import iso

DISC_ID = b"SLUS_205.45"
STAGE_PATH = "ZOE2/STAGE.DAT"
SECTOR = iso.SECTOR


def is_zoe2_disc(image: BinaryIO) -> bool:
    system = iso.find(image, "SYSTEM.CNF")
    if system is None:
        return False
    return DISC_ID in iso.read(image, system, 0, min(system.size, 4096))


def identify_path(path: str) -> bool:
    try:
        with open(path, "rb") as image:
            return is_zoe2_disc(image)
    except OSError:
        return False


def record_of(image: BinaryIO, path: str) -> Optional[Tuple[int, iso.DiscEntry]]:
    """(byte position on the disc of the directory record of the file ``path`` ('A/B.EXT'), its entry), or None."""
    folder = iso._root(image)
    if folder is None:
        return None
    parts = [part for part in path.split("/") if part]
    for depth, part in enumerate(parts):
        image.seek(folder.lba * SECTOR)
        data = image.read(folder.size)
        found = None
        for pos, entry, raw in iso._records(data):
            if raw in (b"\x00", b"\x01") or entry.name.upper() != part.upper():
                continue
            if entry.is_dir != (depth < len(parts) - 1):
                continue
            found = (folder.lba * SECTOR + pos, entry)
            break
        if found is None:
            return None
        if depth == len(parts) - 1:
            return found
        folder = found[1]
    return None


def find_path(image: BinaryIO, path: str) -> Optional[iso.DiscEntry]:
    found = record_of(image, path)
    return None if found is None else found[1]


def file_reader(image: BinaryIO, entry: iso.DiscEntry):
    """``read(offset, count)`` of a file of the disc."""
    return lambda offset, count: iso.read(image, entry, offset, count)


def copy_range(source: BinaryIO, start: int, count: int, out: BinaryIO, at: int, is_cancelled=lambda: False) -> None:
    """Copy ``count`` bytes from ``start`` of ``source`` to ``at`` of ``out``."""
    chunk = 8 * 1024 * 1024
    source.seek(start)
    out.seek(at)
    while count > 0:
        if is_cancelled():
            raise InterruptedError()
        data = source.read(min(chunk, count))
        if not data:
            break
        out.write(data)
        count -= len(data)
