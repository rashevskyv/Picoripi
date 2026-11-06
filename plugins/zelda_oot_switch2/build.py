"""Build of Ocarina of Time (Nintendo Switch 2): a new ``.nup`` with the Ukrainian text in the Russian slot.

Switch 2 has no mod loader yet, so the build writes a whole package (``nup.write``): the original from the unpack's
source mark, with ``romfs/Mals/EUru.*.sarc.zs`` replaced and any edited font of ``romfs/Font2``. The project's
blocks are the English slot (``USen``); a message whose translation differs from the English goes into the same
message of the Russian archive (same members, labels and order in every slot), every other message keeps its
Russian text. The Russian slot uses the ClarimoUDPE fonts, which hold Є І Ї Ґ.
"""
from __future__ import annotations

import posixpath
import shutil
from pathlib import Path
from typing import Callable, Dict, Optional

from core.containers import sarc
from core.i18n import tr
from plugins.common.disc_source import disc_of_source, find_disc_root
from plugins.common.msbt import Msbt
from plugins.zelda_totk.tags import to_editor

from . import nup
from .config import DICTIONARY_PACK, TARGET_LANGUAGE, TEXT_ARCHIVE_PREFIX

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


def build_nup(source_dir: str, translation_dir: str, output_dir: str,
              progress: Callable[[int, str], None], is_cancelled: Callable[[], bool]) -> Optional[str]:
    """Write the translated package into ``output_dir`` and return its path (None when cancelled)."""
    root = find_disc_root(source_dir)
    image = disc_of_source(root)
    changes = changes_of(root, source_dir, translation_dir)
    if not changes:
        raise ValueError(tr("The translation has no translated text yet; nothing to build."))
    need = image.stat().st_size + sum(len(data) for data in changes.values())
    Path(output_dir).mkdir(parents=True, exist_ok=True)
    free = shutil.disk_usage(output_dir).free
    if free < need:
        raise ValueError(tr("Not enough free space on {0}: the package needs {1} MB, and {2} MB is free.",
                            output_dir, str(-(-need // 2**20)), str(free // 2**20)))
    return nup.write(image, Path(output_dir) / f"{image.stem} (UA).nup", changes, progress, is_cancelled)
