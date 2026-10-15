"""Find ``picoripi/project.uiproj`` files under a folder, for the manager's import; skips backups and tool folders."""
from __future__ import annotations

import os
from pathlib import Path
from typing import Callable, Dict, List

from core.project_library.cards import PROJECT_FILE_NAME, PROJECT_FOLDER_NAME, fallback_name, read_card

# Folder names that stand for a platform. Matched case-insensitively with spaces removed ("Wii U" -> "wiiu").
PLATFORM_NAMES = {
    "3ds": "3DS", "switch": "Switch", "wiiu": "Wii U", "wii": "Wii", "gamecube": "GameCube", "gc": "GameCube",
    "gba": "GBA", "ds": "DS", "nds": "DS", "n64": "N64", "nes": "NES", "snes": "SNES",
    "ps2": "PS2", "psp": "PSP", "pc": "PC",
}


def platform_from_parts(parts: List[str]) -> str:
    """The platform named by one of the folder names, nearest first. Empty when none is known."""
    for part in reversed(parts):
        platform = PLATFORM_NAMES.get(part.lower().replace(" ", ""))
        if platform:
            return platform
    return ""


def find_projects(root: str | os.PathLike, cancelled: Callable[[], bool] = lambda: False) -> List[Dict]:
    """Every project under ``root``, sorted by path. Each item has the card fields plus ``series``, ``platform``,
    ``project_file``, ``duplicate`` (its project id was already seen earlier in the list) and ``error``.

    Folders whose name starts with ``_`` or ``.`` are not entered (backups, temporary copies, tool data). A
    ``picoripi`` folder that holds a project file is not entered either: its content is extracted game data.
    """
    root_path = Path(root)
    found: List[Dict] = []
    for directory, subdirectories, files in os.walk(root_path):
        if cancelled():
            break
        subdirectories[:] = sorted(name for name in subdirectories if not name.startswith(("_", ".")))
        if os.path.basename(directory) != PROJECT_FOLDER_NAME or PROJECT_FILE_NAME not in files:
            continue
        subdirectories[:] = []
        project_file = str(Path(directory) / PROJECT_FILE_NAME)
        relative = Path(directory).parent.relative_to(root_path).parts
        series = relative[0] if relative else root_path.name
        item: Dict = {
            "project_file": project_file,
            "series": series,
            "platform": platform_from_parts(list(relative[1:])),
            "error": "",
        }
        try:
            item.update(read_card(project_file))
        except (OSError, ValueError) as exc:
            item.update({"name": fallback_name(project_file), "error": str(exc), "project_id": "",
                         "plugin": "", "blocks": 0, "issues": ["unreadable"], "modified": ""})
        found.append(item)

    seen_ids = set()
    for item in found:
        project_id = item.get("project_id", "")
        item["duplicate"] = bool(project_id) and project_id in seen_ids
        if project_id:
            seen_ids.add(project_id)
    return found
