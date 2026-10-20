"""Problem definitions and defaults of the Vagrant Story plugin."""
from PyQt6.QtGui import QColor

from plugins.common.config_factory import generate_base_config

PLUGIN_PREFIX = "VGS"
DEFAULT_LINES_PER_PAGE = 4

# The game's own limits: a balloon shows only its lines (BATTLE.PRG, initTextBox) and a name
# or staff-roll line has a fixed place in its file.
PROBLEM_LINES = "VGS_LINES_EXCEEDED"
PROBLEM_BYTES = "VGS_BYTES_EXCEEDED"

custom_problems = {
    PROBLEM_LINES: {
        "name": "More Lines Than The Balloon",
        "color": QColor(255, 80, 80, 140),
        "priority": 1,
        "description": "A dialogue page has more lines than its balloon shows. The game starts a new page "
                       "only at {page}; the extra lines are drawn below the balloon.",
    },
    PROBLEM_BYTES: {
        "name": "Longer Than The Place",
        "color": QColor(255, 80, 80, 140),
        "priority": 1,
        "description": "The text needs more bytes than its place in the game file has (item names: 23 bytes; "
                       "names in program data and staff-roll lines: the length of the English line).",
    },
}

PROBLEM_DEFINITIONS, DEFAULT_DETECTION_SETTINGS, DEFAULT_AUTOFIX_SETTINGS = generate_base_config(
    PLUGIN_PREFIX,
    overrides={
        "autofix_settings": {
            "TAG_WARNING": False,
            "SINGLE_WORD_SUBLINE": False,
            "SINGLE_WORD_SUBLINE_NON_START": False,
        }
    },
    custom_problems=custom_problems,
)
