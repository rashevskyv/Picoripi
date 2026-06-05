import os
import json
from PyQt5.QtGui import QColor

CONFIG_DIR = os.path.dirname(os.path.abspath(__file__))
CONFIG_PATH = os.path.join(CONFIG_DIR, 'config.json')

PROBLEM_TAG_WARNING = "ZBMG_TAG_WARNING"
PROBLEM_WIDTH_EXCEEDED = "ZBMG_WIDTH_EXCEEDED"
PROBLEM_SHORT_LINE = "ZBMG_SHORT_LINE"
PROBLEM_EMPTY_ODD_SUBLINE_LOGICAL = "ZBMG_EMPTY_ODD_SUBLINE_LOGICAL"
PROBLEM_EMPTY_ODD_SUBLINE_DISPLAY = "ZBMG_EMPTY_ODD_SUBLINE_DISPLAY"
PROBLEM_SINGLE_WORD_SUBLINE = "ZBMG_SINGLE_WORD_SUBLINE" 
PROBLEM_SINGLE_WORD_SUBLINE_NON_START = "ZBMG_SINGLE_WORD_SUBLINE_NON_START"
PROBLEM_EMPTY_FIRST_LINE_OF_PAGE = "ZBMG_EMPTY_FIRST_LINE_OF_PAGE"
PROBLEM_BAD_SPACING = "ZBMG_BAD_SPACING"
PROBLEM_MISSING_ICON_SPACING = "ZBMG_MISSING_ICON_SPACING"

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
        "description": "Tag count mismatch for {...} or an illegitimate tag."
    },
    PROBLEM_WIDTH_EXCEEDED: {
        "name": "Subline Width Exceeded",
        "color": COLOR_WIDTH_EXCEEDED,
        "priority": PRIORITY_WIDTH_EXCEEDED,
        "description": "The subline is longer than the set width limit."
    },
    PROBLEM_EMPTY_ODD_SUBLINE_LOGICAL: {
        "name": "Empty Odd Logical Subline",
        "color": COLOR_EMPTY_ODD,
        "priority": PRIORITY_EMPTY_ODD,
        "description": "A logical odd-numbered subline (if more than one) is empty or contains only '0' without tags."
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

CONTROL_CODES = []

if os.path.exists(CONFIG_PATH):
    try:
        with open(CONFIG_PATH, 'r', encoding='utf-8') as f:
            config_data = json.load(f)
            # Override any descriptions/names from json if available, but keep color & priority objects
            json_defs = config_data.get("PROBLEM_DEFINITIONS", {})
            for key, val in json_defs.items():
                # Map old keys without ZBMG_ prefix to the ones with prefix
                mapped_key = key
                if key == "PROBLEM_TAG_WARNING":
                    mapped_key = PROBLEM_TAG_WARNING
                elif key == "PROBLEM_WIDTH_EXCEEDED":
                    mapped_key = PROBLEM_WIDTH_EXCEEDED
                
                if mapped_key in PROBLEM_DEFINITIONS:
                    if "name" in val:
                        PROBLEM_DEFINITIONS[mapped_key]["name"] = val["name"]
                    if "description" in val:
                        PROBLEM_DEFINITIONS[mapped_key]["description"] = val["description"]
            CONTROL_CODES = config_data.get("CONTROL_CODES", [])
    except Exception as e:
        from utils.logging_utils import log_error
        log_error(f"Error loading zelda_bmg/config.json: {e}")
