"""Compatibility shim: implementation lives in handlers.translation.glossary.*."""
from __future__ import annotations

# Re-exported so tests can patch symbols on this module path.
from PyQt6.QtWidgets import QMessageBox, QProgressDialog, QDialog
from PyQt6.QtGui import QAction

from core.glossary_manager import GlossaryManager
from handlers.translation.glossary_prompt_manager import GlossaryPromptManager
from handlers.translation.glossary_occurrence_updater import GlossaryOccurrenceUpdater
from components.glossary_dialog import GlossaryDialog
from components.glossary_edit_dialog import GlossaryEditDialog
from core.speaker_alias_merge import load_speaker_aliases

from handlers.translation.glossary import (
    GlossaryHandler,
    CategorySelectionDialog,
    GlossaryOccurrenceWorker,
)
from handlers.translation.glossary import handler as _handler
from handlers.translation.glossary import dialog_mixin as _dialog_mixin
from handlers.translation.glossary import edit_mixin as _edit_mixin
from handlers.translation.glossary import crud_mixin as _crud_mixin
from handlers.translation.glossary import classify_mixin as _classify_mixin
from handlers.translation.glossary import speaker_mixin as _speaker_mixin


def _ShimName(name: str):
    """Late-bound name that always reads from this shim module.

    Returned object is a type so ``isinstance(x, shim)`` and constructor
    patches both work (needed for GlossaryEditDialog).
    """

    def _resolve():
        import sys
        return getattr(sys.modules[__name__], name)

    class _ShimMeta(type):
        def __instancecheck__(cls, instance):
            return isinstance(instance, _resolve())

        def __subclasscheck__(cls, subclass):
            return issubclass(subclass, _resolve())

        def __call__(cls, *args, **kwargs):
            return _resolve()(*args, **kwargs)

        def __getattr__(cls, item):
            return getattr(_resolve(), item)

        def __repr__(cls):
            return repr(_resolve())

    class Shim(metaclass=_ShimMeta):
        pass

    return Shim


# Tests patch these on handlers.translation.glossary_handler; mixins use them as globals.
_handler.GlossaryManager = _ShimName("GlossaryManager")
_handler.GlossaryPromptManager = _ShimName("GlossaryPromptManager")
_handler.GlossaryOccurrenceUpdater = _ShimName("GlossaryOccurrenceUpdater")
_dialog_mixin.QAction = _ShimName("QAction")
_dialog_mixin.QProgressDialog = _ShimName("QProgressDialog")
_dialog_mixin.GlossaryOccurrenceWorker = _ShimName("GlossaryOccurrenceWorker")
_dialog_mixin.GlossaryDialog = _ShimName("GlossaryDialog")
_dialog_mixin.QMessageBox = _ShimName("QMessageBox")
_edit_mixin.GlossaryEditDialog = _ShimName("GlossaryEditDialog")
_edit_mixin.QMessageBox = _ShimName("QMessageBox")
_crud_mixin.QMessageBox = _ShimName("QMessageBox")
_classify_mixin.QMessageBox = _ShimName("QMessageBox")
_speaker_mixin.load_speaker_aliases = _ShimName("load_speaker_aliases")

__all__ = [
    "GlossaryHandler",
    "CategorySelectionDialog",
    "GlossaryOccurrenceWorker",
    "GlossaryManager",
    "GlossaryPromptManager",
    "GlossaryOccurrenceUpdater",
    "GlossaryDialog",
    "GlossaryEditDialog",
    "QMessageBox",
    "QProgressDialog",
    "QDialog",
    "QAction",
    "load_speaker_aliases",
]
