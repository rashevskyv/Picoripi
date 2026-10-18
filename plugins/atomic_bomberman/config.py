"""Problem definitions and defaults of the Atomic Bomberman plugin."""
from PyQt6.QtGui import QColor

from plugins.common.config_factory import generate_base_config

PLUGIN_PREFIX = "ABM"

PROBLEM_PLACEHOLDER = "ABM_PLACEHOLDER_MISMATCH"
PROBLEM_HINT_ROW_WIDTH = "ABM_HINT_ROW_TOO_WIDE"

custom_problems = {
    PROBLEM_PLACEHOLDER: {
        "name": "Placeholder Mismatch",
        "color": QColor(255, 80, 80, 140),
        "priority": 1,
        "description": "The translation does not keep the same {0}, {1}, ... placeholders as the English text.",
    },
    PROBLEM_HINT_ROW_WIDTH: {
        "name": "Hint Row Too Wide",
        "color": QColor(255, 165, 0, 140),
        "priority": 3,
        "description": "The bottom hint row of a menu is wider than the free set's screen (see HINT_ROW_LIMIT_PX in rules.py).",
    },
}

PROBLEM_DEFINITIONS, DEFAULT_DETECTION_SETTINGS, DEFAULT_AUTOFIX_SETTINGS = generate_base_config(
    PLUGIN_PREFIX,
    overrides={"autofix_settings": {}},
    custom_problems=custom_problems,
)
