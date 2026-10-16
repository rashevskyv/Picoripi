"""Unpack Pokémon Brilliant Diamond / Shining Pearl in the Project Manager wizard: the English message tables.

The base game and its update are read with Picoripi's Switch reader (the update's RomFS is a BKTR patch over the base).
The two message bundles are written as they are under ``romfs\\`` (the build writes edited bundles from them), and each
English table of ``source\\message\\`` is written as JSON (``bundles.table_json``). The project's source folder is
``source``; the bundles stay beside it in the unpacked folder.
"""
import re
from pathlib import Path
from typing import Callable, Dict, Optional

from core.containers.image_files import ImageError
from core.i18n import tr
from core.project_library import images
from plugins.pokemon_bdsp import bundles

BASE_IDS = ("0100000011D90000",   # Pokémon Brilliant Diamond base
            "010018E011D92000")   # Pokémon Shining Pearl base
UPDATE_STEP = 0x800               # a game's update title id is the base title id plus this
SOURCE_DIR = "source"
ROMFS = "romfs"
ROMFS_RE = re.compile(r"^romfs/" + re.escape(bundles.MESSAGE_DIR) + r"(?:english|common_msbt)$")


def identify(path: str) -> Optional[Dict[str, object]]:
    """``{"role", "platform", "libraries"}`` of a Brilliant Diamond or Shining Pearl image, else None."""
    found = images.identify(path)
    if found is None or found.get("kind") != images.KIND_SWITCH:
        return None
    game_id = str(found.get("game_id") or "")
    if game_id in BASE_IDS:
        return {"role": "base", "platform": "switch", "libraries": []}
    try:
        base = f"{int(game_id, 16) - UPDATE_STEP:016X}"
    except ValueError:
        return None
    return {"role": "update", "platform": "switch", "libraries": []} if base in BASE_IDS else None


def unpack(sources: Dict[str, str], target_dir: str, progress: Callable[[int, str], None],
           is_cancelled: Callable[[], bool]) -> Optional[str]:
    """Write the two message bundles and the English tables of the patched RomFS into ``target_dir``."""
    base, update = sources.get("base"), sources.get("update")
    if not base:
        return None
    found = images.identify(base)
    if found is None or found.get("game_id") not in BASE_IDS:
        raise ImageError(tr("The base file is not a Brilliant Diamond or Shining Pearl image."))
    if not update:
        raise ImageError(tr("Choose the update file too: the English text is in the update."))
    with images.open_image(base, target_dir, is_cancelled, progress) as base_reader, \
            images.open_image(update, target_dir, is_cancelled, progress) as update_reader:
        wanted = [entry for entry in update_reader.patched_romfs_entries(base_reader) if ROMFS_RE.match(entry.path)]
        if len(wanted) != len(bundles.MESSAGE_BUNDLES):
            raise ImageError(tr("The message bundles are not in this image."))
        progress(0, tr("Writing {0} files", str(len(wanted))))
        if not images.write_entries(update_reader, wanted, target_dir, progress, is_cancelled):
            return None
    root = Path(target_dir)
    messages = root / SOURCE_DIR / "message"
    messages.mkdir(parents=True, exist_ok=True)
    for entry in wanted:
        _, serialized = bundles.open_bundle((root / entry.path).read_bytes())
        for name, path_id in bundles.tables(serialized).items():
            if is_cancelled():
                return None
            _write(messages / f"{name}.bdmsg", bundles.table_json(serialized.read(path_id)))
    return target_dir


def _write(path: Path, data: bytes) -> None:
    temporary = path.with_name(path.name + ".tmp")
    temporary.write_bytes(data)
    temporary.replace(path)
