import sys

with open("d:/git/dev/Picoripi/ui/ui_updater.py", "r", encoding="utf-8") as f:
    lines = f.readlines()

method_ranges = [
    (31, 46),
    (77, 93),
    (113, 144),
    (146, 181),
    (183, 197),
    (199, 310),
    (313, 392)
]

output_lines = [
    "from PyQt5.QtCore import Qt, QTimer\n",
    "from PyQt5.QtGui import QColor, QTextCursor\n",
    "from utils.utils import convert_spaces_to_dots_for_display, convert_dots_to_spaces_from_editor, remove_curly_tags, calculate_string_width, remove_all_tags\n",
    "from core.glossary_manager import GlossaryOccurrence\n",
    "from .base_ui_updater import BaseUIUpdater\n\n",
    "class PreviewUpdater(BaseUIUpdater):\n"
]

for start, end in method_ranges:
    for i in range(start - 1, end):
        if i < len(lines):
            output_lines.append(lines[i])
    output_lines.append("\n")

with open("d:/git/dev/Picoripi/ui/updaters/preview_updater.py", "w", encoding="utf-8") as f:
    f.writelines(output_lines)

print("Extracted successfully.")
