import re
from typing import List
from PyQt5.QtWidgets import QMainWindow, QMessageBox
from PyQt5.QtCore import QPoint
from utils.logging_utils import log_debug

class LNETSpellcheckLogic:
    def __init__(self, editor):
        self.editor = editor

    def open_dialog_for_selection(self, position_in_widget_coords: QPoint):
        try:
            main_window = self.editor.window()
            if not isinstance(main_window, QMainWindow):
                return

            spellchecker_manager = getattr(main_window, 'spellchecker_manager', None)
            if not spellchecker_manager:
                return

            if not hasattr(main_window, 'edited_text_edit') or not main_window.edited_text_edit:
                return

            edited_text_edit = main_window.edited_text_edit
            selected_lines = self.editor.get_selected_lines()

            line_numbers = []
            if selected_lines:
                text_parts = []
                for line_num in selected_lines:
                    block = edited_text_edit.document().findBlockByNumber(line_num)
                    if block.isValid():
                        text_parts.append(block.text())
                        line_numbers.append(line_num)
                text_to_check = '\n'.join(text_parts)
            else:
                cursor = self.editor.cursorForPosition(position_in_widget_coords)
                line_num = cursor.blockNumber()
                block = edited_text_edit.document().findBlockByNumber(line_num)
                if not block.isValid():
                    return
                text_to_check = block.text()
                line_numbers = [line_num]

            if not text_to_check.strip():
                return

            from dialogs.spellcheck_dialog import SpellcheckDialog
            dialog = SpellcheckDialog(self.editor, text_to_check, spellchecker_manager,
                                     starting_line_number=0, line_numbers=line_numbers,
                                     block_idx=main_window.data_store.current_block_idx)

            if dialog.exec_():
                corrected_text = dialog.get_corrected_text()
                self.apply_corrected_text(corrected_text, line_numbers)

        except Exception as e:
            from utils.logging_utils import log_error
            log_error(f"LNETSpellcheckLogic: Error: {e}")

    def apply_corrected_text(self, corrected_text: str, line_numbers: List[int]):
        main_window = self.editor.window()
        if not isinstance(main_window, QMainWindow) or not hasattr(main_window, 'edited_text_edit'):
            return

        edited_text_edit = main_window.edited_text_edit
        corrected_lines = corrected_text.split('\n')

        from PyQt5.QtGui import QTextCursor
        for i, line_num in enumerate(line_numbers):
            if i < len(corrected_lines):
                block = edited_text_edit.document().findBlockByNumber(line_num)
                if block.isValid():
                    cursor = QTextCursor(block)
                    cursor.select(QTextCursor.BlockUnderCursor)
                    cursor.insertText(corrected_lines[i])
