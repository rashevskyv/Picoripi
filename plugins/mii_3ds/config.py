"""Problem definitions and defaults of the Tomodachi Life / Miitopia plugin."""
from plugins.common.config_factory import generate_base_config

PLUGIN_PREFIX = "MII"

PROBLEM_DEFINITIONS, DEFAULT_DETECTION_SETTINGS, DEFAULT_AUTOFIX_SETTINGS = generate_base_config(
    PLUGIN_PREFIX,
    overrides={
        # The text is drawn with the console's shared font: no width model, so no width problems.
        "detection_settings": {"WIDTH_EXCEEDED": False, "SHORT_LINE": False},
        "autofix_settings": {
            "TAG_WARNING": False,
            "WIDTH_EXCEEDED": False,
            "SHORT_LINE": False,
            "SINGLE_WORD_SUBLINE": False,
            "SINGLE_WORD_SUBLINE_NON_START": False,
        }
    },
)
