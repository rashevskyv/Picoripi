import os
import json
from PyQt6.QtGui import QColor
from plugins.common.config_factory import generate_base_config

CONFIG_DIR = os.path.dirname(os.path.abspath(__file__))
CONFIG_PATH = os.path.join(CONFIG_DIR, 'config.json')

PROBLEM_TAG_WARNING = "ZBMG_TAG_WARNING"
PROBLEM_WIDTH_EXCEEDED = "ZBMG_WIDTH_EXCEEDED"
PROBLEM_SHORT_LINE = "ZBMG_SHORT_LINE"
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
COLOR_EMPTY_FIRST_LINE = QColor(255, 105, 180, 100)

custom_problems = {
    "EMPTY_FIRST_LINE_OF_PAGE": {
        "name": "Empty First Line of Page",
        "color": COLOR_EMPTY_FIRST_LINE,
        "priority": PRIORITY_EMPTY_FIRST_LINE,
        "description": "The first line of a 4-line page is empty, but subsequent lines on the page are not."
    }
}

overrides = {
    "priorities": {
        "TAG_WARNING": PRIORITY_TAG_WARNING,
        "WIDTH_EXCEEDED": PRIORITY_WIDTH_EXCEEDED,
        "EMPTY_ODD_SUBLINE_DISPLAY": PRIORITY_EMPTY_ODD,
        "SINGLE_WORD_SUBLINE": PRIORITY_SINGLE_WORD_SUBLINE,
        "SINGLE_WORD_SUBLINE_NON_START": PRIORITY_SINGLE_WORD_SUBLINE_NON_START,
        "SHORT_LINE": PRIORITY_SHORT_LINE,
    },
    "colors": {
        "TAG_WARNING": COLOR_WARNING_TAG,
        "WIDTH_EXCEEDED": COLOR_WIDTH_EXCEEDED,
        "EMPTY_ODD_SUBLINE_DISPLAY": COLOR_EMPTY_ODD,
        "SHORT_LINE": COLOR_SHORT_LINE,
        "SINGLE_WORD_SUBLINE": COLOR_SINGLE_WORD_SUBLINE,
        "SINGLE_WORD_SUBLINE_NON_START": COLOR_SINGLE_WORD_SUBLINE_NON_START,
    }
}

PROBLEM_DEFINITIONS, DEFAULT_DETECTION_SETTINGS, DEFAULT_AUTOFIX_SETTINGS = generate_base_config(
    "ZBMG", overrides=overrides, custom_problems=custom_problems
)

CONTROL_CODES = []

if os.path.exists(CONFIG_PATH):
    try:
        with open(CONFIG_PATH, 'r', encoding='utf-8') as f:
            config_data = json.load(f)
            # Override any descriptions/names from json if available, but keep color & priority objects
            json_defs = config_data.get("PROBLEM_DEFINITIONS", {})
            for key, val in json_defs.items():
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
