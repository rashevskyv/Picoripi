"""Context menu, mass font/width dialogs, and spellcheck helpers."""
from __future__ import annotations

from typing import List

from PyQt6.QtWidgets import QMenu
from PyQt6.QtGui import QTextCursor
from PyQt6.QtCore import QPoint

from components.editor.lnet_dialogs import MassFontDialog, MassWidthDialog


class ContextMixin:
    """Context menu, mass font/width dialogs, and spellcheck helpers."""

    def _replace_word_at_cursor(self, word_cursor: QTextCursor, replacement: str) -> None:
        """Replace the word selected by the given cursor with the replacement text."""
        if word_cursor.hasSelection():
            word_cursor.insertText(replacement)

    def _open_spellcheck_dialog_for_selection(self, position_in_widget_coords: QPoint) -> None:
        """Internal helper to open spellcheck dialog for selection."""
        self.spellcheck_logic.open_dialog_for_selection(position_in_widget_coords)

    def _apply_corrected_text_to_editor(self, corrected_text: str, line_numbers: List[int]) -> None:
        """Internal helper to apply corrected text to editor."""
        self.spellcheck_logic.apply_corrected_text(corrected_text, line_numbers)

    def populateContextMenu(self, menu: QMenu, position_in_widget_coords):
        """Populatecontextmenu."""
        self.context_menu_logic.populate(menu, position_in_widget_coords)

    def handle_mass_set_font(self):
        """Handle mass set font."""
        selected_lines = self.get_selected_lines()
        if not selected_lines: return

        main_window = self.window()
        displayed_indices = getattr(main_window.data_store, 'displayed_string_indices', [])
        if not displayed_indices and hasattr(main_window, 'displayed_string_indices'):
            displayed_indices = main_window.displayed_string_indices

        if displayed_indices:
            real_indices = [displayed_indices[i] for i in selected_lines if i < len(displayed_indices)]
        else:
            real_indices = selected_lines

        dialog = MassFontDialog(main_window)
        if dialog.exec():
            font_file = dialog.get_selected_font()
            main_window.string_settings_handler.apply_font_to_lines(real_indices, font_file)

    def handle_mass_set_width(self):
        """Handle mass set width."""
        selected_lines = self.get_selected_lines()
        if not selected_lines: return

        main_window = self.window()
        displayed_indices = getattr(main_window.data_store, 'displayed_string_indices', [])
        if not displayed_indices and hasattr(main_window, 'displayed_string_indices'):
            displayed_indices = main_window.displayed_string_indices

        if displayed_indices:
            real_indices = [displayed_indices[i] for i in selected_lines if i < len(displayed_indices)]
        else:
            real_indices = selected_lines

        dialog = MassWidthDialog(main_window)
        if dialog.exec():
            if dialog.is_auto_width():
                main_window.string_settings_handler.apply_auto_width_from_original_to_lines(real_indices)
            else:
                width = dialog.get_width()
                main_window.string_settings_handler.apply_width_to_lines(real_indices, width)
