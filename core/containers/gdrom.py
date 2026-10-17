"""Dreamcast GD-ROM disc images as BIN/CUE sets (Redump layout): the disc as 2048-byte sectors and its ISO 9660 files.

``GdRomStream`` reads a cue sheet and its track files as one stream of 2048-byte user sectors, addressed by absolute
sector (byte offset = sector * 2048). The single-density area (LD) starts at sector 0 and the high-density area (HD)
at sector 45000; the tracks of each area follow one another. A data track is MODE1/2352 (sync, header, 2048 user
bytes at offset 16) or MODE1/2048. An audio track holds no data and reads as an error.
``GdRomImage`` lists the files of both ISO 9660 volumes: the HD volume under ``files/`` (the game's files) and the LD
volume under ``ld/`` (the disc's extra files). Facts from the cue sheets and volume descriptors of the owner's discs.
"""
from __future__ import annotations

import bisect
import os
import re
import struct
from dataclasses import dataclass
from typing import BinaryIO, Dict, List, Optional, Tuple

from core.containers.image_files import ImageError, ImageFile, ImageReader, check_name
from core.i18n import tr

SECTOR = 2048
RAW_2352 = 2352
DATA_OFFSET_2352 = 16
MODE2_FORM1_OFFSET = 24
HD_BASE = 45000
PVD_SECTOR = 16
MAX_DEPTH = 16
DIR_FLAG = 0x02
MULTI_EXTENT_FLAG = 0x80
_FILE_LINE = re.compile(r'^\s*FILE\s+(?:"([^"]+)"|(\S+))\s+BINARY\s*$', re.IGNORECASE)
_TRACK_LINE = re.compile(r"^\s*TRACK\s+(\d+)\s+(\S+)", re.IGNORECASE)
_HD_MARK = "HIGH-DENSITY AREA"


@dataclass(frozen=True)
class Segment:
    """A run of sectors of one track file: absolute sectors ``first`` .. ``first + count - 1``.

    ``data_offset`` is the user-data offset inside a raw sector, or None for an audio track.
    """

    first: int
    count: int
    path: str
    raw: int
    data_offset: Optional[int]
    file_offset: int = 0


def parse_layout(cue_path: str) -> List[Segment]:
    """The segments of a cue sheet, with absolute sector numbers. ImageError when the sheet does not fit."""
    folder = os.path.dirname(os.path.abspath(cue_path))
    with open(cue_path, "r", encoding="utf-8", errors="replace") as handle:
        lines = handle.read().splitlines()
    tracks: List[Tuple[bool, str, str]] = []   # (high density, file path, track mode)
    high = False
    file_path: Optional[str] = None
    for line in lines:
        if "REM" in line and "AREA" in line.upper():
            high = _HD_MARK in line.upper()
            continue
        match = _FILE_LINE.match(line)
        if match:
            name = match.group(1) or match.group(2)
            file_path = os.path.join(folder, name)
            continue
        match = _TRACK_LINE.match(line)
        if match and file_path is not None:
            tracks.append((high, file_path, match.group(2).upper()))
            file_path = None
    if not tracks:
        raise ImageError(tr("not a GD-ROM cue sheet: no track line"))
    cursors = {False: 0, True: HD_BASE}
    segments: List[Segment] = []
    for is_high, path, mode in tracks:
        if not os.path.isfile(path):
            raise ImageError(tr("the track file {0} is missing", os.path.basename(path)))
        size = os.path.getsize(path)
        if mode == "AUDIO":
            raw, data_offset = RAW_2352, None
        elif mode == "MODE1/2352":
            raw, data_offset = RAW_2352, DATA_OFFSET_2352
        elif mode == "MODE1/2048":
            raw, data_offset = SECTOR, 0
        elif mode == "MODE2/2352":   # PlayStation 1 data track: Form 1 user data after the 12-byte sync, 4-byte header and 8-byte subheader
            raw, data_offset = RAW_2352, MODE2_FORM1_OFFSET
        else:
            raise ImageError(tr("unsupported track mode {0}", mode))
        if size % raw:
            raise ImageError(tr("track file size is not a multiple of its sector size: {0}", os.path.basename(path)))
        count = size // raw
        segments.append(Segment(cursors[is_high], count, path, raw, data_offset))
        cursors[is_high] += count
    return segments


