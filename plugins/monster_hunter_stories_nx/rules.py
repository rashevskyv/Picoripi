"""Monster Hunter Stories (Switch) plugin: the game's ``GMD`` message tables.

``1_unpack.bat`` (``zt/r3bnx.py``) opens the English archive ``nativeNXx64/archive/message_R/message_all_eng.arc``
(MT Framework ``ARC``, zlib members) as a folder in the project's source folder: one ``.gmd`` file per member
(dialogue, quests, menus, items, monsters, tutorials). Each file is one block; ``2_build.bat`` writes the changed
members back into the archive. Format: ``gmd``.
"""
from __future__ import annotations

import re
from typing import Any, Dict, Optional, Set

from plugins.common.table_rules import TableRules

from . import gmd
from .config import DEFAULT_LINES_PER_PAGE, PLUGIN_PREFIX, PROBLEM_DEFINITIONS
from .tag_manager import TAG_RE, TagManager

_NAMES = re.compile(r"(?i)(^|/)(.*(name|title|keyword|word).*)\.gmd$")


class GameRules(TableRules):
    """Monster Hunter Stories (Switch, English)."""

    problem_prefix = PLUGIN_PREFIX
    problem_definitions = PROBLEM_DEFINITIONS
    tag_manager_class = TagManager
    display_name = "Monster Hunter Stories (Switch)"
    file_formats = (((".gmd",), "Capcom GMD message table (MT Framework 2)"),)
    default_script_name = "monster_hunter_stories_script.md"
    lines_per_page = DEFAULT_LINES_PER_PAGE
    spellcheck_ignore = TAG_RE.pattern

    def parse_table(self, raw: bytes):
        try:
            return gmd.Table(raw)
        except (ValueError, UnicodeDecodeError):
            return None

    def get_capabilities(self) -> Set[str]:
        return {"strict_tags"}

    def get_translation_context_for_string(self, block_idx: int, string_idx: int) -> Dict[str, Any]:
        found = self._locate(block_idx)
        if not found:
            return {}
        path = found[0]
        if _NAMES.search(path):
            return {"role": "Name", "description": "A name or label from a game table (keep it short)."}
        if re.search(r"(?i)npctalk|talk|story|chap|event|demo|msg", path):
            return {"role": "Dialogue", "description": "A line of dialogue; <COL ..>, <SPNM ..>, <ICON ..> tags stay as they are, "
                                                      "<PAGE> starts a new message window."}
        return {"role": "Menu text", "description": "Menu, item description, quest or system text."}

    def get_speaker_for_string(self, block_idx: int, string_idx: int) -> Optional[str]:
        return None
