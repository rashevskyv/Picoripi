"""Problem definitions and defaults of the Skies of Arcadia Legends (GameCube) plugin."""
from PyQt6.QtGui import QColor

from plugins.common.config_factory import generate_base_config

PLUGIN_PREFIX = "SOA"
# A changed line of a script whose text is over the script's budget (the text of all its lines, see scripts.py).
PROBLEM_BYTE_BUDGET = f"{PLUGIN_PREFIX}_BYTE_BUDGET"
PRIORITY_BYTE_BUDGET = 1

PROBLEM_DEFINITIONS, DEFAULT_DETECTION_SETTINGS, DEFAULT_AUTOFIX_SETTINGS = generate_base_config(
    PLUGIN_PREFIX,
    overrides={
        "autofix_settings": {
            "TAG_WARNING": False,
            "SINGLE_WORD_SUBLINE": False,
            "SINGLE_WORD_SUBLINE_NON_START": False,
        },
        "priorities": {"BYTE_BUDGET": PRIORITY_BYTE_BUDGET},
    },
    custom_problems={
        "BYTE_BUDGET": {
            "name": "Byte budget exceeded",
            "color": QColor(220, 0, 80, 120),
            "priority": PRIORITY_BYTE_BUDGET,
            "description": "The script's text is longer than its budget: the source text of all its lines, padded "
                           "to steps of 4 bytes. The build refuses this script. Shorten this line or another line "
                           "of the script.",
        }
    },
)
