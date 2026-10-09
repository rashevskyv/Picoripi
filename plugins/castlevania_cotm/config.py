"""Problem definitions and defaults of the Castlevania: Circle of the Moon (GBA) plugin."""
from plugins.common.config_factory import generate_base_config

PLUGIN_PREFIX = "CVM"

PROBLEM_DEFINITIONS, DEFAULT_DETECTION_SETTINGS, DEFAULT_AUTOFIX_SETTINGS = generate_base_config(
    PLUGIN_PREFIX,
    overrides={"autofix_settings": {name: False for name in (
        "TAG_WARNING", "WIDTH_EXCEEDED", "SHORT_LINE", "EMPTY_ODD_SUBLINE_DISPLAY", "SINGLE_WORD_SUBLINE",
        "SINGLE_WORD_SUBLINE_NON_START", "EMPTY_FIRST_LINE_OF_PAGE", "BAD_SPACING", "MISSING_ICON_SPACING",
        "BROKEN_ICON_HYPHEN")}},
)
