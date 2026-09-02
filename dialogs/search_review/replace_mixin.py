"""Skip/replace, jump, and block/string navigation."""
from __future__ import annotations

from PyQt6.QtWidgets import QApplication
from PyQt6.QtCore import Qt, QTimer

from dialogs.search.search_utils import adjust_replacement_case


class ReplaceMixin:
    """Skip/replace, jump, and block/string navigation."""

    def _navigate_to_block_and_string(self, block_idx: int, string_idx: int):
        if block_idx is None or string_idx is None:
            return

        main_window = self._find_main_window()
        if not main_window:
            return

        if main_window.data_store.current_block_idx != block_idx:
            from PyQt6.QtWidgets import QTreeWidgetItemIterator
            iterator = QTreeWidgetItemIterator(main_window.block_list_widget)
            found_item = None
            while iterator.value():
                item = iterator.value()
                if item.data(0, Qt.ItemDataRole.UserRole) == block_idx and item.data(0, Qt.ItemDataRole.UserRole + 10) is None:
                    found_item = item
                    break
                iterator += 1

            if found_item:
                main_window.block_list_widget.setCurrentItem(found_item)
                QTimer.singleShot(80, lambda: main_window.list_selection_handler.select_string_by_absolute_index(string_idx))
        else:
            main_window.list_selection_handler.select_string_by_absolute_index(string_idx)

        def apply_focus():
            if hasattr(main_window, 'edited_text_edit') and main_window.edited_text_edit:
                main_window.edited_text_edit.setFocus(Qt.FocusReason.OtherFocusReason)
            elif hasattr(main_window, 'original_text_edit') and main_window.original_text_edit:
                main_window.original_text_edit.setFocus(Qt.FocusReason.OtherFocusReason)
            main_window.raise_()
            main_window.activateWindow()

        QTimer.singleShot(120, apply_focus)

    def jump_to_item_from_list(self, item):
        modifiers = QApplication.keyboardModifiers()
        if bool(modifiers & (Qt.KeyboardModifier.ControlModifier | Qt.KeyboardModifier.ShiftModifier)):
            return

        clicked_index = self.matches_list.row(item)
        if clicked_index != self.current_item_index:
            self.clear_current_item_highlight()
            self.current_item_index = clicked_index
            self.show_current_item(from_click=True)

            if clicked_index < len(self.items_to_review):
                _, _, _, line_idx = self.items_to_review[clicked_index]
                if self.line_numbers and line_idx < len(self.line_numbers):
                    b_idx = self.block_indices[line_idx] if (hasattr(self, 'block_indices') and self.block_indices and line_idx < len(self.block_indices)) else self.block_idx
                    self._navigate_to_block_and_string(b_idx, self.line_numbers[line_idx])

    def skip_match(self):
        self.go_to_next_item()

    def replace_match(self):
        if self.current_item_index >= len(self.items_to_review):
            return

        replacement = self.replace_input.text()
        start, end, word, line_idx = self.items_to_review[self.current_item_index]

        match_case = self.match_case_replace_checkbox.isChecked()
        adjusted_replacement = adjust_replacement_case(word, replacement, match_case)

        self.current_text = self.current_text[:start] + adjusted_replacement + self.current_text[end:]
        self.text_edit.setPlainText(self.current_text)
        self._apply_zebra_striping()

        length_diff = len(adjusted_replacement) - len(word)
        self.items_to_review.pop(self.current_item_index)
        for i in range(self.current_item_index, len(self.items_to_review)):
            s, e, w, l = self.items_to_review[i]
            self.items_to_review[i] = (s + length_diff, e + length_diff, w, l)

        self.pre_highlight_all_matches()
        self.show_current_item()

    def replace_all_matches(self):
        if not self.items_to_review:
            return

        replacement = self.replace_input.text()
        match_case = self.match_case_replace_checkbox.isChecked()

        # Sort items in reverse order to replace without shifting offsets of previous ones
        sorted_items = sorted(self.items_to_review, key=lambda x: x[0], reverse=True)

        temp_text = self.current_text
        for start, end, word, _ in sorted_items:
            adjusted_replacement = adjust_replacement_case(word, replacement, match_case)
            temp_text = temp_text[:start] + adjusted_replacement + temp_text[end:]

        self.current_text = temp_text
        self.text_edit.setPlainText(self.current_text)
        self.items_to_review.clear()

        self.pre_highlight_all_matches()
        self.show_current_item()

    def _on_item_double_click(self, item):
        index = self.matches_list.row(item)
        if index < len(self.items_to_review):
            _, _, _, line_idx = self.items_to_review[index]
            if self.line_numbers and line_idx < len(self.line_numbers):
                b_idx = self.block_indices[line_idx] if (hasattr(self, 'block_indices') and self.block_indices and line_idx < len(self.block_indices)) else self.block_idx
                self._navigate_to_block_and_string(b_idx, self.line_numbers[line_idx])

    def _on_text_double_click(self, event):
        cursor = self.text_edit.cursorForPosition(event.pos())
        block_number = cursor.blockNumber()

        if hasattr(self.text_edit, 'custom_line_numbers') and self.text_edit.custom_line_numbers:
            if block_number < len(self.text_edit.custom_line_numbers):
                string_number = self.text_edit.custom_line_numbers[block_number]
                target_block_number = block_number
                if string_number is None:
                    for i in range(block_number - 1, -1, -1):
                        if i < len(self.text_edit.custom_line_numbers):
                            if self.text_edit.custom_line_numbers[i] is not None:
                                string_number = self.text_edit.custom_line_numbers[i]
                                target_block_number = i
                                break
                if string_number is not None:
                    b_idx = self.block_indices[target_block_number] if (hasattr(self, 'block_indices') and self.block_indices and target_block_number < len(self.block_indices)) else self.block_idx
                    self._navigate_to_block_and_string(b_idx, string_number - 1)

        from PyQt6.QtWidgets import QPlainTextEdit
        QPlainTextEdit.mouseDoubleClickEvent(self.text_edit, event)
