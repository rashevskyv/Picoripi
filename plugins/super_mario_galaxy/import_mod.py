"""Import an existing translation (a Switch or Wii mod: a zip, a folder or one message archive) by archive and label.

``import_translation`` writes the project's translated documents (``MessageData/<archive>.smgmsg``) from the mod's
message archives: each project row whose label the mod's archive of the same name has takes the mod's text. A mod
made for the Switch has the Switch button pictures; rows that came from the Wii text get the Wii numbers back
(``messages.swap_pictures``). Each mod archive is also kept as that version's base archive (``versions/<version>/
<slot>/MessageData/<archive>.arc`` of the translation folder): a mod made for a game update carries the update's
labels, and the build writes the text into it. The mod's ``Font.arc`` (when it has one) goes to ``versions/<version>/<slot>/LayoutData/
Font.arc`` of the translation folder for every English slot of that version, where the build takes it. The report
counts matched, missing and extra labels, and lists the labels whose tags differ from the English text.

Command line: ``python -m plugins.super_mario_galaxy.import_mod <source folder> <translation folder> <mod>``.
"""
from __future__ import annotations

import json
import re
import sys
import zipfile
from collections import Counter
from pathlib import PurePosixPath, Path
from typing import Dict, List, Optional, Tuple

from utils.atomic_io import atomic_write_bytes

from . import messages
from .unpack import FONT, MESSAGE_DIR, SWITCH, VERSIONS, WII, document_rel, english_slots, english_versions

TAG_RE = re.compile(r"\{escape:\d+:[0-9a-f]*\}")


def _slot_files(names: List[str]) -> Tuple[Dict[str, str], Optional[str]]:
    """``({archive stem: member}, Font.arc member)`` of the mod's English slot (an EuEnglish folder first)."""
    slots: Dict[str, Dict[str, str]] = {}
    for name in names:
        path = PurePosixPath(name.replace("\\", "/"))
        if path.parent.name == MESSAGE_DIR and path.suffix.lower() == ".arc":
            slots.setdefault(str(path.parent.parent), {})[path.stem] = name
    if not slots:
        return {}, None
    slot = sorted(slots, key=lambda folder: ("euenglish" not in folder.lower(), folder))[0]
    font = next((name for name in names if name.replace("\\", "/").lower() == f"{slot}/{FONT}".lower()), None)
    return slots[slot], font


def read_mod(path: str) -> Tuple[Dict[str, bytes], Optional[bytes]]:
    """``({archive stem: bytes}, Font.arc or None)`` of a mod zip, a mod folder, or one message archive."""
    mod = Path(path)
    if mod.is_dir():
        names = [p.relative_to(mod).as_posix() for p in mod.rglob("*") if p.is_file()]
        archives, font = _slot_files(names)
        return {stem: (mod / name).read_bytes() for stem, name in archives.items()}, \
            (mod / font).read_bytes() if font else None
    if zipfile.is_zipfile(mod):
        with zipfile.ZipFile(mod) as archive:
            stems, font = _slot_files(archive.namelist())
            return {stem: archive.read(name) for stem, name in stems.items()}, archive.read(font) if font else None
    return {mod.stem: mod.read_bytes()}, None


def _tags(text: str) -> Counter:
    return Counter(TAG_RE.findall(text))


def import_translation(source_dir: str, translation_dir: str, mod_path: str) -> Dict[str, object]:
    """Write the translated documents from the mod and return the report."""
    source = Path(source_dir)
    mod_archives, font = read_mod(mod_path)
    if not mod_archives:
        raise ValueError(f"no message archive in {mod_path}")
    report: Dict[str, object] = {"archives": {}, "fonts": []}
    mod_version = WII
    for stem, data in sorted(mod_archives.items()):
        doc = source / document_rel(stem)
        rows = messages.read_document(doc.read_bytes()) if doc.is_file() else None
        if rows is None:
            report["archives"][stem] = {"skipped": "the project has no such archive"}
            continue
        mod_version = SWITCH if messages.archive_little(data) else WII
        mod_texts = messages.texts_by_label(data)
        english = dict(english_versions(source, stem))
        pairs = messages.picture_pairs(english[WII], english[SWITCH]) if mod_version == SWITCH and \
            WII in english and SWITCH in english else {}
        matched, missing, missing_empty, tag_diff = 0, [], 0, []
        for row in rows:
            label = str(row["label"])
            if label not in mod_texts:
                if str(row.get("text", "")).strip():
                    missing.append(label)
                else:
                    missing_empty += 1
                continue
            text = mod_texts[label]
            if pairs and WII in (row.get("in") or []):
                text = messages.swap_pictures(text, label, pairs, reverse=True)
            if _tags(text) != _tags(str(row.get("text", ""))):
                tag_diff.append(label)
            row["text"] = text
            matched += 1
        atomic_write_bytes(Path(translation_dir) / document_rel(stem), messages.make_document(rows))
        for slot in english_slots(source, mod_version):   # the mod's archive: the game update it was made for
            atomic_write_bytes(Path(translation_dir) / VERSIONS / mod_version / slot / MESSAGE_DIR / f"{stem}.arc", data)
        report["archives"][stem] = {
            "mod_version": mod_version, "mod_labels": len(mod_texts), "project_labels": len(rows), "matched": matched,
            "missing_with_text": len(missing), "missing_empty": missing_empty, "missing_sample": missing[:60],
            "extra": sorted(set(mod_texts) - {str(row["label"]) for row in rows}),
            "tag_differences": len(tag_diff), "tag_difference_sample": tag_diff[:60]}
    if font is not None:
        for slot in english_slots(source, mod_version):
            rel = f"{VERSIONS}/{mod_version}/{slot}/{FONT}"
            atomic_write_bytes(Path(translation_dir) / rel, font)
            report["fonts"].append(rel)
    return report


def main(argv: List[str]) -> int:
    if len(argv) != 3:
        print(__doc__)
        return 2
    print(json.dumps(import_translation(*argv), ensure_ascii=False, indent=1))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
