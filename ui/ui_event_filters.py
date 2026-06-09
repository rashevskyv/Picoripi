from PyQt6.QtCore import QObject, QEvent, Qt
from PyQt6.QtWidgets import QApplication, QWidget
from utils.logging_utils import log_debug

class TextEditEventFilter(QObject):
    def __init__(self, main_window):
        parent = main_window if isinstance(main_window, QObject) else None
        super().__init__(parent)
        self.mw = main_window

    def eventFilter(self, obj, event):
        if event.type() == QEvent.Type.KeyPress:
            is_ctrl_pressed = bool(event.modifiers() & Qt.KeyboardModifier.ControlModifier)
            is_alt_pressed = bool(event.modifiers() & Qt.KeyboardModifier.AltModifier)
            is_shift_pressed = bool(event.modifiers() & Qt.KeyboardModifier.ShiftModifier)

            # --- Ctrl+PageDown/PageUp OR Alt+Shift+Up/Down: Navigate between blocks ---
            if is_ctrl_pressed and not is_alt_pressed and not is_shift_pressed:
                if event.key() == Qt.Key.Key_PageDown:
                    log_debug("TextEditEventFilter: Ctrl+PageDown -> navigate_between_blocks(True)")
                    self.mw.list_selection_handler.navigate_between_blocks(True)
                    return True
                elif event.key() == Qt.Key.Key_PageUp:
                    log_debug("TextEditEventFilter: Ctrl+PageUp -> navigate_between_blocks(False)")
                    self.mw.list_selection_handler.navigate_between_blocks(False)
                    return True

            # --- Alt+Shift+Left/Right: Navigate between folders;
            #     Alt+Shift+Up/Down: Navigate between blocks (fallback, WM_HOTKEY is primary) ---
            if is_alt_pressed and is_shift_pressed and not is_ctrl_pressed:
                if event.key() == Qt.Key.Key_Up:
                    log_debug("TextEditEventFilter: Alt+Shift+Up -> navigate_between_blocks(False)")
                    self.mw.list_selection_handler.navigate_between_blocks(False)
                    return True
                elif event.key() == Qt.Key.Key_Down:
                    log_debug("TextEditEventFilter: Alt+Shift+Down -> navigate_between_blocks(True)")
                    self.mw.list_selection_handler.navigate_between_blocks(True)
                    return True
                elif event.key() == Qt.Key.Key_Left:
                    log_debug("TextEditEventFilter: Alt+Shift+Left -> navigate_between_folders(False)")
                    self.mw.list_selection_handler.navigate_between_folders(False)
                    return True
                elif event.key() == Qt.Key.Key_Right:
                    log_debug("TextEditEventFilter: Alt+Shift+Right -> navigate_between_folders(True)")
                    self.mw.list_selection_handler.navigate_between_folders(True)
                    return True
            
            if obj is self.mw.preview_text_edit:
                is_multi_selection_active = len(self.mw.preview_text_edit.get_selected_lines()) > 1
                
                if not is_ctrl_pressed and not is_alt_pressed and not is_shift_pressed and not is_multi_selection_active:
                    if event.key() == Qt.Key.Key_Up:
                        current_row = self.mw.data_store.current_string_idx
                        if current_row > 0:
                            self.mw.list_selection_handler.string_selected_from_preview(current_row - 1)
                        return True
                    elif event.key() == Qt.Key.Key_Down:
                        current_row = self.mw.data_store.current_string_idx
                        if self.mw.data_store.current_block_idx != -1 and current_row < len(self.mw.data_store.data[self.mw.data_store.current_block_idx]) - 1:
                            self.mw.list_selection_handler.string_selected_from_preview(current_row + 1)
                        return True
            
            if is_alt_pressed and not is_ctrl_pressed and not is_shift_pressed:
                if event.key() in (Qt.Key.Key_Up, Qt.Key.Key_Down):
                    displayed_indices = self.mw.list_selection_handler._get_displayed_indices()
                    if not displayed_indices:
                        return True
                        
                    is_chapter = getattr(self.mw.data_store, 'current_chapter_id', None) is not None or (displayed_indices and isinstance(displayed_indices[0], tuple))
                    current_preview_idx = -1
                    if is_chapter:
                        target = (self.mw.data_store.current_block_idx, self.mw.data_store.current_string_idx)
                        if target in displayed_indices:
                            current_preview_idx = displayed_indices.index(target)
                    else:
                        target = self.mw.data_store.current_string_idx
                        if target in displayed_indices:
                            current_preview_idx = displayed_indices.index(target)
                            
                    from utils.utils import get_line_words_and_visible_tags
                    
                    def is_line_empty(preview_idx):
                        if not (0 <= preview_idx < len(displayed_indices)):
                            return True
                        val = displayed_indices[preview_idx]
                        if val == -1:
                            return True
                        if isinstance(val, tuple) and len(val) == 2:
                            b_idx, s_idx = val
                        else:
                            b_idx = self.mw.data_store.current_block_idx
                            s_idx = val
                        if b_idx < 0 or s_idx < 0:
                            return True
                        txt, _ = self.mw.data_processor.get_current_string_text(b_idx, s_idx)
                        if not txt:
                            return True
                        words = get_line_words_and_visible_tags(txt, self.mw)
                        return len(words) == 0
                        
                    if event.key() == Qt.Key.Key_Up:
                        start = current_preview_idx if current_preview_idx != -1 else len(displayed_indices)
                        target_idx = -1
                        for i in range(start - 1, -1, -1):
                            if not is_line_empty(i):
                                target_idx = i
                                break
                        if target_idx != -1:
                            self.mw.list_selection_handler.string_selected_from_preview(target_idx)
                        return True
                        
                    elif event.key() == Qt.Key.Key_Down:
                        start = current_preview_idx
                        target_idx = -1
                        for i in range(start + 1, len(displayed_indices)):
                            if not is_line_empty(i):
                                target_idx = i
                                break
                        if target_idx != -1:
                            self.mw.list_selection_handler.string_selected_from_preview(target_idx)
                        return True
                        
            if is_ctrl_pressed and not is_alt_pressed:
                if event.key() == Qt.Key.Key_Up:
                    log_debug(f"TextEditEventFilter: Ctrl+Up on {obj.objectName()}. Calling navigation.")
                    if hasattr(self.mw, 'list_selection_handler'):
                        self.mw.list_selection_handler.navigate_to_problem_string(direction_down=False)
                    return True
                elif event.key() == Qt.Key.Key_Down:
                    log_debug(f"TextEditEventFilter: Ctrl+Down on {obj.objectName()}. Calling navigation.")
                    if hasattr(self.mw, 'list_selection_handler'):
                        self.mw.list_selection_handler.navigate_to_problem_string(direction_down=True)
                    return True
                    
        if event.type() == QEvent.Type.ToolTip:
            name = obj.objectName() if hasattr(obj, 'objectName') else str(obj)
            log_debug(f"EventFilter: ToolTip event on {name}")
            
        return super().eventFilter(obj, event)


