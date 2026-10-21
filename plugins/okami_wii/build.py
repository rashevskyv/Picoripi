"""Okami (Wii): the changed message entries, as a Wii disc image (ISO) or as one file per entry.

The disc image is the base (ROWP08, from ``source_image.ref``) with a plain copy made by ``wii_writer.copy_as_iso``.
Each archive that has a changed entry is read from the source disc, its entries are replaced (``core.containers.afs``),
and the archive is written back with ``wii_writer.write_changes``. A grown archive moves to a free gap in the DATA
partition; the original disc is never changed. The key is the Wii key file in console keys (slot ``wii``).

``build_changed`` (the first version) writes each changed entry as ``afs/DATA0/0478.bin``, for a tool that patches
the disc itself.
"""
import json
import os
from pathlib import Path
from typing import Callable, Dict

from core.containers import afs as core_afs
from core.containers import wii_disc, wii_writer
from core.i18n import tr
from core.project_library import console_keys
from core.project_library.build import Cancel
from plugins.okami_ps2 import afs
from plugins.okami_ps2 import build as ps2_build

TARGET_ID = "wii_changed_entries"
ISO_TARGET = "wii_iso"
ISO_NAME = "OkamiUA_Wii.iso"
REF_NAME = "source_image.ref"
# The PS2 archive names of the changes (``_DATA0.AFS``) and the Wii file each one is on the disc.
DISC_FILES = {"_DATA0.AFS": "files/_data0.afs", "_DATA1.AFS": "files/_data1.afs"}
Progress = Callable[[int, str], None]
Cancelled = Callable[[], bool]


def read_changes(source_dir: str, translation_dir: str) -> Dict[str, Dict[int, bytes]]:
    """``{disc path: {entry index: bytes}}`` of the changed message entries (``afs/DATA0/NNNN.bin``)."""
    return {DISC_FILES[archive]: files for archive, files in ps2_build.read_changes(source_dir, translation_dir).items()
            if archive in DISC_FILES}


def _read_file(image_path: str, rel: str) -> bytes:
    """The bytes of one file of the Wii disc (decrypted, through the key file)."""
    keys = console_keys.path_for("wii")
    if not keys:
        raise ValueError(tr("Set the Wii key file in the console keys first."))
    with open(image_path, "rb") as stream:
        image = wii_disc.WiiImage(stream, wii_disc.load_common_key(keys))
        entry = {item.path.lower(): item for item in image.entries()}[rel]
        return afs.stream_reader(image.source(entry), entry.offset, entry.size)(0, entry.size)


def build_iso(source_dir: str, translation_dir: str, output_dir: str,
              progress: Progress, is_cancelled: Cancelled) -> str:
    """Write the translated disc image into ``output_dir`` and return its path."""
    ref = Path(source_dir, REF_NAME)
    if not ref.is_file():
        raise ValueError(tr("The unpacked folder has no {0}: unpack the disc again.", REF_NAME))
    image = json.loads(ref.read_text(encoding="utf-8")).get("image", "")
    if not os.path.isfile(image):
        raise ValueError(tr("The disc image {0} is not on disk.", image))
    keys = console_keys.path_for("wii")
    if not keys:
        raise ValueError(tr("Set the Wii key file in the console keys first."))
    common = wii_disc.load_common_key(keys)
    changes = read_changes(source_dir, translation_dir)
    out_dir = Path(output_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    target = out_dir / ISO_NAME
    tmp = target.with_name(target.name + ".tmp")
    try:
        if not wii_writer.copy_as_iso(str(image), str(tmp), common, progress, is_cancelled):
            raise Cancel()
        if changes:
            replaced = {}
            for rel, replacements in changes.items():
                if is_cancelled():
                    raise InterruptedError()
                progress(96, tr("Rebuilding {0}", rel))
                replaced[rel] = core_afs.write(_read_file(image, rel), replacements)
            with open(tmp, "r+b") as stream:
                wii_writer.write_changes(stream, common, replaced)
        os.replace(tmp, target)
    except BaseException:
        tmp.unlink(missing_ok=True)
        raise
    progress(100, "")
    return str(target)


def build_changed(source_dir: str, translation_dir: str, output_dir: str,
                  progress: Progress, is_cancelled: Cancelled) -> str:
    """Write each changed message entry under ``output_dir/afs/<archive>/<index>.bin``; returns the folder."""
    changes = ps2_build.read_changes(source_dir, translation_dir)
    written = 0
    total = max(1, sum(len(files) for files in changes.values()))
    for archive, files in changes.items():
        folder = archive[1:-4]          # "_DATA0.AFS" -> "DATA0"
        for index, data in sorted(files.items()):
            if is_cancelled():
                raise InterruptedError()
            target = Path(output_dir, "afs", folder, f"{index:04d}.bin")
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(data)
            written += 1
            progress(100 * written // total, folder)
    progress(100, "")
    return output_dir
