"""Build a LayeredFS mod for a Pokémon 3DS game from the translated member files.

The unpack step keeps a copy of each GARC archive it read, under ``garc_original/<base title id>/<garc>.garc`` in the
source folder. A translated file is ``translation/romfs/<garc a/d/d/d>/<name>``:

* ``NNN.ext`` or ``NNN.b.ext``: the whole member ``NNN`` (sub-file ``b``) of the archive;
* ``NNN[.b].ext/<path>``: one file inside the DARC pack that member ``NNN[.b]`` holds (Pokémon X/Y pictures).

The build puts each changed member into a copy of its archive (the game loads the whole archive from the mod) and
writes the archive to ``<output>/titles/<base title id>/romfs/<garc>``. The archive keeps its FAT shape; each member
keeps its compression.
"""
from __future__ import annotations

from pathlib import Path
from typing import Callable, Dict, Iterable, Tuple

from core.i18n import tr
from plugins.common.darc_pack import DarcError, darc_replace, pack_darc_at
from plugins.common.garc import Garc, wrap

ORIGINAL_DIR = "garc_original"
Members = Dict[Tuple[int, int], Dict[str, bytes]]   # (index, bit) -> {"" (whole member) or pack path: bytes}


class ModError(ValueError):
    """The build cannot be made from the project's files."""


def base_title(source_dir: Path) -> str:
    """The base title id the unpack kept archives for (the one folder under ``garc_original``)."""
    root = Path(source_dir, ORIGINAL_DIR)
    folders = [f.name for f in root.iterdir() if f.is_dir()] if root.is_dir() else []
    if len(folders) != 1:
        raise ModError(tr("The source folder has no single game archive set: unpack the game again."))
    return folders[0]


def original_path(source_dir: Path, title_id: str, rel: str) -> Path:
    """Where the archive ``rel`` (``a/0/3/2``) of the base title ``title_id`` is kept in the source folder."""
    return Path(source_dir, ORIGINAL_DIR, title_id.lower(), rel + ".garc")


def store_original(source_dir: Path, title_id: str, rel: str, data: bytes) -> None:
    """Keep the archive ``rel`` (as the game reads it, an Ultra update already applied) for later builds."""
    out = original_path(source_dir, title_id, rel)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_bytes(data)


def _split(rel: str) -> Tuple[str, int, int, str]:
    """``(garc, index, bit, member path)`` of a translation path ``romfs/a/d/d/d/<name>``; ValueError when not one."""
    parts = rel.split("/")
    if len(parts) < 6 or parts[0] != "romfs":
        raise ValueError(rel)
    garc = "/".join(parts[1:5])
    stem = parts[5].split(".")
    index = int(stem[0])
    bit = int(stem[1]) if len(stem) >= 2 and stem[1].isdigit() else 0
    return garc, index, bit, "/".join(parts[6:])


def changed_members(translation_dir: Path, source_dir: Path, garcs: Iterable[str]) -> Dict[str, Members]:
    """``{garc: {(index, bit): {member: bytes}}}`` for every translated file that differs from the source."""
    allowed = set(garcs)
    changes: Dict[str, Members] = {}
    root = Path(translation_dir)
    if not root.is_dir():
        return changes
    for path in sorted(p for p in root.rglob("*") if p.is_file()):
        rel = path.relative_to(root).as_posix()
        if rel.endswith((".tmp", ".bak")):
            continue
        try:
            garc, index, bit, member = _split(rel)
        except ValueError:
            continue
        if garc not in allowed:
            continue
        data = path.read_bytes()
        original = Path(source_dir, *rel.split("/"))
        if original.is_file() and original.read_bytes() == data:
            continue
        changes.setdefault(garc, {}).setdefault((index, bit), {})[member] = data
    return changes


def build(source_dir: Path, translation_dir: Path, output_dir: Path, title_id: str, garcs: Iterable[str],
          progress: Callable[[int, str], None], is_cancelled: Callable[[], bool]) -> Path:
    """Write the changed archives of ``title_id`` into ``output_dir``. Returns the output folder, None when cancelled."""
    changes = changed_members(translation_dir, source_dir, garcs)
    if not changes:
        progress(100, "")
        return Path(output_dir)
    mod = Path(output_dir, "titles", title_id.lower(), "romfs")
    for number, (rel, members_of) in enumerate(sorted(changes.items()), 1):
        if is_cancelled():
            return None
        progress(100 * (number - 1) // len(changes), rel)
        original = original_path(source_dir, title_id, rel)
        if not original.is_file():
            raise ModError(tr("The original archive {0} is not in the source folder: unpack the game again.", rel))
        garc = Garc(original.read_bytes())
        replace = {}
        for (index, bit), members in sorted(members_of.items()):
            plain, compressed = garc.member(index, bit)
            if "" in members:
                new = members[""]
            else:
                at = pack_darc_at(plain)
                if at is None:
                    raise ModError(tr("The member {0} of {1} is not a pack: its translated parts cannot be put back.",
                                      str((index, bit)), rel))
                try:
                    new = plain[:at] + darc_replace(plain[at:], members)
                except DarcError as error:
                    raise ModError(str(error)) from None
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


def stored_garcs(source_dir: Path, title_id: str) -> list:
    """The archives the unpack kept for ``title_id``, as paths like ``a/0/7/4`` (the build's allowed set)."""
    root = Path(source_dir, ORIGINAL_DIR, title_id.lower())
    if not root.is_dir():
        return []
    return sorted(p.relative_to(root).as_posix()[:-len(".garc")] for p in root.rglob("*.garc"))
