"""Compatibility shim: implementation lives in ui.components.bfn_preview.*."""
from __future__ import annotations

from ui.components.bfn_preview import (
    BfnEditorAdapter,
    BfnPreviewSideBar,
    BfnPreviewWidget,
    BfnPreviewWindowBar,
    BfnSideButton,
    _looks_like_bfn_core,
    _looks_like_bfn_editor,
)
from ui.components.bfn_preview.helpers import _letter_icon, _preview_icon

__all__ = [
    "BfnPreviewWidget",
    "BfnPreviewWindowBar",
    "BfnPreviewSideBar",
    "BfnSideButton",
    "BfnEditorAdapter",
    "_looks_like_bfn_editor",
    "_looks_like_bfn_core",
    "_preview_icon",
    "_letter_icon",
]
