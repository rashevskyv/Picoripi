"""Okami (PlayStation 2, USA): the message containers of the two AFS archives on the disc, one file per entry.

The disc is read in place. An entry is written to ``afs/DATA0/0478.bin`` (archive, then the entry index); each file is the
container exactly as on the disc, so the HD text layer (``plugins.okami_hd.textfile``) reads and writes it.
``source_image.ref`` holds the absolute path of the disc, so the build can write a new disc image from it.
"""
import json
import os
from pathlib import Path
from typing import Any, Callable, Dict, Optional

from core.i18n import tr
from core.containers.image_files import ImageError
from plugins.okami_ps2 import afs, iso

DISC_ID = b"SLUS_211.15"
ARCHIVES = ("_DATA0.AFS", "_DATA1.AFS")
REF_NAME = "source_image.ref"
PICTURES = "pictures"                 # the TIM2 pictures of each archive: pictures/DATA0/0022.tm2
PICTURE_SUFFIX = ".tm2"


def identify(path: str) -> Optional[Dict[str, Any]]:
    """``{"role", "platform", "libraries"}`` of the PlayStation 2 disc of Okami (USA), else None."""
    try:
        with open(path, "rb") as image:
            system = iso.find(image, "SYSTEM.CNF")
            if system is None:
                return None
            cnf = iso.read(image, system, 0, min(system.size, 4096))
    except OSError:
        return None
    if DISC_ID not in cnf:
        return None
    return {"role": "base", "platform": "ps2", "libraries": []}


def unpack(sources: Dict[str, str], target_dir: str, progress: Callable[[int, str], None],
           is_cancelled: Callable[[], bool]) -> Optional[str]:
    base = sources.get("base")
    if not base:
        return None
    if identify(base) is None:
        raise ImageError(tr("The file is not the Okami PlayStation 2 disc."))
    with open(base, "rb") as image:
        for name in ARCHIVES:
            archive = iso.find(image, name)
            if archive is None:
                raise ImageError(tr("The disc has no {0}.", name))
            read = afs.ps2_reader(image, archive)
            # Message containers (text) and TIM2 pictures (the pictures with words are listed in texture_sources.json).
            messages = afs.message_entries(read, archive.size)
            folder = os.path.join(target_dir, "afs", name[1:-4])
            os.makedirs(folder, exist_ok=True)
            for position, entry in enumerate(messages, start=1):
                if is_cancelled():
                    return None
                progress(100 * position // max(1, len(messages)), name)
                with open(os.path.join(folder, f"{entry.index:04d}.bin"), "wb") as out:
                    out.write(afs.read_entry(read, entry))
            # The TIM2 pictures (not message files: the translator opens them in the Textures window).
            pictures = afs.texture_entries(read, archive.size)
            picture_folder = os.path.join(target_dir, PICTURES, name[1:-4])
            os.makedirs(picture_folder, exist_ok=True)
            for entry in pictures:
                if is_cancelled():
                    return None
                with open(os.path.join(picture_folder, f"{entry.index:04d}{PICTURE_SUFFIX}"), "wb") as out:
                    out.write(afs.read_entry(read, entry))
    Path(target_dir, REF_NAME).write_text(json.dumps({"game_id": DISC_ID.decode(), "image": os.path.abspath(base)}),
                                          encoding="utf-8")
    progress(100, "")
    return target_dir
