"""Problem definitions and defaults of the A Link Between Worlds plugin."""
from plugins.common.config_factory import generate_base_config

PLUGIN_PREFIX = "ZLB"
DEFAULT_LINES_PER_PAGE = 3   # the dialogue window shows 3 lines (message project style "default")

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
