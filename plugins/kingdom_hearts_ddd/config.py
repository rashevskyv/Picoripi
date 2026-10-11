"""Problem definitions and defaults of the Kingdom Hearts 3D: Dream Drop Distance plugin."""
from plugins.common.config_factory import generate_base_config

PLUGIN_PREFIX = "KHDDD"
DEFAULT_LINES_PER_PAGE = 3   # a message window shows up to three lines

PROBLEM_DEFINITIONS, DEFAULT_DETECTION_SETTINGS, DEFAULT_AUTOFIX_SETTINGS = generate_base_config(
    PLUGIN_PREFIX,
    overrides={
        "autofix_settings": {
            "TAG_WARNING": False,
            "SINGLE_WORD_SUBLINE": False,
            "SINGLE_WORD_SUBLINE_NON_START": False,
        }
    },
)
