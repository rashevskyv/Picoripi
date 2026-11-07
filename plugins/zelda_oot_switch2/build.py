"""Build of Ocarina of Time (Nintendo Switch 2): a new ``.nup`` with the Ukrainian text in the Russian slot.

Switch 2 has no mod loader yet, so the build writes a whole package (``nup.write``): the original from the unpack's
source mark, with ``romfs/Mals/EUru.*.sarc.zs`` replaced and any edited font of ``romfs/Font2``. The project's
The game reserves memory for a file from its resource size table and refuses a file that outgrew its entry (the
text then shows as MsgNotFound), so the build also raises the entries of the files it replaces. The project's
blocks are the English slot (``USen``); a message whose translation differs from the English goes into the same
message of the Russian archive (same members, labels and order in every slot), every other message keeps its
Russian text. The Russian slot uses the ClarimoUDPE fonts, which hold Є І Ї Ґ.

Hookshot, the game recompiled for Windows, reads the same files: ``build_hookshot`` writes only the changed ones
into a ``romfs`` folder, and a launcher starts Hookshot with that folder over the game's own (``HOS_FS_OVERLAY``)
in the Russian slot (``HOS_LANGUAGE=ru``), so the Hookshot game folder and its ``language.txt`` stay as they are.
"""
from __future__ import annotations

import os
import posixpath
import shutil
from pathlib import Path
from typing import Callable, Dict, Optional

from core.containers import sarc
from core.i18n import tr
from plugins.common.disc_source import disc_of_source, find_disc_root
from plugins.common.msbt import Msbt
from plugins.zelda_totk.restbl import Restbl, grown_like
from plugins.zelda_totk.tags import to_editor

from . import nup
from .config import DICTIONARY_PACK, TARGET_LANGUAGE, TEXT_ARCHIVE_PREFIX

RESOURCE_TABLE = "romfs/System/Resource/ResourceSizeTable.Product."
FONT_FOLDER = "Font2"   # a font edit lands in ``<translation>/../Font2``, the mirror of the source's ``../Font2``


def graft(english_raw: bytes, translated_raw: bytes, russian_raw: bytes) -> Optional[bytes]:
    """The Russian archive with every translated message of the English one put in; None when none is translated."""
    english, translated, russian = (sarc.SarcContainer(raw) for raw in (english_raw, translated_raw, russian_raw))
    changed = False
    for member in translated.list_files():
        if not member.endswith(".msbt"):
            continue
        source, target, slot = (Msbt(archive.read_file(member)) for archive in (english, translated, russian))
        if not len(source.messages) == len(target.messages) == len(slot.messages):
            raise ValueError(tr("{0}: the number of messages changed; only the text may change", member))
        messages = [new if to_editor(new, target.little) != to_editor(old, source.little) else kept
                    for old, new, kept in zip(source.messages, target.messages, slot.messages)]
        if any(message is not kept for message, kept in zip(messages, slot.messages)):
            russian.write_file(member, slot.build(messages))
            changed = True
    return russian.pack() if changed else None


def changes_of(root: Path, source_dir: str, translation_dir: str) -> Dict[str, bytes]:
    """``{path in the package: new bytes}`` for the translated text archives and the edited fonts."""
    source = Path(source_dir)
    source_rel = source.resolve().relative_to(root.resolve()).as_posix()
    changes: Dict[str, bytes] = {}
    archives = sorted(Path(translation_dir).glob(f"{TEXT_ARCHIVE_PREFIX}*.sarc.zs"))
    if archives:
        sarc.add_dictionary_pack((root / DICTIONARY_PACK).read_bytes())
    for archive in archives:
        slot_name = f"{TARGET_LANGUAGE}.{archive.name.split('.', 1)[1]}"
        data = graft((source / archive.name).read_bytes(), archive.read_bytes(), (source / slot_name).read_bytes())
        if data is not None:
            changes[f"{source_rel}/{slot_name}"] = data
    fonts = Path(translation_dir).parent / FONT_FOLDER
    for path in sorted(fonts.rglob("*")) if fonts.is_dir() else ():
        if path.is_file():
            rel = path.relative_to(fonts).as_posix()
            changes[posixpath.normpath(f"{source_rel}/../{FONT_FOLDER}/{rel}")] = path.read_bytes()
    return changes


