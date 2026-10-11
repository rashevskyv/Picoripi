"""Problem definitions and defaults of the Paper Mario: Sticker Star plugin."""
from plugins.common.config_factory import generate_base_config

PLUGIN_PREFIX = "PMSS"
DEFAULT_LINES_PER_PAGE = 3   # a dialogue page shows three lines (most pages have one to three)

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
