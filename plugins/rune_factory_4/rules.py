"""Rune Factory 4 plugin (3DS, USA): the game's ``TEXT`` tables, its menu pictures.

``1_unpack.bat`` (``zt/rf4.py``) copies the English tables of the game's romfs into the project's source
folder at the same paths: ``romfs/script/rf3mc.eng`` (dialogue and events), ``romfs/text/*.eng`` and
``romfs/textAndData/text/*.eng`` (items, NPCs, quests, skills, menus, map names). Each file is one block;
``2_build.bat`` copies the changed files into a Luma / Azahar mod. The game has no font file of its own:
it draws with the console's shared font. Pictures with text (``texture_sources.json``) are CGFX ``.bctex``
files in the same romfs; the Switch game has the same tables (plus rf4TxtShinkonHelp) and its pictures are
.bntx files (BC7) at the same paths.
"""
from __future__ import annotations

import re
from typing import Any, Dict, Optional, Set

from plugins.common.table_rules import TableRules

from . import text
from .config import DEFAULT_LINES_PER_PAGE, PLUGIN_PREFIX, PROBLEM_DEFINITIONS
from .tag_manager import TAG_RE, TagManager

_NAME_TABLES = re.compile(r"TxtItem_split\d_1|TxtNpc_split\d_1|MapName|CropName|MonsterName|TravelerName|Skill_split\d_1")


class GameRules(TableRules):
    """Rune Factory 4 (3DS, USA English)."""

    problem_prefix = PLUGIN_PREFIX
    problem_definitions = PROBLEM_DEFINITIONS
    tag_manager_class = TagManager
    display_name = "Rune Factory 4 (3DS) / Special (Switch)"
    file_formats = (((".eng",), "Rune Factory TEXT table (English)"), ((".jpn",), "Rune Factory TEXT table (Japanese)"))
    default_script_name = "rune_factory_4_script.md"
    lines_per_page = DEFAULT_LINES_PER_PAGE
    spellcheck_ignore = TAG_RE.pattern

    def parse_table(self, raw: bytes):
        try:
            return text.Table(raw)
        except (ValueError, UnicodeDecodeError):
            return None

    def get_capabilities(self) -> Set[str]:
        return {"strict_tags"}

    def get_translation_context_for_string(self, block_idx: int, string_idx: int) -> Dict[str, Any]:
        found = self._locate(block_idx)
        if not found:
            return {}
        path = found[0]
        if _NAME_TABLES.search(path):
            return {"role": "Name", "description": "A name or label from a game table (keep it short)."}
        if path.endswith("rf3mc.eng"):
            return {"role": "Dialogue", "description": "A line of dialogue or an event; ＠...＠ variables stay as they are."}
        return {"role": "Menu text", "description": "Menu, item description, quest or system text."}

    def get_speaker_for_string(self, block_idx: int, string_idx: int) -> Optional[str]:
        return None
