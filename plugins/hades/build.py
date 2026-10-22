"""Build the Hades Switch mod: the changed text, subtitle and font files as an Atmosphere LayeredFS romfs.

The changed files of the translation go to ``atmosphere/contents/0100535012974000/romfs/<romfs path>``. The base title
ID is the mod's title: the game reads these files in place of the ones of the package, for the update as well.
"""
from pathlib import Path
from typing import Callable

from plugins.common import romfs_mod
from plugins.hades.unpack import BASE_ID

MOD_DIR = "atmosphere"


def build_switch(source_dir: str, translation_dir: str, output_dir: str,
                 progress: Callable[[int, str], None], is_cancelled: Callable[[], bool]) -> str:
    """Write the changed files under ``output_dir/atmosphere``; returns the output folder."""
    if is_cancelled():
        raise InterruptedError()
    progress(0, "Hades: changed files")
    changes = romfs_mod.changed_files(Path(source_dir), translation_dir)
    if is_cancelled():
        raise InterruptedError()
    romfs_mod.write_titles(Path(output_dir) / MOD_DIR, [BASE_ID], changes)
    progress(100, "Hades: done")
    return output_dir
