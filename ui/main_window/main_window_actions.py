"""Compatibility shim: implementation lives in ui.main_window.actions.*."""
from __future__ import annotations

from PyQt6.QtWidgets import QMessageBox, QProgressDialog, QDialog, QApplication
from dialogs.tag_alias_dialog import TagAliasDialog, AliasUpdateWorker

from ui.main_window.actions import MainWindowActions


# QMessageBox.question is a class-attribute patch on the shared Qt class; still late-bind
# so whole-class replacements would work the same as project_action_handler.

__all__ = [
    "MainWindowActions",
    "TagAliasDialog",
    "AliasUpdateWorker",
    "QMessageBox",
    "QProgressDialog",
    "QDialog",
    "QApplication",
]
