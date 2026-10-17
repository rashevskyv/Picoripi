"""Write a Dreamcast GD-ROM set (BIN/CUE) whose HD volume has some files replaced.

Facts from the owner's Grandia II disc (see ``core.containers.gdrom``): ISO 9660 extents of the HD volume are
absolute sectors; the last data track of the HD area ends the disc. A replaced file is appended as new sectors at
the end of that track, the track file grows, and its directory record (in an earlier track) gets the new extent
and size in both byte orders. The PVD volume size is set to the new end. A changed sector gets a new EDC; ECC bytes
are left zero (the user data and the EDC are what a reader checks; no ECC is generated here).

Tracks that change nothing are copied byte for byte: a write with no replacements gives the same files.
"""
from __future__ import annotations

import os
import shutil
import struct
from typing import Callable, Dict, List, Mapping, Optional, Tuple

from core.containers.gdrom import HD_BASE, PVD_SECTOR, RAW_2352, SECTOR, GdRomImage, GdRomStream, parse_layout
from core.containers.image_files import ImageError, copy_range
from core.i18n import tr

SYNC = b"\x00" + b"\xff" * 10 + b"\x00"
MSF_OFFSET = 150
EDC_TABLE = []
for _i in range(256):
    _r = _i
    for _ in range(8):
        _r = (_r >> 1) ^ 0xD8018001 if _r & 1 else _r >> 1
    EDC_TABLE.append(_r)

Progress = Callable[[int, str], None]
Cancelled = Callable[[], bool]


def edc(data: bytes) -> int:
    """The CD-ROM mode 1 error detection code of the first 2064 bytes of a raw sector."""
    value = 0
    for byte in data:
        value = EDC_TABLE[(value ^ byte) & 0xFF] ^ (value >> 8)
    return value


def bcd(value: int) -> int:
    return (value // 10) << 4 | (value % 10)


def raw_sector(user: bytes, lba: int) -> bytes:
    """A MODE1/2352 sector: sync, the MSF address (absolute sector + 150, as the owner's tracks), mode 1, 2048 user
    bytes, EDC, 8 zero bytes and 276 zero ECC bytes."""
    frames = lba + MSF_OFFSET
    msf = bytes((bcd(frames // (75 * 60)), bcd(frames // 75 % 60), bcd(frames % 75), 1))
    body = SYNC + msf + user.ljust(SECTOR, b"\x00")[:SECTOR]
    return body + struct.pack("<I", edc(body)) + b"\x00" * 8 + b"\x00" * 276


def _set_edc(raw: bytes) -> bytes:
    return raw[:2064] + struct.pack("<I", edc(raw[:2064])) + raw[2068:]


def _segment_of(segments, lba: int):
    for seg in segments:
        if seg.first <= lba < seg.first + seg.count:
            return seg
    raise ImageError(tr("sector {0} is not on the disc", lba))


def write_set(cue_path: str, out_dir: str, replacements: Mapping[str, bytes], progress: Progress,
              is_cancelled: Cancelled) -> Optional[str]:
    """Write the set with the HD files of ``replacements`` (path inside the image, e.g. ``files/MAP/A000.AFS``).

    Returns the new cue path, or None when cancelled. ImageError for a file that is not on the HD volume, or when
    the output folder is the folder of the input set.
    """
    segments = parse_layout(cue_path)
    tail = [seg for seg in segments if seg.first >= HD_BASE][-1]
    if tail.data_offset is None:
        raise ImageError(tr("the last track of the HD area holds no data"))
    src_dir = os.path.dirname(os.path.abspath(cue_path))
    if os.path.abspath(out_dir) == src_dir:
        raise ImageError(tr("the output folder is the folder of the disc image"))
    stream = GdRomStream(cue_path)
    try:
        where: Dict[str, int] = {}
        entries = {entry.path: entry for entry in GdRomImage(stream).entries(where)}
    finally:
        stream.close()
    cursor = tail.first + tail.count
    records: List[Tuple[int, int, int]] = []   # (stream offset of the record, new extent, new size)
    appended: List[Tuple[int, bytes]] = []     # (first new sector, file bytes)
    for path in sorted(replacements):
        if path not in entries or entries[path].offset < HD_BASE * SECTOR:
            raise ImageError(tr("{0} is not a file of the HD volume", path))
        data = replacements[path]
        sectors = (len(data) + SECTOR - 1) // SECTOR
        records.append((where[path], cursor, len(data)))
        appended.append((cursor, data))
        cursor += sectors
    new_end = cursor
    patches: Dict[str, List[Tuple[int, bytes]]] = {}   # track file -> (byte offset in file, bytes)
    touched: Dict[str, set] = {}                       # track file -> sector starts to re-EDC
    for rec_offset, extent, size in records:
        lba = rec_offset // SECTOR
        seg = _segment_of(segments, lba)
        sector_start = seg.file_offset + (lba - seg.first) * seg.raw
        at = sector_start + seg.data_offset + rec_offset % SECTOR
        fields = struct.pack("<I", extent) + struct.pack(">I", extent)
        fields_size = struct.pack("<I", size) + struct.pack(">I", size)
        patches.setdefault(seg.path, []).append((at + 2, fields))
        patches.setdefault(seg.path, []).append((at + 10, fields_size))
        touched.setdefault(seg.path, set()).add(sector_start)
    if records:   # the volume size follows the new end; an unchanged set keeps its PVD byte for byte
        pvd_lba = HD_BASE + PVD_SECTOR
        pvd_seg = _segment_of(segments, pvd_lba)
        pvd_start = pvd_seg.file_offset + (pvd_lba - pvd_seg.first) * pvd_seg.raw
        volume = new_end - HD_BASE
        pvd_at = pvd_start + pvd_seg.data_offset
        patches.setdefault(pvd_seg.path, []).append((pvd_at + 80, struct.pack("<I", volume) + struct.pack(">I", volume)))
        touched.setdefault(pvd_seg.path, set()).add(pvd_start)
    os.makedirs(out_dir, exist_ok=True)
    seen = set()
    for seg in segments:
        if seg.path in seen:
            continue
        seen.add(seg.path)
        name = os.path.basename(seg.path)
        progress(0, name)
        total = os.path.getsize(seg.path)
        dst = os.path.join(out_dir, name)
        with open(seg.path, "rb") as src, open(dst, "wb") as out:
            done = [0]

            def on_bytes(count: int) -> None:
                done[0] += count
                progress(min(99, 100 * done[0] // max(1, total)), name)

            if not copy_range(src, 0, total, out, is_cancelled, on_bytes):
                return None
        if seg.path in patches or seg.path == tail.path:
            with open(dst, "r+b") as out:
                for at, blob in patches.get(seg.path, []):
                    out.seek(at)
                    out.write(blob)
                for start in sorted(touched.get(seg.path, ())):
                    out.seek(start)
                    raw = out.read(RAW_2352)
                    out.seek(start)
                    out.write(_set_edc(raw))
                if seg.path == tail.path:
                    out.seek(0, 2)
                    for first, data in appended:
                        for index in range((len(data) + SECTOR - 1) // SECTOR):
                            chunk = data[index * SECTOR:(index + 1) * SECTOR]
                            out.write(raw_sector(chunk, first + index))
        if is_cancelled():
            return None
    cue_out = os.path.join(out_dir, os.path.basename(cue_path))
    shutil.copyfile(cue_path, cue_out)
    progress(100, "")
    return cue_out
