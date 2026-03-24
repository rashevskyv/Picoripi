import sys
import os

with open("d:/git/dev/Picoripi/ui/ui_updater.py", "r", encoding="utf-8") as f:
    lines = f.readlines()

method_ranges = [
    (19, 73),
    (75, 127),
    (129, 146),
    (165, 204),
    (207, 236),
    (238, 270),
    (272, 365),
    (367, 488),
    (490, 542),
    (573, 574),
    (577, 594)
]

output_lines = [
    "from PyQt5.QtCore import Qt, QTimer\n",
    "from PyQt5.QtGui import QIcon\n",
    "from PyQt5.QtWidgets import QTreeWidgetItem, QTreeWidgetItemIterator, QStyle\n",
    "from utils.logging_utils import log_info, log_warning\n",
    "from pathlib import Path\n",
    "from .base_ui_updater import BaseUIUpdater\n\n",
    "class BlockListUpdater(BaseUIUpdater):\n"
]

for start, end in method_ranges:
    for i in range(start - 1, end):
        if i < len(lines):
            output_lines.append(lines[i])
    output_lines.append("\n")

with open("d:/git/dev/Picoripi/ui/updaters/block_list_updater.py", "w", encoding="utf-8") as f:
    f.writelines(output_lines)

print("Extracted successfully.")
