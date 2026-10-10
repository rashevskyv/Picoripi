"""Problem definitions and defaults of the Animal Crossing 3DS (New Leaf, Happy Home Designer) plugin."""
from PyQt6.QtGui import QColor

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
    custom_problems={
        "CHOICE_ANSWERS": {
            "name": "Answer lines changed", "color": QColor(255, 80, 0, 160), "priority": 1,
            "description": "The answers after a question or menu tag are one per line; their number must stay "
                           "the same as in the original.",
        },
        "PAGE_LINES": {
            "name": "Too many lines in the window", "color": QColor(255, 0, 160, 110), "priority": 3,
            "description": "This window page has more lines than the game's window holds; "
                           "add {pageBreak} or let Autofix wrap the text.",
        },
    },
)
