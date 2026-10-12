"""Sly Cooper plugin: the game text as JSON blocks (one block per level, the level's text in file order)."""
from plugins.common.block_json import BlockJsonRules

from .config import PROBLEM_DEFINITIONS

PLUGIN_PREFIX = "SLY"


class GameRules(BlockJsonRules):
    """Sly Cooper and the Thievius Raccoonus: the English text of one language column, one block per level."""

    problem_prefix = PLUGIN_PREFIX
    problem_definitions = PROBLEM_DEFINITIONS
    text_extension = ".json"
    text_label = "Sly Cooper text"

    def get_display_name(self) -> str:
        return "Sly Cooper and the Thievius Raccoonus"
