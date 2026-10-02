"""Script Markup Studio — convert a raw walkthrough into the standardized
Picoripi script format ([Chapter:]/[Location:]/{Action:}/SPEAKER:) that the
MemePalace builders and the .md/.txt parsers consume.

Concept: ONE colour-coded view of the raw script. The colour of each line is the
live result (green = speech, amber = action, blue = location, grey = dropped), so
there is no second pane to keep in sync. The fully rendered standardized script
is available on demand via "Preview result…" and written by "Export".

All heavy logic lives in core/script_markup (Qt-free, tested); this is the shell.

Compatibility shim: implementation lives in ui.script_markup.*.
"""
from __future__ import annotations

# Re-exported for callers/tests that patch symbols on this module path.
# Qt class attribute patches (QFileDialog.getSaveFileName, QMessageBox.question,
# QInputDialog.getText, QMenu.exec) apply to the shared class object globally.
# time.monotonic patches via this module's `time` also hit the stdlib module.
import time

from PyQt6.QtWidgets import (
    QFileDialog,
    QMessageBox,
    QInputDialog,
    QMenu,
)
from core.script_markup import (
    line_styles_for_marks,
    build_hierarchy_auto_markup_messages,
)
from core.script_markup.hierarchy_ai_jobs import (
    HierarchyAIWorker as _HierarchyAIWorker,
)

from ui.script_markup.studio_dialog import ScriptMarkupStudioDialog
from ui.script_markup.constants import (
    _HELP_HTML,
    _RAW_HIERARCHY_GUTTER_WIDTH,
)
from ui.script_markup.widgets import _ClassificationHighlighter



__all__ = [
    "ScriptMarkupStudioDialog",
    "_ClassificationHighlighter",
    "_RAW_HIERARCHY_GUTTER_WIDTH",
    "_HELP_HTML",
    "_HierarchyAIWorker",
    "QFileDialog",
    "QMessageBox",
    "QInputDialog",
    "QMenu",
    "line_styles_for_marks",
    "build_hierarchy_auto_markup_messages",
    "time",
]
