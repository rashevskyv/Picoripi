"""Problem definitions and defaults of the Senran Kagura Burst plugin."""
from plugins.common.config_factory import generate_base_config

PLUGIN_PREFIX = "SKB"
DEFAULT_LINES_PER_PAGE = 3   # a page of the story ends with the page marker; most pages have two or three lines

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
