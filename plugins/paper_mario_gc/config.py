"""Problem definitions and defaults of the Paper Mario: The Thousand-Year Door plugin."""
from plugins.common.config_factory import generate_base_config

PLUGIN_PREFIX = "PMT"
DEFAULT_LINES_PER_PAGE = 3

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
