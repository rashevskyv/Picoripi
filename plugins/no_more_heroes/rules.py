"""No More Heroes (Wii, Europe RNHP99) plugin.

The project's source folder is ``source`` of the workspace, which its ``1_unpack.bat`` fills from the disc
(``_shared/scripts/zt/nmh.py``): ``text/<disc file>.nmt`` -- the English lines of every text box of one game
file (dialogue, cut-scene subtitles, missions, shops, items, menus), as JSON blocks --, ``text/main.dol.nmt``
(menu words the game keeps in its program, written in place), ``hbm/home.csv`` (Wii HOME Menu). The game draws
no text from a font: every box carries a picture of its own glyphs, which ``2_build.bat`` draws anew from the
box's old picture and the fonts (``font/*.tpl``, a glyph grid each; Ukrainian letters have empty cells to draw).
Textures are the TPL files under ``ui``, ``hbm`` and ``opening.bnr``.
"""
import re
from typing import Set

from plugins.common.block_json import BlockJsonRules
from plugins.common.tag_manager import GenericTagManager

from .config import DEFAULT_LINES_PER_PAGE, PLUGIN_PREFIX, PROBLEM_DEFINITIONS

TAG_RE = re.compile(r"<\$[0-9A-F]{4}>|%[-+0 #]*\d*(?:\.\d+)?[dsxXcfu]")


class TagManager(GenericTagManager):
    """Raw Shift-JIS codes the text cannot show (``<$8256>``) and the game's number fields (``%02d``)."""

    def get_legitimate_tags(self) -> Set[str]:
        return {TAG_RE.pattern}

    def is_tag_legitimate(self, tag_to_check: str) -> bool:
        return isinstance(tag_to_check, str) and TAG_RE.fullmatch(tag_to_check) is not None


class GameRules(BlockJsonRules):
    """No More Heroes (Wii, Europe)."""

    problem_prefix = PLUGIN_PREFIX
    problem_definitions = PROBLEM_DEFINITIONS
    tag_manager_class = TagManager
    text_extension = ".nmt"
    text_label = "No More Heroes text"

    def get_display_name(self) -> str:
        return "No More Heroes"

    def get_spellcheck_ignore_pattern(self) -> str:
        return TAG_RE.pattern

    def get_tag_tooltip(self, tag: str) -> str:
        if not TAG_RE.fullmatch(str(tag)):
            return ""
        return "Raw game character code" if str(tag).startswith("<$") else "Number or name the game fills in"

    def get_editor_page_size(self) -> int:
        return DEFAULT_LINES_PER_PAGE
