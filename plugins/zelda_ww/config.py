from PyQt5.QtGui import QColor

PROBLEM_TAG_WARNING = "ZWW_TAG_WARNING"
PROBLEM_WIDTH_EXCEEDED = "ZWW_WIDTH_EXCEEDED"
PROBLEM_SHORT_LINE = "ZWW_SHORT_LINE"
PROBLEM_EMPTY_ODD_SUBLINE_DISPLAY = "ZWW_EMPTY_ODD_SUBLINE_DISPLAY"
PROBLEM_SINGLE_WORD_SUBLINE = "ZWW_SINGLE_WORD_SUBLINE" 
PROBLEM_SINGLE_WORD_SUBLINE_NON_START = "ZWW_SINGLE_WORD_SUBLINE_NON_START"
PROBLEM_EMPTY_FIRST_LINE_OF_PAGE = "ZWW_EMPTY_FIRST_LINE_OF_PAGE"
PROBLEM_BAD_SPACING = "ZWW_BAD_SPACING"
PROBLEM_MISSING_ICON_SPACING = "ZWW_MISSING_ICON_SPACING"

PRIORITY_TAG_CRITICAL = 1 
PRIORITY_TAG_WARNING = 2
PRIORITY_WIDTH_EXCEEDED = 3
PRIORITY_EMPTY_ODD = 4
PRIORITY_EMPTY_FIRST_LINE = 5
PRIORITY_SINGLE_WORD_SUBLINE = 6 
PRIORITY_SINGLE_WORD_SUBLINE_NON_START = 5
PRIORITY_SHORT_LINE = 7
PRIORITY_DEFAULT = 99

COLOR_CRITICAL_TAG = QColor(255, 192, 203, 100)
COLOR_WARNING_TAG = QColor(255, 255, 0, 80) 
COLOR_WIDTH_EXCEEDED = QColor(255, 0, 0, 100)
COLOR_EMPTY_ODD = QColor(255, 165, 0, 180)
COLOR_SHORT_LINE = QColor(0, 200, 0, 100)
COLOR_SINGLE_WORD_SUBLINE = QColor(0, 0, 255, 120) 
COLOR_SINGLE_WORD_SUBLINE_NON_START = QColor(139, 69, 19, 120)
COLOR_EMPTY_FIRST_LINE = QColor(255, 105, 180, 100) # HotPink

PROBLEM_DEFINITIONS = {
    PROBLEM_TAG_WARNING: {
        "name": "Tag Warning",
        "color": COLOR_WARNING_TAG, 
        "priority": PRIORITY_TAG_WARNING,
        "description": "Tag count mismatch for [...] or an illegitimate tag."
    },
    PROBLEM_WIDTH_EXCEEDED: {
        "name": "Subline Width Exceeded",
        "color": COLOR_WIDTH_EXCEEDED,
        "priority": PRIORITY_WIDTH_EXCEEDED,
        "description": "The subline is longer than the set width limit."
    },
    PROBLEM_EMPTY_ODD_SUBLINE_DISPLAY: {
        "name": "Empty Odd Display Subline",
        "color": COLOR_EMPTY_ODD,
        "priority": PRIORITY_EMPTY_ODD,
        "description": "A displayed odd-numbered subline (QTextBlock) is empty or contains '0' (if not the only subline)."
    },
    PROBLEM_SHORT_LINE: {
        "name": "Short Subline",
        "color": COLOR_SHORT_LINE,
        "priority": PRIORITY_SHORT_LINE,
        "description": "The subline does not end with a punctuation mark and has enough space for the first word of the next subline."
    },
    PROBLEM_SINGLE_WORD_SUBLINE: { 
        "name": "Single Word Subline",
        "color": COLOR_SINGLE_WORD_SUBLINE,
        "priority": PRIORITY_SINGLE_WORD_SUBLINE,
        "description": "The subline consists of only one word (and possible punctuation)."
    },
    PROBLEM_SINGLE_WORD_SUBLINE_NON_START: {
        "name": "Single Word Subline (Non-Start)",
        "color": COLOR_SINGLE_WORD_SUBLINE_NON_START,
        "priority": PRIORITY_SINGLE_WORD_SUBLINE_NON_START,
        "description": "The subline consists of only one word, but not at the start of a page/dialogue window."
    },
    PROBLEM_EMPTY_FIRST_LINE_OF_PAGE: {
        "name": "Empty First Line of Page",
        "color": COLOR_EMPTY_FIRST_LINE,
        "priority": PRIORITY_EMPTY_FIRST_LINE,
        "description": "The first line of a 4-line page is empty, but subsequent lines on the page are not."
    },
    PROBLEM_BAD_SPACING: {
        "name": "Bad Spacing",
        "color": COLOR_WARNING_TAG,
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
    PROBLEM_TAG_WARNING: True,
    PROBLEM_WIDTH_EXCEEDED: True,
    PROBLEM_SHORT_LINE: True,
    PROBLEM_EMPTY_ODD_SUBLINE_DISPLAY: True,
    PROBLEM_SINGLE_WORD_SUBLINE: True,
    PROBLEM_SINGLE_WORD_SUBLINE_NON_START: True,
    PROBLEM_EMPTY_FIRST_LINE_OF_PAGE: True,
    PROBLEM_BAD_SPACING: True,
    PROBLEM_MISSING_ICON_SPACING: True
}

DEFAULT_AUTOFIX_SETTINGS = {
    PROBLEM_TAG_WARNING: False,
    PROBLEM_WIDTH_EXCEEDED: True,
    PROBLEM_SHORT_LINE: True,
    PROBLEM_EMPTY_ODD_SUBLINE_DISPLAY: True,
    PROBLEM_SINGLE_WORD_SUBLINE: False,
    PROBLEM_SINGLE_WORD_SUBLINE_NON_START: False,
    PROBLEM_EMPTY_FIRST_LINE_OF_PAGE: True,
    PROBLEM_BAD_SPACING: True,
    PROBLEM_MISSING_ICON_SPACING: True
}