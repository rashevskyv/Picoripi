"""Unpack Lunar: Silver Star Story Remastered (Switch) in the Project Manager wizard.

The base game and its update are read with Picoripi's Switch reader. The base package holds three program NCAs; the
one with ``romfs/data.cpk`` is the Silver Star Story program. The update's patched RomFS gives the final ``data.cpk``.
The unpacked folder keeps ``data.cpk`` whole (the build patches it), and the text files of the archive as ``FIL/`` (the
Japanese source) and ``FIL_us/`` (the English reference). ``TEXT200.DAT`` holds no dialogue and is not extracted.
"""
import os
import re
import shutil
from pathlib import Path
from typing import Any, Callable, Dict, Optional

from core.containers import cpk
from core.containers.image_files import ImageError
from core.i18n import tr
from core.project_library import images
from plugins.lunar_sssc_remastered.config import TITLE_ID, UPDATE_TITLE_ID

UPDATE_STEP = 0x800
CPK_PATH = "romfs/data.cpk"
TEXT_FOLDERS = ("FIL", "FIL_us")
TEXT_RE = re.compile(r"^TEXT(0\d\d|100)\.DAT$")    # the dialogue files; TEXT200 has none


def identify(path: str) -> Optional[Dict[str, Any]]:
    """``{"role", "platform", "libraries"}`` of the base or the update image, else None.

    A PC (Steam) game folder holds ``data.cpk`` and ``lunar1.exe``; its data is the same as the Switch patched data.
    """
    if Path(path).is_dir():
        if (Path(path) / "data.cpk").is_file() and (Path(path) / "lunar1.exe").is_file():
            return {"role": "base", "platform": "pc", "libraries": []}
        return None
    found = images.identify(path)
    if found is None or found.get("kind") != images.KIND_SWITCH:
        return None
    game_id = str(found.get("game_id") or "").upper()
    if game_id == TITLE_ID:
        return {"role": "base", "platform": "switch", "libraries": []}
    if game_id == UPDATE_TITLE_ID:
        return {"role": "update", "platform": "switch", "libraries": []}
    return None


def _program_with_cpk(base: str, update: str, target_dir: str, progress, is_cancelled) -> Optional[int]:
    """The program NCA index whose RomFS holds ``data.cpk`` in the base image (the update uses the same order)."""
    with images.open_image(base, target_dir, is_cancelled, progress) as reader:
        programs = reader.program_list()
    for program in programs:
        if is_cancelled():
            return None
        with images.open_image(base, target_dir, is_cancelled, progress, program=program["index"]) as reader:
            names = [entry.path for entry in reader.entries()]
        if CPK_PATH in names:
            return program["index"]
    return None


def unpack(sources: Dict[str, str], target_dir: str, progress: Callable[[int, str], None],
           is_cancelled: Callable[[], bool]) -> Optional[str]:
    """Write ``data.cpk`` and the text files of the patched archive into ``target_dir``; return that folder.

    Raises ImageError when the base file is not the base game, when the update is missing, or when no program holds
    ``data.cpk``.
    """
    base, update = sources.get("base"), sources.get("update")
    if not base:
        return None
    if (identify(base) or {}).get("platform") == "pc":
        shutil.copyfile(Path(base) / "data.cpk", Path(target_dir) / "data.cpk")
        _extract_text(target_dir, progress, is_cancelled)
        return target_dir
    if (identify(base) or {}).get("role") != "base":
        raise ImageError(tr("The base file is not a Lunar: Silver Star Story Remastered image."))
    if not update:
        raise ImageError(tr("Choose the update file too: the English text is in the update."))
    program = _program_with_cpk(base, update, target_dir, progress, is_cancelled)
    if program is None:
        if is_cancelled():
            return None
        raise ImageError(tr("No program of the image holds data.cpk."))
    with images.open_image(base, target_dir, is_cancelled, progress, program=program) as base_reader, \
            images.open_image(update, target_dir, is_cancelled, progress, program=program) as update_reader:
        wanted = []
        for entry in update_reader.patched_romfs_entries(base_reader):
            if entry.path == CPK_PATH:
                wanted.append(entry._replace(path="data.cpk"))
        if not wanted:
            raise ImageError(tr("No program of the image holds data.cpk."))
        progress(0, tr("Writing {0} files", str(len(wanted))))
        if not images.write_entries(update_reader, wanted, target_dir, progress, is_cancelled):
            return None
    _extract_text(target_dir, progress, is_cancelled)
    return target_dir


def _extract_text(target_dir: str, progress: Callable[[int, str], None],
                  is_cancelled: Callable[[], bool]) -> None:
    """Write the dialogue files of ``data.cpk`` as ``FIL/`` and ``FIL_us/`` folders beside it."""
    root = Path(target_dir)
    with open(root / "data.cpk", "rb") as stream:
        entries = [entry for entry in cpk.read_cpk(stream)
                   if entry.path.rsplit("/", 1)[0] in TEXT_FOLDERS and TEXT_RE.match(entry.path.rsplit("/", 1)[-1])]
        for index, entry in enumerate(entries, start=1):
            if is_cancelled():
                return
            progress(100 * index // max(1, len(entries)), entry.path)
            target = root.joinpath(*entry.path.split("/"))
            target.parent.mkdir(parents=True, exist_ok=True)
            temporary = target.with_name(target.name + ".tmp")
            temporary.write_bytes(cpk.read_file(stream, entry))
            os.replace(temporary, target)
