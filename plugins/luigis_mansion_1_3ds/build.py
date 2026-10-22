"""Build target of Luigi's Mansion (3DS): a Luma LayeredFS folder with the translated message files.

The source folder is the CIA's romfs as ``images.extract`` writes it, limited to ``romfs/Region_US/English/`` (the
English slot; the French and Spanish tables are not extracted). A changed file goes to
``titles/00040000001D1900/romfs/<the same path>``, which Luma loads over the CIA's RomFS. Nothing else is written.
"""
import os
from pathlib import Path
from typing import Callable, Dict

from core.i18n import tr
from plugins.common.disc_source import SOURCE_MARK
from plugins.luigis_mansion_1_3ds import gmsg

TITLE_ID = "00040000001D1900"
ENGLISH_FOLDER = "romfs/region_us/english/"

Progress = Callable[[int, str], None]
Cancelled = Callable[[], bool]


def select_english(path: str) -> bool:
    """True for the files the source folder keeps: the English message tables (``images.extract`` ``select``)."""
    return path.replace("\\", "/").lower().startswith(ENGLISH_FOLDER)


def changed_files(source_dir: str | os.PathLike, translation_dir: str | os.PathLike) -> Dict[str, bytes]:
    """{path in the source tree: new bytes} for each translated file that differs from the source. A message table
    keeps its message count; a file the source does not hold is refused."""
    source, translation = Path(source_dir), Path(translation_dir)
    changes: Dict[str, bytes] = {}
    for path in sorted(translation.rglob("*")):
        if not path.is_file():
            continue
        rel = path.relative_to(translation).as_posix()
        if rel == SOURCE_MARK:
            continue
        base = source / rel
        if not base.is_file():
            raise ValueError(tr("{0}: not on the disc (new files are not written)", rel))
        data = path.read_bytes()
        old = base.read_bytes()
        if data == old:
            continue
        if rel.lower().endswith(".gmsg") and len(gmsg.Table(data).ids()) != len(gmsg.Table(old).ids()):
            raise ValueError(tr("{0}: the number of messages changed; only the text may change", rel))
        changes[rel] = data
    return changes


def build_layeredfs(source_dir: str, translation_dir: str, output_dir: str,
                    progress: Progress, is_cancelled: Cancelled) -> str:
    """Write ``titles/<title>/romfs`` (the changed files only) into ``output_dir`` and return its path."""
    changes = changed_files(source_dir, translation_dir)
    root = Path(output_dir) / "titles" / TITLE_ID / "romfs"
    count = len(changes) or 1
    for index, (rel, data) in enumerate(changes.items()):
        if is_cancelled():
            break
        progress(100 * index // count, rel)
        target = root / rel[len("romfs/"):]
        target.parent.mkdir(parents=True, exist_ok=True)
        tmp = target.with_name(target.name + ".tmp")
        tmp.write_bytes(data)
        os.replace(tmp, target)
    progress(100, "")
    return str(root)
