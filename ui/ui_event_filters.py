from PyQt6.QtCore import QObject, QEvent, Qt, QTimer
from PyQt6.QtGui import QKeySequence
from PyQt6.QtWidgets import QLineEdit, QWidget
from utils.logging_utils import log_debug

class TextEditEventFilter(QObject):
    """Text edit event filter implementation."""
    def __init__(self, main_window):
        """Initialize a new instance."""
        parent = main_window if isinstance(main_window, QObject) else None
        super().__init__(parent)
        self.mw = main_window

    def eventFilter(self, obj, event):
        """Eventfilter."""
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
                            self.mw.list_selection_handler.string_selected_from_preview(current_row - 1, is_manual_click=True)
                        return True
                    elif event.key() == Qt.Key.Key_Down:
                        current_row = self.mw.data_store.current_string_idx
                        if self.mw.data_store.current_block_idx != -1 and current_row < len(self.mw.data_store.data[self.mw.data_store.current_block_idx]) - 1:
                            self.mw.list_selection_handler.string_selected_from_preview(current_row + 1, is_manual_click=True)
                        return True
            
            if is_alt_pressed and not is_ctrl_pressed and not is_shift_pressed:
                if event.key() in (Qt.Key.Key_Up, Qt.Key.Key_Down):
                    displayed_indices = self.mw.list_selection_handler._get_displayed_indices()
                    if not displayed_indices:
                        return True
                        
                    is_chapter = getattr(self.mw.data_store, 'current_chapter_id', None) is not None or (displayed_indices and isinstance(displayed_indices[0], tuple))
                    if is_chapter:
                        target = (self.mw.data_store.current_block_idx, self.mw.data_store.current_string_idx)
                    else:
                        target = self.mw.data_store.current_string_idx
                    current_preview_idx = self.mw.list_selection_handler._get_relative_index(target)
                            
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
                            self.mw.list_selection_handler.string_selected_from_preview(target_idx, is_manual_click=True)
                        return True
                        
                    elif event.key() == Qt.Key.Key_Down:
                        start = current_preview_idx
                        target_idx = -1
                        for i in range(start + 1, len(displayed_indices)):
                            if not is_line_empty(i):
                                target_idx = i
                                break
                        if target_idx != -1:
                            self.mw.list_selection_handler.string_selected_from_preview(target_idx, is_manual_click=True)
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
    """Main window event filter implementation."""
    def __init__(self, main_window):
        """Initialize a new instance."""
        super().__init__(main_window)
        self.mw = main_window

    def _is_speaker_combobox_event_source(self, obj) -> bool:
        """Return True when a key event came from the speaker combobox or its popup."""
        combo = getattr(self.mw, 'speaker_combobox', None)
        if combo is None:
            return False

        if obj is combo:
            return True

        try:
            line_edit = combo.lineEdit()
        except (AttributeError, RuntimeError):
            line_edit = None
        if line_edit is not None and obj is line_edit:
            return True

        try:
            view = combo.view()
        except (AttributeError, RuntimeError):
            view = None
        if view is not None:
            if obj is view:
                return True
            try:
                if obj is view.viewport():
                    return True
            except RuntimeError:
                pass

        if isinstance(obj, QWidget):
            parent = obj.parentWidget()
            while parent:
                if parent is combo or parent is line_edit or parent is view:
                    return True
                parent = parent.parentWidget()

        return False

    def _handle_speaker_combobox_undo_shortcut(self, event) -> bool:
        """Route Ctrl+Z/Y from the speaker editor to the app undo stack."""
        is_undo = event.matches(QKeySequence.StandardKey.Undo) or (
            event.modifiers() == Qt.KeyboardModifier.ControlModifier
            and event.key() == Qt.Key.Key_Z
        )
        if is_undo:
            if hasattr(self.mw, 'undo_typing_action') and self.mw.undo_typing_action:
                self.mw.undo_typing_action.trigger()
            elif hasattr(self.mw, 'undo_manager') and self.mw.undo_manager:
                self.mw.undo_manager.undo()
            return True

        is_redo = event.matches(QKeySequence.StandardKey.Redo) or (
            event.modifiers() == Qt.KeyboardModifier.ControlModifier
            and event.key() == Qt.Key.Key_Y
        ) or (
            event.modifiers() == (Qt.KeyboardModifier.ControlModifier | Qt.KeyboardModifier.ShiftModifier)
            and event.key() == Qt.Key.Key_Z
        )
        if is_redo:
            if hasattr(self.mw, 'redo_typing_action') and self.mw.redo_typing_action:
                self.mw.redo_typing_action.trigger()
            elif hasattr(self.mw, 'undo_manager') and self.mw.undo_manager:
                self.mw.undo_manager.redo()
            return True

        return False

    @staticmethod
    def _is_search_line_edit(obj) -> bool:
        """Recognize search/filter inputs shared by the app and its dialogs."""
        if not isinstance(obj, QLineEdit):
            return False
        if bool(obj.property("selectAllOnClick")):
            return True
        hint = " ".join((
            obj.objectName(),
            obj.placeholderText(),
            type(obj).__name__,
        )).casefold()
        return any(word in hint for word in ("search", "find", "filter"))

    def eventFilter(self, obj, event):
        """Eventfilter."""
        if (
            event.type() == QEvent.Type.MouseButtonRelease
            and event.button() == Qt.MouseButton.LeftButton
        ):
            line_edit = obj if self._is_search_line_edit(obj) else None
            if line_edit is None and self._is_speaker_combobox_event_source(obj):
                combo = getattr(self.mw, 'speaker_combobox', None)
                line_edit = combo.lineEdit() if combo is not None else None
                if obj not in (combo, line_edit):
                    line_edit = None
            if line_edit is not None and line_edit.text():
                # Run after Qt finishes the click, otherwise the native mouse
                # release handler immediately clears the selection again.
                QTimer.singleShot(0, line_edit.selectAll)

        if event.type() == QEvent.Type.KeyPress:
            if self._is_speaker_combobox_event_source(obj) and self._handle_speaker_combobox_undo_shortcut(event):
                return True

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
