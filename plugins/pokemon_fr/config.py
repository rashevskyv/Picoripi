from PyQt6.QtGui import QColor

P_NEWLINE_MARKER = "▶"
L_NEWLINE_MARKER = "▷"
P_VISUAL_EDITOR_MARKER = "▶"
L_VISUAL_EDITOR_MARKER = "▷"

PROBLEM_WIDTH_EXCEEDED = "PKFR_WIDTH_EXCEEDED"
PROBLEM_SHORT_LINE = "PKFR_SHORT_LINE"
PROBLEM_EMPTY_SUBLINE = "PKFR_EMPTY_SUBLINE"
PROBLEM_SINGLE_WORD_SUBLINE = "PKFR_SINGLE_WORD_SUBLINE"
PROBLEM_SINGLE_WORD_SUBLINE_NON_START = "PKFR_SINGLE_WORD_SUBLINE_NON_START"
PROBLEM_TAG_WARNING = "PKFR_TAG_WARNING"
PROBLEM_BAD_SPACING = "PKFR_BAD_SPACING"
PROBLEM_MISSING_ICON_SPACING = "PKFR_MISSING_ICON_SPACING"

PRIORITY_WIDTH_EXCEEDED = 1
PRIORITY_TAG_WARNING = 2
PRIORITY_EMPTY_SUBLINE = 3
PRIORITY_SINGLE_WORD_SUBLINE = 4
PRIORITY_SINGLE_WORD_SUBLINE_NON_START = 3
PRIORITY_SHORT_LINE = 5

PROBLEM_DEFINITIONS = {
    PROBLEM_WIDTH_EXCEEDED: {
        "name": "Width Exceeded",
        "color": QColor(255, 0, 0, 100),
        "priority": PRIORITY_WIDTH_EXCEEDED,
        "description": "The subline is wider than the set limit."
    },
    PROBLEM_SHORT_LINE: {
        "name": "Short Line",
        "color": QColor(0, 200, 0, 100),
        "priority": PRIORITY_SHORT_LINE,
        "description": "The subline does not end with a punctuation mark and has enough space for the first word of the next subline."
    },
    PROBLEM_EMPTY_SUBLINE: {
        "name": "Empty Subline",
        "color": QColor(255, 165, 0, 180),
        "priority": PRIORITY_EMPTY_SUBLINE,
        "description": "An empty subline created by two consecutive newline tags is present."
    },
    PROBLEM_SINGLE_WORD_SUBLINE: {
        "name": "Single Word Subline",
        "color": QColor(0, 0, 255, 120),
        "priority": PRIORITY_SINGLE_WORD_SUBLINE,
        "description": "The subline consists of only one word (and possible punctuation)."
    },
    PROBLEM_SINGLE_WORD_SUBLINE_NON_START: {
        "name": "Single Word Subline (Non-Start)",
        "color": QColor(139, 69, 19, 120),
        "priority": PRIORITY_SINGLE_WORD_SUBLINE_NON_START,
        "description": "The subline consists of only one word, but not at the start of a page/dialogue window."
    },
    PROBLEM_TAG_WARNING: {
        "name": "Tag Warning",
        "color": QColor(255, 255, 0, 80),
        "priority": PRIORITY_TAG_WARNING,
        "description": "A syntactically incorrect or unknown tag was found in the text."
    },
    PROBLEM_BAD_SPACING: {
        "name": "Bad Spacing",
        "color": QColor(255, 255, 0, 80),
        "priority": PRIORITY_TAG_WARNING,
        "description": "Double spaces or line starting with a space (ignoring tags)."
    },
    PROBLEM_MISSING_ICON_SPACING: {
        "name": "Missing Icon Spacing",
        "color": QColor(173, 216, 230, 150),
        "priority": 8,
        "description": "Missing space before or after a visible tag (button or width-having tag)."
    }
}

DEFAULT_DETECTION_SETTINGS = {
    PROBLEM_WIDTH_EXCEEDED: True,
    PROBLEM_SHORT_LINE: True,
    PROBLEM_EMPTY_SUBLINE: True,
    PROBLEM_SINGLE_WORD_SUBLINE: True,
    PROBLEM_SINGLE_WORD_SUBLINE_NON_START: True,
    PROBLEM_TAG_WARNING: True,
    PROBLEM_BAD_SPACING: True,
    PROBLEM_MISSING_ICON_SPACING: True
}

DEFAULT_AUTOFIX_SETTINGS = {
    PROBLEM_WIDTH_EXCEEDED: True,
    PROBLEM_SHORT_LINE: True,
    PROBLEM_EMPTY_SUBLINE: True,
    PROBLEM_SINGLE_WORD_SUBLINE: False,
    PROBLEM_SINGLE_WORD_SUBLINE_NON_START: False,
    PROBLEM_TAG_WARNING: False,
    PROBLEM_BAD_SPACING: True,
    PROBLEM_MISSING_ICON_SPACING: True
}

DEFAULT_TAG_MAPPINGS_POKEMON_FR = {
    "{PLAYER}": "{PLAYER}",
    "{RIVAL}": "{RIVAL}",
    "{DPAD_UPDOWN}": "{DPAD_UPDOWN}",
    "{A_BUTTON}": "{A_BUTTON}",
    "{B_BUTTON}": "{B_BUTTON}",
    "{DPAD_LEFTRIGHT}": "{DPAD_LEFTRIGHT}",
    "{PLUS}": "{PLUS}",
    "{START_BUTTON}": "{START_BUTTON}",
    "{NO}": "{NO}",
    "{LV_2}": "{LV_2}",
    "{ID}": "{ID}",
    "{PP}": "{PP}",
    "{ESCAPE 0x03}": "{ESCAPE 0x03}",
    "{ID}{NO}": "{ID}{NO}",
    "{PKMN}": "{PKMN}"
}

CONTROL_CODES = ["\\p", "\\l", "\\n"]