"""Build the translated Dreamcast disc set: the changed field scripts go into a copy of the USA GD-ROM set.

The source disc is read in place and never changed. The new set (cue sheet and track files) goes into the output
folder under the disc's own file names. A file the disc does not hold is refused: no file is added.
"""
from __future__ import annotations

from typing import Callable

from core.containers import gdrom_writer
from core.i18n import tr
from plugins.skies_of_arcadia.build import changed_files, disc_of_source

from . import unpack

Progress = Callable[[int, str], None]
Cancelled = Callable[[], bool]


def build_gdrom_set(source_dir: str, translation_dir: str, output_dir: str,
                    progress: Progress, is_cancelled: Cancelled) -> str:
    """Write the translated disc set into ``output_dir`` and return the new cue sheet's path."""
    cue = disc_of_source(source_dir)
    replacements = {unpack.FILES + rel: data for rel, data in changed_files(source_dir, translation_dir).items()}
    progress(0, tr("Writing the disc set..."))
    result = gdrom_writer.write_set(str(cue), output_dir, replacements, progress, is_cancelled)
    if result is None:
        return output_dir
    progress(100, "")
    return result
