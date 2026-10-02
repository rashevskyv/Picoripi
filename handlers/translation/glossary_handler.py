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
