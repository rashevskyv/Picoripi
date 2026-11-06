"""Problem definitions and defaults of the Ocarina of Time (Nintendo Switch 2) plugin."""
from plugins.common.config_factory import generate_base_config

PLUGIN_PREFIX = "ZOS2"
TITLE_ID = "0400486024DEC000"
SOURCE_SUBFOLDER = "romfs/Mals"
# The English slot the project translates; the other Mals archives stay as reference columns.
TEXT_ARCHIVE_PREFIX = "USen."
# What the wizard copies out of the package (path prefixes inside it): the text, its zstd dictionaries, the fonts.
UNPACKED_PREFIXES = ("romfs/Mals/", "romfs/Pack/ZsDic.pack.zs", "romfs/Font2/")

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
