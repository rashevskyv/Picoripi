"""Jak and Daxter plugin: the game text as JSON blocks (one block per text group, ids kept in each block)."""
from plugins.common.block_json import BlockJsonRules

from .config import PROBLEM_DEFINITIONS

PLUGIN_PREFIX = "JAK"


class GameRules(BlockJsonRules):
    """Jak and Daxter (PS2 disc, Switch port): the game text of one language column."""

    problem_prefix = PLUGIN_PREFIX
    problem_definitions = PROBLEM_DEFINITIONS
    text_extension = ".json"
    text_label = "Jak and Daxter text"

    def get_display_name(self) -> str:
        return "Jak and Daxter"
