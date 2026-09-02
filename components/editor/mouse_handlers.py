from PyQt6.QtWidgets import QApplication, QMainWindow, QStyle
from PyQt6.QtGui import QTextCursor, QMouseEvent
from PyQt6.QtCore import Qt, QPoint
import re
from typing import Optional, Tuple, List

from utils.logging_utils import log_debug
from core.i18n import tr

class LNETMouseHandlers:
    """L n e t mouse handlers implementation."""
    def __init__(self, editor): # editor - С†Рµ LineNumberedTextEdit
        """Initialize a new instance."""
        self.editor = editor

    def _get_icon_sequences(self) -> List[str]:
        """Internal helper to get the icon sequences."""
        main_window = self.editor.window()
        if isinstance(main_window, QMainWindow):
            sequences = getattr(main_window, 'icon_sequences', None)
            if isinstance(sequences, list):
                return sequences
        return []

    def _find_icon_sequence_hit(self, cursor: QTextCursor, sequences: List[str]):
        """Internal helper to find icon sequence hit."""
        if not sequences:
            return None
        block = cursor.block()
        if not block.isValid():
            return None
        block_text = block.text()
        position_in_block = cursor.position() - block.position()
        for token in sequences:
            start = block_text.find(token)
            while start != -1:
                end = start + len(token)
                if start <= position_in_block < end:
                    return block, start, end, token
                start = block_text.find(token, start + 1)
        return None

    def _move_cursor_to_icon_sequence_end(self, block, start_in_block: int, end_in_block: int, token: str):
        """Internal helper to move cursor to icon sequence end."""
        final_cursor = QTextCursor(block)
        final_cursor.setPosition(block.position() + end_in_block)
        self.editor.setTextCursor(final_cursor)
        if token:
            self.editor._momentary_highlight_tag(block, start_in_block, len(token))

    def _wrap_selection_with_color(self, color_name: str):
        """Internal helper to wrap selection with color."""
        prefix_tag = f"{{Color:{color_name.capitalize()}}}"
        suffix_tag = "{Color:White}"
        self.wrap_selection_with_custom_tags(prefix_tag, suffix_tag)

    def insert_single_tag(self, tag: str):
        """Insert single tag."""
        cursor = self.editor.textCursor()
        cursor.beginEditBlock()
        cursor.insertText(tag)
        cursor.endEditBlock()
        log_debug(f"Inserted single tag: {tag}")

    def wrap_selection_with_custom_tags(self, open_tag: str, close_tag: str):
        """Wrap selection with custom tags."""
        cursor = self.editor.textCursor()
        if not cursor.hasSelection():
            return

        selected_text = cursor.selectedText()
        new_text = f"{open_tag}{selected_text}{close_tag}"
        
        cursor.beginEditBlock()
        cursor.insertText(new_text)
        cursor.endEditBlock()
        log_debug(f"Wrapped selection with {open_tag}...{close_tag}. New text length: {len(new_text)}")

    def copy_tag_to_clipboard(self, tag_text_curly):
         # self.editor С‚СѓС‚ - С†Рµ LineNumberedTextEdit (original_text_edit)
         """Copy tag to clipboard."""
         actual_main_window = self.editor.window()
         if not isinstance(actual_main_window, QMainWindow): return

         text_to_copy = tag_text_curly
         # Р”РѕСЃС‚СѓРї РґРѕ editor_player_tag С‚Р° original_player_tag С‡РµСЂРµР· self.editor
         if tag_text_curly == self.editor.original_player_tag: 
             text_to_copy = self.editor.editor_player_tag
         QApplication.clipboard().setText(text_to_copy)
         if hasattr(actual_main_window, 'statusBar'):
             actual_main_window.statusBar.showMessage(f"Copied to clipboard: {text_to_copy}", 2000)

    def get_tag_at_cursor(self, cursor: QTextCursor, pattern: str) -> Tuple[Optional[str], int, int]:
        """Get the tag at cursor."""
        block = cursor.block()
        if not block.isValid(): return None, -1, -1
        block_text = block.text()
        cursor_pos_in_text_block = cursor.position() - block.position()
        for match in re.finditer(pattern, block_text):
            start, end = match.span()
            if start <= cursor_pos_in_text_block < end:
                return match.group(0), start, end
        return None, -1, -1

    def showContextMenu(self, pos: QPoint): # pos - С†Рµ РєРѕРѕСЂРґРёРЅР°С‚Рё РєР»С–РєСѓ РІС–РґРЅРѕСЃРЅРѕ РІС–РґР¶РµС‚Р° self.editor
        """Showcontextmenu."""
        log_debug(f"showContextMenu for editor: {self.editor.objectName()} at pos {pos}")
        menu = self.editor.createStandardContextMenu()
        
        # Р’РёРєР»РёРєР°С”РјРѕ РјРµС‚РѕРґ СЃР°РјРѕРіРѕ СЂРµРґР°РєС‚РѕСЂР° РґР»СЏ Р·Р°РїРѕРІРЅРµРЅРЅСЏ РјРµРЅСЋ
        if hasattr(self.editor, 'populateContextMenu'):
            self.editor.populateContextMenu(menu, pos) # РџРµСЂРµРґР°С”РјРѕ pos
        else:
            log_debug(f"Editor {self.editor.objectName()} has no populateContextMenu method.")

        main_window = self.editor.window()
        if isinstance(main_window, QMainWindow):
            ai_chat_handler = getattr(main_window, 'ai_chat_handler', None)
            if ai_chat_handler:
                menu.addSeparator()
                discuss_action = menu.addAction(main_window.style().standardIcon(QStyle.StandardPixmap.SP_DialogHelpButton), tr('Discuss with AI...'))
                
                text_to_discuss = ""
                cursor = self.editor.textCursor()
                if cursor.hasSelection():
                    text_to_discuss = cursor.selectedText().replace('\u2029', '\n')
                else:
                    if self.editor.objectName() == "preview_text_edit":
                        clicked_cursor = self.editor.cursorForPosition(pos)
                        line_num = clicked_cursor.blockNumber()
                        if main_window.data_store.current_block_idx != -1:
                            orig_text = main_window.data_processor._get_string_from_source(main_window.data_store.current_block_idx, line_num, main_window.data_store.data, "context_menu")
                            edited_text, _ = main_window.data_processor.get_current_string_text(main_window.data_store.current_block_idx, line_num)
                            text_to_discuss = f"Original:\n---\n{orig_text}\n---\n\nTranslated:\n---\n{edited_text}\n---"
                    else: # original_text_edit or edited_text_edit
                        text_to_discuss = self.editor.toPlainText().replace('\u2029', '\n')
                
                if text_to_discuss.strip():
                    discuss_action.triggered.connect(lambda checked=False, text=text_to_discuss: ai_chat_handler.show_chat_window(text))
                else:
                    discuss_action.setEnabled(False)

        log_debug(f"Executing menu for {self.editor.objectName()}.")
        menu.exec(self.editor.mapToGlobal(pos))


    def mouseReleaseEvent(self, event: QMouseEvent):
        """Mousereleaseevent."""
        if self.editor.objectName() == "preview_text_edit":
            if event.button() == Qt.MouseButton.LeftButton:
                self.editor.drag_start_pos = None
            event.accept()
            return
        
        self.editor.super_mouseReleaseEvent(event) # Р’РёРєР»РёРєР°С”РјРѕ Р±Р°С‚СЊРєС–РІСЃСЊРєРёР№ РјРµС‚РѕРґ Р· LineNumberedTextEdit
        if event.button() == Qt.MouseButton.LeftButton:
            text_cursor_at_click = self.editor.cursorForPosition(event.pos())
            actual_main_window = self.editor.window()
            if not isinstance(actual_main_window, QMainWindow): return
            
            icon_sequences = self._get_icon_sequences()
            if (icon_sequences and event.modifiers() == Qt.KeyboardModifier.NoModifier
                    and not self.editor.textCursor().hasSelection()):
                icon_hit = self._find_icon_sequence_hit(text_cursor_at_click, icon_sequences)
                if icon_hit:
                    block, start, end, token = icon_hit
                    self._move_cursor_to_icon_sequence_end(block, start, end, token)
                    event.accept(); return

            if self.editor.isReadOnly() and hasattr(actual_main_window, 'original_text_edit') and self.editor == actual_main_window.original_text_edit:
                translator = getattr(actual_main_window, 'translation_handler', None)
                if event.modifiers() & Qt.KeyboardModifier.ControlModifier:
                    finder = getattr(self.editor, '_find_glossary_entry_at', None)
                    glossary_entry = finder(event.pos()) if callable(finder) else None
                    if glossary_entry and translator and hasattr(translator, 'edit_glossary_entry'):
                         log_debug(f'Ctrl+Click edit glossary for "{glossary_entry.original}".')
                         translator.edit_glossary_entry(glossary_entry.original)
                         event.accept(); return
                tag_text_curly, tag_start, tag_end = self.get_tag_at_cursor(text_cursor_at_click, r"\{[^}]*\}")
                if tag_text_curly:
                    self.copy_tag_to_clipboard(tag_text_curly)
                    self.editor._momentary_highlight_tag(text_cursor_at_click.block(), tag_start, len(tag_text_curly))
                    event.accept(); return
            elif not self.editor.isReadOnly() and hasattr(actual_main_window, 'edited_text_edit') and self.editor == actual_main_window.edited_text_edit:
                clicked_bracket_tag, tag_start_in_block, _ = self.get_tag_at_cursor(text_cursor_at_click, r"\[[^\]]*\]")
                clipboard_text = QApplication.clipboard().text()
                if event.modifiers() & Qt.KeyboardModifier.ControlModifier and clicked_bracket_tag:
                    if re.fullmatch(r"\{[^}]*\}", clipboard_text):
                        self.editor.addTagMappingRequest.emit(clicked_bracket_tag, clipboard_text)
                        if hasattr(actual_main_window, 'statusBar'):
                            actual_main_window.statusBar.showMessage(f"Requested to map: {clicked_bracket_tag} -> {clipboard_text}", 3000)
                        self.editor._momentary_highlight_tag(text_cursor_at_click.block(), tag_start_in_block, len(clicked_bracket_tag))
                        event.accept(); return
                    else:
                        if hasattr(actual_main_window, 'statusBar'):
                             actual_main_window.statusBar.showMessage(f"Ctrl+Click: Clipboard does not contain a valid {{...}} tag to map with '{clicked_bracket_tag}'.", 3000)
                        event.accept(); return
                elif clicked_bracket_tag:
                    is_curly_tag_in_clipboard = re.fullmatch(r"\{[^}]*\}", clipboard_text)
                    # Р”РѕСЃС‚СѓРї РґРѕ editor_player_tag С‡РµСЂРµР· self.editor
                    is_editor_player_tag_in_clipboard = (clipboard_text == self.editor.editor_player_tag) 
                    if is_curly_tag_in_clipboard or is_editor_player_tag_in_clipboard:
                        current_block = text_cursor_at_click.block(); modify_cursor = QTextCursor(current_block)
                        modify_cursor.setPosition(current_block.position() + tag_start_in_block)
                        modify_cursor.movePosition(QTextCursor.MoveOperation.Right, QTextCursor.MoveMode.KeepAnchor, len(clicked_bracket_tag))
                        new_cursor_pos_in_block = tag_start_in_block + len(clipboard_text)
                        modify_cursor.beginEditBlock(); modify_cursor.insertText(clipboard_text); modify_cursor.endEditBlock()
                        final_cursor = QTextCursor(current_block); final_cursor.setPosition(current_block.position() + new_cursor_pos_in_block); self.editor.setTextCursor(final_cursor)
                        if hasattr(actual_main_window, 'statusBar'): actual_main_window.statusBar.showMessage(f"Replaced '{clicked_bracket_tag}' with '{clipboard_text}'", 2000)
                        self.editor._momentary_highlight_tag(current_block, tag_start_in_block, len(clipboard_text))
                    else:
                        if hasattr(actual_main_window, 'statusBar'): actual_main_window.statusBar.showMessage("Clipboard does not contain a valid tag for replacement.", 2000)
                    event.accept(); return

    def handle_line_number_click(self, y_pos: int):
        """Handle a click on the line number area."""
        editor = self.editor
        cursor = editor.cursorForPosition(QPoint(5, y_pos))
        if cursor.isNull():
            return

        block = cursor.block()
        if not block.isValid():
            return

        if editor.objectName() == "preview_text_edit":
            editor.lineClicked.emit(block.blockNumber())
        else:
            scroll_value = editor.horizontalScrollBar().value()

            selection_cursor = QTextCursor(block)
            selection_cursor.select(QTextCursor.SelectionType.BlockUnderCursor)
            editor.setTextCursor(selection_cursor)

            editor.horizontalScrollBar().setValue(scroll_value)
            editor.setFocus()

    def handle_line_number_double_click(self, y_pos: int):
        """Handle a double-click on the line number area."""
        actual_main_window = self.editor.window()
        if hasattr(actual_main_window, 'list_selection_handler') and actual_main_window.list_selection_handler:
            actual_main_window.list_selection_handler.scroll_to_current_string_in_preview()
        elif hasattr(self.editor, 'custom_line_numbers') and self.editor.custom_line_numbers:
            line_idx = self._get_line_index_from_y(y_pos)
            if line_idx != -1 and line_idx < len(self.editor.custom_line_numbers):
                string_number = self.editor.custom_line_numbers[line_idx]
                if string_number is None:
                    for i in range(line_idx - 1, -1, -1):
                        if i < len(self.editor.custom_line_numbers):
                            if self.editor.custom_line_numbers[i] is not None:
                                string_number = self.editor.custom_line_numbers[i]
                                break
                if string_number is not None and hasattr(actual_main_window, '_navigate_to_string_in_main_window'):
                    actual_main_window._navigate_to_string_in_main_window(string_number)

    def handle_line_number_area_mouse_move(self, event):
        """Show tooltip when hovering over the line number area."""
        from PyQt6.QtWidgets import QToolTip

        line_idx = self._get_line_index_from_y(event.pos().y())
        if line_idx == -1:
            QToolTip.hideText()
            return

        metadata_tooltip = None
        number_part_width = 0
        if self.editor.objectName() == "preview_text_edit":
            main_window = self.editor.window()
            total_width = self.editor.lineNumberArea.width()
            extra_part_width = self.editor.preview_indicator_area_width
            number_part_width = total_width - extra_part_width
            
            real_idx = line_idx
            if hasattr(main_window, 'data_store') and main_window.data_store.displayed_string_indices:
                if 0 <= line_idx < len(main_window.data_store.displayed_string_indices):
                    real_idx = main_window.data_store.displayed_string_indices[line_idx]
                else:
                    real_idx = -1
            
            if real_idx != -1 and main_window and hasattr(main_window, 'string_metadata'):
                current_block_idx = main_window.data_store.current_block_idx
                if isinstance(real_idx, tuple):
                    string_meta = main_window.string_metadata.get(real_idx, {})
                else:
                    string_meta = main_window.string_metadata.get((current_block_idx, real_idx), {})
                
                default_font = getattr(main_window, 'default_font_file', None)
                max_width = getattr(main_window, 'game_dialog_max_width_pixels', None)
                
                has_custom_font = "font_file" in string_meta and string_meta["font_file"] != default_font
                has_custom_width = "width" in string_meta and string_meta["width"] != max_width
                
                if has_custom_font or has_custom_width:
                    font_name = string_meta.get("font_file")
                    width_val = string_meta.get("width")
                    
                    tooltip_lines = []
                    if has_custom_font:
                        tooltip_lines.append(f"Custom Font: {font_name} is applied")
                    if has_custom_width:
                        tooltip_lines.append(f"Custom Width: {width_val}px is applied")
                    
                    metadata_tooltip = "<b>Line Settings Overrides:</b><br>" + "<br>".join(tooltip_lines)

        dummy_pos = QPoint(self.editor.lineNumberArea.width() + 10, event.pos().y())
        text_warning_tooltip = self.editor.tooltip_logic.find_warning_tooltip_at(dummy_pos)

        if text_warning_tooltip:
            QToolTip.showText(event.globalPosition().toPoint(), text_warning_tooltip, self.editor.lineNumberArea)
        elif metadata_tooltip and (event.pos().x() >= number_part_width or not text_warning_tooltip):
            QToolTip.showText(event.globalPosition().toPoint(), metadata_tooltip, self.editor.lineNumberArea)
        else:
            QToolTip.hideText()

    def _get_line_index_from_y(self, y: int) -> int:
        """Get the block number for a given y coordinate."""
        editor = self.editor
        block = editor.firstVisibleBlock()
        top = int(editor.blockBoundingGeometry(block).translated(editor.contentOffset()).top())
        bottom = top + int(editor.blockBoundingRect(block).height())

        while block.isValid() and top <= y:
            if block.isVisible() and y >= top and y <= bottom:
                return block.blockNumber()
            block = block.next()
            top = bottom
            bottom = top + int(editor.blockBoundingRect(block).height())
        return -1

    def mousePressEvent(self, event: QMouseEvent):
        """Mousepressevent."""
        if self.editor.objectName() == "preview_text_edit":
            cursor = self.editor.cursorForPosition(event.pos())
            block_number = cursor.blockNumber()
            log_debug(f"DIAG_MOUSE_PRESS: modifiers={event.modifiers()}, button={event.button()}, block={block_number}, last_clicked={self.editor._last_clicked_line}")

            if event.button() == Qt.MouseButton.LeftButton:
                self.editor.setFocus()
                self.editor.setTextCursor(cursor)
                
                self.editor.drag_start_pos = event.pos()
                modifiers = event.modifiers()
                
                if modifiers & Qt.KeyboardModifier.ShiftModifier and self.editor._last_clicked_line != -1:
                    start_line = self.editor._last_clicked_line
                    end_line = block_number
                    
                    if not (modifiers & Qt.KeyboardModifier.ControlModifier):
                        self.editor._selected_lines.clear()
                        
                    line_range = range(min(start_line, end_line), max(start_line, end_line) + 1)
                    self.editor._selected_lines.update(line_range)
                    
                elif modifiers & Qt.KeyboardModifier.ControlModifier:
                    if block_number in self.editor._selected_lines:
                        self.editor._selected_lines.remove(block_number)
                    else:
                        self.editor._selected_lines.add(block_number)
                    self.editor._last_clicked_line = block_number
                else:
                    self.editor.clear_selection()
                    self.editor._selected_lines.add(block_number)
                    self.editor._last_clicked_line = block_number
                    self.editor.lineClicked.emit(block_number)
                    
                self.editor._update_selection_highlight()
                self.editor._update_selection_highlight()
                self.editor._emit_selection_changed()
                event.accept()
                return 
                
            elif event.button() == Qt.MouseButton.RightButton:
                if block_number not in self.editor._selected_lines:
                    self.editor.setTextCursor(cursor)
                    self.editor.clear_selection()
                    self.editor._selected_lines.add(block_number)
                    self.editor._last_clicked_line = block_number
                    self.editor._update_selection_highlight()
                    self.editor._emit_selection_changed()
                    self.editor.lineClicked.emit(block_number)
                event.accept()
                return

        self.editor.super_mousePressEvent(event)
