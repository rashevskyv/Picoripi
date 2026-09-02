"""Compatibility shim: implementation lives in ui.main_window.actions.*."""
from __future__ import annotations

from PyQt6.QtWidgets import QMessageBox, QProgressDialog, QDialog, QApplication
from dialogs.tag_alias_dialog import TagAliasDialog, AliasUpdateWorker

from ui.main_window.actions import MainWindowActions
from ui.main_window.actions import settings_mixin as _settings_mixin
from ui.main_window.actions import tools_mixin as _tools_mixin
from ui.main_window.actions import tag_alias_mixin as _tag_alias_mixin


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


# Tests patch these on ui.main_window.main_window_actions; mixins use them as globals.
_tag_alias_mixin.TagAliasDialog = _ShimName("TagAliasDialog")
_tag_alias_mixin.AliasUpdateWorker = _ShimName("AliasUpdateWorker")
_tag_alias_mixin.QProgressDialog = _ShimName("QProgressDialog")
# QMessageBox.question is a class-attribute patch on the shared Qt class; still late-bind
# so whole-class replacements would work the same as project_action_handler.
_tag_alias_mixin.QMessageBox = _ShimName("QMessageBox")
_settings_mixin.QMessageBox = _ShimName("QMessageBox")
_tools_mixin.QMessageBox = _ShimName("QMessageBox")

__all__ = [
    "MainWindowActions",
    "TagAliasDialog",
    "AliasUpdateWorker",
    "QMessageBox",
    "QProgressDialog",
    "QDialog",
    "QApplication",
]
