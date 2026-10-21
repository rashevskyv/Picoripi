"""Okami HD (Switch, RomFS of the .nsz): the English message files, one per block, into the project's source folder.

Only the English files (no language suffix, e.g. ``st1/r101.bin``; the suffixes _f, _g, _j are other languages) in the
message folders are read; a file is kept when it has an MSD section the codec reads. The Switch key comes from the
key store (console "switch"), through ``images.open_image`` as for the other Switch plugins.
"""
import re
from typing import Any, Callable, Dict, Optional

from core.containers.image_files import ImageError
from core.i18n import tr
from core.project_library import images
from plugins.okami_hd import msd

TITLE_ID = "0100276009872000"          # Okami HD (Switch base game)
ROMFS = "romfs"
MESSAGE_FOLDERS = ("st0", "st1", "st2", "st3", "stc", "std", "ste", "stf", "id", "iteminfo")
MESSAGE_FILE = re.compile(r"^romfs/data/(?:%s)/[^/_]+\.(?:bin|dat|pac)$" % "|".join(MESSAGE_FOLDERS))
# The English font atlas (a BC7 texture at 0x93C0 of etc/core_30.bin) and the English help and control pictures.
FONT_FILE = "romfs/data/etc/core_30.bin"
PICTURE_FILE = re.compile(r"^romfs/data/illust/(?:help|control)_\d+(?:_[a-z]+)?\.dds$")


def identify(path: str) -> Optional[Dict[str, Any]]:
    """``{"role", "platform", "libraries"}`` of the Okami HD Switch image, else None."""
    found = images.identify(path)
    if found is None or found.get("kind") != images.KIND_SWITCH:
        return None
    if str(found.get("game_id") or "").upper() != TITLE_ID.upper():
        return None
    return {"role": "base", "platform": "switch", "libraries": []}


def _has_messages(data: bytes) -> bool:
    try:
        container = msd.parse_container(data)
    except msd.MsdError:
        return False
    return any(tag == "MSD" and msd.parse_section(container.section_bytes(index)) is not None
               for index, tag in enumerate(container.tags))


def unpack(sources: Dict[str, str], target_dir: str, progress: Callable[[int, str], None],
           is_cancelled: Callable[[], bool]) -> Optional[str]:
    """Write the English message files of the base game into ``target_dir``; the folder is the source root."""
    base = sources.get("base")
    if not base:
        return None
    found = images.identify(base)
    if found is None or str(found.get("game_id") or "").upper() != TITLE_ID.upper():
        raise ImageError(tr("The file is not the Okami HD Switch image."))
    with images.open_image(base, target_dir, is_cancelled, progress) as reader:
        candidates = [entry for entry in reader.entries() if MESSAGE_FILE.match(entry.path)]
        progress(0, tr("Checking {0} files", str(len(candidates))))
        wanted = []
        for entry in candidates:
            if is_cancelled():
                return None
            if _has_messages(reader.read(entry)):
                wanted.append(entry._replace(path=entry.path[len(ROMFS) + 1:]))
        for entry in reader.entries():
            if entry.path == FONT_FILE or (PICTURE_FILE.match(entry.path)
                                           and not re.search(r"_[fgj]\.dds$", entry.path)):
                wanted.append(entry._replace(path=entry.path[len(ROMFS) + 1:]))
        progress(0, tr("Writing {0} files", str(len(wanted))))
        if not images.write_entries(reader, wanted, target_dir, progress, is_cancelled):
            return None
    return target_dir


