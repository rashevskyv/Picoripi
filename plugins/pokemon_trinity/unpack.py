"""Unpack Pokémon Scarlet / Violet or Legends: Z-A in the Project Manager wizard: the English text, fonts and layouts.

The base game and its update are read with Picoripi's Switch reader (the update's RomFS is a BKTR patch over the base).
``arc/data.trpfd`` (the index) is written beside the source folder, at ``romfs/<title id>/arc/data.trpfd``: the build
patches it for that title.
The packs of the English text, fonts and layouts (``packs``) are read with the Oodle library, whose path the user gives
once in the wizard (console key store, slot ``oodle``). Each file is named as zt names it (``trinity_pack.resolve``)
and written under ``source/``.
"""
from pathlib import Path
from typing import Callable, Dict, List, Optional, Tuple

from core.containers import console_crypto
from core.containers.game_freak import path_hash
from core.containers.image_files import ImageError
from core.containers.trinity_pack import (TRPFD, TRPFS, Trinity, TrinityError, name_others, quoted_names,
                                          resolve)
from core.i18n import tr
from core.project_library import images
from core.unreal.oodle import Oodle, OodleError

OODLE = "oodle"
UPDATE_STEP = 0x800
SOURCE_DIR = "source"
ROMFS = "romfs"
# game -> (pack name pattern for the source files, title ids of the base game)
# The battle and the sub-window message boxes (applidatamsg_btlmsg_btl_body_00, applidatamsg_submsg_sub_body_00) have no
# language suffix, so the _eng rule above misses them; they hold the message box layouts the preview reads.
SV_PACKS = (r"^arc/(messagedatEnglish|applifontbin|applidata.*_eng\.arc\.trpak$|ymap_e\.trpak$"
            r"|applidatamsg_(btlmsg_btl|submsg_sub)_body_00\.arc\.trpak$)")
# The message box of Z-A: view_msg_body_00.truiv names the archive msg_body_00.arc (layout msg_00.bflyt). Both sit in
# one pack, and the pack has no language suffix, so the _eng rule above misses it.
ZA_PACKS = (r"^arc/(ik_messagedatEnglish|uifontbin|uidata.*_eng\.arc\.trpak$|uitexhud_spmgtga_eng"
            r"|uidatamsgview_msg_body_01\.truiv\.trpak$)")
GAMES = {
    "0100A3D008C5C000": SV_PACKS,   # Pokémon Scarlet
    "01008F6008C5E000": SV_PACKS,   # Pokémon Violet
    "0100F43008C44000": ZA_PACKS,   # Pokémon Legends: Z-A
}
OTHER_VERSION = "01008F6008C5E000"   # Pokémon Violet: the other version of Scarlet (its own index is built too)


def identify(path: str) -> Optional[Dict[str, object]]:
    """``{"role", "platform", "libraries"}`` of a Scarlet, Violet or Z-A image, else None."""
    found = images.identify(path)
    if found is None or found.get("kind") != images.KIND_SWITCH:
        return None
    game_id = str(found.get("game_id") or "")
    if game_id in GAMES:
        role = "other_base" if game_id == OTHER_VERSION else "base"
    else:
        try:
            base = f"{int(game_id, 16) - UPDATE_STEP:016X}"
        except ValueError:
            return None
        if base not in GAMES:
            return None
        role = "other_update" if base == OTHER_VERSION else "update"
    return {"role": role, "platform": "switch", "libraries": [OODLE]}


def _romfs_entries(reader, base_reader) -> dict:
    """The patched RomFS entries of an update (its base applied), by path without the ``romfs/`` folder."""
    return {entry.path[len(ROMFS) + 1:]: entry for entry in reader.patched_romfs_entries(base_reader)
            if entry.path.startswith(ROMFS + "/")}


def _other_index(base: str, update: str, target_dir: str, progress, is_cancelled) -> Tuple[str, bytes]:
    """(title id, index bytes) of the other version: only its ``arc/data.trpfd`` is read."""
    found = images.identify(base)
    if found is None or found.get("game_id") not in GAMES:
        raise ImageError(tr("The other version file is not a Scarlet, Violet or Legends: Z-A image."))
    with images.open_image(base, target_dir, is_cancelled, progress) as base_reader,             images.open_image(update, target_dir, is_cancelled, progress) as update_reader:
        entries = _romfs_entries(update_reader, base_reader)
        if TRPFD not in entries:
            raise ImageError(tr("The other version has no Trinity index (arc/data.trpfd)."))
        return found["game_id"], update_reader.read(entries[TRPFD])


