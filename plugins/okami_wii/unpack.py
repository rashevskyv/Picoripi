"""Okami (Wii, ROWP08): the message containers of the two AFS archives in files/, one file per entry.

The disc is an encrypted Wii image, read through ``core.containers.wii_disc.WiiImage`` with the key file the user gave
(``console_keys`` slot ``wii``). The archives are streamed: only their tables and the message entries are read. An
entry is written to ``afs/DATA0/0478.bin``; each file is the container exactly as on the disc (big-endian). The AFS
table is little-endian, as on the PS2 disc. ``source_image.ref`` holds the absolute path of the disc.
"""
import json
import os
from pathlib import Path
from typing import Any, Callable, Dict, Optional

from core.containers import wii_disc
from core.containers.console_crypto import encrypted_error, key_path
from core.containers.image_files import ImageError
from core.i18n import tr
from plugins.okami_ps2 import afs

GAME_ID = "ROWP08"
ENDIAN = ">"                                    # the message containers of the Wii disc
ARCHIVES = (("files/_data0.afs", "DATA0"), ("files/_data1.afs", "DATA1"))
REF_NAME = "source_image.ref"


def identify(path: str) -> Optional[Dict[str, Any]]:
    """``{"role", "platform", "libraries"}`` of the Wii disc of Okami (ROWP08), else None. Reads the disc header only."""
    try:
        with open(path, "rb") as image:
            head = image.read(0x20)
    except OSError:
        return None
    info = wii_disc.locate(head)
    if info is None or info["game_id"] != GAME_ID:
        return None
    return {"role": "base", "platform": "wii", "libraries": []}


def unpack(sources: Dict[str, str], target_dir: str, progress: Callable[[int, str], None],
           is_cancelled: Callable[[], bool]) -> Optional[str]:
    base = sources.get("base")
    if not base:
        return None
    if identify(base) is None:
        raise ImageError(tr("The file is not the Okami Wii disc."))
    keys = key_path("wii")
    if keys is None:
        raise encrypted_error("wii", tr("Okami (Wii)"))
    with open(base, "rb") as stream:
        image = wii_disc.WiiImage(stream, wii_disc.load_common_key(keys))
        files = {entry.path.lower(): entry for entry in image.entries()}
        for path, folder_name in ARCHIVES:
            entry = files.get(path)
            if entry is None:
                raise ImageError(tr("The disc has no {0}.", path))
            read = afs.stream_reader(image.source(entry), entry.offset, entry.size)
            entries = afs.message_entries(read, entry.size, ENDIAN)
            folder = os.path.join(target_dir, "afs", folder_name)
            os.makedirs(folder, exist_ok=True)
            for position, item in enumerate(entries, start=1):
                if is_cancelled():
                    return None
                progress(100 * position // max(1, len(entries)), folder_name)
                with open(os.path.join(folder, f"{item.index:04d}.bin"), "wb") as out:
                    out.write(afs.read_entry(read, item))
    Path(target_dir, REF_NAME).write_text(json.dumps({"game_id": GAME_ID, "image": os.path.abspath(base)}),
                                          encoding="utf-8")
    progress(100, "")
    return target_dir
