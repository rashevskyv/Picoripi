"""Okami (Wii): the changed message entries as files, one per entry (``afs/DATA0/0478.bin``).

A new Wii disc image is not written yet. A Wii entry changes size with its text, so the archive and the disc need the
Wii writer (``feat/wii-writer``, not on main). Until it lands, the translated entries are the output.
"""
from pathlib import Path
from typing import Callable

from plugins.okami_ps2 import build as ps2_build

TARGET_ID = "wii_changed_entries"


def build_changed(source_dir: str, translation_dir: str, output_dir: str,
                  progress: Callable[[int, str], None], is_cancelled: Callable[[], bool]) -> str:
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
