"""One Piece: Unlimited World Red plugin (3DS, Europe): the game's ``jMSG`` message tables, fonts and pictures.

``1_unpack.bat`` (``zt/r3b3ds.py``) opens the game's ``.jarc`` archives as folders in the project's source folder
and copies the loose files: ``romfs/message_eu/msg_en.jmsg``, ``system.jmsg``, ``tutorial.jmsg`` (the English
text, system and tutorial strings), ``romfs/staffroll_eu/staffroll.jmsg``, ``romfs/chara/*_msg2.jmsg``,
``romfs/event/**/<scene>_en_eu.jarc/_talkconv_msg.bin`` (cutscene and talk subtitles, one jMSG per scene) and
``romfs/quest_eu/category*.jarc/*.jmsg`` (quest texts). Each table is one block showing its English strings;
``2_build.bat`` appends the changed members to their archive. Fonts are ``romfs/font_eu/*.jfnt``, pictures
``romfs/menu_eu/**/*.jtex`` (``texture_sources.json``).
"""
from __future__ import annotations

from struct import error as struct_error
from typing import Any, Dict, Optional, Set

from plugins.common.table_rules import TableRules

from . import jmsg
from .config import DEFAULT_LINES_PER_PAGE, PLUGIN_PREFIX, PROBLEM_DEFINITIONS
from .tag_manager import TAG_RE, TagManager


class GameRules(TableRules):
    """One Piece: Unlimited World Red (3DS, European English)."""

    problem_prefix = PLUGIN_PREFIX
    problem_definitions = PROBLEM_DEFINITIONS
    tag_manager_class = TagManager
    display_name = "One Piece: Unlimited World Red (3DS)"
    file_formats = (((".jmsg",), "Ganbarion jMSG message table"), ((".bin",), "Ganbarion jMSG message table (.bin)"))
    default_script_name = "one_piece_uwr_script.md"
    lines_per_page = DEFAULT_LINES_PER_PAGE
    spellcheck_ignore = TAG_RE.pattern

    def parse_table(self, raw: bytes):
        try:
            return jmsg.Table(raw)
        except (ValueError, UnicodeDecodeError, struct_error):
            return None

    def get_capabilities(self) -> Set[str]:
        return {"strict_tags"}

    def get_translation_context_for_string(self, block_idx: int, string_idx: int) -> Dict[str, Any]:
        found = self._locate(block_idx)
        if not found:
            return {}
        path = found[0]
        if "message_eu/msg_en" in path:
            return {"role": "Dialogue / menu text", "description": "A string of the game's main text table; {c:..} tags are colour changes."}
        if "/event/" in path or path.startswith("romfs/event/"):
            return {"role": "Dialogue", "description": "A subtitle of a cutscene or talk event; line breaks are kept."}
        if "quest_eu" in path:
            return {"role": "Quest text", "description": "A quest title or description."}
        return {"role": "Menu text", "description": "System, tutorial or staff roll text."}

    def get_speaker_for_string(self, block_idx: int, string_idx: int) -> Optional[str]:
        return None
