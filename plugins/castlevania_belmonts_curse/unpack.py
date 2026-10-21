"""Unpack Castlevania: Belmont's Curse (Switch) in the Project Manager wizard: the English string tables.

The base game and its update are read with Picoripi's Switch reader. The base's RomFS is sparse: the update's BKTR patch
maps most of it into the base, so the update's patched RomFS is the game's RomFS. The English localization bundle is
written under ``romfs\\`` as it is; the build writes an edited copy of it. The project's source folder is ``source``:
``message\\<table>.json`` for each of the 45 string tables (``tables.table_json``).
"""
import re
from pathlib import Path
from typing import Callable, Dict, Optional

from core.containers.image_files import ImageError
from core.i18n import tr
from core.project_library import images
from plugins.castlevania_belmonts_curse import tables

BASE_ID = "0100BA4026E94000"
UPDATE_ID = "0100BA4026E94800"       # the base title id plus 0x800
SOURCE_DIR = "source"
ROMFS = "romfs"
LOCALIZATION = re.compile(r"^Data/StreamingAssets/aa/Switch/localization-string-tables-english\(en\)_assets_all_[0-9a-f]+\.bundle$")


def identify(path: str) -> Optional[Dict[str, object]]:
    """``{"role", "platform", "libraries"}`` of a Castlevania: Belmont's Curse image, else None."""
    found = images.identify(path)
    if found is None or found.get("kind") != images.KIND_SWITCH:
        return None
    game_id = str(found.get("game_id") or "")
    if game_id == BASE_ID:
        return {"role": "base", "platform": "switch", "libraries": []}
    if game_id == UPDATE_ID:
        return {"role": "update", "platform": "switch", "libraries": []}
    return None


def localization_entries(entries) -> list:
    """The English localization bundle among the patched RomFS entries (``romfs/`` paths)."""
    return [entry for entry in entries if LOCALIZATION.match(entry.path[len(ROMFS) + 1:])]


def unpack(sources: Dict[str, str], target_dir: str, progress: Callable[[int, str], None],
           is_cancelled: Callable[[], bool]) -> Optional[str]:
    """Write the English localization bundle and its table files into ``target_dir``."""
    base, update = sources.get("base"), sources.get("update")
    if not base:
        return None
    found = images.identify(base)
    if found is None or found.get("game_id") != BASE_ID:
        raise ImageError(tr("The base file is not a Castlevania: Belmont's Curse image."))
    if not update:
        raise ImageError(tr("Choose the update file too: the game's RomFS is in the update."))
    with images.open_image(base, target_dir, is_cancelled, progress) as base_reader, \
            images.open_image(update, target_dir, is_cancelled, progress) as update_reader:
        wanted = localization_entries(update_reader.patched_romfs_entries(base_reader))
        if not wanted:
            raise ImageError(tr("The English localization bundle is not in this image."))
        progress(0, tr("Writing {0} files", str(len(wanted))))
        if not images.write_entries(update_reader, wanted, target_dir, progress, is_cancelled):
            return None
    root = Path(target_dir)
    for entry in wanted:
        if is_cancelled():
            return None
        data = (root / entry.path).read_bytes()
        _bundle, serialized = tables.open_bundle(data)
        for name, path_id in tables.tables(serialized).items():
            entries = tables.read_entries(serialized, path_id)
            _write(root / SOURCE_DIR / "message" / f"{name}.json", tables.table_json(name, entries))
    return target_dir


def _write(path: Path, data: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(data)
