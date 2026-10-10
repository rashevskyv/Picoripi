"""Problem definitions and defaults of the Animal Crossing 3DS (New Leaf, Happy Home Designer) plugin."""
from plugins.common.config_factory import generate_base_config

PLUGIN_PREFIX = "AC3DS"
# The EUR games keep five languages in every .umsbt: English, Spanish, French, Italian, German. The English set is
# translated; a European console set to English shows it, so no code patch is needed.
LANGUAGE_SLOT = 0

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
