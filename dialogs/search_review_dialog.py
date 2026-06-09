# Dialog for interactive searching and replacing of text in a block
from PyQt6.QtWidgets import (QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QLineEdit, QListWidget, QApplication)
from PyQt6.QtCore import Qt, QTimer
from PyQt6.QtGui import QTextCursor, QTextCharFormat, QColor
from typing import List, Tuple
import re
from utils.logging_utils import log_debug, log_error
from dialogs.base_text_review_dialog import BaseTextReviewDialog
from utils.utils import ALL_TAGS_PATTERN, FORCED_ALIAS_PATTERN, prepare_text_for_tagless_search, is_fuzzy_match

def map_forced_aliases(text: str) -> Tuple[str, List[int]]:
    # Returns (processed_text, list of original indices)
    result_chars = []
    mapping = []
    idx = 0
    n = len(text)
    while idx < n:
        match = FORCED_ALIAS_PATTERN.match(text, idx)
        if match:
            content = match.group(1)
            content_start = match.start(1)
            for offset, char in enumerate(content):
                result_chars.append(char)
                mapping.append(content_start + offset)
            idx = match.end()
        else:
            result_chars.append(text[idx])
            mapping.append(idx)
            idx += 1
    return "".join(result_chars), mapping

def map_remove_all_tags(text: str, current_mapping: List[int]) -> Tuple[str, List[int]]:
    result_chars = []
    mapping = []
    idx = 0
    n = len(text)
    while idx < n:
        match = ALL_TAGS_PATTERN.match(text, idx)
        if match:
            idx = match.end()
        else:
            result_chars.append(text[idx])
            mapping.append(current_mapping[idx])
            idx += 1
    return "".join(result_chars), mapping

def prepare_text_for_tagless_search_with_mapping(text: str) -> Tuple[str, List[int]]:
    if text is None:
        return "", []
        
    t1, m1 = map_forced_aliases(text)
    t2, m2 = map_remove_all_tags(t1, m1)
    
    t3_chars = []
    for char in t2:
        if char == '+' or char == '·' or char == '\n':
            t3_chars.append(' ')
        else:
            t3_chars.append(char)
    t3 = "".join(t3_chars)
    m3 = m2
    
    t4_chars = []
    m4 = []
    n = len(t3)
    idx = 0
    while idx < n:
        if t3[idx] == ' ':
            t4_chars.append(' ')
            m4.append(m3[idx])
            idx += 1
            while idx < n and t3[idx] == ' ':
                idx += 1
        else:
            t4_chars.append(t3[idx])
            m4.append(m3[idx])
            idx += 1
    t4 = "".join(t4_chars)
    
    start_strip = 0
    while start_strip < len(t4) and t4[start_strip] == ' ':
        start_strip += 1
        
    end_strip = len(t4)
    while end_strip > start_strip and t4[end_strip - 1] == ' ':
        end_strip -= 1
        
    final_text = t4[start_strip:end_strip]
    final_mapping = m4[start_strip:end_strip]
    
    return final_text, final_mapping

def adjust_replacement_case(original: str, replacement: str, match_case: bool) -> str:
    if not replacement:
        return replacement
    # If the user explicitly enters a replacement starting with an uppercase letter,
    # respect their choice (user's input casing takes priority).
    if replacement[0].isupper():
        return replacement
    if not match_case:
        return replacement
    
    # Check original word casing
    # An all-uppercase word must have length > 1 to be considered truly all-caps,
    # otherwise a single letter (like "O" or "I") is treated as capitalized.
    if len(original) > 1 and original.isupper():
        return replacement.upper()
    if original and original[0].isupper():
        return replacement[0].upper() + replacement[1:] if len(replacement) > 1 else replacement.upper()
    return replacement

