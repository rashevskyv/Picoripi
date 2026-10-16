"""Build the Pokémon Scarlet / Violet or Legends: Z-A mod: the changed files at their romfs paths, and the title's index.

The game loads a file from its pack when the file's path hash is in ``arc/data.trpfd``; otherwise it reads the romfs
path. So the mod has the changed files at their romfs paths, and a ``data.trpfd`` in which their hashes no longer match
(``trinity_pack.patch_trpfd``). A changed English layout ``X_eng.arc`` is written as ``X.arc`` too
(``trinity_pack.base_layout``).

The index of each title is the one the wizard kept (``romfs/<title id>/arc/data.trpfd`` beside the source): Scarlet from
the base and update, Violet from the other version's roles. Each title is built from its own index.
"""
from pathlib import Path
from typing import Callable

from core.containers.game_freak import path_hash
from core.containers.trinity_pack import TRPFD, TrinityError, base_layout, patch_trpfd
from core.i18n import tr
from plugins.common import romfs_mod


def build_switch(source_dir: str, translation_dir: str, output_dir: str,
                 progress: Callable[[int, str], None], is_cancelled: Callable[[], bool]) -> str:
    source = Path(source_dir)
    romfs = source.parent / "romfs"
    indexes = sorted(p.parent.parent for p in romfs.glob(f"*/arc/{TRPFD.split('/')[-1]}"))
    if not indexes:
        raise ValueError(tr("The index of the game is missing; unpack the game again."))
    changes = romfs_mod.changed_files(source, translation_dir)
    files = dict(changes)
    for rel in changes:
        for extra in base_layout(rel):
            files[extra] = changes[rel]
    out = Path(output_dir) / "atmosphere"
    for number, title_dir in enumerate(indexes, start=1):
        if is_cancelled():
            raise InterruptedError()
        progress(100 * number // len(indexes), title_dir.name)
        original = (title_dir / TRPFD).read_bytes()
        hashes = [path_hash(path) for path in files]
        try:
            patched = patch_trpfd(original, hashes)
        except TrinityError as exc:
            raise ValueError(str(exc)) from None
        romfs_mod.write_title(out, title_dir.name, files)
        target = out / "contents" / title_dir.name / "romfs" / TRPFD
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(patched)
    return str(out)
