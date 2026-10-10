"""Problem definitions and defaults of the Castlevania: Mirror of Fate plugin."""
from plugins.common.config_factory import generate_base_config

PLUGIN_PREFIX = "CVMOF"
DEFAULT_LINES_PER_PAGE = 4   # a help box shows up to four lines (| breaks)

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
