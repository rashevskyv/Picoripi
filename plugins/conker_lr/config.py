"""Problem definitions and defaults of the Conker: Live & Reloaded plugin."""
from PyQt6.QtGui import QColor

from plugins.common.config_factory import generate_base_config

PLUGIN_PREFIX = "CLR"

PROBLEM_TAG_WARNING = f"{PLUGIN_PREFIX}_TAG_WARNING"
PROBLEM_WIDTH_EXCEEDED = f"{PLUGIN_PREFIX}_WIDTH_EXCEEDED"
PROBLEM_SHORT_LINE = f"{PLUGIN_PREFIX}_SHORT_LINE"
PROBLEM_EMPTY_ODD_SUBLINE_DISPLAY = f"{PLUGIN_PREFIX}_EMPTY_ODD_SUBLINE_DISPLAY"
PROBLEM_SINGLE_WORD_SUBLINE = f"{PLUGIN_PREFIX}_SINGLE_WORD_SUBLINE"
PROBLEM_SINGLE_WORD_SUBLINE_NON_START = f"{PLUGIN_PREFIX}_SINGLE_WORD_SUBLINE_NON_START"
PROBLEM_EMPTY_FIRST_LINE_OF_PAGE = f"{PLUGIN_PREFIX}_EMPTY_FIRST_LINE_OF_PAGE"
PROBLEM_BAD_SPACING = f"{PLUGIN_PREFIX}_BAD_SPACING"
PROBLEM_MISSING_ICON_SPACING = f"{PLUGIN_PREFIX}_MISSING_ICON_SPACING"
PROBLEM_BROKEN_ICON_HYPHEN = f"{PLUGIN_PREFIX}_BROKEN_ICON_HYPHEN"

CONTROL_CODES = []
DEFAULT_LINES_PER_PAGE = 4

PROBLEM_DEFINITIONS, DEFAULT_DETECTION_SETTINGS, DEFAULT_AUTOFIX_SETTINGS = generate_base_config(
    PLUGIN_PREFIX,
    overrides={
        "autofix_settings": {
            "TAG_WARNING": False,
            "SINGLE_WORD_SUBLINE": False,
            "SINGLE_WORD_SUBLINE_NON_START": False,
            "STRING_LIMIT": False,
            "LINE_LIMIT": False,
            "BUBBLE_LINES": False,
        }
    },
    custom_problems={
        "STRING_LIMIT": {
            "name": "Text too long for one string", "color": QColor(255, 0, 0, 120), "priority": 3,
            "description": "This line has more than 2047 characters, the most one displayed string holds. "
                           "Shorten it; the game does not show the rest.",
        },
        "LINE_LIMIT": {
            "name": "Cutscene line over 511 characters", "color": QColor(255, 140, 0, 140), "priority": 4,
            "description": "A cutscene line (all its paragraphs together) should stay under 511 characters, "
                           "the size the game's line buffer is tested for.",
        },
        "BUBBLE_LINES": {
            "name": "Bubble over 4 lines", "color": QColor(255, 255, 0, 110), "priority": 5,
            "description": "A paragraph wraps to more than 4 lines at 20 characters per line. The bubble stays "
                           "4 lines tall and the text scrolls; shorten the paragraph or split it with {PARAGRAPH}.",
        },
    },
)

