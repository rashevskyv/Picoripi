"""Dialog for viewing glossary entries and navigating to occurrences.

Compatibility shim: implementation lives in components.glossary.*.
"""
from __future__ import annotations

# Re-exported so tests can patch components.glossary_dialog.QMessageBox.question
# (class-attribute patches apply to the shared Qt class object).
from PyQt6.QtWidgets import QMessageBox

from components.glossary import (
    GlossaryDialog,
    _DetailPane,
    _GlossaryTermTable,
    _MULTI_VARIANT_BRUSH,
    _NEEDS_REVIEW_BRUSH,
    _PROVISIONAL_FOREGROUND,
    _RichTextItemDelegate,
    _UNREVIEWED_BRUSH,
    _VariantItemDelegate,
)

__all__ = [
    "GlossaryDialog",
    "QMessageBox",
    "_DetailPane",
    "_GlossaryTermTable",
    "_MULTI_VARIANT_BRUSH",
    "_NEEDS_REVIEW_BRUSH",
    "_PROVISIONAL_FOREGROUND",
    "_RichTextItemDelegate",
    "_UNREVIEWED_BRUSH",
    "_VariantItemDelegate",
]
