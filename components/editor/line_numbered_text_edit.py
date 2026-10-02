"""Compatibility shim: implementation lives in components.editor.line_edit.*."""
from __future__ import annotations

from components.editor.lnet_dialogs import MassFontDialog, MassWidthDialog
from components.editor.line_edit import LineNumberedTextEdit


__all__ = [
    "LineNumberedTextEdit",
    "MassFontDialog",
    "MassWidthDialog",
]
