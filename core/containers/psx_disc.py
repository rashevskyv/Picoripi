"""PlayStation 1 disc images: a MODE2/2352 cue sheet (CloneCD or BIN/CUE) read as its ISO 9660 files.

``PsxDiscImage`` reads the disc's Form 1 user data (2048 bytes at offset 24 of each raw sector) through ``GdRomStream``,
the cue-sheet reader shared with the Dreamcast GD-ROM reader. It lists the files of the one data volume with their
paths (``FIELD/3034.MDP``). A file whose XA attribute says interleaved (``XA_INTERLEAVED``) is a streamed movie or sound
file: its sectors mix Form 1 video with Form 2 audio, so it is listed as ``interleaved`` and is not read as data.
``identify_psx`` gives the product code from ``SYSTEM.CNF`` (``BOOT = cdrom:\\SCUS_944.57;1``). Facts from the disc
files of the owner's Grandia discs (2 discs, SCUS-94457 and SCUS-94465).
"""
from __future__ import annotations

import re
import struct
from dataclasses import dataclass
from typing import Any, Dict, List, Optional

from core.containers.gdrom import GdRomStream, SECTOR
from core.containers.image_files import ImageError, ImageFile, ImageReader, check_name
from core.i18n import tr

PVD_SECTOR = 16
DIR_FLAG = 0x02
MULTI_EXTENT_FLAG = 0x80
XA_INTERLEAVED = 0x2000   # bit 13 of the XA attribute word: the file is interleaved with Form 2 audio
MAX_DEPTH = 8
_BOOT = re.compile(rb"BOOT\s*=\s*cdrom:\\?([^\s;\r\n]+)", re.IGNORECASE)


@dataclass(frozen=True)
class PsxFile:
    """One file of a PS1 disc: ``path`` inside the disc, first sector, byte size, and whether it is interleaved."""

    path: str
    extent: int
    size: int
    interleaved: bool


def _xa_attributes(system_use: bytes) -> Optional[int]:
    """The XA attribute word of a directory record's system use area, or None without an XA entry."""
    at = system_use.find(b"XA")
    if at < 2:
        return None
    return struct.unpack_from(">H", system_use, at - 2)[0]


class PsxDiscImage(ImageReader):
    """A PS1 disc read in place from its cue sheet. Offsets address the user-data stream (2048 bytes a sector)."""

    def __init__(self, stream: GdRomStream) -> None:
        super().__init__(stream)
        pvd = self.read_at(PVD_SECTOR * SECTOR, SECTOR)
        if pvd[0] != 1 or pvd[1:6] != b"CD001":
            raise ImageError(tr("no ISO 9660 volume on the PlayStation disc"))

    def files(self) -> List[PsxFile]:
        """Every file of the data volume, directories walked. Interleaved files are listed with their flag."""
        pvd = self.read_at(PVD_SECTOR * SECTOR, SECTOR)
        root = pvd[156:190]
        out: List[PsxFile] = []
        self._walk("", struct.unpack_from("<I", root, 2)[0], struct.unpack_from("<I", root, 10)[0], 0, set(), out)
        return out

    def _walk(self, folder: str, extent: int, size: int, depth: int, ancestors: set, out: List[PsxFile]) -> None:
        if depth > MAX_DEPTH:
            raise ImageError(tr("a directory is nested too deep"))
        if extent in ancestors:
            raise ImageError(tr("a directory is listed twice in the image"))
        ancestors.add(extent)
        data = self.read_table(extent * SECTOR, size)
        subdirs = []
        at = 0
        while at < len(data):
            length = data[at]
            if length == 0:
                at = (at // SECTOR + 1) * SECTOR
                continue
            if length < 34 or at + length > len(data):
                raise ImageError(tr("a directory record in the image is malformed"))
            rec_extent = struct.unpack_from("<I", data, at + 2)[0]
            rec_size = struct.unpack_from("<I", data, at + 10)[0]
            flags = data[at + 25]
            name_len = data[at + 32]
            raw_name = data[at + 33:at + 33 + name_len].decode("latin-1")
            pad = 1 if name_len % 2 == 0 else 0
            system_use = data[at + 33 + name_len + pad:at + length]
            at += length
            if raw_name in ("\x00", "\x01"):
                continue
            if flags & MULTI_EXTENT_FLAG:
                raise ImageError(tr("a multi-extent file in the image is not read"))
            name = check_name(raw_name.split(";")[0].rstrip("."))
            if flags & DIR_FLAG:
                subdirs.append((f"{folder}/{name}", rec_extent, rec_size))
            else:
                attr = _xa_attributes(system_use)
                interleaved = bool(attr is not None and attr & XA_INTERLEAVED)
                out.append(PsxFile(f"{folder}/{name}".lstrip("/"), rec_extent, rec_size, interleaved))
        for sub_folder, sub_extent, sub_size in subdirs:
            self._walk(sub_folder, sub_extent, sub_size, depth + 1, ancestors, out)
        ancestors.discard(extent)

    def entries(self) -> List[ImageFile]:
        """The plain-data files as ``ImageFile`` entries, for ``write_entries``. Interleaved streams are left out."""
        return [ImageFile(entry.path, entry.extent * SECTOR, entry.size) for entry in self.files()
                if not entry.interleaved]

    def read_file(self, entry: PsxFile) -> bytes:
        """The data of one file. ImageError for an interleaved file: its sectors are not plain data."""
        if entry.interleaved:
            raise ImageError(tr("{0} is an interleaved stream, not plain data", entry.path))
        return self.read_at(entry.extent * SECTOR, entry.size)

    def boot_name(self) -> Optional[str]:
        """The boot file named by ``SYSTEM.CNF`` (``SCUS_944.57``), or None when the disc has no such line."""
        for entry in self.files():
            if entry.path.upper() == "SYSTEM.CNF":
                match = _BOOT.search(self.read_file(entry))
                return match.group(1).decode("ascii", "replace").split(";")[0] if match else None
        return None


def product_code(boot: str) -> str:
    """``SCUS_944.57`` -> ``SCUS-94457`` (the form used by product lists)."""
    return re.sub(r"^([A-Z]{4})[_-]?(\d{3})\.?(\d{2})$", r"\1-\2\3", boot.upper())


def open_psx(cue_path: str) -> PsxDiscImage:
    """A PS1 disc from its cue sheet. ImageError when the sheet is not a MODE2/2352 disc."""
    return PsxDiscImage(GdRomStream(cue_path))


def identify_psx(cue_path: str) -> Optional[Dict[str, Any]]:
    """``{"kind": "psx", "game_id": "SCUS-94457", "encrypted": False}`` for a PS1 disc, or None for another disc."""
    stream = GdRomStream(cue_path)
    try:
        image = PsxDiscImage(stream)
        boot = image.boot_name()
    finally:
        stream.close()
    if boot is None:
        return None
    return {"kind": "psx", "game_id": product_code(boot), "encrypted": False}
