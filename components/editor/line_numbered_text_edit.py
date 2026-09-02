"""Compatibility shim: implementation lives in components.editor.line_edit.*."""
from __future__ import annotations

from components.editor.lnet_dialogs import MassFontDialog, MassWidthDialog
from components.editor.line_edit import LineNumberedTextEdit
from components.editor.line_edit import context_mixin as _context_mixin


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


_context_mixin.MassFontDialog = _ShimName("MassFontDialog")
_context_mixin.MassWidthDialog = _ShimName("MassWidthDialog")

__all__ = [
    "LineNumberedTextEdit",
    "MassFontDialog",
    "MassWidthDialog",
]
