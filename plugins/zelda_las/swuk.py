"""Import the Ukrainian SWUK mod of Link's Awakening (Switch; written for v1.1.0) into a project's translation folder.

The mod ships message files for ``regionEU/EUen``. Each of its messages goes to the 1.0.0 file of the same name in
``regionUS/USen``, the only slot LAS Recomp reads (its language is fixed to en-US), matched by label. ``regionEU/EUen``
is not written; the project shows it as a reference column. A label the 1.0.0 file does not have is dropped and counted. A 1.0.0 label the mod lacks keeps its English text and is counted. The mod's
other files (``region_common/...``) replace the 1.0.0 file of the same path.

Run with the project closed in Picoripi::

    python -m plugins.zelda_las.swuk <mod.zip> <unpacked romfs folder> <project translation folder>
"""
from __future__ import annotations

import struct
import sys
import zipfile
from pathlib import Path
from typing import Dict, List, Tuple

from plugins.common.msbt import Msbt
from utils.atomic_io import atomic_write_bytes

SLOT = "regionUS/USen"          # the translated slot: the recomp's language is en-US; the project's blocks are this slot
MOD_MESSAGES = "regionEU/EUen/message/"
MOD_OTHER = "region_common/"
MAX_MEMBER = 32 * 1024 * 1024
MAX_TOTAL = 128 * 1024 * 1024


def _safe_relative(rel: str) -> bool:
    parts = rel.split("/")
    return not rel.startswith("/") and "\\" not in rel and ":" not in rel and all(p not in ("", ".", "..") for p in parts)


def read_mod(zip_path: str | Path) -> Dict[str, bytes]:
    """The mod's files under ``romfs/``: ``{path relative to romfs: bytes}``. Other members are ignored.

    Member names are checked; a member or the whole mod over the size limits raises ValueError.
    """
    files: Dict[str, bytes] = {}
    total = 0
    with zipfile.ZipFile(zip_path) as archive:
        for info in archive.infolist():
            _head, marker, rel = info.filename.replace("\\", "/").partition("/romfs/")
            if info.is_dir() or not marker or not _safe_relative(rel):
                continue
            if not (rel.startswith(MOD_MESSAGES) or rel.startswith(MOD_OTHER)):
                continue
            if info.file_size > MAX_MEMBER:
                raise ValueError(f"the mod file {rel} is too large")
            total += info.file_size
            if total > MAX_TOTAL:
                raise ValueError("the mod is too large")
            with archive.open(info) as member:
                files[rel] = member.read(MAX_MEMBER + 1)
    return files


def map_messages(mod: bytes, target: bytes) -> Tuple[bytes, Dict[str, int]]:
    """``target`` (an MSBT) with each message text taken from ``mod`` by its label; the other sections are kept.

    Returns the new file and the counts ``matched``, ``kept`` (English, no label in the mod) and ``extra`` (mod labels the
    target lacks). Raises ValueError (or a struct/index error from a damaged file) when a file does not parse.
    """
    source = Msbt(mod)
    texts = {label: source.messages[index] for index, label in source.labels.items() if index < len(source.messages)}
    msbt = Msbt(target)
    rebuilt = []
    matched = kept = 0
    for index, tokens in enumerate(msbt.messages):
        label = msbt.labels.get(index)
        if label in texts:
            rebuilt.append(texts[label])
            matched += 1
        else:
            rebuilt.append(tokens)
            kept += 1
    target_labels = set(msbt.labels.values())
    extra = len([label for label in texts if label not in target_labels])
    return msbt.build(rebuilt), {"matched": matched, "kept": kept, "extra": extra}


def import_mod(zip_path: str | Path, romfs_dir: str | Path, translation_dir: str | Path) -> List[str]:
    """Write the mod into ``translation_dir`` (same relative paths as the romfs). Returns one report line per file."""
    files = read_mod(zip_path)
    romfs, translation = Path(romfs_dir), Path(translation_dir)
    report: List[str] = []
    for rel in sorted(files):
        data = files[rel]
        if rel.startswith(MOD_MESSAGES):
            target_rel = f"{SLOT}/message/{rel[len(MOD_MESSAGES):]}"
            target = romfs / target_rel
            if not target.is_file():
                report.append(f"{target_rel}: not in the unpacked romfs, skipped")
                continue
            try:
                out, counts = map_messages(data, target.read_bytes())
            except (ValueError, IndexError, struct.error) as error:
                report.append(f"{target_rel}: cannot read ({error}), skipped")
                continue
            atomic_write_bytes(translation / target_rel, out)
            report.append(f"{target_rel}: {counts['matched']} matched, {counts['kept']} kept English, "
                          f"{counts['extra']} extra label(s) dropped")
        else:
            target = romfs / rel
            if not target.is_file():
                report.append(f"{rel}: not in the unpacked romfs, skipped")
                continue
            atomic_write_bytes(translation / rel, data)
            report.append(f"{rel}: copied ({len(data)} bytes; the 1.0.0 file has {target.stat().st_size} bytes)")
    return report


def main(argv: List[str]) -> int:
    if len(argv) != 3:
        print(__doc__)
        return 2
    for line in import_mod(argv[0], argv[1], argv[2]):
        print(line)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