class SearchReviewDialog(BaseTextReviewDialog):
    """Interactive dialog for reviewing search results in a block with a replace option."""

    def __init__(self, parent, text: str, query: str, starting_line_number: int = 0, line_numbers: List[int] = None, case_sensitive: bool = False, is_fuzzy: bool = False, search_in_original: bool = False, ignore_tags: bool = True, block_idx: int = -1, block_indices: List[int] = None):
        log_debug("SearchReviewDialog: __init__ started")
        self.query = query
        self.case_sensitive = case_sensitive
        self.is_fuzzy = is_fuzzy
        self.search_in_original = search_in_original
        self.ignore_tags = ignore_tags
        self.starting_line_number = starting_line_number
        self.block_indices = block_indices if block_indices is not None else ([block_idx] * len(line_numbers) if line_numbers else [])
        
        self.unique_string_indices = []
        if line_numbers and self.block_indices:
            for s_idx, b_idx in zip(line_numbers, self.block_indices):
                if s_idx is not None and b_idx is not None:
                    pair = (b_idx, s_idx)
                    if not self.unique_string_indices or self.unique_string_indices[-1] != pair:
                        self.unique_string_indices.append(pair)
        
        super().__init__(parent, "Advanced Search & Replace", text, line_numbers, block_idx)
        
        # Mapping base class variables
        self.matches = self.items_to_review 
        
        # Rebuild text if we are searching in the original source
        if self.search_in_original:
            self.rebuild_text_by_options()

        log_debug("SearchReviewDialog: Starting content loading")
        is_test = parent is None or "Mock" in str(type(parent))
        if not is_test:
            QTimer.singleShot(50, self._load_content)

    def setup_left_panel(self, layout: QVBoxLayout):
        layout.addWidget(QLabel("Search Matches:"))
        self.matches_list = QListWidget()
        self.matches_list.itemClicked.connect(self.jump_to_item_from_list)
        self.matches_list.itemDoubleClicked.connect(self._on_item_double_click)
        layout.addWidget(self.matches_list)

    def setup_right_panel(self, layout: QVBoxLayout):
        from PyQt6.QtWidgets import QCheckBox, QHBoxLayout
        layout.addWidget(QLabel("Find:"))
        self.find_input = QLineEdit()
        self.find_input.setText(self.query)
        self.find_input.setPlaceholderText("Enter search query...")
        self.find_input.returnPressed.connect(self.perform_search)
        layout.addWidget(self.find_input)
        
        # Options checkboxes layout
        options_layout = QHBoxLayout()
        
        self.case_sensitive_checkbox = QCheckBox("Aa")
        self.case_sensitive_checkbox.setToolTip("Case sensitive")
        self.case_sensitive_checkbox.setChecked(self.case_sensitive)
        options_layout.addWidget(self.case_sensitive_checkbox)
        
        self.fuzzy_checkbox = QCheckBox("Fuzzy")
        self.fuzzy_checkbox.setToolTip("Search for similar words (ignores endings)")
        self.fuzzy_checkbox.setChecked(self.is_fuzzy)
        options_layout.addWidget(self.fuzzy_checkbox)
        
        self.original_checkbox = QCheckBox("Original")
        self.original_checkbox.setToolTip("Search in original text")
        self.original_checkbox.setChecked(self.search_in_original)
        options_layout.addWidget(self.original_checkbox)
        
        self.no_tags_checkbox = QCheckBox("No Tags")
        self.no_tags_checkbox.setToolTip("Ignore tags {...} [...], newlines, and extra spaces")
        self.no_tags_checkbox.setChecked(self.ignore_tags)
        options_layout.addWidget(self.no_tags_checkbox)
        
        layout.addLayout(options_layout)
        
        layout.addWidget(QLabel("Replace with:"))
        self.replace_input = QLineEdit()
        self.replace_input.setPlaceholderText("Enter replacement text...")
        layout.addWidget(self.replace_input)

        self.match_case_replace_checkbox = QCheckBox("Match case on replace")
        self.match_case_replace_checkbox.setToolTip("Preserve the casing of the original word (e.g., 'Word' -> 'Replacement', 'WORD' -> 'REPLACEMENT')")
        self.match_case_replace_checkbox.setChecked(False)
        layout.addWidget(self.match_case_replace_checkbox)

        # Action buttons
        button_layout = QVBoxLayout()
        
        self.find_button = QPushButton("Find")
        self.find_button.clicked.connect(self.perform_search)
        button_layout.addWidget(self.find_button)
        
        self.replace_button = QPushButton("Replace")
        self.replace_button.clicked.connect(self.replace_match)
        button_layout.addWidget(self.replace_button)

        self.replace_all_button = QPushButton("Replace All")
        self.replace_all_button.clicked.connect(self.replace_all_matches)
        self.replace_all_button.setStyleSheet("background-color: #047857; color: white; font-weight: bold;")
        button_layout.addWidget(self.replace_all_button)

        self.skip_button = QPushButton("Skip")
        self.skip_button.clicked.connect(self.skip_match)
        button_layout.addWidget(self.skip_button)

        button_layout.addStretch()
        layout.addLayout(button_layout)

    def _load_content(self):
        try:
            log_debug("SearchReviewDialog: _load_content started")
            self.status_label.setText("Searching text...")
            QApplication.processEvents()

            self.find_matches()
            
            self.status_label.setText("Highlighting matches...")
            QApplication.processEvents()

            self.pre_highlight_all_matches()
            self.show_current_item()
            if not self.query:
                self.find_input.setFocus()
            log_debug("SearchReviewDialog: Content loading complete")
        except Exception as e:
            log_error(f"SearchReviewDialog: Error in _load_content: {e}", exc_info=True)
            self.status_label.setText(f"Error loading search results: {e}")

    def find_matches(self):
        """Find all occurrences of the query and populate items_to_review."""
        self.items_to_review.clear()
        
        effective_query = self.query
        if self.ignore_tags:
            effective_query = prepare_text_for_tagless_search(self.query)
            
        if not effective_query:
            return

        lines = self.current_text.split('\n')
        char_offset = 0
        
        for line_idx, line in enumerate(lines):
            # Skip spacer lines
            if self.line_numbers and line_idx < len(self.line_numbers) and self.line_numbers[line_idx] is None:
                char_offset += len(line) + 1
                continue

            if self.ignore_tags:
                clean_line, mapping = prepare_text_for_tagless_search_with_mapping(line)
            else:
                clean_line = line.replace('·', ' ')
                mapping = list(range(len(line)))

            if self.is_fuzzy:
                word_pattern = re.compile(r'\w+')
                for match in word_pattern.finditer(clean_line):
                    word = match.group(0)
                    if is_fuzzy_match(effective_query, word, threshold=0.75):
                        start_in_clean = match.start()
                        end_in_clean = match.end()
                        
                        raw_start = mapping[start_in_clean]
                        raw_end = mapping[end_in_clean - 1] + 1
                        
                        start_pos = char_offset + raw_start
                        end_pos = char_offset + raw_end
                        matched_text = line[raw_start:raw_end]
                        self.items_to_review.append((start_pos, end_pos, matched_text, line_idx))
            else:
                compare_query = effective_query if self.case_sensitive else effective_query.lower()
                compare_line = clean_line if self.case_sensitive else clean_line.lower()
                
                start_search_pos = 0
                while True:
                    match_pos = compare_line.find(compare_query, start_search_pos)
                    if match_pos == -1:
                        break
                    
                    start_in_clean = match_pos
                    end_in_clean = start_in_clean + len(compare_query)
                    
                    raw_start = mapping[start_in_clean]
                    raw_end = mapping[end_in_clean - 1] + 1
                    
                    start_pos = char_offset + raw_start
                    end_pos = char_offset + raw_end
                    matched_text = line[raw_start:raw_end]
                    self.items_to_review.append((start_pos, end_pos, matched_text, line_idx))
                    
                    start_search_pos = match_pos + max(1, len(compare_query))
                
            char_offset += len(line) + 1

    def pre_highlight_all_matches(self):
        """Highlight all matches with a light green background."""
        cursor = self.text_edit.textCursor()
        cursor.select(QTextCursor.SelectionType.Document)
        clear_format = QTextCharFormat()
        clear_format.setBackground(Qt.GlobalColor.transparent)
        cursor.mergeCharFormat(clear_format)

        match_format = QTextCharFormat()
        match_format.setBackground(QColor(144, 238, 144, 100)) # Very light green

        for start, end, word, line_idx in self.items_to_review:
            cursor.setPosition(start)
            cursor.setPosition(end, QTextCursor.MoveMode.KeepAnchor)
            cursor.mergeCharFormat(match_format)

        self.matches_list.clear()
        for start, end, word, line_idx in self.items_to_review:
            if self.line_numbers and line_idx < len(self.line_numbers):
                display_line_num = self.line_numbers[line_idx]
            else:
                display_line_num = self.starting_line_number + line_idx + 1
            
            block_name = self.block_name
            if hasattr(self, 'block_indices') and self.block_indices and line_idx < len(self.block_indices):
                b_idx = self.block_indices[line_idx]
                if b_idx is not None:
                    main_window = self._find_main_window()
                    if main_window and hasattr(main_window, 'data_store') and getattr(main_window.data_store, 'block_names', None):
                        block_name = main_window.data_store.block_names.get(str(b_idx), f"Block {b_idx}")

            # Show some context around the match
            full_line_text = self.current_text.split('\n')[line_idx]
            from utils.utils import convert_spaces_to_dots_for_display
            main_window = self._find_main_window()
            show_dots = getattr(main_window, 'show_multiple_spaces_as_dots', True) if main_window else True
            context = convert_spaces_to_dots_for_display(full_line_text, show_dots)
            self.matches_list.addItem(f"[{block_name}] String {display_line_num}: \"{word}\" in \"{context}\"")

    def show_current_item(self):
        """Display current match and highlight it."""
        if self.current_item_index >= len(self.items_to_review):
            self.status_label.setText("Enter a query to search." if not self.query else "No matches found.")
            self.matches_list.clear()
            for btn in [self.skip_button, self.replace_button, self.replace_all_button, self.prev_button, self.next_button]:
                btn.setEnabled(False)
            return

        start, end, word, line_idx = self.items_to_review[self.current_item_index]
        total = len(self.items_to_review)
        current = self.current_item_index + 1
        
        display_line_num = "Unknown"
        if self.line_numbers and line_idx < len(self.line_numbers):
            display_line_num = self.line_numbers[line_idx]
            
        block_name = self.block_name
        if hasattr(self, 'block_indices') and self.block_indices and line_idx < len(self.block_indices):
            b_idx = self.block_indices[line_idx]
            if b_idx is not None:
                main_window = self._find_main_window()
                if main_window and hasattr(main_window, 'data_store') and getattr(main_window.data_store, 'block_names', None):
                    block_name = main_window.data_store.block_names.get(str(b_idx), f"Block {b_idx}")

        self.status_label.setText(f"Match {current} of {total} | Block: {block_name} | String: {display_line_num}")

        cursor = self.text_edit.textCursor()
        cursor.setPosition(start)
        cursor.setPosition(end, QTextCursor.MoveMode.KeepAnchor)

        fmt = QTextCharFormat()
        fmt.setBackground(QColor("#FFFF00")) # Yellow highlight for active
        cursor.mergeCharFormat(fmt)

        self.text_edit.setTextCursor(cursor)
        self.text_edit.ensureCursorVisible()
        self.matches_list.setCurrentRow(self.current_item_index)

        self.prev_button.setEnabled(self.current_item_index > 0)
        self.next_button.setEnabled(self.current_item_index < len(self.items_to_review) - 1)

    def clear_current_item_highlight(self):
        """Remove yellow highlight and restore light green highlight."""
        if self.current_item_index < len(self.items_to_review):
            start, end, _, _ = self.items_to_review[self.current_item_index]
            cursor = self.text_edit.textCursor()
            cursor.setPosition(start)
            cursor.setPosition(end, QTextCursor.MoveMode.KeepAnchor)
            fmt = QTextCharFormat()
            fmt.setBackground(QColor(144, 238, 144, 100)) # Light green back
            cursor.mergeCharFormat(fmt)

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
        clicked_index = self.matches_list.row(item)
        if clicked_index != self.current_item_index:
            self.clear_current_item_highlight()
            self.current_item_index = clicked_index
            self.show_current_item()
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
                    self._navigate_to_block_and_string(b_idx, string_number)

        from PyQt6.QtWidgets import QPlainTextEdit
        QPlainTextEdit.mouseDoubleClickEvent(self.text_edit, event)

    def perform_search(self):
        # Save changes from current search view state back to project
        self.save_changes_to_project()

        # Update search parameters from checkboxes
        self.query = self.find_input.text()
        self.case_sensitive = self.case_sensitive_checkbox.isChecked()
        self.is_fuzzy = self.fuzzy_checkbox.isChecked()
        self.search_in_original = self.original_checkbox.isChecked()
        self.ignore_tags = self.no_tags_checkbox.isChecked()
        
        # Dynamic search across the entire project
        self.rebuild_text_from_project()
            
        self.clear_current_item_highlight()
        self.find_matches()
        self.pre_highlight_all_matches()
        self.current_item_index = 0
        
        # Enable buttons for the new search
        for btn in [self.skip_button, self.replace_button, self.replace_all_button, self.prev_button, self.next_button]:
            btn.setEnabled(True)
            
        self.show_current_item()

    def rebuild_text_by_options(self):
        main_window = self._find_main_window()
        if not main_window or not hasattr(main_window, 'data_processor'):
            return
            
        text_parts = []
        for b_idx, s_idx in self.unique_string_indices:
            if self.search_in_original:
                text = main_window.data_processor._get_string_from_source(
                    b_idx, s_idx, main_window.data_store.data, "dialog_original"
                )
            else:
                text, _ = main_window.data_processor.get_current_string_text(b_idx, s_idx)
                
            if text is None:
                text = ""
            text_parts.append(text)
            
        raw_text = '\n'.join(text_parts)
        
        flat_line_numbers = []
        flat_block_indices = []
        for (b_idx, s_idx), text in zip(self.unique_string_indices, text_parts):
            subline_count = text.count('\n') + 1
            for _ in range(subline_count):
                flat_line_numbers.append(s_idx)
                flat_block_indices.append(b_idx)
                
        self.current_text = raw_text
        self.line_numbers = flat_line_numbers
        self.block_indices = flat_block_indices
        
        self._process_text_spacing_and_line_numbers()
        self._apply_zebra_striping()

    def _process_text_spacing_and_line_numbers(self):
        if not hasattr(self, 'block_indices') or not self.block_indices:
            super()._process_text_spacing_and_line_numbers()
            return

        line_count = self.current_text.count('\n') + 1

        if self.line_numbers and len(self.line_numbers) >= line_count:
            text_lines = self.current_text.split('\n')
            text_with_spacing = []
            new_line_numbers = []
            new_block_indices = []
            display_line_numbers = []
            subline_numbers = []

            prev_pair = (None, None)
            current_sub_idx = 0
            for i in range(line_count):
                current_line_num = self.line_numbers[i]
                current_block_idx = self.block_indices[i]
                current_pair = (current_block_idx, current_line_num)

                if current_pair != prev_pair:
                    display_line_numbers.append(current_line_num)
                    prev_pair = current_pair
                    current_sub_idx = 1
                else:
                    display_line_numbers.append(None)
                    current_sub_idx += 1

                text_with_spacing.append(text_lines[i] if i < len(text_lines) else '')
                new_line_numbers.append(current_line_num)
                new_block_indices.append(current_block_idx)
                subline_numbers.append(current_sub_idx)

            self.current_text = '\n'.join(text_with_spacing)
            self.line_numbers = new_line_numbers
            self.block_indices = new_block_indices
            self.text_edit.setPlainText(self.current_text)

            self.text_edit.custom_line_numbers = display_line_numbers
            self.text_edit.custom_subline_numbers = subline_numbers
            self.text_edit.custom_message_numbers = new_line_numbers
            self.text_edit.updateLineNumberAreaWidth(0)

    def save_changes_to_project(self):
        main_window = self._find_main_window()
        if not main_window or not hasattr(main_window, 'data_store'):
            return

        corrected_text = self.get_corrected_text()
        if not corrected_text:
            return
            
        corrected_lines = corrected_text.split('\n')
        if not self.line_numbers or not self.block_indices:
            return

        grouped_lines = {}
        for line_text, s_idx, b_idx in zip(corrected_lines, self.line_numbers, self.block_indices):
            if s_idx is not None and b_idx is not None:
                key = (b_idx, s_idx)
                if key not in grouped_lines:
                    grouped_lines[key] = []
                grouped_lines[key].append(line_text)

        edited_data = main_window.data_store.edited_data
        changes_made = False
        changed_blocks = set()

        undo_manager = getattr(main_window, "undo_manager", None)
        if undo_manager:
            undo_manager.begin_group()

        for (b_idx, string_idx), lines_list in grouped_lines.items():
            new_text = '\n'.join(lines_list)
            old_text, _ = main_window.data_processor.get_current_string_text(b_idx, string_idx)
            if new_text != old_text:
                key = (b_idx, string_idx)
                edited_data[key] = new_text
                changes_made = True
                changed_blocks.add(b_idx)
                
                if b_idx == main_window.data_store.current_block_idx and string_idx == main_window.data_store.current_string_idx:
                    if hasattr(main_window, 'text_operation_handler'):
                        main_window.text_operation_handler.sync_subline_asterisks(
                            b_idx, string_idx, new_text
                        )

        if undo_manager:
            undo_manager.end_group()

        if changes_made:
            for b_idx in changed_blocks:
                if hasattr(main_window, 'project_manager'):
                    main_window.project_manager.mark_block_unsaved(b_idx)
            if hasattr(main_window, 'ui_updater'):
                main_window.ui_updater.update_text_views()
                main_window.ui_updater.update_block_list()

    def rebuild_text_from_project(self):
        main_window = self._find_main_window()
        if not main_window or not hasattr(main_window, 'data_store') or not main_window.data_store.data:
            return

        query = self.query
        case_sensitive = self.case_sensitive
        search_in_original = self.search_in_original
        ignore_tags = self.ignore_tags
        is_fuzzy = self.is_fuzzy

        all_lines = []
        for b_idx in range(len(main_window.data_store.data)):
            block_data = main_window.data_store.data[b_idx]
            if not isinstance(block_data, list):
                continue
            for string_idx in range(len(block_data)):
                if search_in_original:
                    text = main_window.data_processor._get_string_from_source(
                        b_idx, string_idx, main_window.data_store.data, "dialog_original"
                    )
                else:
                    text, _ = main_window.data_processor.get_current_string_text(b_idx, string_idx)
                if text is not None:
                    all_lines.append((b_idx, string_idx, text))

        text_parts = []
        line_numbers = []
        block_indices = []
        unique_string_indices = []

        import re
        from utils.utils import prepare_text_for_tagless_search, is_fuzzy_match

        effective_query = query
        if ignore_tags and query:
            effective_query = prepare_text_for_tagless_search(query)

        if query and effective_query:
            if is_fuzzy:
                word_pattern = re.compile(r'\w+')
                for b_idx, string_idx, text in all_lines:
                    if ignore_tags:
                        text_for_search = prepare_text_for_tagless_search(text)
                    else:
                        text_for_search = text.replace('·', ' ')

                    has_match = False
                    for match in word_pattern.finditer(text_for_search):
                        word = match.group(0)
                        if is_fuzzy_match(effective_query, word, threshold=0.75):
                            has_match = True
                            break
                    if has_match:
                        text_parts.append(text)
                        pair = (b_idx, string_idx)
                        if not unique_string_indices or unique_string_indices[-1] != pair:
                            unique_string_indices.append(pair)
                        subline_count = text.count('\n') + 1
                        for _ in range(subline_count):
                            line_numbers.append(string_idx)
                            block_indices.append(b_idx)
            else:
                compare_query = effective_query if case_sensitive else effective_query.lower()
                for b_idx, string_idx, text in all_lines:
                    if ignore_tags:
                        text_for_search = prepare_text_for_tagless_search(text)
                    else:
                        text_for_search = text.replace('·', ' ')

                    compare_text = text_for_search if case_sensitive else text_for_search.lower()
                    if compare_query in compare_text:
                        text_parts.append(text)
                        pair = (b_idx, string_idx)
                        if not unique_string_indices or unique_string_indices[-1] != pair:
                            unique_string_indices.append(pair)
                        subline_count = text.count('\n') + 1
                        for _ in range(subline_count):
                            line_numbers.append(string_idx)
                            block_indices.append(b_idx)

        self.unique_string_indices = unique_string_indices
        self.current_text = '\n'.join(text_parts)
        self.line_numbers = line_numbers
        self.block_indices = block_indices
        
        self._process_text_spacing_and_line_numbers()
        self._apply_zebra_striping()
