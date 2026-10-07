r"""Lunar 2: Eternal Blue Complete (PlayStation, USA) plugin: scripts, people's talk, menus, names, font.

The project's source folder is the ``source`` folder the workspace's unpack step fills
(``E:\Emulators\RomHacking\Lunar\Eternal Blue``): ``DATA/EVENT`` (event scripts), ``DATA/PEOPLE``
(what people on a map say), ``DATA/SYSTEM/2499/05-12.bin`` (items, spells, menus), ``DATA/BATTLE``
(monster names), ``DATA/MAP`` (place names), ``DATA/SYSTEM/0003.bin`` (system messages). The font
(Tools -> Font Editor) and the pictures (Tools -> Textures) are in the same folder. Saving writes the
same files into the translation folder; the build step puts them back on the three discs.
Load and save are those of ``lunar_sssc`` with this game's text module (``doc``).
"""
from plugins.lunar_sssc.rules import GameRules as LunarRules

from . import doc
from .config import DEFAULT_LINES_PER_PAGE, PLUGIN_PREFIX, PROBLEM_DEFINITIONS
from .tag_manager import TagManager

UNIT_TIPS = {
    "1": "Next line.",
    "2": "Wait for a button, then a new page.",
    "3": "An icon (07: the 'more' arrow).",
    "4": "A choice: the next lines are its answers.",
    "5": "Close the window.",
    "6": "Wait for a button, then a new page (and go on).",
    "B": "Speaker portrait and name (the number picks the character).",
    "C": "A character's name (the number picks it).",
    "D": "Pause, in frames.",
}


class GameRules(LunarRules):
    """Lunar 2: Eternal Blue Complete (PlayStation, USA, SLUS-01071 / 01239 / 01240)."""

    problem_prefix = PLUGIN_PREFIX
    problem_definitions = PROBLEM_DEFINITIONS
    tag_manager_class = TagManager
    display_name = "Lunar 2: Eternal Blue Complete"
    text_doc = doc

    def get_file_formats(self) -> list:
        from core.formats import DEFAULT_FORMATS, FileFormat
        return [FileFormat((".bin",), "bytes", "Lunar 2 text data"), *DEFAULT_FORMATS]

    def get_editor_page_size(self) -> int:
        return DEFAULT_LINES_PER_PAGE

    def get_tag_tooltip(self, tag: str) -> str:
        if tag == "{/}":
            return "Two lines of text that follow each other."
        if len(tag) == 4:
            return "A character byte the font has no glyph for (kept as it is)."
        return UNIT_TIPS.get(tag[1:2], "A control unit of the game (kept as it is).")
