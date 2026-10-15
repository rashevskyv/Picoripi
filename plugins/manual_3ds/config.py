"""Problem definitions and defaults of the 3DS electronic manual plugin.

The generic text problems (tags, sublines, short lines) do not apply: the manual is wrapped by the viewer's pane
model, which plugins/manual_3ds/layout.py reproduces. Only the problems below are detected, and none is autofixed.
"""
from PyQt6.QtGui import QColor

from plugins.common.config_factory import generate_base_config

PLUGIN_PREFIX = "M3D"

CUSTOM_PROBLEMS = {
    "LINES": {
        "name": "Too many lines", "color": QColor(255, 0, 0, 120), "priority": 1,
        "description": "The text needs more lines than its paragraph has on the console page.",
    },
    "WORD": {
        "name": "Word does not fit its box", "color": QColor(255, 0, 0, 120), "priority": 1,
        "description": "One word is wider than the pane box it has to fit (small text). Reword the sentence.",
    },
    "WIDTH": {
        "name": "Line past the card edge", "color": QColor(255, 80, 0, 110), "priority": 2,
        "description": "A line's ink runs past the right edge of the page card on the console (onto the scroll track).",
    },
    "WRAP": {
        "name": "Line breaks on the console", "color": QColor(255, 80, 0, 110), "priority": 2,
        "description": "The console breaks this stored line inside its pane: the line is wider than its pane box, "
                       "so its end lands on the next line, over the text there.",
    },
    "BESIDE": {
        "name": "Line runs into a picture or frame", "color": QColor(255, 80, 0, 110), "priority": 2,
        "description": "A line runs into a picture or a box frame beside it on the console page. Shorten the line or "
                       "the paragraph.",
    },
    "CELL": {
        "name": "Line leaves its cell", "color": QColor(255, 80, 0, 110), "priority": 2,
        "description": "A line starts inside a filled cell (a table's grey label cell) and runs out of it on the "
                       "console page: white text vanishes on the white page there. Shorten the line.",
    },
    "OVERLAP": {
        "name": "Lines overlap", "color": QColor(255, 80, 0, 110), "priority": 2,
        "description": "The ink of this line meets the ink of a line of another paragraph on the console page (a "
                       "table label under the next cell's text, a caption running into the next caption).",
    },
    "COVERED": {
        "name": "Line painted over", "color": QColor(255, 80, 0, 110), "priority": 2,
        "description": "A picture or a filled box drawn after this line paints over its ink on the console page.",
    },
    "ICON": {
        "name": "Button glyph mismatch", "color": QColor(255, 0, 0, 120), "priority": 1,
        "description": "A button glyph of the Russian original is missing or repeated in the translation.",
    },
    "PANES": {
        "name": "Out of panes", "color": QColor(255, 0, 0, 120), "priority": 1,
        "description": "The text needs more text panes of one style (plain text or a highlighted phrase) than the "
                       "original paragraph has on the console.",
    },
    "MARKUP": {
        "name": "Markup changed", "color": QColor(255, 165, 0, 150), "priority": 1,
        "description": "The icon and style markers ({i0}, {s1|...}, {br}) differ from the Russian original.",
    },
    "GLYPH": {
        "name": "Missing glyph", "color": QColor(200, 0, 200, 110), "priority": 1,
        "description": "A character has no glyph in the console font.",
    },
    "STYLE": {
        "name": "Text style", "color": QColor(120, 120, 255, 120), "priority": 6,
        "description": "A spelling or word-form check: Russian letters, mixed scripts, spacing, the page reference form.",
    },
}

PROBLEM_DEFINITIONS, _DETECTION, _AUTOFIX = generate_base_config(
    PLUGIN_PREFIX, custom_problems=CUSTOM_PROBLEMS
)
CUSTOM_IDS = tuple(f"{PLUGIN_PREFIX}_{key}" for key in CUSTOM_PROBLEMS)
# Only the plugin's own problems are detected; the generic ones are switched off.
DEFAULT_DETECTION_SETTINGS = {key: key in CUSTOM_IDS for key in _DETECTION}
DEFAULT_AUTOFIX_SETTINGS = {key: False for key in _AUTOFIX}
