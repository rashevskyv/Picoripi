"""Okami (PlayStation 2, USA): the message containers of the two AFS archives on the disc, one file per entry.

The disc is read in place. An entry is written to ``afs/DATA0/0478.bin`` (archive, then the entry index); each file is the
container exactly as on the disc, so the HD text layer (``plugins.okami_hd.textfile``) reads and writes it.
"""
import os
from typing import Any, Callable, Dict, Optional

from core.i18n import tr
from core.containers.image_files import ImageError
from plugins.okami_ps2 import afs, iso

DISC_ID = b"SLUS_211.15"
ARCHIVES = ("_DATA0.AFS", "_DATA1.AFS")


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
        for number, name in enumerate(ARCHIVES, start=1):
            archive = iso.find(image, name)
            if archive is None:
                raise ImageError(tr("The disc has no {0}.", name))
            entries = afs.message_entries(image, archive)
            folder = os.path.join(target_dir, "afs", name[1:-4])
            os.makedirs(folder, exist_ok=True)
            for position, entry in enumerate(entries, start=1):
                if is_cancelled():
                    return None
                progress(100 * position // max(1, len(entries)), name)
                with open(os.path.join(folder, f"{entry.index:04d}.bin"), "wb") as out:
                    out.write(afs.read_entry(image, archive, entry))
    progress(100, "")
    return target_dir
