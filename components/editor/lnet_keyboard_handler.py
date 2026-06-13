from PyQt6.QtWidgets import QMainWindow
from PyQt6.QtGui import QKeyEvent, QKeySequence
from PyQt6.QtCore import Qt

from utils.utils import SPACE_DOT_SYMBOL


class LNETKeyboardHandler:
    """Handles keyboard input for LineNumberedTextEdit."""

    def __init__(self, editor):
        """Initialize a new instance."""
        self.editor = editor

    def handle_key_press(self, event: QKeyEvent) -> bool:
        """Process key press event. Returns True if the event was consumed."""
        editor = self.editor
        main_window = editor.window()

        # --- Allow Ctrl+S to propagate to parent window actions ---
        if event.modifiers() == Qt.KeyboardModifier.ControlModifier and event.key() == Qt.Key.Key_S:
            from utils.logging_utils import log_debug
            log_debug("LNETKeyboardHandler: Ctrl+S detected. Let it propagate to parent window.")
            return False

        # --- Undo ---
        is_undo = event.matches(QKeySequence.StandardKey.Undo) or \
                  (event.modifiers() == Qt.KeyboardModifier.ControlModifier and event.key() == Qt.Key.Key_Z)
        if is_undo:
            if hasattr(main_window, 'undo_typing_action'):
                main_window.undo_typing_action.trigger()
            return True

        # --- Redo ---
        is_redo = event.matches(QKeySequence.StandardKey.Redo) or \
                  (event.modifiers() == Qt.KeyboardModifier.ControlModifier and event.key() == Qt.Key.Key_Y) or \
                  (event.modifiers() == (Qt.KeyboardModifier.ControlModifier | Qt.KeyboardModifier.ShiftModifier) and event.key() == Qt.Key.Key_Z)
        if is_redo:
            if hasattr(main_window, 'redo_typing_action'):
                main_window.redo_typing_action.trigger()
            return True

        # --- Arrow keys: snap cursor out of icon sequences ---
        is_arrow_key = event.key() in (Qt.Key.Key_Left, Qt.Key.Key_Right)
        if is_arrow_key and event.modifiers() == Qt.KeyboardModifier.NoModifier and not editor.isReadOnly():
            move_right = event.key() == Qt.Key.Key_Right
            if editor._snap_cursor_out_of_icon_sequences(move_right):
                return True

        # --- Space: dot symbol substitution ---
        if not editor.isReadOnly() and event.key() == Qt.Key.Key_Space and \
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
            is_enter_key = event.key() in (Qt.Key.Key_Return, Qt.Key.Key_Enter)

            if is_enter_key:
                char_to_insert = ''
                modifiers = event.modifiers()

                if modifiers & Qt.KeyboardModifier.ShiftModifier:
                    char_to_insert = game_rules.get_shift_enter_char()
                elif modifiers & Qt.KeyboardModifier.ControlModifier:
                    char_to_insert = game_rules.get_ctrl_enter_char()
                elif modifiers == Qt.KeyboardModifier.NoModifier:
                    char_to_insert = game_rules.get_enter_char()

                if char_to_insert:
                    editor.textCursor().insertText(char_to_insert)
                    return True

        return False
