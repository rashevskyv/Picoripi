"""Problem definitions and defaults of the Grandia (Dreamcast and PlayStation) plugin."""
from PyQt6.QtGui import QColor

from plugins.common.config_factory import generate_base_config

PLUGIN_PREFIX = "GR2"
# A changed line of a PlayStation script whose growth no later line of the script pays (see psx_text.write_report).
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
            "description": "The PlayStation script is longer than its budget: the text of its other lines gives no "
                           "more bytes. The build refuses this script. Shorten this line or another line of the script.",
        }
    },
)
