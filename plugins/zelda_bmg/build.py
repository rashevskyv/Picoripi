"""Build targets of Twilight Princess GameCube: the disc image (``gc_iso``) and a Dusklight mod (``dusk_mod``).

The source folder is the project's ``files/res/Msgus`` in the unpacked disc. The translation folder holds the archives
that Picoripi saved, at the same relative paths (``bmgres1.arc``), and the Font Editor's fonts in ``../Fontus``. A
changed file replaces the disc's file of the same path; a file the disc does not hold is refused (see write_disc).

The original disc is never changed: ``unpack_sources`` records its path (plugins/common/disc_source.py) and the build
copies it through ``write_disc``. The Dusklight mod is a ``.dusk`` zip: ``mod.json`` and ``overlay/`` with each file at
its disc path, so the port reads the translation next to the user's own disc.
"""
import json
import os
import zipfile
from pathlib import Path
from typing import Callable, Dict, List, Tuple

from core.containers.gcm_writer import write_disc
from core.i18n import tr
from plugins.common.disc_source import disc_of_source, find_disc_root

Progress = Callable[[int, str], None]
Cancelled = Callable[[], bool]

GC_ISO_NAME = "Legend of Zelda, The - Twilight Princess (USA)_UA.iso"
DUSK_NAME = "Twilight Princess (UA).dusk"
DUSK_ID = "org.picoripi.zelda_tp_ua"
DISC_PREFIX = "files/"   # the unpacked tree's folder for the disc's file system; a Dusklight overlay path drops it


def changed_files(pairs: List[Tuple[Path, Path, str]]) -> Dict[str, bytes]:
    """{disc path: new bytes} for each translated file that differs from its source file.

    ``pairs`` holds (source folder, translation folder, disc folder). A translation folder that does not exist is
    skipped. A translated file the source folder does not hold is refused, so no file is added to the disc.
    """
    changes: Dict[str, bytes] = {}
    for source, translation, disc_folder in pairs:
        if not translation.is_dir():
            continue
        for path in sorted(translation.rglob("*")):
            if not path.is_file():
                continue
            rel = path.relative_to(translation).as_posix()
            base = source / rel
            if not base.is_file():
                raise ValueError(tr("{0}: not on the disc (new files are not written)", f"{disc_folder}/{rel}"))
            data = path.read_bytes()
            if data != base.read_bytes():
                changes[f"{disc_folder}/{rel}"] = data
    return changes


def _gc_changes(source_dir: str, translation_dir: str) -> Tuple[Path, Dict[str, bytes]]:
    """(the disc image, {disc path: bytes}) of a GameCube source and its translation folders."""
    source, translation = Path(source_dir), Path(translation_dir)
    root = find_disc_root(source)
    prefix = source.relative_to(root).as_posix()             # files/res/Msgus
    font_prefix = Path(prefix).parent.as_posix() + "/Fontus"  # files/res/Fontus
    changes = changed_files([
        (source, translation, prefix),
        (source.parent / "Fontus", translation.parent / "Fontus", font_prefix),
    ])
    return disc_of_source(root), changes


def build_gc_iso(source_dir: str, translation_dir: str, output_dir: str,
                 progress: Progress, is_cancelled: Cancelled) -> str:
    """Write the translated disc into ``output_dir`` and return its path. With no change the disc is copied as it is."""
    image, changes = _gc_changes(source_dir, translation_dir)
    out = Path(output_dir) / GC_ISO_NAME
    write_disc(image, out, changes, progress, is_cancelled)
    return str(out)


def build_dusk_mod(source_dir: str, translation_dir: str, output_dir: str,
                   progress: Progress, is_cancelled: Cancelled) -> str:
    """Write ``<output_dir>/Twilight Princess (UA).dusk`` and return its path. It needs the user's own disc."""
    _image, changes = _gc_changes(source_dir, translation_dir)
    if not changes:
        raise ValueError(tr("No translated file differs from the game: nothing to build."))
    manifest = {
        "id": DUSK_ID,
        "name": "The Legend of Zelda: Twilight Princess (Ukrainian)",
        "version": "1.0.0",
        "author": "Picoripi",
        "description": "Ukrainian text and fonts. Needs the original USA disc image.",
    }
    out = Path(output_dir) / DUSK_NAME
    tmp = out.with_name(out.name + ".tmp")
    total = len(changes)
    with zipfile.ZipFile(tmp, "w", zipfile.ZIP_DEFLATED) as bundle:
        bundle.writestr("mod.json", json.dumps(manifest, ensure_ascii=False, indent=2))
        for index, (disc_path, data) in enumerate(sorted(changes.items())):
            if is_cancelled():
                break
            progress(100 * index // total, disc_path)
            overlay = disc_path[len(DISC_PREFIX):] if disc_path.startswith(DISC_PREFIX) else disc_path
            bundle.writestr("overlay/" + overlay, data)
    os.replace(tmp, out)
    progress(100, "")
    return str(out)
