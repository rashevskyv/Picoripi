"""Problem definitions and defaults of the Skies of Arcadia Legends (GameCube) plugin."""
from PyQt6.QtGui import QColor

from plugins.common.config_factory import generate_base_config

PLUGIN_PREFIX = "SOA"
# A fixed-size script's text longer than the source segment it replaces. The game freezes when such a script grows.
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
            "description": "The text is longer than the page it replaces in this script. The game freezes when "
                           "this script grows, so the build keeps the source text. Shorten the text.",
        }
    },
)
