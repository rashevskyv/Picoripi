from PyQt6.QtWidgets import QMainWindow
from PyQt6.QtCore import QPoint, Qt

class LNETSpellcheckLogic:
    """L n e t spellcheck logic implementation."""
    def __init__(self, editor):
        """Initialize a new instance."""
        self.editor = editor

    def open_dialog_for_selection(self, position_in_widget_coords: QPoint):
        """Open dialog for selection."""
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
            
            # Check if spellcheck dialog is already active
            if getattr(main_window, 'active_spellcheck_dialog', None) is not None:
                main_window.active_spellcheck_dialog.raise_()
                main_window.active_spellcheck_dialog.activateWindow()
                return

            dialog = SpellcheckDialog(self.editor, text_to_check, spellchecker_manager,
                                     starting_line_number=0, line_numbers=line_numbers,
                                     block_idx=main_window.data_store.current_block_idx)

            main_window.active_spellcheck_dialog = dialog
            dialog.setAttribute(Qt.WidgetAttribute.WA_DeleteOnClose)
            dialog.destroyed.connect(lambda: setattr(main_window, 'active_spellcheck_dialog', None))
            dialog.show()

        except Exception as e:
            from utils.logging_utils import log_error
            log_error(f"LNETSpellcheckLogic: Error: {e}")
