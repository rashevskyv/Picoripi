"""The LayeredFS mod of a Pokémon Mystery Dungeon 3DS game, made from the translated files (``translation/romfs``).

A changed loose file goes into the mod as it is. A changed pack member (``message_en.bin/<name>``) goes into the
game's own pack (kept by the unpack step): the pack is written again with the member changed, and each member is
read back to check it. The mod is ``<output>/titles/<title id>/romfs/...``; the game loads it from the Azahar mod folder.
"""
from __future__ import annotations

from pathlib import Path
from typing import Callable, Dict, List

from core.containers import farc
from core.i18n import tr
from plugins.pokemon_md_3ds.unpack import ORIGINAL_DIR, PSMD_PACKS, original_pack


class ModError(ValueError):
    """The build cannot be made from the project's files."""


def _title(source_dir: Path) -> str:
    root = Path(source_dir, ORIGINAL_DIR)
    titles = [f.name for f in root.iterdir() if f.is_dir()] if root.is_dir() else []
    if len(titles) != 1:
        raise ModError(tr("The source folder has no single game archive set: unpack the game again."))
    return titles[0]


def _changed(translation_dir: Path, source_dir: Path) -> Dict[str, bytes]:
    """``{path under romfs: bytes}`` of every translated file that differs from the source file (or has none)."""
    trans = Path(translation_dir, "romfs")
    out: Dict[str, bytes] = {}
    if not trans.is_dir():
        return out
    for path in sorted(p for p in trans.rglob("*") if p.is_file()):
        rel = path.relative_to(trans).as_posix()
        if path.name.lower() in ("desktop.ini", "thumbs.db") or path.name.endswith((".tmp", ".bak")):
            continue
        data = path.read_bytes()
        source = Path(source_dir, "romfs", *rel.split("/"))
        if source.is_file() and source.read_bytes() == data:
            continue
        out[rel] = data
    return out


def build(source_dir: Path, translation_dir: Path, output_dir: Path, progress: Callable[[int, str], None],
          is_cancelled: Callable[[], bool]) -> Path | None:
    """Write the mod under ``output_dir``. Returns the output folder, or None when cancelled."""
    title = _title(source_dir)
    mod = Path(output_dir, "titles", title, "romfs")
    changes = _changed(translation_dir, source_dir)
    packs: Dict[str, Dict[int, bytes]] = {}
    loose: List[str] = []
    for rel in changes:
        parts = rel.split("/")
        if parts[0] in PSMD_PACKS and len(parts) == 2:
            packs.setdefault(parts[0], {})[farc.name_hash(parts[1])] = changes[rel]
        else:
            loose.append(rel)
    total = max(1, len(loose) + len(packs))
    for number, rel in enumerate(loose, 1):
        if is_cancelled():
            return None
        progress(100 * (number - 1) // total, rel)
        out = mod / Path(*rel.split("/"))
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_bytes(changes[rel])
    for number, (pack, members) in enumerate(sorted(packs.items()), len(loose) + 1):
        if is_cancelled():
            return None
        progress(100 * (number - 1) // total, pack)
        try:
            rebuilt = farc.replace(original_pack(source_dir, pack).read_bytes(), members)
        except farc.FarcError as error:
            raise ModError(str(error)) from None
        check = farc.member_bytes(rebuilt)
        for h, blob in members.items():
            if check.get(h, b"")[:len(blob)] != blob:
                raise ModError(tr("The rebuilt pack {0} does not hold member {1}.", pack, f"{h:08X}"))
        out = mod / pack
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_bytes(rebuilt)
    progress(100, "")
    return Path(output_dir)
