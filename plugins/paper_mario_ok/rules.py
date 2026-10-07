"""Paper Mario: The Origami King (Switch, 2020) plugin: the game's MSBT text, fonts and UI textures.

Same formats as the Switch Thousand-Year Door, so the rules are ``plugins.paper_mario_nx`` with this game's tag
catalogue. ``1_unpack.bat`` of the workspace (``_shared/scripts/zt/pmok.py``) fills the source folder:
``msg/EU_English/*.msbt`` (all text: 59 files, ~9,700 messages), the fonts without their zstd wrapper
(``font/*.bffnt``) and the BNTX textures of the UI (``ui/<folder>/<name>.bfres.bntx``, the English
``ui/<folder>/<name>.bfres.en.bntx`` of a BFRES that keeps one texture per language, ``ui/<name>.bntx``).
"""
from plugins.paper_mario_nx.rules import GameRules as ThousandYearDoorRules
from plugins.paper_mario_nx.tag_manager import TagManager as ThousandYearDoorTagManager

from .config import PLUGIN_PREFIX, PROBLEM_DEFINITIONS
from .tags import CODEC


class TagManager(ThousandYearDoorTagManager):
    """Tags of this game's MSBP."""

    codec = CODEC


class GameRules(ThousandYearDoorRules):
    """Paper Mario: The Origami King (Nintendo Switch)."""

    problem_prefix = PLUGIN_PREFIX
    problem_definitions = PROBLEM_DEFINITIONS
    tag_manager_class = TagManager
    codec = CODEC

    def get_display_name(self) -> str:
        return "Paper Mario: The Origami King (Switch)"
