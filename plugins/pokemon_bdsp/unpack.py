"""Unpack Pokémon Brilliant Diamond / Shining Pearl in the Project Manager wizard: the English text, fonts and pictures.

The base game and its update are read with Picoripi's Switch reader (the update's RomFS is a BKTR patch over the base).
The picture bundles the workspace keeps (``assets.is_picture_bundle``) are written as they are under ``romfs\\``; the
build writes edited bundles from them. The project's source folder is ``source``:

- ``message\\english_*.bdmsg``: each English message table as JSON (``bundles.table_json``);
- ``font\\<bundle>\\``: TextMesh Pro font assets (JSON and atlas PNG) and the font files (``assets.font_files``);
- ``texture\\<bundle>\\*.png``: the pictures of the other bundles (``assets.texture_files``).
"""
from pathlib import Path
from typing import Callable, Dict, Optional

from core.containers.image_files import ImageError
from core.i18n import tr
from core.project_library import images
from plugins.pokemon_bdsp import assets, bundles

BASE_IDS = ("0100000011D90000",   # Pokémon Brilliant Diamond base
            "010018E011D92000")   # Pokémon Shining Pearl base
UPDATE_STEP = 0x800               # a game's update title id is the base title id plus this
SOURCE_DIR = "source"
ROMFS = "romfs"


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
    """Write the picture bundles of the patched RomFS and the English tables, fonts and pictures into ``target_dir``."""
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
        wanted = [entry for entry in update_reader.patched_romfs_entries(base_reader)
                  if assets.is_picture_bundle(entry.path[len(ROMFS):])]
        for rel in bundles.MESSAGE_BUNDLES:
            if not any(entry.path == f"{ROMFS}/{rel}" for entry in wanted):
                raise ImageError(tr("The message bundles are not in this image."))
        progress(0, tr("Writing {0} files", str(len(wanted))))
        if not images.write_entries(update_reader, wanted, target_dir, progress, is_cancelled):
            return None
    root = Path(target_dir)
    source = root / SOURCE_DIR
    for entry in wanted:
        if is_cancelled():
            return None
        short = assets.short_name(entry.path[len(ROMFS):])
        bundle, serialized = assets.open_serialized((root / entry.path).read_bytes())
        if short.startswith("Message/"):
            for name, path_id in bundles.tables(serialized).items():
                _write(source / "message" / f"{name}.bdmsg", bundles.table_json(serialized.read(path_id)))
        elif short.startswith(assets.FONT_FOLDER):
            for rel, data in assets.font_files(bundle, serialized, "font/" + short.rsplit("/", 1)[-1]):
                _write(source / rel, data)
        else:
            for rel, data in assets.texture_files(bundle, serialized, "texture/" + short):
                _write(source / rel, data)
    return target_dir


def _write(path: Path, data: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(path.name + ".tmp")
    temporary.write_bytes(data)
    temporary.replace(path)
