"""Problem definitions and defaults of the Lunar: Silver Star Story Remastered (Switch) plugin."""
from plugins.common.config_factory import generate_base_config

PLUGIN_PREFIX = "LUNR"
DEFAULT_LINES_PER_PAGE = 3
TITLE_ID = "0100DCD01E9EE000"        # the base game; the update (0100DCD01E9EE800) carries the patched data.cpk
UPDATE_TITLE_ID = "0100DCD01E9EE800"

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
