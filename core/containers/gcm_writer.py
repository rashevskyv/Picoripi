"""Write a GameCube disc image with changed files: copy the image, then write each changed file in place.

The source image is never written. ``write_disc`` streams a copy into ``<out>.tmp`` (chunks, cancel between chunks),
then patches that copy: a file that is not longer than before is written over its old bytes (its tail zero-filled);
a file that grew moves to the first free gap that is aligned to ``ALIGN``. Each changed file gets its FST entry's
offset and size patched. No new files: a path the disc does not hold is refused. ``sys/main.dol`` may change only
within its size. Unchanged input gives a byte-identical output. The output replaces ``out`` only after the write is
done, through ``os.replace``, so a cancelled or failed write leaves no partial image.
"""
from __future__ import annotations

from core.i18n import tr
import os
import struct
from pathlib import Path
from typing import Callable, Dict, List, Mapping, Optional, Tuple

from core.containers.gcm import GameCubeImage
from core.containers.image_files import CHUNK, ImageError, ImageFile
from core.containers.wia import WiaStream, open_disc

ALIGN = 0x8000
# The largest single-layer GameCube disc. A changed file may use the space up to here.
GC_LAYER_LIMIT = 1459978240
Progress = Callable[[int, str], None]
Cancelled = Callable[[], bool]


def _align(value: int) -> int:
    return (value + ALIGN - 1) // ALIGN * ALIGN


def _free_offset(spans: List[Tuple[int, int]], need: int) -> Optional[int]:
    """The first aligned offset where ``need`` bytes fit between the used ``spans`` (start, end) and the limit."""
    cursor = 0
    for start, end in sorted(spans) + [(GC_LAYER_LIMIT, GC_LAYER_LIMIT)]:
        at = _align(cursor)
        if at + need <= start:
            return at
        cursor = max(cursor, end)
    return None


def _check_changes(changes: Mapping[str, bytes], by_path: Dict[str, Tuple[int, ImageFile]],
                   sys_by_path: Dict[str, ImageFile]) -> None:
    for rel, blob in changes.items():
        if not isinstance(blob, (bytes, bytearray)):
            raise ImageError(tr("{0}: the new content is not bytes", rel))
        if rel.startswith("sys/"):
            if rel != "sys/main.dol":
                raise ImageError(tr("{0}: only sys/main.dol may change, and only within its size", rel))
            if len(blob) != sys_by_path[rel].size:
                raise ImageError(tr("sys/main.dol changed size: the executable must keep its size"))
        elif rel not in by_path:
            raise ImageError(tr("{0}: the disc holds no such file (new files are not written)", rel))


def _copy(source: Path, tmp: Path, progress: Progress, is_cancelled: Cancelled) -> bool:
    """Stream the disc ``source`` into ``tmp`` in chunks, decoding a WIA or RVZ source. False when cancelled."""
    done = 0
    with open_disc(source) as src, open(tmp, "wb") as dst:
        total = (src.size if isinstance(src, WiaStream) else source.stat().st_size) or 1
        while True:
            if is_cancelled():
                return False
            data = src.read(CHUNK)
            if not data:
                break
            dst.write(data)
            done += len(data)
            progress(min(89, 90 * done // total), "copy")
    return True


def write_disc(source: str | Path, out: str | Path, changes: Mapping[str, bytes],
               progress: Progress, is_cancelled: Cancelled) -> Optional[str]:
    """Write ``out``: the disc ``source`` with the ``changes`` ({disc path: new bytes}) applied.

    Returns the path of ``out``, or None when cancelled (no ``out`` is written then). Raises ImageError for a
    change the disc cannot take, and for an ``out`` that is the source itself.
    """
    source, out = Path(source), Path(out)
    if out.exists() and os.path.samefile(source, out):
        raise ImageError(tr("the output must not be the source image"))
    with open_disc(source) as stream:
        image = GameCubeImage(stream)
        slots = image.fst_slots()
        sys_entries = [entry for entry in image.entries() if not entry.path.startswith("files/")]
    by_path = {entry.path: (entry_at, entry) for entry_at, entry in slots}
    sys_by_path = {entry.path: entry for entry in sys_entries}
    _check_changes(changes, by_path, sys_by_path)

    # The used spans: the system files and every file of the disc. A moved file takes one of the free gaps.
    spans = [(entry.offset, entry.offset + entry.size) for entry in sys_entries]
    spans += [(entry.offset, entry.offset + entry.size) for _at, entry in slots]

    tmp = out.with_name(out.name + ".tmp")
    try:
        if not _copy(source, tmp, progress, is_cancelled):
            return None
        progress(90, "write")
        with open(tmp, "r+b") as disc:
            for index, rel in enumerate(sorted(changes)):
                if is_cancelled():
                    return None
                blob = bytes(changes[rel])
                if rel == "sys/main.dol":   # same size, not in the FST: written in place, nothing else to patch
                    disc.seek(sys_by_path[rel].offset)
                    disc.write(blob)
                    progress(90 + 9 * (index + 1) // max(1, len(changes)), rel)
                    continue
                entry_at, entry = by_path[rel]
                if len(blob) <= entry.size:
                    offset = entry.offset
                    disc.seek(offset)
                    disc.write(blob)
                    if len(blob) < entry.size:   # a shorter file: zero the tail of its old place
                        disc.write(bytes(entry.size - len(blob)))
                    size = len(blob)
                else:
                    own = (entry.offset, entry.offset + entry.size)
                    others = [span for span in spans if span != own]
                    offset = _free_offset(others, len(blob))
                    if offset is None:
                        raise ImageError(tr("{0} does not fit on the disc", rel))
                    disc.seek(offset)
                    disc.write(blob)
                    size = len(blob)
                    spans = others + [(offset, offset + size)]
                disc.seek(entry_at + 4)
                disc.write(struct.pack(">II", offset, size))
                progress(90 + 9 * (index + 1) // max(1, len(changes)), rel)
        if is_cancelled():
            return None
        os.replace(tmp, out)
        progress(100, "")
        return str(out)
    finally:
        if tmp.exists():
            tmp.unlink()
