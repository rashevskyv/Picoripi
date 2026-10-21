"""Build the Okami HD Switch mod: the changed message files as a LayeredFS romfs (Atmosphere).

The changed files of the translation go to ``atmosphere/contents/0100276009872000/romfs/<romfs path>``. The game
reads them in place of the files of the .nsz. Nothing in the .nsz is rewritten.
"""
from pathlib import Path
from typing import Callable

from plugins.common import romfs_mod
from plugins.okami_hd.unpack import TITLE_ID

MOD_DIR = "atmosphere"


def build_switch(source_dir: str, translation_dir: str, output_dir: str,
                 progress: Callable[[int, str], None], is_cancelled: Callable[[], bool]) -> str:
    """Write the changed files under ``output_dir/atmosphere``; returns the output folder."""
    if is_cancelled():
        raise InterruptedError()
    progress(0, "Okami HD: changed files")
    changes = romfs_mod.changed_files(Path(source_dir), translation_dir)
    if is_cancelled():
        raise InterruptedError()
    romfs_mod.write_titles(Path(output_dir) / MOD_DIR, [TITLE_ID], changes)
    progress(100, "Okami HD: done")
    return output_dir
