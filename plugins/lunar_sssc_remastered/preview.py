"""The PS1 message-window preview of ``lunar_sssc`` for the combined Lunar SSS project.

The window, portraits, palette and program font come from the PS1 disc (``unpack.extract_ps1`` puts them in the
project's source folder as the PS1 project has them). Characters the PS1 program font lacks (the Japanese text) are
drawn with the Remastered font 0 (``atlas.py``) at its own widths, the edited font of the translation folder first.
Without the PS1 disc the window is drawn with that font only.
"""
from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from typing import Any, Dict, Tuple

from plugins.common.switch_message_preview import source_folder
from plugins.lunar_sssc import dialogue_panel

from . import atlas, unpack


@lru_cache(maxsize=4)
def font_folders(project_dir: str) -> Tuple[Path, ...]:
    """Where font 0 is read from: the translation folder's copy (edited in the font editor), then the source's."""
    roots = [source_folder(project_dir, "translation_path"), source_folder(project_dir) or project_dir]
    return tuple(Path(root).joinpath(*unpack.FONT_FOLDER.split("/")) for root in roots if root)


def font_widths(project_dir: str) -> Dict[str, int]:
    """Character -> pen advance in PS1 pixels of font 0 (cached until the font file changes)."""
    return atlas.widths(*font_folders(project_dir))


def read_sources(project_dir: str) -> Dict[str, Any]:
    """The PS1 preview's sources, with the Remastered glyphs and widths for every character the PS1 font lacks."""
    try:
        result = dialogue_panel.load_sources(project_dir)
    except (OSError, ValueError):  # no PS1 program in the project (or not a Lunar one): no PS1 font, no portraits
        result = {"glyphs": {}, "files": {}, "index": {}, "palette": None, "colours": {}}
    folders = font_folders(project_dir)
    extra = atlas.glyphs(*folders, skip=result["glyphs"])
    if not result["glyphs"] and not extra:
        raise ValueError("no PS1 program font and no Remastered font in the source folder")
    result["glyphs"] = {**extra, **result["glyphs"]}
    result["widths"] = atlas.widths(*folders)
    return result


class RemasteredDialoguePreview(dialogue_panel.LunarDialoguePreview):
    """The PS1 window with the Remastered glyphs for the Japanese text (GameRules.get_custom_preview_widget)."""

    read_sources = staticmethod(read_sources)