class GdRomStream:
    """Read-only stream of the disc's user sectors: ``seek``, ``tell`` and ``read`` as on a plain ISO."""

    def __init__(self, cue_path: str) -> None:
        self._segments = parse_layout(cue_path)
        self._firsts = [seg.first for seg in self._segments]
        self._files: Dict[str, BinaryIO] = {}
        self.size = max(seg.first + seg.count for seg in self._segments) * SECTOR
        self._pos = 0

    def seek(self, offset: int, whence: int = 0) -> int:
        if whence == 0:
            target = offset
        elif whence == 1:
            target = self._pos + offset
        else:
            target = self.size + offset
        if target < 0:
            raise ImageError(tr("a seek before the start of the disc"))
        self._pos = target
        return self._pos

    def tell(self) -> int:
        return self._pos

    def readable(self) -> bool:
        return True

    def seekable(self) -> bool:
        return True

    def read(self, size: int = -1) -> bytes:
        if size is None or size < 0:
            size = max(0, self.size - self._pos)
        out = bytearray()
        while size > 0 and self._pos < self.size:
            lba, within = divmod(self._pos, SECTOR)
            seg = self._segment_for(lba)
            run = min(seg.first + seg.count - lba, (size + within + SECTOR - 1) // SECTOR)
            block = self._read_sectors(seg, lba, run)
            take = min(size, len(block) - within)
            out += block[within:within + take]
            self._pos += take
            size -= take
        return bytes(out)

    def close(self) -> None:
        for handle in self._files.values():
            handle.close()
        self._files.clear()

    def _segment_for(self, lba: int) -> Segment:
        index = bisect.bisect_right(self._firsts, lba) - 1
        if index >= 0:
            seg = self._segments[index]
            if lba < seg.first + seg.count:
                return seg
        raise ImageError(tr("sector {0} is not on the disc", lba))

    def _read_sectors(self, seg: Segment, lba: int, run: int) -> bytes:
        if seg.data_offset is None:
            raise ImageError(tr("sector {0} is an audio sector and holds no data", lba))
        handle = self._files.get(seg.path)
        if handle is None:
            handle = open(seg.path, "rb")
            self._files[seg.path] = handle
        start = seg.file_offset + (lba - seg.first) * seg.raw
        handle.seek(start)
        raw = handle.read(run * seg.raw)
        out = bytearray()
        for i in range(run):
            at = i * seg.raw + seg.data_offset
            out += raw[at:at + SECTOR]
        return bytes(out)


class GdRomImage(ImageReader):
    """The files of a GD-ROM image: ``files/`` (HD volume) and ``ld/`` (LD volume). Offsets address the stream."""

    def __init__(self, stream: GdRomStream) -> None:
        super().__init__(stream)
        self._volumes: List[Tuple[str, int]] = []
        for prefix, base in (("files", HD_BASE), ("ld", 0)):
            pvd = self.read_at((base + PVD_SECTOR) * SECTOR, SECTOR)
            if pvd[0] == 1 and pvd[1:6] == b"CD001":
                self._volumes.append((prefix, base))
        if not self._volumes:
            raise ImageError(tr("no ISO 9660 volume on the GD-ROM disc"))

    def entries(self, where: Optional[Dict[str, int]] = None) -> List[ImageFile]:
        """The files of both volumes. ``where``, when given, receives the stream offset of each file's directory record."""
        out: List[ImageFile] = []
        for prefix, base in self._volumes:
            pvd = self.read_at((base + PVD_SECTOR) * SECTOR, SECTOR)
            root = pvd[156:190]
            self._walk(prefix, struct.unpack_from("<I", root, 2)[0], struct.unpack_from("<I", root, 10)[0],
                       0, set(), out, where)
        return out

    def _walk(self, folder: str, extent: int, size: int, depth: int, ancestors: set,
              out: List[ImageFile], where: Optional[Dict[str, int]] = None) -> None:
        """Append the files of the directory at ``extent`` under ``folder``, then recurse into its directories."""
        if depth > MAX_DEPTH:
            raise ImageError(tr("a directory is nested too deep"))
        if extent in ancestors:
            raise ImageError(tr("a directory is listed twice in the image"))
        ancestors.add(extent)
        data = self.read_table(extent * SECTOR, size)
        subdirs: List[Tuple[str, int, int]] = []
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
            rec_offset = extent * SECTOR + at
            at += length
            if raw_name in ("\x00", "\x01"):
                continue
            if flags & MULTI_EXTENT_FLAG:
                raise ImageError(tr("a multi-extent file in the image is not read"))
            name = check_name(raw_name.split(";")[0].rstrip("."))
            if flags & DIR_FLAG:
                subdirs.append((f"{folder}/{name}", rec_extent, rec_size))
            else:
                out.append(ImageFile(f"{folder}/{name}", rec_extent * SECTOR, rec_size))
                if where is not None:
                    where[f"{folder}/{name}"] = rec_offset
        for sub_folder, sub_extent, sub_size in subdirs:
            self._walk(sub_folder, sub_extent, sub_size, depth + 1, ancestors, out, where)
        ancestors.discard(extent)