class MainWindowEventFilter(QObject):
    def __init__(self, main_window):
        super().__init__(main_window)
        self.mw = main_window

    def eventFilter(self, obj, event):
        if event.type() == QEvent.Type.KeyPress:
            if event.modifiers() & Qt.KeyboardModifier.AltModifier and event.modifiers() & Qt.KeyboardModifier.ShiftModifier:
                if event.key() == Qt.Key.Key_Up:
                    log_debug("AppFilter: Alt+Shift+Up -> navigate_between_blocks(False)")
                    self.mw.list_selection_handler.navigate_between_blocks(False)
                    return True
                elif event.key() == Qt.Key.Key_Down:
                    log_debug("AppFilter: Alt+Shift+Down -> navigate_between_blocks(True)")
                    self.mw.list_selection_handler.navigate_between_blocks(True)
                    return True
                elif event.key() == Qt.Key.Key_Left:
                    log_debug("AppFilter: Alt+Shift+Left -> navigate_between_folders(False)")
                    self.mw.list_selection_handler.navigate_between_folders(False)
                    return True
                elif event.key() == Qt.Key.Key_Right:
                    log_debug("AppFilter: Alt+Shift+Right -> navigate_between_folders(True)")
                    self.mw.list_selection_handler.navigate_between_folders(True)
                    return True
                    
            # F3 shortcuts - only handle when main window is active
            if isinstance(obj, QWidget) and obj.window() is self.mw:
                if event.key() == Qt.Key.Key_F3:
                    if event.modifiers() & Qt.KeyboardModifier.ShiftModifier:
                        log_debug("AppFilter: Shift+F3 pressed - Find Previous")
                        self.mw.helper.execute_find_previous_shortcut()
                        return True
                    else:
                        log_debug("AppFilter: F3 pressed - Find Next")
                        self.mw.helper.execute_find_next_shortcut()
                        return True

        return super().eventFilter(obj, event)
