"""Headless translation import: write a map of translations into a project's translation files.

The plugin builds each file through its own table format (``parse_table`` and ``Table.build``). The table works on the
file's bytes, so the host reads and writes the bytes as they are (atomically) whatever the file's format. The project
file is read and never changed.

A line id of the lines file gives its block by ``file`` (the block's source file) and its string by the table's own
id, or by ``name:N`` for record N (1-based). A line is written only when the project's English equals the lines file's
English. A block is written in one piece, and only when every line of it builds. Before ``apply`` the project file is
copied to ``data/backups``.
"""
from __future__ import annotations

import json
import shutil
import warnings
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from core.project_library.plugin_facts import default_load_rules
from utils.atomic_io import atomic_write_bytes


def _root(base: Path, value: Any) -> Optional[Path]:
    if not value:
        return None
    path = Path(str(value))
    return path if path.is_absolute() else base / path


def _string_index(line_id: str, table: Any) -> Optional[int]:
    """Position of the line in the table: ``name:N`` is record N (1-based), otherwise the table's own id."""
    if ":" in line_id:
        number = line_id.rsplit(":", 1)[1]
        count = len(table.texts())
        return int(number) - 1 if number.isdigit() and 1 <= int(number) <= count else None
    ids = table.ids()
    return ids.index(line_id) if line_id in ids else None


def _read_bytes(path: Path) -> Tuple[Optional[bytes], Optional[str]]:
    try:
        return path.read_bytes(), None
    except OSError as error:
        return None, f"Failed to read {path.name}: {error}"


def _backup(project_file: Path) -> Path:
    folder = project_file.parent / "data" / "backups"
    folder.mkdir(parents=True, exist_ok=True)
    target = folder / f"{project_file.name}.{datetime.now():%Y%m%d-%H%M%S}.bak"
    shutil.copy2(project_file, target)
    return target


def import_translations(project_file: Any, lines: Dict[str, Dict[str, Any]], translations: Dict[str, str],
                        apply: bool = False) -> Dict[str, Any]:
    """Import ``translations`` (line id -> text). Dry run unless ``apply``. Returns the report."""
    project_file = Path(project_file)
    data = json.loads(project_file.read_text(encoding="utf-8"))
    base = project_file.parent
    metadata = data.get("metadata") or {}
    source_root = _root(base, metadata.get("source_path")) or base / "unpacked"
    translation_root = _root(base, metadata.get("translation_path")) or base / "translation"
    rules = default_load_rules(data["plugin_name"])
    blocks = {str(block.get("source_file") or "").replace("\\", "/"): block for block in data.get("blocks") or []}

    report: Dict[str, Any] = {"lines": len(translations), "applied": 0, "same_as_english": 0,
                              "files": [], "problems": [], "warnings": []}
    groups: Dict[str, List[Tuple[str, str, str]]] = {}
    for line_id, text in translations.items():
        line = lines.get(line_id)
        if line is None:
            report["problems"].append({"id": line_id, "problem": "id not in the lines file"})
            continue
        key = str(line["file"]).replace("\\", "/")
        if key not in blocks:
            report["problems"].append({"id": line_id, "problem": "no block has this source file"})
            continue
        groups.setdefault(key, []).append((line_id, str(line["en"]), str(text)))

    if apply:
        report["backup"] = str(_backup(project_file))
    for key, entries in groups.items():
        block = blocks[key]
        content, error = _read_bytes(source_root / block["source_file"])
        source = rules.parse_table(content) if content is not None else None
        if source is None:
            report["problems"].append({"file": key, "problem": error or "source is not a text table"})
            continue
        source_texts = source.texts()
        target = translation_root / block["translation_file"]
        table = source
        if target.exists():   # keep the work already in the translation file
            content, error = _read_bytes(target)
            table = rules.parse_table(content) if content is not None else None
            if table is None or len(table.texts()) != len(source_texts):
                report["problems"].append({"file": key, "problem": "existing translation file does not match the source"})
                continue
        texts = table.texts()
        accepted: List[Tuple[str, str, str]] = []
        for line_id, en, text in entries:
            index = _string_index(line_id, source)
            if index is None or source_texts[index] != en:
                report["problems"].append({"id": line_id, "problem": "English differs from the project"})
                continue
            trial = list(texts)
            trial[index] = text
            try:   # a line whose text the format cannot hold is refused alone; its block still goes in
                with warnings.catch_warnings(record=True) as notes:   # a substitution is a warning, the line stays
                    warnings.simplefilter("always")
                    table.build(trial)
            except ValueError as error:
                report["problems"].append({"id": line_id, "problem": str(error)})
                continue
            report["warnings"] += [{"id": line_id, "warning": str(note.message)} for note in notes]
            texts = trial
            accepted.append((line_id, en, text))
        if not accepted:
            continue
        out = table.build(texts)
        if apply:
            target.parent.mkdir(parents=True, exist_ok=True)
            try:
                atomic_write_bytes(target, out)
            except OSError as error:
                report["problems"].append({"file": key, "problem": f"write failed: {error}"})
                continue
            report["files"].append(str(target))
        report["applied"] += len(accepted)
        report["same_as_english"] += sum(1 for _, en, text in accepted if text == en)
    return report
