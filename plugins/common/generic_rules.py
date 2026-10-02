"""Rules for no game in particular: the standard checks and fixes with ``{curly}`` tags.

Used where the application needs working rules and has no real plugin to ask
(code driven without a main window). It used to borrow the Minish Cap plugin
for this, so whatever ran there was tested against one game's behaviour.
"""
from plugins.base_game_rules import BaseGameRules
from plugins.common.config_factory import generate_base_config, problem_ids

PROBLEM_DEFINITIONS, DEFAULT_DETECTION_SETTINGS, DEFAULT_AUTOFIX_SETTINGS = generate_base_config("GEN")


class GenericRules(BaseGameRules):
    """The standard problem checks and autofix, wired by the base class."""

    problem_prefix = "GEN"
    problem_definitions = PROBLEM_DEFINITIONS
    problem_ids = problem_ids(PROBLEM_DEFINITIONS, "GEN", without=("BROKEN_ICON_HYPHEN",))
    tag_style = "curly"

    def get_display_name(self) -> str:
        return "Generic rules"
