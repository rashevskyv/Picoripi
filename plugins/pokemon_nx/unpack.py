"""Unpack Pokémon Sword / Shield / Legends: Arceus in the Project Manager wizard: the English text, fonts and layouts.

The base game and its newest update are read with Picoripi's Switch reader (``core/containers/switch_images``): the
update's RomFS is a BKTR patch over the base RomFS, and the reader applies it. Legends: Arceus packs (``.gfpak``) are
written as they are, and their decoded files go into ``<pack>.gfpak.d`` beside them. The decoding needs the Oodle core
library; the user gives its path once in the wizard (``console_keys``, slot ``oodle``).
"""
import os
import re
from pathlib import Path
from typing import Any, Callable, Dict, Optional

from core.containers import console_crypto, gfpak
from core.containers.image_files import ImageError
from core.i18n import tr
from core.project_library import images
from core.unreal.oodle import Oodle, OodleError

# RomFS paths the project needs: English messages, fonts, English layout archives, the Oodle packs as files, and the
# dialogue window layout (msg_00.arc; the preview draws it).
SOURCE_RE = re.compile(r"^/bin/message/English/|^/bin/font/|^/bin/appli/[^/]+/bin/[^/]+_eng\.arc$"
                       r"|^/bin/archive/appli/[^/]+_eng\.gfpak$|^/bin/appli/msg/bin/msg_00\.arc$")
BASE_IDS = ("0100ABF008968000",   # Pokémon Sword base
            "01008DB008C2C000",   # Pokémon Shield base
            "01001F5010DFA000")   # Pokémon Legends: Arceus base
ARCEUS_IDS = ("01001F5010DFA000",)
UPDATE_STEP = 0x800               # a game's update title id is the base title id plus this
ROMFS = "romfs"
OODLE = "oodle"                   # the console_keys slot of the Oodle core library


def identify(path: str) -> Optional[Dict[str, Any]]:
    """``{"role", "platform", "libraries"}`` of a Sword, Shield or Legends: Arceus image, else None.

    The update's title id is the base title id plus ``UPDATE_STEP``. The Arceus packs need the Oodle library.
    """
    found = images.identify(path)
    if found is None or found.get("kind") != images.KIND_SWITCH:
        return None
    game_id = str(found.get("game_id") or "")
    if game_id in BASE_IDS:
        role, base = "base", game_id
    else:
        try:
            base = f"{int(game_id, 16) - UPDATE_STEP:016X}"
        except ValueError:
            return None
        if base not in BASE_IDS:
            return None
        role = "update"
    return {"role": role, "platform": "switch", "libraries": [OODLE] if base in ARCEUS_IDS else []}


def unpack(sources: Dict[str, str], target_dir: str, progress: Callable[[int, str], None],
           is_cancelled: Callable[[], bool]) -> Optional[str]:
    """Write the selected files of the patched RomFS into ``target_dir``; the folder is the project's source root.

    Raises ImageError when the base file is not one of the games above, when the update is missing, or when the
    Arceus packs need the Oodle library and the user has not given its path.
    """
    base, update = sources.get("base"), sources.get("update")
    if not base:
        return None
    found = images.identify(base)
    if found is None or found.get("game_id") not in BASE_IDS:
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
    if found.get("game_id") in ARCEUS_IDS:
        _decode_packs(target_dir, progress, is_cancelled)
    return target_dir


def _decode_packs(target_dir: str, progress: Callable[[int, str], None], is_cancelled: Callable[[], bool]) -> None:
    """Write ``<pack>.gfpak.d/NN_<name>`` for every pack under ``target_dir``, decoded with the Oodle library."""
    packs = sorted(Path(target_dir).rglob("*.gfpak"))
    if not packs:
        return
    library = console_crypto.key_path(OODLE)
    if library is None:
        raise ImageError(tr("Legends: Arceus packs need the Oodle library. Choose its file in the wizard."))
    try:
        oodle = Oodle(library)
    except OodleError as exc:
        raise ImageError(str(exc)) from None
    for index, pack in enumerate(packs, start=1):
        if is_cancelled():
            return
        progress(0, tr("Decoding pack {0} of {1}", str(index), str(len(packs))))
        data = pack.read_bytes()
        entries = gfpak.read_entries(data)
        try:
            files = gfpak.decode(data, oodle.decompress)
        except (OodleError, gfpak.GfpakError) as exc:
            raise ImageError(str(exc)) from None
        names = gfpak.file_names(files, [entry.path_hash for entry in entries])
        folder = pack.with_name(pack.name + ".d")
        folder.mkdir(exist_ok=True)
        for name, raw in zip(names, files):
            _write_atomic(folder / name, raw)


def _write_atomic(path: Path, data: bytes) -> None:
    """Write ``data`` to ``path`` through a temporary file beside it, then replace."""
    temporary = path.with_name(path.name + ".tmp")
    temporary.write_bytes(data)
    os.replace(temporary, path)
