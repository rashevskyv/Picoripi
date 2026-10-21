"""Build the Okami PlayStation 2 disc image: the changed message entries written into their AFS archives.

The output is a copy of the disc image. An archive that grew into the free sectors after it is written in place; one
that grew past them is written at the end of the image. Its root directory record (extent and size) and the volume
size change to match. Nothing else of the disc changes. A build without changes is a copy, byte for byte.
"""
import json
import os
from pathlib import Path
from typing import Callable, Dict, List, Tuple

from core.containers import afs as core_afs
from core.containers.image_files import ImageError
from core.i18n import tr
from plugins.common import romfs_mod
from plugins.okami_ps2 import afs, iso
from plugins.okami_ps2.unpack import ARCHIVES, REF_NAME
from utils.logging_utils import log_warning

COPY_CHUNK = 8 * 1024 * 1024
IMAGE_NAME = "Okami (USA) Ukrainian.iso"
SECTOR = iso.SECTOR


def read_changes(source_dir: str, translation_dir: str) -> Dict[str, Dict[int, bytes]]:
    """``{archive name: {entry index: bytes}}`` of the translation files that differ from the unpacked source."""
    out: Dict[str, Dict[int, bytes]] = {}
    for rel, data in romfs_mod.changed_files(source_dir, translation_dir).items():
        parts = rel.split("/")
        archive = f"_{parts[1]}.AFS" if len(parts) == 3 and parts[0] == "afs" else ""
        if archive not in ARCHIVES or not parts[2].endswith(".bin") or not parts[2][:-4].isdigit():
            log_warning(f"okami_ps2: {rel} is not a message entry of the disc; it is not written")
            continue
        out.setdefault(archive, {})[int(parts[2][:-4])] = data
    return out


def _copy(source: str, target: str, progress: Callable[[int, str], None], is_cancelled: Callable[[], bool]) -> None:
    total = os.path.getsize(source)
    done = 0
    with open(source, "rb") as src, open(target, "wb") as out:
        while True:
            if is_cancelled():
                raise InterruptedError()
            chunk = src.read(COPY_CHUNK)
            if not chunk:
                break
            out.write(chunk)
            done += len(chunk)
            progress(100 * done // max(1, total), tr("Copying the disc image"))


def _room_bytes(extents: List[Tuple[int, int]], lba: int, volume: int) -> int:
    """The bytes from sector ``lba`` up to the next used sector of the disc (or the end of the volume)."""
    starts = [start for start, _count in extents if start > lba]
    return ((min(starts) if starts else volume) - lba) * SECTOR


def build_image(source_image: str, changes: Dict[str, Dict[int, bytes]], output_path: str,
                progress: Callable[[int, str], None], is_cancelled: Callable[[], bool]) -> str:
    """Write the disc image with ``changes`` (archive name, entry index, bytes) to ``output_path``."""
    _copy(source_image, output_path, progress, is_cancelled)
    if not changes:
        return output_path
    with open(source_image, "rb") as src, open(output_path, "r+b") as out:
        extents = iso.used_extents(src)
        volume = iso.volume_sectors(src)
        for name in ARCHIVES:
            files = changes.get(name)
            if not files:
                continue
            if is_cancelled():
                raise InterruptedError()
            archive = iso.find(src, name)
            record = iso.root_record(src, name)
            if archive is None or record is None:
                raise ImageError(tr("The disc has no {0}.", name))
            read = afs.ps2_reader(src, archive)
            size = core_afs.new_size(read, archive.size, files)
            lba = archive.lba
            if size > _room_bytes(extents, archive.lba, volume):
                lba = volume
                volume = lba + size // SECTOR
                iso.write_volume_sectors(out, volume)
            out.seek(lba * SECTOR)
            core_afs.write_to(read, archive.size, out, files)
            iso.write_extent(out, record[0], lba, size)
            progress(100, tr("Writing {0}", name))
    return output_path


def build_ps2(source_dir: str, translation_dir: str, output_dir: str,
              progress: Callable[[int, str], None], is_cancelled: Callable[[], bool]) -> str:
    """The disc image of the translation, written into ``output_dir``; returns its path."""
    ref = Path(source_dir, REF_NAME)
    if not ref.is_file():
        raise ValueError(tr("The unpacked folder has no {0}: unpack the disc again.", REF_NAME))
    image = json.loads(ref.read_text(encoding="utf-8")).get("image", "")
    if not os.path.isfile(image):
        raise ValueError(tr("The disc image {0} is not on disk.", image))
    changes = read_changes(source_dir, translation_dir)
    return build_image(image, changes, os.path.join(output_dir, IMAGE_NAME), progress, is_cancelled)
