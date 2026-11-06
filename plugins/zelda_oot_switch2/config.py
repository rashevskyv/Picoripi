"""Problem definitions and defaults of the Ocarina of Time (Nintendo Switch 2) plugin."""
from plugins.common.config_factory import generate_base_config

PLUGIN_PREFIX = "ZOS2"
TITLE_ID = "0400486024DEC000"
SOURCE_SUBFOLDER = "romfs/Mals"
# The English slot is the project's source (the Original column); the other Mals archives are reference columns.
TEXT_ARCHIVE_PREFIX = "USen."
# The slot the build writes the translation into: the Russian one, whose ClarimoUDPE fonts hold Є І Ї Ґ.
TARGET_LANGUAGE = "EUru"
REFERENCE_LANGUAGES = ("EUru", "EUen")  # the reference columns, in this order (the AI prompt gets each)
DICTIONARY_PACK = "romfs/Pack/ZsDic.pack.zs"
BUILD_TARGET = "nup"
# What the wizard copies out of the package (path prefixes inside it): the text, its zstd dictionaries, the fonts.
UNPACKED_PREFIXES = ("romfs/Mals/", DICTIONARY_PACK, "romfs/Font2/")

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
