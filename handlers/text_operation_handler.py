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
from handlers.text_operation import scan_mixin as _scan_mixin
from handlers.text_operation import preview_mixin as _preview_mixin
from handlers.text_operation import edit_mixin as _edit_mixin
from handlers.text_operation import autofix_mixin as _autofix_mixin


class _ShimName:
    """Late-bound name that always reads from this shim module."""

    __slots__ = ("_name",)

    def __init__(self, name: str):
        object.__setattr__(self, "_name", name)

    def _resolve(self):
        import sys
        return getattr(sys.modules[__name__], object.__getattribute__(self, "_name"))

    def __call__(self, *args, **kwargs):
        return self._resolve()(*args, **kwargs)

    def __getattr__(self, item):
        return getattr(self._resolve(), item)

    def __repr__(self):
        return repr(self._resolve())


# Spec D names tests patch on this module.
_scan_mixin.AsyncIssueScanner = _ShimName("AsyncIssueScanner")
_scan_mixin.get_scanner_thread_pool = _ShimName("get_scanner_thread_pool")
_preview_mixin.AsyncIssueScanner = _ShimName("AsyncIssueScanner")
_preview_mixin.get_scanner_thread_pool = _ShimName("get_scanner_thread_pool")
_autofix_mixin.AutofixSelectionDialog = _ShimName("AutofixSelectionDialog")
_autofix_mixin.QProgressDialog = _ShimName("QProgressDialog")
_autofix_mixin.AutofixWorker = _ShimName("AutofixWorker")

# Additional names tests patch on this module and mixins use as globals.
_scan_mixin.QTextCursor = _ShimName("QTextCursor")
_preview_mixin.QTextCursor = _ShimName("QTextCursor")
_autofix_mixin.QTextCursor = _ShimName("QTextCursor")
_preview_mixin.convert_dots_to_spaces_from_editor = _ShimName("convert_dots_to_spaces_from_editor")
_autofix_mixin.convert_dots_to_spaces_from_editor = _ShimName("convert_dots_to_spaces_from_editor")
_edit_mixin.QMessageBox = _ShimName("QMessageBox")
_autofix_mixin.QMessageBox = _ShimName("QMessageBox")
_edit_mixin.calculate_string_width = _ShimName("calculate_string_width")

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
