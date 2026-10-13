"""Monster Hunter Portable 3rd HD (PSP, Yakumo port): game rules for the translation of the game's text.

The project file is the dict form of a Yakumo translation file (see ``lang_file.to_json_obj``): block name ->
{key: text}, a key being TABLE:INDEX (id:index in the dialogue block 4289). Each block is one list of strings;
the keys are kept on the instance, so a save writes them back in the same order.
"""
from typing import Any, Dict, List, Optional, Tuple

from plugins.base_game_rules import BaseGameRules
from plugins.common.config_factory import problem_ids

from .config import PROBLEM_DEFINITIONS

ProblemIDs = problem_ids(PROBLEM_DEFINITIONS, "MHP3")


class GameRules(BaseGameRules):
    """Rules for the Yakumo text of Monster Hunter Portable 3rd HD."""

    problem_prefix = "MHP3"
    problem_definitions = PROBLEM_DEFINITIONS
    problem_ids = ProblemIDs
    tag_style = "square"

    def __init__(self, main_window_ref=None):
        """Initialize a new instance."""
        super().__init__(main_window_ref)
        self._keys: List[List[str]] = []

    def get_display_name(self) -> str:
        """Return the display name for this plugin."""
        return "Monster Hunter Portable 3rd HD (PSP, Yakumo)"

    def load_data_from_json_obj(self, json_obj: Any) -> Tuple[List[List[str]], Dict[str, str]]:
        """Blocks of strings from {block: {key: text}}. The keys are remembered for the save."""
        if isinstance(json_obj, list):  # plain blocks of strings: keys are their positions
            blocks = [[str(text) for text in block] for block in json_obj] or [[]]
            self._keys = [[str(i) for i in range(len(block))] for block in blocks]
            return blocks, {str(i): "block%d" % i for i in range(len(blocks))}
        if not isinstance(json_obj, dict):
            raise ValueError("the translation data must be an object of blocks")
        blocks: List[List[str]] = []
        block_names: Dict[str, str] = {}
        keys: List[List[str]] = []
        for index, (name, values) in enumerate(json_obj.items()):
            if not isinstance(values, dict):
                raise ValueError("block %s must hold an object of key -> text" % name)
            keys.append([str(key) for key in values])
            blocks.append([str(value) for value in values.values()])
            block_names[str(index)] = str(name)
        if not blocks:
            blocks, keys, block_names = [[]], [[]], {"0": "main"}
        self._keys = keys
        return blocks, block_names

    def save_data_to_json_obj(self, blocks: List[List[str]], block_names: Optional[Dict[str, str]] = None) -> Any:
        """The dict form again, with the keys of the load in their order."""
        names = block_names or {}
        result: Dict[str, Dict[str, str]] = {}
        for index, block in enumerate(blocks):
            name = names.get(str(index), "main" if index == 0 else "block%d" % index)
            known = self._keys[index] if index < len(self._keys) else []
            keys = known if len(known) == len(block) else [str(i) for i in range(len(block))]
            result[name] = dict(zip(keys, block))
        return result
