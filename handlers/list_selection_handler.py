"""Compatibility shim: implementation lives in handlers.list_selection.*."""
from __future__ import annotations

# Re-exported for callers/tests that patch symbols on this module path.
from PyQt6.QtWidgets import QTreeWidgetItemIterator
from PyQt6.QtGui import QTextCursor

from handlers.list_selection import ListSelectionHandler


__all__ = [
    "ListSelectionHandler",
    "QTreeWidgetItemIterator",
    "QTextCursor",
]
