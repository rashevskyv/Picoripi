"""MadWorld (Wii, Europe RZZP8P) plugin.

The project's source folder is ``source`` of the workspace, which its ``1_unpack.bat`` fills from the disc
(``_shared/scripts/zt/madworld.py``): ``text/<disc file>.mwt`` -- the English messages of one message table
(cut-scene subtitles in ``event``, mission and tutorial messages in ``case*``, system and save messages in
``subscr``), as JSON blocks -- and ``hbm/home.csv`` (Wii HOME Menu). The game draws each table's text from a
picture of just the glyphs it uses; ``2_build.bat`` draws that picture anew from the old one and the fonts
(``font/font_subtitle.tpl``, ``font/font_heading.tpl``; Ukrainian letters have empty cells to draw).
Control codes show as tags: ``<8010:0064>`` (a code and its argument), ``<8002>``, ``<#0003>`` (a number or
argument word).
"""
import re
from typing import Set

from plugins.common.block_json import BlockJsonRules
from plugins.common.tag_manager import GenericTagManager

from .config import DEFAULT_LINES_PER_PAGE, PLUGIN_PREFIX, PROBLEM_DEFINITIONS

TAG_RE = re.compile(r"<[0-9A-F]{4}(?::[0-9A-F]{4})?>|<(?:G:|#)[0-9A-F]{4}>")


class TagManager(GenericTagManager):
    """The game's control codes (``<8010:0064>``, ``<8002>``) and raw words (``<#0003>``, ``<G:1012>``)."""

    def get_legitimate_tags(self) -> Set[str]:
        return {TAG_RE.pattern}

    def is_tag_legitimate(self, tag_to_check: str) -> bool:
        return isinstance(tag_to_check, str) and TAG_RE.fullmatch(tag_to_check) is not None


class GameRules(BlockJsonRules):
    """MadWorld (Wii, Europe)."""

    problem_prefix = PLUGIN_PREFIX
    problem_definitions = PROBLEM_DEFINITIONS
    tag_manager_class = TagManager
    text_extension = ".mwt"
    text_label = "MadWorld text"

    def get_display_name(self) -> str:
        return "MadWorld"

    def get_spellcheck_ignore_pattern(self) -> str:
        return TAG_RE.pattern

    def get_tag_tooltip(self, tag: str) -> str:
        if not TAG_RE.fullmatch(str(tag)):
            return ""
        return "Number or argument the game reads" if str(tag).startswith(("<#", "<G:")) else "Game control code"

    def get_editor_page_size(self) -> int:
        return DEFAULT_LINES_PER_PAGE
