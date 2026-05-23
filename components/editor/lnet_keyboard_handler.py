# --- START OF FILE components/editor/lnet_keyboard_handler.py ---
from PyQt5.QtWidgets import QMainWindow
from PyQt5.QtGui import QKeyEvent, QKeySequence
from PyQt5.QtCore import Qt

from utils.utils import SPACE_DOT_SYMBOL


class LNETKeyboardHandler:
    """Handles keyboard input for LineNumberedTextEdit."""

    def __init__(self, editor):
        self.editor = editor

    def handle_key_press(self, event: QKeyEvent) -> bool:
        """Process key press event. Returns True if the event was consumed."""
        editor = self.editor
        main_window = editor.window()

        # --- Allow Ctrl+S to propagate to parent window actions ---
        if event.modifiers() == Qt.ControlModifier and event.key() == Qt.Key_S:
            from utils.logging_utils import log_debug
            log_debug("LNETKeyboardHandler: Ctrl+S detected. Let it propagate to parent window.")
            return False

        # --- Undo ---
        is_undo = event.matches(QKeySequence.Undo) or \
                  (event.modifiers() == Qt.ControlModifier and event.key() == Qt.Key_Z)
        if is_undo:
            if hasattr(main_window, 'undo_typing_action'):
                main_window.undo_typing_action.trigger()
            return True

        # --- Redo ---
        is_redo = event.matches(QKeySequence.Redo) or \
                  (event.modifiers() == Qt.ControlModifier and event.key() == Qt.Key_Y) or \
                  (event.modifiers() == (Qt.ControlModifier | Qt.ShiftModifier) and event.key() == Qt.Key_Z)
        if is_redo:
            if hasattr(main_window, 'redo_typing_action'):
                main_window.redo_typing_action.trigger()
            return True

        # --- Arrow keys: snap cursor out of icon sequences ---
        is_arrow_key = event.key() in (Qt.Key_Left, Qt.Key_Right)
        if is_arrow_key and event.modifiers() == Qt.NoModifier and not editor.isReadOnly():
            move_right = event.key() == Qt.Key_Right
            if editor._snap_cursor_out_of_icon_sequences(move_right):
                return True

        # --- Space: dot symbol substitution ---
        if not editor.isReadOnly() and event.key() == Qt.Key_Space and \
                getattr(main_window, 'show_multiple_spaces_as_dots', False):
            cursor = editor.textCursor()
            block_text = cursor.block().text()
            pos = cursor.positionInBlock()

            char_before = block_text[pos - 1] if pos > 0 else '\n'
            char_after = block_text[pos] if pos < len(block_text) else '\n'

            if char_before in (' ', SPACE_DOT_SYMBOL) or char_after in (' ', SPACE_DOT_SYMBOL) \
                    or pos == 0 or pos == len(block_text):
                editor.textCursor().insertText(SPACE_DOT_SYMBOL)
            else:
                editor.textCursor().insertText(' ')
            return True

        # --- Enter keys with game rules ---
        if not editor.isReadOnly() and isinstance(main_window, QMainWindow) \
                and main_window.current_game_rules:
            game_rules = main_window.current_game_rules
            is_enter_key = event.key() in (Qt.Key_Return, Qt.Key_Enter)

            if is_enter_key:
                char_to_insert = ''
                modifiers = event.modifiers()

                if modifiers & Qt.ShiftModifier:
                    char_to_insert = game_rules.get_shift_enter_char()
                elif modifiers & Qt.ControlModifier:
                    char_to_insert = game_rules.get_ctrl_enter_char()
                elif modifiers == Qt.NoModifier:
                    char_to_insert = game_rules.get_enter_char()

                if char_to_insert:
                    editor.textCursor().insertText(char_to_insert)
                    return True

        return False
