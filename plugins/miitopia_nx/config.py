"""Problem definitions and defaults of the Miitopia (Switch) plugin (the 3DS plugin's, with its own prefix)."""
from plugins.common.config_factory import generate_base_config

PLUGIN_PREFIX = "MIINX"

PROBLEM_DEFINITIONS, DEFAULT_DETECTION_SETTINGS, DEFAULT_AUTOFIX_SETTINGS = generate_base_config(
    PLUGIN_PREFIX,
    overrides={
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