def unpack(sources: Dict[str, str], target_dir: str, progress: Callable[[int, str], None],
           is_cancelled: Callable[[], bool]) -> Optional[str]:
    base, update = sources.get("base"), sources.get("update")
    if not base:
        return None
    found = images.identify(base)
    if found is None or found.get("game_id") not in GAMES:
        raise ImageError(tr("The base file is not a Scarlet, Violet or Legends: Z-A image."))
    if not update:
        raise ImageError(tr("Choose the update file too: the English text is in the update."))
    library = console_crypto.key_path(OODLE)
    if library is None:
        raise ImageError(tr("The Trinity packs need the Oodle library. Choose its file in the wizard."))
    try:
        oodle = Oodle(library)
    except OodleError as exc:
        raise ImageError(str(exc)) from None
    pattern = GAMES[found["game_id"]]
    root = Path(target_dir)
    with images.open_image(base, target_dir, is_cancelled, progress) as base_reader, \
            images.open_image(update, target_dir, is_cancelled, progress) as update_reader:
        entries = _romfs_entries(update_reader, base_reader)
        if TRPFD not in entries or TRPFS not in entries:
            raise ImageError(tr("The image has no Trinity archive (arc/data.trpfs)."))
        index_entry, archive_entry = entries[TRPFD], entries[TRPFS]
        index = update_reader.read(index_entry)
        stream = update_reader.source(archive_entry)

        def read_archive(offset: int, size: int) -> bytes:
            stream.seek(archive_entry.offset + offset)
            return stream.read(size)

        try:
            trinity = Trinity(index, read_archive)
        except TrinityError as exc:
            raise ImageError(str(exc)) from None
        _write(root / ROMFS / found["game_id"] / TRPFD, index)   # the build patches each title's own index
        names_written = _extract(trinity, pattern, oodle, root / SOURCE_DIR, progress, is_cancelled)
        if names_written is None:
            return None
    other_base, other_update = sources.get("other_base"), sources.get("other_update")
    if other_base or other_update:
        if not (other_base and other_update):
            raise ImageError(tr("Choose the update of the other version too."))
        other_id, other_index = _other_index(other_base, other_update, target_dir, progress, is_cancelled)
        _write(root / ROMFS / other_id / TRPFD, other_index)
    return target_dir


def _extract(trinity: Trinity, pattern: str, oodle: Oodle, dest: Path, progress, is_cancelled) -> Optional[int]:
    """The files of the packs matching ``pattern``, named and written under ``dest``; None when cancelled."""
    paths: List[str] = []
    unnamed: List[Tuple[int, bytes]] = []
    quoted = set()
    indexes = list(trinity.pack_index(pattern))
    for number, index in enumerate(indexes, start=1):
        if is_cancelled():
            return None
        progress(100 * number // max(1, len(indexes)), trinity.pack_names[index])
        files = trinity.pack_files(index, oodle.decompress)
        names = resolve(trinity.pack_names[index], [h for h, _d in files])
        name_others(names, files)
        folder = next(iter(names.values()), "/").rsplit("/", 1)[0]
        for h, data in files:
            quoted |= quoted_names(data, folder)
            if h in names:
                paths.append(names[h])
                _write(dest / names[h], data)
            else:
                unnamed.append((h, data))
    siblings = {path_hash(p[:-4] + ".dat"): p[:-4] + ".dat" for p in paths if p.endswith(".tbl")}   # grouped packs
    siblings.update({path_hash(p): p for p in quoted})          # quoted in another pack (font settings -> fonts)
    for h, data in unnamed:
        if h in siblings:
            _write(dest / siblings[h], data)
            paths.append(siblings[h])
    return len(paths)


def _write(path: Path, data: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(path.name + ".tmp")
    temporary.write_bytes(data)
    temporary.replace(path)
