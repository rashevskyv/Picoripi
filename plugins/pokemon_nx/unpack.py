"""Unpack Pokémon Sword / Shield / Legends: Arceus in the Project Manager wizard: the English text, fonts and layouts.

The base game and its newest update are read with Picoripi's Switch reader (``core/containers/switch_images``): the
update's RomFS is a BKTR patch over the base RomFS, and the reader applies it. Legends: Arceus packs (``.gfpak``) are
written as they are; their contents need Oodle and are unpacked by ``1_unpack.bat`` only.
"""
import re
from typing import Callable, Dict, Optional

from core.containers.image_files import ImageError
from core.i18n import tr
from core.project_library import images

# RomFS paths the project needs: English messages, fonts, English layout archives, and the Oodle packs as files.
SOURCE_RE = re.compile(r"^/bin/message/English/|^/bin/font/|^/bin/appli/[^/]+/bin/[^/]+_eng\.arc$"
                       r"|^/bin/archive/appli/[^/]+_eng\.gfpak$")
GAME_IDS = ("0100ABF008968000",   # Pokémon Sword base
            "01008DB008C2C000",   # Pokémon Shield base
            "01001F5010DFA000")   # Pokémon Legends: Arceus base
ROMFS = "romfs"


def unpack(sources: Dict[str, str], target_dir: str, progress: Callable[[int, str], None],
           is_cancelled: Callable[[], bool]) -> Optional[str]:
    """Write the selected files of the patched RomFS into ``target_dir``; the folder is the project's source root.

    Raises ImageError when the base file is not one of the games above, or when the update is missing.
    """
    base, update = sources.get("base"), sources.get("update")
    if not base:
        return None
    found = images.identify(base)
    if found is None or found.get("game_id") not in GAME_IDS:
        raise ImageError(tr("The base file is not a Sword, Shield or Legends: Arceus image."))
    if not update:
        raise ImageError(tr("Choose the update file too: the English text is in the update."))
    # The cache of a compressed (.nsz) image is a folder of the target: the reader deletes its copy on close.
    with images.open_image(base, target_dir, is_cancelled, progress) as base_reader, \
            images.open_image(update, target_dir, is_cancelled, progress) as update_reader:
        wanted = []
        for entry in update_reader.patched_romfs_entries(base_reader):
            path = entry.path[len(ROMFS):]
            if SOURCE_RE.search(path):
                wanted.append(entry._replace(path=path.lstrip("/")))
        progress(0, tr("Writing {0} files", str(len(wanted))))
        if not images.write_entries(update_reader, wanted, target_dir, progress, is_cancelled):
            return None
    return target_dir
