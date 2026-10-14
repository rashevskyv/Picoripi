"""LAS Recomp: the version check of an unpacked base game and the ``lasrecomp`` build target (``romfs.bin``).

The recomp runs only Link's Awakening v1.0.0. It checks 8 bytes of ``exefs/main`` at 0x40 and reads ``romfs.bin`` from
its data folder. The build writes that image from the unpacked ``romfs`` tree, with the translated files replaced.
"""
from __future__ import annotations

import shutil
from pathlib import Path
from typing import Callable, Dict

from core.containers.romfs_write import RomfsWriteCancelled, write_romfs

TITLE_ID = "01006BB00C6F0000"
TARGET_ID = "lasrecomp"
BUILD_ID_AT = 0x40
BUILD_ID = bytes.fromhex("ae16f71e002af8cb")      # Link's Awakening v1.0.0, the id the recomp's launcher checks
ROMFS_NAME = "romfs.bin"
README = r"""Link's Awakening (Switch) for LAS Recomp

1. Copy romfs.bin over <data root>\extracted\romfs.bin.
2. Copy the files under romfs\ over <data root>\extracted\romfs\ (same paths). The recomp reads them too.
3. Start the recomp. Do not run its setup again: setup would rebuild romfs.bin from the old files.
"""


def check_unpacked(folder: str | Path) -> None:
    """Raise ValueError unless ``folder`` holds the base game v1.0.0 (the one the recomp runs)."""
    root = Path(folder)
    if not (root / "romfs").is_dir():
        raise ValueError("The package has no RomFS. It is an update, not the base game. Use the base game package.")
    try:
        with open(root / "exefs" / "main", "rb") as handle:
            handle.seek(BUILD_ID_AT)
            build_id = handle.read(len(BUILD_ID))
    except OSError:
        build_id = b""
    if build_id != BUILD_ID:
        raise ValueError("This is not Link's Awakening v1.0.0. LAS Recomp runs only v1.0.0. Use the base game package.")


def _overlay(romfs: Path, translation: Path) -> Dict[str, str]:
    """Translation files that replace a file of the unpacked romfs: relative path ("/") -> file on disk."""
    found: Dict[str, str] = {}
    if not translation.is_dir():
        return found
    for path in sorted(translation.rglob("*")):
        rel = path.relative_to(translation).as_posix()
        if path.is_file() and (romfs / rel).is_file():   # a file the 1.0.0 tree does not have is not added
            found[rel] = str(path)
    return found


def build(source_dir: str, translation_dir: str, output_dir: str,
          progress: Callable[[int, str], None], is_cancelled: Callable[[], bool]) -> str:
    """Write ``romfs.bin``, the overlaid files under ``romfs/`` and a README into ``output_dir``."""
    out = Path(output_dir)
    overlay = _overlay(Path(source_dir), Path(translation_dir))

    def on_bytes(done: int, total: int) -> None:
        progress(100 * done // max(total, 1), ROMFS_NAME)

    try:
        write_romfs(source_dir, str(out / ROMFS_NAME), on_bytes, is_cancelled, overlay)
    except RomfsWriteCancelled:
        return output_dir          # build.run_build sees the cancel and removes the folder
    for rel, source in overlay.items():   # texpatch and movie read these from the folder, not from romfs.bin
        target = out / "romfs" / rel
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(source, target)
    (out / "README.txt").write_text(README, encoding="utf-8")
    return output_dir
