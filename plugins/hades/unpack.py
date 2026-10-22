"""Hades (Switch): the English text, the English subtitles and the English fonts, unpacked in the project's source.

The base game (0100535012974000) and its update (0100535012974800) are read with Picoripi's Switch reader. A base file
that already holds the update (a merged package) needs no update file; a base file with an update's BKTR patch needs
the update file too. The Ukrainian reference files (``pl``) are kept in the source folder but are not translation blocks.
The Switch key comes from the key store (console ``switch``).
"""
import re
from contextlib import nullcontext
from typing import Any, Callable, Dict, Optional

from core.containers import console_crypto
from core.containers.image_files import ImageError
from core.i18n import tr
from core.project_library import console_keys, images

BASE_ID = "0100535012974000"     # Hades (Switch base game)
UPDATE_ID = "0100535012974800"   # Hades (Switch update)
HADES_MARKER = "Content/Game/Text/Languages.sjson"   # the language list every Hades RomFS holds
ROMFS_PREFIX = re.compile(r"^/?(?:romfs/)?")
SOURCE_RE = re.compile(r"^Content/(?:"
                       r"Game/Text/(?:en|pl)/[^/]+\.sjson"
                       r"|Game/Text/Languages\.sjson"
                       r"|Subtitles/(?:en|pl)/[^/]+\.csv"
                       r"|Win/Fonts/(?:en|pl)/[^/]+\.(?:xnb|remap)"
                       r")$")


def identify(path: str) -> Optional[Dict[str, Any]]:
    """``{"role", "platform", "libraries"}`` of a Hades Switch base or update image, else None.

    A repack with no ticket and no content meta names no title ID; it is the base game when its RomFS holds the
    Hades language list (``HADES_MARKER``) and no update patch.
    """
    found = images.identify(path)
    if found is None or found.get("kind") != images.KIND_SWITCH:
        return None
    game_id = str(found.get("game_id") or "").upper()
    if game_id == BASE_ID or (not game_id and _merged_hades(path)):
        return {"role": "base", "platform": "switch", "libraries": []}
    if game_id == UPDATE_ID:
        return {"role": "update", "platform": "switch", "libraries": []}
    return None


def _merged_hades(path: str) -> bool:
    """True when the .nsp's RomFS is the Hades RomFS and is not a BKTR patch. Reads the file table only."""
    if not str(path).lower().endswith(".nsp"):
        return False
    scope = nullcontext() if console_crypto.key_path("switch") is not None \
        else console_crypto.key_source(console_keys.path_for)
    try:
        with scope:
            with images.open_image(path) as reader:
                if not any(ROMFS_PREFIX.sub("", entry.path) == HADES_MARKER for entry in reader.entries()):
                    return False
                return not reader.romfs_is_patch
    except (OSError, ValueError):
        return False


def unpack(sources: Dict[str, str], target_dir: str, progress: Callable[[int, str], None],
           is_cancelled: Callable[[], bool]) -> Optional[str]:
    """Write the English text, subtitles and fonts (and the Ukrainian reference) into ``target_dir``."""
    base, update = sources.get("base"), sources.get("update")
    if not base:
        return None
    found = identify(base)
    if found is None or found.get("role") != "base":
        raise ImageError(tr("The file is not the Hades Switch base game image."))
    with images.open_image(base, target_dir, is_cancelled, progress) as base_reader:
        if update:
            with images.open_image(update, target_dir, is_cancelled, progress) as update_reader:
                entries = update_reader.patched_romfs_entries(base_reader)
                return _write(update_reader, entries, target_dir, progress, is_cancelled)
        entries = base_reader.entries()
        if base_reader.romfs_is_patch:
            raise ImageError(tr("This Hades image holds an update patch: choose the update file too."))
        return _write(base_reader, entries, target_dir, progress, is_cancelled)


def _write(reader: Any, entries: Any, target_dir: str, progress: Callable[[int, str], None],
           is_cancelled: Callable[[], bool]) -> Optional[str]:
    """Write the entries the project keeps (paths under ``Content/``) through ``reader``."""
    wanted = []
    for entry in entries:
        path = ROMFS_PREFIX.sub("", entry.path)
        if SOURCE_RE.match(path):
            wanted.append(entry._replace(path=path))
    progress(0, tr("Writing {0} files", str(len(wanted))))
    if not images.write_entries(reader, wanted, target_dir, progress, is_cancelled):
        return None
    return target_dir
