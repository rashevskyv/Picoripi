"""PlayStation 1 disc images: a MODE2/2352 cue sheet (CloneCD or BIN/CUE) read as its ISO 9660 files.

``PsxDiscImage`` reads the disc's Form 1 user data (2048 bytes at offset 24 of each raw sector) through ``GdRomStream``,
the cue-sheet reader shared with the Dreamcast GD-ROM reader. It lists the files of the one data volume with their
paths (``FIELD/3034.MDP``). A file whose XA attribute says interleaved (``XA_INTERLEAVED``) is a streamed movie or sound
file: its sectors mix Form 1 video with Form 2 audio, so it is listed as ``interleaved`` and is not read as data.
``identify_psx`` gives the product code from ``SYSTEM.CNF`` (``BOOT = cdrom:\\SCUS_944.57;1``). Facts from the disc
files of the owner's Grandia discs (2 discs, SCUS-94457 and SCUS-94465).

``write_file`` changes the bytes of one plain file in place, with the length kept. Every sector it touches gets a new
EDC and new P and Q parity (``fix_sector``, ECMA-130 Mode 2 Form 1). The code reproduces the owner's disc sectors byte
for byte, so an unchanged sector rebuilds to itself. The image is changed in place: copy it first.
"""
from __future__ import annotations

import os
import re
import struct
from dataclasses import dataclass
from typing import Any, Callable, Dict, List, Mapping, Optional, Tuple

from core.containers.gdrom import MODE2_FORM1_OFFSET, RAW_2352, SECTOR, GdRomStream, Segment, parse_layout
from core.containers.image_files import ImageError, ImageFile, ImageReader, check_name
from core.i18n import tr

COPY_CHUNK = 1 << 20   # bytes copied per read when a disc set is copied

PVD_SECTOR = 16
EDC_AT = 2072            # EDC after the 2048 user bytes of a Mode 2 Form 1 raw sector (user data at byte 24)
ECC_AT = 2076            # P parity (172 bytes), then Q parity (104 bytes), ECMA-130 annex
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


# -- writing: same-length file changes with EDC and ECC regenerated ------------------------------------------------

def _gf_tables() -> Tuple[List[int], List[int]]:
    """GF(2^8) tables of the ECC code (polynomial 0x11D): multiply by 2, and the inverse of that map."""
    times2, div2 = [0] * 256, [0] * 256
    for value in range(256):
        doubled = ((value << 1) ^ (0x11D if value & 0x80 else 0)) & 0xFF
        times2[value] = doubled
        div2[value ^ doubled] = value
    return times2, div2


def _edc_table() -> List[int]:
    table = []
    for value in range(256):
        crc = value
        for _ in range(8):
            crc = (crc >> 1) ^ (0xD8018001 if crc & 1 else 0)
        table.append(crc)
    return table


_TIMES2, _DIV2 = _gf_tables()
_EDC_TABLE = _edc_table()


def _ecc_plan(major_count: int, minor_count: int, major_mult: int, minor_inc: int) -> List[List[int]]:
    """Byte indexes (into the 2064-byte ECC span) of every parity codeword, one list per codeword."""
    size = major_count * minor_count
    plan = []
    for major in range(major_count):
        index = (major >> 1) * major_mult + (major & 1)
        row = []
        for _minor in range(minor_count):
            row.append(index)
            index += minor_inc
            if index >= size:
                index -= size
        plan.append(row)
    return plan


_P_PLAN = _ecc_plan(86, 24, 2, 86)
_Q_PLAN = _ecc_plan(52, 43, 86, 88)


def _edc(data: bytes) -> int:
    value = 0
    for byte in data:
        value = (value >> 8) ^ _EDC_TABLE[(value ^ byte) & 0xFF]
    return value


def _parity(src: bytes, plan: List[List[int]], out: bytearray, at: int) -> None:
    """Write the two parity bytes of every codeword in ``plan`` (P or Q) to ``out`` starting at ``at``."""
    count = len(plan)
    for major, row in enumerate(plan):
        acc = folded = 0
        for index in row:
            byte = src[index]
            acc = _TIMES2[acc ^ byte]
            folded ^= byte
        acc = _DIV2[_TIMES2[acc] ^ folded]
        out[at + major] = acc
        out[at + major + count] = acc ^ folded


def fix_sector(sector: bytearray) -> None:
    """Recompute the EDC, and the P and Q parity, of a raw Mode 2 Form 1 sector in place.

    The sector address (bytes 12-15) is left out of the parity span, as the Mode 2 code does. Form 2 sectors are not
    rewritten: their EDC is optional and their parity does not apply.
    """
    if sector[18] & 0x20:
        raise ImageError(tr("a Form 2 sector cannot be rewritten"))
    struct.pack_into("<I", sector, EDC_AT, _edc(bytes(sector[16:EDC_AT])))
    address = bytes(sector[12:16])
    sector[12:16] = bytes(4)
    _parity(bytes(sector[12:]), _P_PLAN, sector, ECC_AT)
    _parity(bytes(sector[12:]), _Q_PLAN, sector, ECC_AT + 172)
    sector[12:16] = address


