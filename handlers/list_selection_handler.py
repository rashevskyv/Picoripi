"""Compatibility shim: implementation lives in handlers.list_selection.*."""
from __future__ import annotations

# Re-exported for callers/tests that patch symbols on this module path.
from PyQt6.QtWidgets import QTreeWidgetItemIterator
from PyQt6.QtGui import QTextCursor

from handlers.list_selection import ListSelectionHandler
from handlers.list_selection import physical_selection_mixin as _physical_selection_mixin
from handlers.list_selection import navigation_mixin as _navigation_mixin


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


_physical_selection_mixin.QTextCursor = _ShimName("QTextCursor")
_physical_selection_mixin.QTreeWidgetItemIterator = _ShimName("QTreeWidgetItemIterator")
_navigation_mixin.QTreeWidgetItemIterator = _ShimName("QTreeWidgetItemIterator")

__all__ = [
    "ListSelectionHandler",
    "QTreeWidgetItemIterator",
    "QTextCursor",
]
