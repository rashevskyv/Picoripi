"""Problem definitions and defaults of the Stella Glow plugin."""
from plugins.common.config_factory import generate_base_config

PLUGIN_PREFIX = "SGL"
DEFAULT_LINES_PER_PAGE = 2   # a message window shows two lines; the flow starts the next page itself

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
