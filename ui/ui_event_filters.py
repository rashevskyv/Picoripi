# --- START OF FILE ui/ui_event_filters.py ---
from PyQt5.QtCore import QObject, QEvent, Qt
from PyQt5.QtWidgets import QApplication, QWidget
from utils.logging_utils import log_debug

class TextEditEventFilter(QObject):
    def __init__(self, main_window):
        super().__init__(main_window)
        self.mw = main_window

    def eventFilter(self, obj, event):
        if event.type() == QEvent.KeyPress:
            is_ctrl_pressed = bool(event.modifiers() & Qt.ControlModifier)
            is_alt_pressed = bool(event.modifiers() & Qt.AltModifier)
            is_shift_pressed = bool(event.modifiers() & Qt.ShiftModifier)

            # --- Ctrl+PageDown/PageUp OR Alt+Shift+Up/Down: Navigate between blocks ---
            if is_ctrl_pressed and not is_alt_pressed and not is_shift_pressed:
                if event.key() == Qt.Key_PageDown:
                    log_debug("TextEditEventFilter: Ctrl+PageDown -> navigate_between_blocks(True)")
                    self.mw.list_selection_handler.navigate_between_blocks(True)
                    return True
                elif event.key() == Qt.Key_PageUp:
                    log_debug("TextEditEventFilter: Ctrl+PageUp -> navigate_between_blocks(False)")
                    self.mw.list_selection_handler.navigate_between_blocks(False)
                    return True

            # --- Alt+Shift+Left/Right: Navigate between folders;
            #     Alt+Shift+Up/Down: Navigate between blocks (fallback, WM_HOTKEY is primary) ---
            if is_alt_pressed and is_shift_pressed and not is_ctrl_pressed:
                if event.key() == Qt.Key_Up:
                    log_debug("TextEditEventFilter: Alt+Shift+Up -> navigate_between_blocks(False)")
                    self.mw.list_selection_handler.navigate_between_blocks(False)
                    return True
                elif event.key() == Qt.Key_Down:
                    log_debug("TextEditEventFilter: Alt+Shift+Down -> navigate_between_blocks(True)")
                    self.mw.list_selection_handler.navigate_between_blocks(True)
                    return True
                elif event.key() == Qt.Key_Left:
                    log_debug("TextEditEventFilter: Alt+Shift+Left -> navigate_between_folders(False)")
                    self.mw.list_selection_handler.navigate_between_folders(False)
                    return True
                elif event.key() == Qt.Key_Right:
                    log_debug("TextEditEventFilter: Alt+Shift+Right -> navigate_between_folders(True)")
                    self.mw.list_selection_handler.navigate_between_folders(True)
                    return True
            
            if obj is self.mw.preview_text_edit:
                is_multi_selection_active = len(self.mw.preview_text_edit.get_selected_lines()) > 1
                
                if not is_ctrl_pressed and not is_alt_pressed and not is_shift_pressed and not is_multi_selection_active:
                    if event.key() == Qt.Key_Up:
                        current_row = self.mw.data_store.current_string_idx
                        if current_row > 0:
                            self.mw.list_selection_handler.string_selected_from_preview(current_row - 1)
                        return True
                    elif event.key() == Qt.Key_Down:
                        current_row = self.mw.data_store.current_string_idx
                        if self.mw.data_store.current_block_idx != -1 and current_row < len(self.mw.data_store.data[self.mw.data_store.current_block_idx]) - 1:
                            self.mw.list_selection_handler.string_selected_from_preview(current_row + 1)
                        return True

            if is_alt_pressed and not is_ctrl_pressed and not is_shift_pressed:
                if event.key() == Qt.Key_Up:
                    current_row = self.mw.data_store.current_string_idx
                    if current_row > 0:
                        self.mw.list_selection_handler.string_selected_from_preview(current_row - 1)
                    return True
                elif event.key() == Qt.Key_Down:
                    current_row = self.mw.data_store.current_string_idx
                    if self.mw.data_store.current_block_idx != -1 and self.mw.data_store.data and current_row < len(self.mw.data_store.data[self.mw.data_store.current_block_idx]) - 1:
                        self.mw.list_selection_handler.string_selected_from_preview(current_row + 1)
                    return True

            if is_ctrl_pressed and not is_alt_pressed:
                if event.key() == Qt.Key_Up:
                    log_debug(f"TextEditEventFilter: Ctrl+Up on {obj.objectName()}. Calling navigation.")
                    if hasattr(self.mw, 'list_selection_handler'):
                        self.mw.list_selection_handler.navigate_to_problem_string(direction_down=False)
                    return True
                elif event.key() == Qt.Key_Down:
                    log_debug(f"TextEditEventFilter: Ctrl+Down on {obj.objectName()}. Calling navigation.")
                    if hasattr(self.mw, 'list_selection_handler'):
                        self.mw.list_selection_handler.navigate_to_problem_string(direction_down=True)
                    return True
                    
        if event.type() == QEvent.ToolTip:
            name = obj.objectName() if hasattr(obj, 'objectName') else str(obj)
            log_debug(f"EventFilter: ToolTip event on {name}")
            
        return super().eventFilter(obj, event)


class MainWindowEventFilter(QObject):
    def __init__(self, main_window):
        super().__init__(main_window)
        self.mw = main_window

    def eventFilter(self, obj, event):
        if event.type() == QEvent.KeyPress:
            if event.modifiers() & Qt.AltModifier and event.modifiers() & Qt.ShiftModifier:
                if event.key() == Qt.Key_Up:
                    log_debug("AppFilter: Alt+Shift+Up -> navigate_between_blocks(False)")
                    self.mw.list_selection_handler.navigate_between_blocks(False)
                    return True
                elif event.key() == Qt.Key_Down:
                    log_debug("AppFilter: Alt+Shift+Down -> navigate_between_blocks(True)")
                    self.mw.list_selection_handler.navigate_between_blocks(True)
                    return True
                elif event.key() == Qt.Key_Left:
                    log_debug("AppFilter: Alt+Shift+Left -> navigate_between_folders(False)")
                    self.mw.list_selection_handler.navigate_between_folders(False)
                    return True
                elif event.key() == Qt.Key_Right:
                    log_debug("AppFilter: Alt+Shift+Right -> navigate_between_folders(True)")
                    self.mw.list_selection_handler.navigate_between_folders(True)
                    return True

            # F3 shortcuts - only handle when main window is active
            if isinstance(obj, QWidget) and obj.window() is self.mw:
                if event.key() == Qt.Key_F3:
                    if event.modifiers() & Qt.ShiftModifier:
                        log_debug("AppFilter: Shift+F3 pressed - Find Previous")
                        self.mw.helper.execute_find_previous_shortcut()
                        return True
                    else:
                        log_debug("AppFilter: F3 pressed - Find Next")
                        self.mw.helper.execute_find_next_shortcut()
                        return True

        return super().eventFilter(obj, event)
