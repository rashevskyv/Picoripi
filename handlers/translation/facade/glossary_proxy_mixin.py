"""Glossary pass-throughs for TranslationHandler."""
from __future__ import annotations

from typing import Optional

from PyQt6.QtWidgets import QMessageBox

from core.glossary_manager import GlossaryEntry
from core.i18n import tr


class GlossaryProxyMixin:
    """Glossary pass-throughs + append_selection."""

    def initialize_glossary_highlighting(self) -> None:
        """Initialize glossary highlighting."""
        self.glossary_handler.initialize_glossary_highlighting()

    def show_glossary_dialog(self, initial_term: Optional[str] = None) -> None:
        """Show glossary dialog."""
        self.glossary_handler.show_glossary_dialog(initial_term)

    def get_glossary_entry(self, term: str) -> Optional[GlossaryEntry]:
        """Get the glossary entry."""
        return self.glossary_handler.glossary_manager.get_entry(term)

    def add_glossary_entry(self, term: str, context: Optional[str] = None, translation: str = "") -> None:
        """Add glossary entry."""
        self.glossary_handler.add_glossary_entry(term, context, translation)

    def edit_glossary_entry(self, term: str, translation: str = "") -> None:
        """Edit glossary entry."""
        self.glossary_handler.edit_glossary_entry(term, translation=translation)

    def append_selection_to_glossary(self) -> None:
        """Append selection to glossary."""
        preview_edit = self.mw.preview_text_edit
        selected_lines = preview_edit.get_selected_lines()
        if not selected_lines:
            QMessageBox.information(self.mw, tr('Glossary'), tr('No lines selected in the preview.'))
            return

        start_line = min(selected_lines)
        end_line = max(selected_lines)
        
        block_idx = self.mw.data_store.physical_block_idx
        if block_idx == -1:
            return

        selected_lines = []
        for i in range(start_line, end_line + 1):
            line_text = self.glossary_handler._get_original_string(block_idx, i)
            if line_text is not None:
                selected_lines.append(line_text)
        
        if not selected_lines:
            return

        term_to_add = "\n".join(selected_lines)
        self.add_glossary_entry(term_to_add)
