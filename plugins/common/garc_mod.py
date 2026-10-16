"""Build a LayeredFS mod for a Pokémon 3DS game from the translated member files.

The unpack step keeps a copy of each GARC archive it read, under ``garc_original/<base title id>/<garc>.garc`` in the
source folder. A translated member is a file ``translation/romfs/<garc>/NNN[.b].<ext>``. The build puts each changed
member into a copy of its archive (the game loads the whole archive from the mod) and writes the archive to
``<output>/titles/<base title id>/romfs/<garc>``. The archive keeps its FAT shape; the member's compression is kept.
"""
from __future__ import annotations

import re
from pathlib import Path
from typing import Callable, Dict, Iterable, Optional, Tuple

from core.i18n import tr
from plugins.common.garc import Garc, wrap

ORIGINAL_DIR = "garc_original"
_NAME = re.compile(r"^romfs/(a/\d/\d/\d)/(\d{3})(?:\.(\d+))?\.(dat|bffnt|bflim)$")


class ModError(ValueError):
    """The build cannot be made from the project's files."""


def original_path(source_dir: Path, title_id: str, rel: str) -> Path:
    """Where the archive ``rel`` (``a/0/3/2``) of the base title ``title_id`` is kept in the source folder."""
    return Path(source_dir, ORIGINAL_DIR, title_id.lower(), rel + ".garc")


def base_title(source_dir: Path) -> str:
    """The base title id the unpack kept archives for (the one folder under ``garc_original``)."""
    folders = [f.name for f in Path(source_dir, ORIGINAL_DIR).iterdir() if f.is_dir()]         if Path(source_dir, ORIGINAL_DIR).is_dir() else []
    if len(folders) != 1:
        raise ModError(tr("The source folder has no single game archive set: unpack the game again."))
    return folders[0]


def store_original(source_dir: Path, title_id: str, rel: str, data: bytes) -> None:
    """Keep the archive ``rel`` (as the game reads it, an Ultra update already applied) for later builds."""
    out = original_path(source_dir, title_id, rel)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_bytes(data)


def changed_members(translation_dir: Path, source_dir: Path, garcs: Iterable[str]) -> Dict[str, Dict[Tuple[int, int], bytes]]:
    """``{garc: {(index, bit): new plain bytes}}`` for every translated member that differs from the source."""
    allowed = set(garcs)
    changes: Dict[str, Dict[Tuple[int, int], bytes]] = {}
    root = Path(translation_dir)
    if not root.is_dir():
        return changes
    for path in sorted(p for p in root.rglob("*") if p.is_file()):
        rel = path.relative_to(root).as_posix()
        if rel.endswith((".tmp", ".bak")):
            continue
        match = _NAME.match(rel)
        if not match or match.group(1) not in allowed:
            continue
        data = path.read_bytes()
        original = Path(source_dir, *rel.split("/"))
        if original.is_file() and original.read_bytes() == data:
            continue
        index, bit = int(match.group(2)), int(match.group(3) or 0)
        changes.setdefault(match.group(1), {})[(index, bit)] = data
    return changes


def build(source_dir: Path, translation_dir: Path, output_dir: Path, title_id: str, garcs: Iterable[str],
          progress: Callable[[int, str], None], is_cancelled: Callable[[], bool]) -> Optional[Path]:
    """Write the changed archives of ``title_id`` into ``output_dir``. Returns the mod folder, or None when cancelled."""
    changes = changed_members(translation_dir, source_dir, garcs)
    mod = Path(output_dir, "titles", title_id.lower(), "romfs")
    if not changes:
        progress(100, "")
        return Path(output_dir)
    for number, (rel, members) in enumerate(sorted(changes.items()), 1):
        if is_cancelled():
            return None
        progress(100 * (number - 1) // len(changes), rel)
        original = original_path(source_dir, title_id, rel)
        if not original.is_file():
            raise ModError(tr("The original archive {0} is not in the source folder: unpack the game again.", rel))
        garc = Garc(original.read_bytes())
        replace = {}
        for (index, bit), new in sorted(members.items()):
            _plain, compressed = garc.member(index, bit)
            replace[(index, bit)] = wrap(new, compressed)
        rebuilt = garc.rebuild(replace)
        check = Garc(rebuilt)
        for key, blob in replace.items():
            if check.stored(*key) != blob:
                raise ModError(tr("The rebuilt archive {0} does not hold member {1}.", rel, str(key)))
        out = mod / Path(*rel.split("/"))
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_bytes(rebuilt)
    progress(100, "")
    return Path(output_dir)
