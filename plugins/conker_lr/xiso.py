"""Read an Xbox XISO (original Xbox disc image): list the files and copy the chosen ones out.

Layout: the volume descriptor starts at 0x10000 with the magic ``MICROSOFT*XBOX*MEDIA``; its root directory
sector is at 0x10014 and its size at 0x10018. A directory is a binary tree of entries: each entry holds a
left and a right child (offsets in dwords from the directory start, 0 or 0xFFFF for none), the start sector,
the size, the attributes (0x10 = directory) and the name. Sectors are 2048 bytes.
"""
from __future__ import annotations

import os
import struct
from dataclasses import dataclass
from typing import Callable, Dict, Iterator, List, Optional, Tuple

MAGIC = b"MICROSOFT*XBOX*MEDIA"
MAGIC_OFFSET = 0x10000
ROOT_SECTOR_OFFSET = 0x10014
SECTOR = 2048
ATTR_DIRECTORY = 0x10
NONE = (0, 0xFFFF)


class XisoError(ValueError):
    """The file is not an XISO, or its tree is broken."""


@dataclass(frozen=True)
class Entry:
    path: str  # "/"-separated, relative to the image root
    sector: int
    size: int
    is_dir: bool


class XisoImage:
    """A read-only view of an XISO file."""

    def __init__(self, path: str):
        self.path = path
        self._handle = open(path, "rb")
        head = self._read_at(MAGIC_OFFSET, len(MAGIC))
        if head != MAGIC:
            self._handle.close()
            raise XisoError("not an Xbox XISO image")

    def close(self) -> None:
        self._handle.close()

    def __enter__(self) -> "XisoImage":
        return self

    def __exit__(self, *exc) -> None:
        self.close()

    def _read_at(self, offset: int, size: int) -> bytes:
        self._handle.seek(offset)
        return self._handle.read(size)

    def _dir_bytes(self, sector: int, size: int) -> bytes:
        return self._read_at(sector * SECTOR, size)

    def _children(self, dir_data: bytes) -> List[Tuple[str, int, int, bool]]:
        """Every entry of one directory, as (name, sector, size, is_dir), found by walking the tree."""
        found: List[Tuple[str, int, int, bool]] = []
        todo = [0]
        seen = set()
        while todo:
            offset = todo.pop()
            if offset in seen or offset * 4 + 14 > len(dir_data):
                continue
            seen.add(offset)
            pos = offset * 4
            left, right = struct.unpack_from("<HH", dir_data, pos)
            if left not in NONE:
                todo.append(left)
            if right not in NONE:
                todo.append(right)
            sector, size, attr, name_len = struct.unpack_from("<IIBB", dir_data, pos + 4)
            if name_len == 0:
                continue
            name = dir_data[pos + 14: pos + 14 + name_len].decode("latin-1")
            found.append((name, sector, size, bool(attr & ATTR_DIRECTORY)))
        return found

    def walk(self) -> Iterator[Entry]:
        """Every file and directory of the image, depth first, sorted by name within a directory."""
        root_sector, root_size = struct.unpack("<II", self._read_at(ROOT_SECTOR_OFFSET, 8))
        stack: List[Tuple[str, int, int]] = [("", root_sector, root_size)]
        while stack:
            prefix, sector, size = stack.pop()
            children = sorted(self._children(self._dir_bytes(sector, size)), key=lambda e: e[0].lower())
            for name, child_sector, child_size, is_dir in reversed(children):
                path = f"{prefix}/{name}" if prefix else name
                yield Entry(path, child_sector, child_size, is_dir)
                if is_dir:
                    stack.append((path, child_sector, child_size))

    def read(self, entry: Entry) -> bytes:
        if entry.is_dir:
            raise XisoError(f"{entry.path} is a folder")
        return self._read_at(entry.sector * SECTOR, entry.size)

    def extract(self, wanted: Callable[[str], bool], target_dir: str,
                progress: Callable[[int, str], None], is_cancelled: Callable[[], bool]) -> List[str]:
        """Copy every file whose path ``wanted`` accepts into ``target_dir``. Returns the written paths."""
        entries = [e for e in self.walk() if not e.is_dir and wanted(e.path)]
        written: List[str] = []
        for position, entry in enumerate(entries, start=1):
            if is_cancelled():
                break
            target = os.path.join(target_dir, *entry.path.split("/"))
            os.makedirs(os.path.dirname(target), exist_ok=True)
            with open(target, "wb") as handle:
                handle.write(self.read(entry))
            written.append(entry.path)
            progress(100 * position // max(1, len(entries)), entry.path)
        return written

    def find(self, path: str) -> Optional[Entry]:
        for entry in self.walk():
            if entry.path == path:
                return entry
        return None


def is_xiso(path: str) -> bool:
    try:
        with open(path, "rb") as handle:
            handle.seek(MAGIC_OFFSET)
            return handle.read(len(MAGIC)) == MAGIC
    except OSError:
        return False


def xbe_title_id(xbe: bytes) -> Optional[int]:
    """The title id of an XBE (its certificate), or None when the bytes are not an XBE."""
    if xbe[:4] != b"XBEH":
        return None
    base = struct.unpack_from("<I", xbe, 0x104)[0]
    cert = struct.unpack_from("<I", xbe, 0x118)[0] - base
    if cert < 0 or cert + 12 > len(xbe):
        return None
    return struct.unpack_from("<I", xbe, cert + 8)[0]


def default_xbe(image: XisoImage) -> Optional[bytes]:
    entry = image.find("default.xbe")
    return image.read(entry) if entry is not None else None


def describe(path: str) -> Dict[str, object]:
    """Small summary for identification: magic, title id and file count (no extraction)."""
    with XisoImage(path) as image:
        xbe = default_xbe(image)
        count = sum(1 for e in image.walk() if not e.is_dir)
        return {"title_id": xbe_title_id(xbe) if xbe else None, "files": count}
