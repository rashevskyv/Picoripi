"""Problem definitions and defaults of the Rhythm Paradise Megamix plugin."""
from plugins.common.config_factory import generate_base_config

PLUGIN_PREFIX = "RPM"
DEFAULT_LINES_PER_PAGE = 2   # the dialogue boxes of the story and the cafe show two lines

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
