"""Problem definitions and defaults of the Conker's Bad Fur Day (N64) plugin."""
from PyQt6.QtGui import QColor

from plugins.common.config_factory import generate_base_config

PLUGIN_PREFIX = "CBFD"

PROBLEM_LENGTH = "CBFD_LENGTH_OVER"
PROBLEM_CHARACTER = "CBFD_CHARACTER_NOT_IN_TEXT"

custom_problems = {
    PROBLEM_LENGTH: {
        "name": "Longer Than The Original",
        "color": QColor(255, 80, 80, 140),
        "priority": 1,
        "description": "The translation takes more bytes than the original text. The game's table has no room for it.",
    },
    PROBLEM_CHARACTER: {
        "name": "Character Not In Text Form",
        "color": QColor(255, 80, 80, 140),
        "priority": 1,
        "description": "The text has a character the game's text form cannot carry: plain ASCII, newline and [@hh] tags only.",
    },
}

PROBLEM_DEFINITIONS, DEFAULT_DETECTION_SETTINGS, DEFAULT_AUTOFIX_SETTINGS = generate_base_config(
    PLUGIN_PREFIX,
    overrides={"autofix_settings": {}},
    custom_problems=custom_problems,
)
