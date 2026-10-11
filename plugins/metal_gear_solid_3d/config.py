"""Problem definitions and defaults of the Metal Gear Solid: Snake Eater 3D plugin."""
from plugins.common.config_factory import generate_base_config

PLUGIN_PREFIX = "MGS3D"
DEFAULT_LINES_PER_PAGE = 2   # a subtitle shows two lines

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
