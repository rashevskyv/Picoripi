"""Unpack Pokémon Sword / Shield in the Project Manager wizard: the English text, fonts and layout archives.

The base game and its newest update are read with Picoripi's Switch reader (``core/containers/switch_images``): the
update's RomFS is a BKTR patch over the base RomFS, and the reader applies it. Other Pokémon Switch games are not
unpacked here (Legends: Arceus packs need Oodle); for them the function returns None and the wizard uses the files as
they are.
"""
import re
import tempfile
from typing import Callable, Dict, Optional

from core.containers.image_files import ImageError
from core.i18n import tr
from core.project_library import images

# RomFS paths the project needs: English messages, fonts, and the English layout archives (text and pictures).
SOURCE_RE = re.compile(r"^/bin/message/English/|^/bin/font/|^/bin/appli/[^/]+/bin/[^/]+_eng\.arc$")
SWORD_SHIELD = ("0100ABF008968000", "01008DB008C2C000")   # Sword and Shield base title ids
ROMFS = "romfs"


def unpack(sources: Dict[str, str], target_dir: str, progress: Callable[[int, str], None],
           is_cancelled: Callable[[], bool]) -> Optional[str]:
    """Write the selected files of the patched RomFS into ``target_dir``; the folder is the project's source root."""
    base, update = sources.get("base"), sources.get("update")
    if not base or images.base_identity(base, SWORD_SHIELD) is None:
        return None
    if not update:
        raise ImageError(tr("Choose the update file too: the English text is in the update."))
    with tempfile.TemporaryDirectory() as cache:
        with images.open_image(base, cache, is_cancelled, progress) as base_reader, \
                images.open_image(update, cache, is_cancelled, progress) as update_reader:
            wanted = []
            for entry in update_reader.patched_romfs_entries(base_reader):
                path = entry.path[len(ROMFS):]
                if SOURCE_RE.search(path):
                    wanted.append(entry._replace(path=path.lstrip("/")))
            progress(0, tr("Writing {0} files", str(len(wanted))))
            if not images.write_entries(update_reader, wanted, target_dir, progress, is_cancelled):
                return None
    return target_dir
