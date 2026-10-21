"""Problem definitions and defaults of the Castlevania: Symphony of the Night plugin."""
from PyQt6.QtGui import QColor

from plugins.common.config_factory import generate_base_config

PLUGIN_PREFIX = "SOTN"
DEFAULT_LINES_PER_PAGE = 4
# A prologue caption line wider than the panel right of its x offset (12 px a letter, 8 px a space).
PROBLEM_CAPTION_WIDTH = f"{PLUGIN_PREFIX}_CAPTION_WIDTH"
PRIORITY_CAPTION_WIDTH = 2

PROBLEM_DEFINITIONS, DEFAULT_DETECTION_SETTINGS, DEFAULT_AUTOFIX_SETTINGS = generate_base_config(
    PLUGIN_PREFIX,
    overrides={
        "autofix_settings": {
            "TAG_WARNING": False,
            "SINGLE_WORD_SUBLINE": False,
            "SINGLE_WORD_SUBLINE_NON_START": False,
        },
        "priorities": {"CAPTION_WIDTH": PRIORITY_CAPTION_WIDTH},
    },
    custom_problems={
        "CAPTION_WIDTH": {
            "name": "Caption line too wide",
            "color": QColor(220, 0, 80, 120),
            "priority": PRIORITY_CAPTION_WIDTH,
            "description": "A prologue caption line is wider than the panel right of its x offset: 12 px a letter, "
                           "8 px a space, 512 px the panel, 4 px a halfword of x. Shorten the line.",
        }
    },
)
