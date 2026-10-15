"""Problem definitions and defaults of the Super Mario Galaxy plugin."""
from PyQt6.QtGui import QColor

from plugins.common.config_factory import generate_base_config

PLUGIN_PREFIX = "SMG"
CONTROL_CODES = []
VERSION_WORDING = f"{PLUGIN_PREFIX}_VERSION_WORDING"
CUSTOM_PROBLEMS = {
    "VERSION_WORDING": {
        "name": "Switch translation; Wii English differs", "color": QColor(255, 140, 0, 110), "priority": 2,
        "description": "The Wii and the Switch word this message differently, so it has one row per version. The "
                       "Switch row holds the Switch wording (and an imported Switch translation); the Wii row is "
                       "translated on its own. The Wii and Nebula builds take the Wii row, or the Wii English.",
    },
}

PROBLEM_DEFINITIONS, DEFAULT_DETECTION_SETTINGS, DEFAULT_AUTOFIX_SETTINGS = generate_base_config(
    PLUGIN_PREFIX,
    overrides={"autofix_settings": {"TAG_WARNING": False, "SINGLE_WORD_SUBLINE": False,
                                    "SINGLE_WORD_SUBLINE_NON_START": False}},
    custom_problems=CUSTOM_PROBLEMS,
)
DEFAULT_AUTOFIX_SETTINGS[VERSION_WORDING] = False
