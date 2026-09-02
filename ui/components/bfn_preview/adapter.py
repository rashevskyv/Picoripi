"""Adapter that exposes a BFN editor window as a BfnCore-like object."""
from __future__ import annotations

class BfnEditorAdapter:
    """Bfn editor adapter implementation."""
    def __init__(self, editor):
        """Initialize a new instance."""
        self.editor = editor

    @property
    def gly1(self):
        """Gly1."""
        return self.editor.metadata.get("GLY1", [])

    @property
    def map1(self):
        """Map1."""
        return self.editor.metadata.get("MAP1", [])

    @property
    def wid1(self):
        """Wid1."""
        return self.editor.metadata.get("WID1", [])

    @property
    def inf1(self):
        """Inf1."""
        return self.editor.metadata.get("INF1", [])

    def get_sheets_qimages(self):
        """Get the sheets qimages."""
        return self.editor.sheet_images

    def layout_text(self, text: str, translation_map = None, line_spacing: int = 10, **kwargs):
        """Layout text."""
        from core.bfn_core import BfnCore
        return BfnCore.layout_text(self, text, translation_map, line_spacing, **kwargs)