def _segment_of(segments: List[Segment], lba: int) -> Segment:
    for seg in segments:
        if seg.first <= lba < seg.first + seg.count:
            return seg
    raise ImageError(tr("sector {0} is not on the disc", lba))


def write_file(cue_path: str, entry: PsxFile, data: bytes) -> int:
    """Overwrite the bytes of one plain file in its track files; the length must not change.

    Each sector whose user bytes change gets a new EDC and new ECC parity. The disc image is changed in place: copy it
    first. Returns the number of sectors rewritten.
    """
    if entry.interleaved:
        raise ImageError(tr("{0} is an interleaved stream, not plain data", entry.path))
    if len(data) != entry.size:
        raise ImageError(tr("the new data of {0} is {1} bytes; the file is {2} bytes", entry.path, len(data), entry.size))
    segments = parse_layout(cue_path)
    # Plan every changed sector before the first write, so a refused sector leaves the image untouched.
    planned: List[Tuple[str, int, bytes]] = []
    for index in range((entry.size + SECTOR - 1) // SECTOR):
        lba = entry.extent + index
        seg = _segment_of(segments, lba)
        if seg.data_offset is None or seg.raw != RAW_2352 or seg.data_offset != MODE2_FORM1_OFFSET:
            raise ImageError(tr("sector {0} is not a PlayStation Mode 2 Form 1 sector", lba))
        position = seg.file_offset + (lba - seg.first) * seg.raw
        with open(seg.path, "rb") as handle:
            handle.seek(position)
            raw = bytearray(handle.read(RAW_2352))
        if len(raw) != RAW_2352:
            raise ImageError(tr("sector {0} is cut short in the track file", lba))
        chunk = data[index * SECTOR:(index + 1) * SECTOR]
        old = bytes(raw[MODE2_FORM1_OFFSET:MODE2_FORM1_OFFSET + SECTOR])
        new = chunk + old[len(chunk):]
        if new == old:
            continue
        raw[MODE2_FORM1_OFFSET:MODE2_FORM1_OFFSET + SECTOR] = new
        fix_sector(raw)
        planned.append((seg.path, position, bytes(raw)))
    for path, position, raw in planned:
        with open(path, "r+b") as handle:
            handle.seek(position)
            handle.write(raw)
    return len(planned)


def _copy_file(src_path: str, dst_path: str, progress: Callable[[int, str], None],
               is_cancelled: Callable[[], bool]) -> bool:
    """Copy one file in chunks, reporting progress. False when cancelled."""
    total = os.path.getsize(src_path)
    name = os.path.basename(src_path)
    done = 0
    with open(src_path, "rb") as src, open(dst_path, "wb") as out:
        while done < total:
            if is_cancelled():
                return False
            chunk = src.read(min(COPY_CHUNK, total - done))
            if not chunk:
                raise ImageError(tr("the image ends inside a file"))
            out.write(chunk)
            done += len(chunk)
            progress(min(99, 100 * done // total), name)
    return True


def write_set(cue_path: str, out_dir: str, replacements: Mapping[str, bytes], progress: Callable[[int, str], None],
              is_cancelled: Callable[[], bool]) -> Optional[str]:
    """Copy the disc set to ``out_dir`` and write ``replacements`` (disc path -> same-length bytes) into the copy.

    Returns the new cue path, or None when cancelled. The source set is not changed. ImageError for a path that is not
    a plain file of the disc, or for a length that differs from the file's.
    """
    src_dir = os.path.dirname(os.path.abspath(cue_path))
    if os.path.abspath(out_dir) == src_dir:
        raise ImageError(tr("the output folder is the folder of the disc image"))
    os.makedirs(out_dir, exist_ok=True)
    tracks: List[str] = []
    for seg in parse_layout(cue_path):
        if seg.path not in tracks:
            tracks.append(seg.path)
    for src_path in [*tracks, cue_path]:
        if not _copy_file(src_path, os.path.join(out_dir, os.path.basename(src_path)), progress, is_cancelled):
            return None
    out_cue = os.path.join(out_dir, os.path.basename(cue_path))
    stream = GdRomStream(out_cue)
    try:
        entries = {entry.path: entry for entry in PsxDiscImage(stream).files()}
    finally:
        stream.close()
    for path in sorted(replacements):
        if is_cancelled():
            return None
        if path not in entries:
            raise ImageError(tr("{0} is not a file of the disc", path))
        write_file(out_cue, entries[path], replacements[path])
    return out_cue