def size_table(image: Path, changes: Dict[str, bytes]) -> Dict[str, bytes]:
    """``{table path: new bytes}``: the package's resource size table with an entry raised for every changed file
    that outgrew it; empty when no entry needs it."""
    with open(image, "rb") as stream:
        package = nup.Nup(stream)
        by_path = {entry.path: entry for entry in package.entries}
        tables = sorted(path for path in by_path if path.startswith(RESOURCE_TABLE) and path.endswith(".rsizetable.zs"))
        if not tables:
            return {}
        if DICTIONARY_PACK in by_path:
            sarc.add_dictionary_pack(package.read(by_path[DICTIONARY_PACK]))
        data, dict_id = sarc.decompress(package.read(by_path[tables[-1]]))
        table = Restbl(data)
        for path, new in changes.items():
            key = path.removeprefix("romfs/").removesuffix(".zs")
            entry = table.size(key)
            if entry is not None and path in by_path:
                table.set_size(key, grown_like(entry, _size(package.read(by_path[path])), _size(new)))
    built = table.build()
    return {} if built == data else {tables[-1]: sarc.compress(built, dict_id)}


def _size(data: bytes) -> int:
    """The size of a file the way the game loads it: a zstd frame decompressed."""
    return len(sarc.decompress(data)[0]) if data[:4] == sarc.ZSTD_MAGIC else len(data)


def _translated(source_dir: str, translation_dir: str):
    """``(the source package, {path in the package: new bytes})`` with the size table raised to fit."""
    root = find_disc_root(source_dir)
    image = disc_of_source(root)
    changes = changes_of(root, source_dir, translation_dir)
    if not changes:
        raise ValueError(tr("The translation has no translated text yet; nothing to build."))
    changes.update(size_table(image, changes))
    return image, changes


HOOKSHOT_LAUNCHER = "Hookshot UA.bat"
_LAUNCHER = """@echo off
rem Starts Hookshot with the Ukrainian translation. Copy this file next to hookshot.exe once.
set "HOS_FS_OVERLAY={romfs}"
set "HOS_LANGUAGE=ru"
start "" /d "%~dp0" "%~dp0hookshot.exe"
"""


def build_hookshot(source_dir: str, translation_dir: str, output_dir: str, final_dir: str) -> str:
    """The changed game files in ``output_dir/romfs`` and the launcher; returns the launcher's path.

    ``final_dir`` is where ``output_dir`` ends up (the launcher names the folder there).
    """
    _image, changes = _translated(source_dir, translation_dir)
    romfs = Path(output_dir) / "romfs"
    for path, data in changes.items():
        target = romfs / path.removeprefix("romfs/")
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(data)
    launcher = Path(output_dir) / HOOKSHOT_LAUNCHER
    launcher.write_text(_LAUNCHER.format(romfs=Path(final_dir) / "romfs"), encoding="ascii", newline="\r\n")
    return str(launcher)


def build_nup(source_dir: str, translation_dir: str, output_dir: str,
              progress: Callable[[int, str], None], is_cancelled: Callable[[], bool],
              previous_dir: Optional[str] = None) -> Optional[str]:
    """Write the translated package into ``output_dir`` and return its path (None when cancelled).

    When ``previous_dir`` holds the package an earlier build made from the same disc, that package moves into
    ``output_dir`` and is updated in place (seconds instead of a copy of the whole disc).
    """
    image, changes = _translated(source_dir, translation_dir)
    name = f"{image.stem} (UA).nup"
    Path(output_dir).mkdir(parents=True, exist_ok=True)
    previous = Path(previous_dir) / name if previous_dir else None
    if previous is not None and nup.is_update_of(image, previous):
        target = Path(output_dir) / name
        record = previous.with_name(previous.name + nup.SOURCE_RECORD)
        os.replace(record, target.with_name(record.name))
        os.replace(previous, target)
        return nup.update(image, target, changes, progress)
    need = image.stat().st_size + sum(len(data) for data in changes.values())
    free = shutil.disk_usage(output_dir).free
    if free < need:
        raise ValueError(tr("Not enough free space on {0}: the package needs {1} MB, and {2} MB is free.",
                            output_dir, str(-(-need // 2**20)), str(free // 2**20)))
    return nup.write(image, Path(output_dir) / name, changes, progress, is_cancelled)
