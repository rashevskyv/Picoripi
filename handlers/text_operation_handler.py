"""Compatibility shim: implementation lives in handlers.text_operation.*."""
from __future__ import annotations

# Re-exported for callers/tests that patch symbols on this module path.
from PyQt6.QtWidgets import QMessageBox, QProgressDialog
from PyQt6.QtGui import QTextCursor

from ui.autofix_selection_dialog import AutofixSelectionDialog
from utils.utils import convert_dots_to_spaces_from_editor, calculate_string_width
from handlers.async_issue_scanner import AsyncIssueScanner, get_scanner_thread_pool
from handlers.autofix_worker import AutofixWorker
from handlers.text_operation import TextOperationHandler, PREVIEW_UPDATE_DELAY


# Spec D names tests patch on this module.

# Additional names tests patch on this module and mixins use as globals.

__all__ = [
    "TextOperationHandler",
    "PREVIEW_UPDATE_DELAY",
    "AsyncIssueScanner",
    "get_scanner_thread_pool",
    "AutofixSelectionDialog",
    "QProgressDialog",
    "AutofixWorker",
    "QMessageBox",
    "QTextCursor",
    "convert_dots_to_spaces_from_editor",
    "calculate_string_width",
]
