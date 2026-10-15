"""Facts about one project read from its project.uiproj, plus the string counts recorded from memory."""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, List, Optional

from core.project_library.flags import flags_of
from core.tag_utils import strip_tags
from utils.constants import plugins_root

PROJECT_FILE_NAME = "project.uiproj"
PROJECT_FOLDER_NAME = "picoripi"  # a game workspace keeps its project in <game>/picoripi/project.uiproj


def fallback_name(project_file: str | Path) -> str:
    """The name of a project whose file names none: its folder, or the game folder above a ``picoripi`` folder."""
    folder = Path(project_file).parent
    if folder.name.casefold() == PROJECT_FOLDER_NAME and folder.parent.name:
        return folder.parent.name
    return folder.name


def _exists(base: Path, value: str) -> bool:
    candidate = Path(value)
    if not candidate.is_absolute():
        candidate = base / candidate
    return candidate.exists()


def read_card(project_file: str | Path) -> Dict[str, Any]:
    """The card of one project. Raises ``OSError`` when the file is missing, ``ValueError`` when it is not JSON.

    Only the project file is read. The plugin's parser is not run here; that is why the card has no line counts.
    """
    path = Path(project_file)
    stat = path.stat()
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError("project file is not a JSON object")

    metadata = data.get("metadata") or {}
    plugin = str(data.get("plugin_name") or "")
    issues: List[str] = []
    if plugin and not (plugins_root() / plugin / "config.json").is_file():
        issues.append("plugin_missing")
    for key, code in (("source_path", "source_missing"), ("translation_path", "translation_missing")):
        value = metadata.get(key)
        if value and not _exists(path.parent, str(value)):
            issues.append(code)

    return {
        "name": str(data.get("name") or fallback_name(path)),
        "plugin": plugin,
        "blocks": len(data.get("blocks") or []),
        "project_id": str(data.get("id") or ""),
        "modified": str(data.get("modified_at") or ""),
        "issues": issues,
        "flags": flags_of(metadata),
        "mtime_ns": stat.st_mtime_ns,
        "size": stat.st_size,
    }


def count_strings(original: Any, translated_file: Any, edited: Dict[Any, Any]) -> Dict[str, int]:
    """Count lines, lines that need a translation and translated lines.

    Same rule as ``DataStateProcessor.is_string_translated``: a line needs a translation when its source has
    text after the tags are removed; it is translated when the current text is non-empty and differs from the source.
    ``edited`` holds unsaved edits by ``(block, string)``; ``translated_file`` is the loaded translation, by block.
    """
    lines = needs = translated = 0
    for block_index, block in enumerate(original or []):
        if not isinstance(block, list):
            continue
        for string_index, source in enumerate(block):
            lines += 1
            source_text = str(source)
            if not strip_tags(source_text).strip():
                continue
            needs += 1
            current = edited.get((block_index, string_index))
            if current is None:
                current = _string_at(translated_file, block_index, string_index)
            current_text = str(current).strip() if current is not None else ""
            if current_text and current_text != source_text.strip():
                translated += 1
    return {"lines": lines, "needs_translation": needs, "translated": translated}


def _string_at(blocks: Any, block_index: int, string_index: int) -> Optional[Any]:
    if not isinstance(blocks, list) or not 0 <= block_index < len(blocks):
        return None
    block = blocks[block_index]
    if not isinstance(block, list) or not 0 <= string_index < len(block):
        return None
    return block[string_index]


def percent_translated(counts: Dict[str, int]) -> Optional[int]:
    """Translated share of the lines that need a translation, in whole percent. None when nothing needs one."""
    needs = counts.get("needs_translation") or 0
    if needs <= 0:
        return None
    return round(100 * (counts.get("translated") or 0) / needs)
