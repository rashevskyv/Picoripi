# --- START OF FILE components/editor/text_highlight_manager.py ---
# --- START OF FILE components/text_highlight_manager.py ---
# --- START OF FILE components/TextHighlightManager.py ---
from PyQt5.QtWidgets import QTextEdit
from PyQt5.QtGui import QColor, QTextBlockFormat, QTextFormat, QTextCursor, QTextBlock, QTextCharFormat
from PyQt5.QtCore import QTimer, QPoint, Qt
from typing import Optional, List, Tuple
import re
from utils.logging_utils import log_debug

class TextHighlightManager:
    def __init__(self, editor):
        self.editor = editor
        
        # State trackers to prevent infinite recursion
        self._last_active_line_block = None
        self._last_linked_cursor_params = None
        
        self._active_line_selections = [] 
        self._linked_cursor_selections = []
        self._critical_problem_selections = []
        self._warning_problem_selections = []
        self._preview_selected_line_selections = []
        self._tag_interaction_selections = []
        self._search_match_selections = []
        self._width_exceed_char_selections = [] 
        self._empty_odd_subline_selections = []
        self._zebra_selections = []
        self._categorized_line_selections = []
        
        self._tag_highlight_timer = QTimer()
        self._tag_highlight_timer.setSingleShot(True)
        self._tag_highlight_timer.timeout.connect(self.clearTagInteractionHighlight)
        
        self._current_selected_lines = []

    def _create_block_background_selection(self, block: QTextBlock, color: QColor, use_full_width: bool = False) -> Optional[QTextEdit.ExtraSelection]:
        if not block.isValid(): return None
        selection = QTextEdit.ExtraSelection()
        selection.format.setBackground(color)
        cursor = QTextCursor(block)
        if use_full_width: 
            selection.format.setProperty(QTextFormat.FullWidthSelection, True)
            selection.cursor = cursor 
            selection.cursor.clearSelection() 
        else: 
            cursor.select(QTextCursor.BlockUnderCursor) 
            selection.cursor = cursor
        return selection

    def _create_search_match_selection(self, block_number: int, start_char_in_block: int, length: int, color: QColor) -> Optional[QTextEdit.ExtraSelection]:
        doc = self.editor.document()
        if not (0 <= block_number < doc.blockCount()):
            return None
        block = doc.findBlockByNumber(block_number)
        if not block.isValid():
            return None
        
        selection = QTextEdit.ExtraSelection()
        selection.format.setBackground(color)
        
        cursor = QTextCursor(block)
        cursor.setPosition(block.position() + start_char_in_block)
        cursor.movePosition(QTextCursor.Right, QTextCursor.KeepAnchor, length)
        
        if cursor.hasSelection():
            selection.cursor = cursor
            return selection
        return None

    def applyHighlights(self):
        all_selections = []
        if self._active_line_selections: all_selections.extend(list(self._active_line_selections)) 
        if self._linked_cursor_selections: 
            all_selections.extend([s for s in self._linked_cursor_selections if s.format.property(QTextFormat.FullWidthSelection)]) 
        if self._preview_selected_line_selections: all_selections.extend(list(self._preview_selected_line_selections)) 
        
        if self._critical_problem_selections: all_selections.extend(list(self._critical_problem_selections))
        if self._warning_problem_selections: all_selections.extend(list(self._warning_problem_selections))
        if self._empty_odd_subline_selections: all_selections.extend(list(self._empty_odd_subline_selections))
        
        if self._search_match_selections: all_selections.extend(list(self._search_match_selections))
        if self._width_exceed_char_selections: all_selections.extend(list(self._width_exceed_char_selections))
        if self._categorized_line_selections: all_selections.extend(list(self._categorized_line_selections))


        if self._linked_cursor_selections: 
            all_selections.extend([s for s in self._linked_cursor_selections if not s.format.property(QTextFormat.FullWidthSelection)]) 
        if self._tag_interaction_selections: all_selections.extend(list(self._tag_interaction_selections)) 
        
        if self._tag_interaction_selections: all_selections.extend(list(self._tag_interaction_selections)) 
        
        # Add zebra stripes at the very beginning (bottom layer)
        zebra_selections = list(self._zebra_selections)
        all_selections = zebra_selections + all_selections

        self.editor.setExtraSelections(all_selections)
        self.editor.viewport().update()
        if hasattr(self.editor, 'lineNumberArea'): 
            self.editor.lineNumberArea.update()


    def updateCurrentLineHighlight(self): 
        if self.editor.isReadOnly():
            if getattr(self, '_last_active_line_block', None) is not None:
                self._last_active_line_block = None
                self._active_line_selections = []
                self.applyHighlights()
            return

        cursor = self.editor.textCursor()
        current_block_idx = cursor.blockNumber()
        if getattr(self, '_last_active_line_block', None) == current_block_idx:
            return

        self._last_active_line_block = current_block_idx
        
        new_selections = [] 
        selection = QTextEdit.ExtraSelection()
        selection.format.setBackground(self.editor.current_line_color) 
        selection.format.setProperty(QTextFormat.FullWidthSelection, True) 
        selection.cursor = cursor
        selection.cursor.clearSelection()
        new_selections.append(selection)
            
        self._active_line_selections = new_selections
        self.applyHighlights()

    def clearCurrentLineHighlight(self):
        self._last_active_line_block = None
        if self._active_line_selections:
             self._active_line_selections = []
             self.applyHighlights()

    def setLinkedCursorPosition(self, line_number: int, column_number: int): 
        if getattr(self, '_last_linked_cursor_params', None) == (line_number, column_number):
            return
        self._last_linked_cursor_params = (line_number, column_number)

        new_linked_selections = [] 
        doc = self.editor.document()
        if line_number >= 0 and line_number < doc.blockCount():
            block = doc.findBlockByNumber(line_number)
            if block.isValid():
                line_sel = self._create_block_background_selection(block, self.editor.linked_cursor_block_color, use_full_width=True) 
                if line_sel: new_linked_selections.append(line_sel)
                
                line_text_length = len(block.text()); actual_column = min(column_number, line_text_length)
                pos_sel_obj = QTextEdit.ExtraSelection()
                cursor_for_pos = QTextCursor(block)
                cursor_for_pos.movePosition(QTextCursor.Right, QTextCursor.MoveAnchor, actual_column)
                pos_format = QTextCharFormat(); pos_format.setBackground(self.editor.linked_cursor_pos_color) 
                pos_sel_obj.format = pos_format
                temp_cursor_highlight = QTextCursor(cursor_for_pos)
                if actual_column < line_text_length: 
                    temp_cursor_highlight.movePosition(QTextCursor.Right, QTextCursor.KeepAnchor, 1)
                elif actual_column == line_text_length and line_text_length > 0 : 
                    if temp_cursor_highlight.movePosition(QTextCursor.Left, QTextCursor.MoveAnchor, 1):
                         temp_cursor_highlight.movePosition(QTextCursor.Right, QTextCursor.KeepAnchor, 1) 

                if temp_cursor_highlight.hasSelection(): 
                    pos_sel_obj.cursor = temp_cursor_highlight
                    new_linked_selections.append(pos_sel_obj)
                elif actual_column == 0 and line_text_length == 0:
                     pass 

        self._linked_cursor_selections = new_linked_selections
        self.applyHighlights()

    def clearLinkedCursorPosition(self):
         self._last_linked_cursor_params = None
         if self._linked_cursor_selections:
              self._linked_cursor_selections = []
              self.applyHighlights()

    def setPreviewSelectedLineHighlight(self, line_numbers: List[int]):
        self._current_selected_lines = line_numbers.copy()
        new_selections = []
        doc = self.editor.document()

        for line_number in line_numbers:
            if line_number >= 0 and line_number < doc.blockCount():
                block = doc.findBlockByNumber(line_number)
                selection = self._create_block_background_selection(block, self.editor.preview_selected_line_color, use_full_width=True)
                if selection:
                    new_selections.append(selection)

        self._preview_selected_line_selections = new_selections
        self.applyHighlights()

    def set_background_for_lines(self, lines_to_highlight: set, lines_to_clear: set):
        # Using ExtraSelections instead of QTextBlockFormat to avoid RecursionError
        # and keep the document content clean.
        doc = self.editor.document()
        new_selections = list(self._preview_selected_line_selections)
        
        # Remove cleared lines
        new_selections = [s for s in new_selections if s.cursor.blockNumber() not in lines_to_clear]
        
        # Add highlighted lines
        for line_number in lines_to_highlight:
            if 0 <= line_number < doc.blockCount():
                block = doc.findBlockByNumber(line_number)
                selection = self._create_block_background_selection(block, self.editor.preview_selected_line_color, use_full_width=True)
                if selection:
                    new_selections.append(selection)

        self._preview_selected_line_selections = new_selections
        self.applyHighlights()

    def clearPreviewSelectedLineHighlight(self):
        if self._preview_selected_line_selections:
            self._preview_selected_line_selections = []
            self.applyHighlights()

    def setCategorizedLineHighlights(self, line_numbers: List[int], color: QColor):
        new_selections = []
        doc = self.editor.document()
        for line_number in line_numbers:
            if 0 <= line_number < doc.blockCount():
                block = doc.findBlockByNumber(line_number)
                selection = self._create_block_background_selection(block, color, use_full_width=True)
                if selection:
                    new_selections.append(selection)
        self._categorized_line_selections = new_selections
        self.applyHighlights()

    def clearCategorizedLineHighlights(self):
        if self._categorized_line_selections:
            self._categorized_line_selections = []
            self.applyHighlights()

    def addProblemLineHighlight(self, line_number: int):
        self.addCriticalProblemHighlight(line_number)

    def addCriticalProblemHighlight(self, line_number: int, color: QColor = None):
        # Не підсвічуємо фон тексту в редакторах, тільки в прев'ю (якщо потрібно)
        return

    def removeCriticalProblemHighlight(self, line_number: int) -> bool:
        removed = False; initial_len = len(self._critical_problem_selections)
        self._critical_problem_selections = [s for s in self._critical_problem_selections if s.cursor.blockNumber() != line_number]
        if len(self._critical_problem_selections) < initial_len: 
            removed = True
            self.applyHighlights()
        return removed

    def clearCriticalProblemHighlights(self):
        needs_update = bool(self._critical_problem_selections)
        self._critical_problem_selections = []
        if needs_update: self.applyHighlights()

    def hasCriticalProblemHighlight(self, line_number: Optional[int] = None) -> bool:
        if line_number is not None: return any(s.cursor.blockNumber() == line_number for s in self._critical_problem_selections)
        return bool(self._critical_problem_selections)

    def addWarningLineHighlight(self, line_number: int, color: QColor = None):
        # Не підсвічуємо фон тексту в редакторах
        return

    def removeWarningLineHighlight(self, line_number: int) -> bool:
        removed = False; initial_len = len(self._warning_problem_selections)
        self._warning_problem_selections = [s for s in self._warning_problem_selections if s.cursor.blockNumber() != line_number]
        if len(self._warning_problem_selections) < initial_len: 
            removed = True
            self.applyHighlights()
        return removed

    def clearWarningLineHighlights(self):
        needs_update = bool(self._warning_problem_selections)
        self._warning_problem_selections = []
        if needs_update: self.applyHighlights()

    def hasWarningLineHighlight(self, line_number: Optional[int] = None) -> bool:
        if line_number is not None: return any(s.cursor.blockNumber() == line_number for s in self._warning_problem_selections)
        return bool(self._warning_problem_selections)

    def momentaryHighlightTag(self, block, start_in_block, length):
        if not block.isValid(): return
        self.clearTagInteractionHighlight() 
        selection = QTextEdit.ExtraSelection()
        selection.format.setBackground(self.editor.tag_interaction_highlight_color)
        cursor = QTextCursor(block)
        cursor.setPosition(block.position() + start_in_block)
        cursor.movePosition(QTextCursor.Right, QTextCursor.KeepAnchor, length)
        selection.cursor = cursor
        self._tag_interaction_selections.append(selection)
        self.applyHighlights()
        self._tag_highlight_timer.start(300)

    def clearTagInteractionHighlight(self):
        if self._tag_interaction_selections:
            self._tag_interaction_selections = []
            self.applyHighlights()

    def add_search_match_highlight(self, block_number: int, start_char_in_block: int, length: int):
        selection = self._create_search_match_selection(block_number, start_char_in_block, length, self.editor.search_match_highlight_color)
        if selection:
            current_selections = list(self._search_match_selections)
            current_selections.append(selection)
            self._search_match_selections = current_selections
            self.applyHighlights()

    def clear_search_match_highlights(self):
        if self._search_match_selections:
            self._search_match_selections = []
            self.applyHighlights()
            
    def add_width_exceed_char_highlight(self, block: QTextBlock, char_index_in_block: int, color: QColor):
        if not block.isValid():
            return
        selection = QTextEdit.ExtraSelection()
        selection.format.setBackground(color)
        
        char_cursor = QTextCursor(block)
        char_cursor.setPosition(block.position() + char_index_in_block)
        char_cursor.movePosition(QTextCursor.Right, QTextCursor.KeepAnchor, 1) 
        
        if char_cursor.hasSelection():
            selection.cursor = char_cursor
            already_exists = False
            for existing_sel in self._width_exceed_char_selections:
                if existing_sel.cursor.blockNumber() == selection.cursor.blockNumber() and \
                   existing_sel.cursor.selectionStart() == selection.cursor.selectionStart() and \
                   existing_sel.cursor.selectionEnd() == selection.cursor.selectionEnd():
                    already_exists = True
                    break
            if not already_exists:
                self._width_exceed_char_selections.append(selection)
        pass


    def clear_width_exceed_char_highlights(self):
        if self._width_exceed_char_selections:
            self._width_exceed_char_selections = []
        pass

    def addEmptyOddSublineHighlight(self, block_number: int):
        # Background highlighting disabled by request to keep the text area clean
        return

    def removeEmptyOddSublineHighlight(self, block_number: int) -> bool:
        removed = False
        initial_len = len(self._empty_odd_subline_selections)
        self._empty_odd_subline_selections = [s for s in self._empty_odd_subline_selections if s.cursor.blockNumber() != block_number]
        if len(self._empty_odd_subline_selections) < initial_len:
            removed = True
            self.applyHighlights()
        return removed

    def clearEmptyOddSublineHighlights(self):
        needs_update = bool(self._empty_odd_subline_selections)
        self._empty_odd_subline_selections = []
        if needs_update:
            self.applyHighlights()

    def hasEmptyOddSublineHighlight(self, block_number: Optional[int] = None) -> bool:
        if block_number is not None:
            return any(s.cursor.blockNumber() == block_number for s in self._empty_odd_subline_selections)
        return bool(self._empty_odd_subline_selections)

    def clearAllProblemHighlights(self):
        needs_update = bool(self._critical_problem_selections) or \
                       bool(self._warning_problem_selections) or \
                       bool(self._empty_odd_subline_selections)
        
        self._critical_problem_selections = []
        self._warning_problem_selections = []
        self._empty_odd_subline_selections = []
        
        if self._width_exceed_char_selections:
            self._width_exceed_char_selections = []
            needs_update = True

        if needs_update: self.applyHighlights()
        
    def clearAllHighlights(self):
        self._last_active_line_block = None
        self._last_linked_cursor_params = None
        self._active_line_selections = [] 
        self._linked_cursor_selections = []
        self._critical_problem_selections = []
        self._warning_problem_selections = []
        self._preview_selected_line_selections = []
        self._tag_interaction_selections = []
        self._search_match_selections = []
        self._width_exceed_char_selections = [] 
        self._empty_odd_subline_selections = []
        self._zebra_selections = [] # Added _zebra_selections
        self._categorized_line_selections = []
        self.applyHighlights()

    def update_zebra_stripes(self):
        new_selections = []
        doc = self.editor.document()
        odd_color = getattr(self.editor, 'zebra_odd_color', None)
        even_color = getattr(self.editor, 'zebra_even_color', None)
        
        if not odd_color or not even_color:
            self._zebra_selections = [] # Clear if colors are not set
            self.applyHighlights()
            return

        for i in range(doc.blockCount()):
            block = doc.findBlockByNumber(i)
            is_odd = i % 2 != 0
            color = odd_color if is_odd else even_color
            
            # Only add if the line is not currently selected by preview_selected_line_highlight
            # and if the color is valid (not transparent or fully opaque alpha 0)
            if color and color != Qt.transparent and color.alpha() != 0 and i not in self._current_selected_lines:
                selection = self._create_block_background_selection(block, color, use_full_width=True)
                if selection:
                    new_selections.append(selection)

        self._zebra_selections = new_selections
        self.applyHighlights()