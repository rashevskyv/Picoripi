# Dialog for interactive searching and replacing of text in a block
from PyQt5.QtWidgets import (QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QLineEdit, QListWidget, QApplication)
from PyQt5.QtCore import Qt, QTimer
from PyQt5.QtGui import QTextCursor, QTextCharFormat, QColor
from typing import List
import re
from utils.logging_utils import log_debug, log_error
from dialogs.base_text_review_dialog import BaseTextReviewDialog

class SearchReviewDialog(BaseTextReviewDialog):
    """Interactive dialog for reviewing search results in a block with a replace option."""

    def __init__(self, parent, text: str, query: str, starting_line_number: int = 0, line_numbers: List[int] = None, case_sensitive: bool = False, is_fuzzy: bool = False):
        log_debug("SearchReviewDialog: __init__ started")
        self.query = query
        self.case_sensitive = case_sensitive
        self.is_fuzzy = is_fuzzy
        self.starting_line_number = starting_line_number
        
        super().__init__(parent, "Advanced Search & Replace", text, line_numbers)
        
        # Mapping base class variables
        self.matches = self.items_to_review 

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
        layout.addWidget(QLabel("Find:"))
        self.find_input = QLineEdit()
        self.find_input.setText(self.query)
        self.find_input.setPlaceholderText("Enter search query...")
        self.find_input.textChanged.connect(self.update_search_query)
        layout.addWidget(self.find_input)
        
        layout.addWidget(QLabel("Replace with:"))
        self.replace_input = QLineEdit()
        self.replace_input.setPlaceholderText("Enter replacement text...")
        layout.addWidget(self.replace_input)

        # Action buttons
        button_layout = QVBoxLayout()
        
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
        if not self.query:
            return

        lines = self.current_text.split('\n')
        char_offset = 0
        
        # Build search regex or use simple string search
        if self.is_fuzzy:
            word_pattern = re.compile(r'\w+')
            from utils.utils import is_fuzzy_match
            
            for line_idx, line in enumerate(lines):
                # Skip spacer lines
                if self.line_numbers and line_idx < len(self.line_numbers) and self.line_numbers[line_idx] is None:
                    char_offset += len(line) + 1
                    continue

                line_cleaned = line.replace('·', ' ')
                for match in word_pattern.finditer(line_cleaned):
                    word = match.group(0)
                    if is_fuzzy_match(self.query, word, threshold=0.75):
                        start_pos = char_offset + match.start()
                        end_pos = char_offset + match.end()
                        self.items_to_review.append((start_pos, end_pos, word, line_idx))
                char_offset += len(line) + 1
        else:
            compare_query = self.query if self.case_sensitive else self.query.lower()
            
            for line_idx, line in enumerate(lines):
                # Skip spacer lines
                if self.line_numbers and line_idx < len(self.line_numbers) and self.line_numbers[line_idx] is None:
                    char_offset += len(line) + 1
                    continue

                line_cleaned = line.replace('·', ' ')
                compare_line = line_cleaned if self.case_sensitive else line_cleaned.lower()
                
                start_search_pos = 0
                while True:
                    match_pos = compare_line.find(compare_query, start_search_pos)
                    if match_pos == -1:
                        break
                    
                    start_pos = char_offset + match_pos
                    end_pos = start_pos + len(compare_query)
                    matched_text = line_cleaned[match_pos:match_pos + len(compare_query)]
                    self.items_to_review.append((start_pos, end_pos, matched_text, line_idx))
                    
                    start_search_pos = match_pos + max(1, len(compare_query))
                
                char_offset += len(line) + 1

    def pre_highlight_all_matches(self):
        """Highlight all matches with a light green background."""
        cursor = self.text_edit.textCursor()
        cursor.select(QTextCursor.Document)
        clear_format = QTextCharFormat()
        clear_format.setBackground(Qt.transparent)
        cursor.mergeCharFormat(clear_format)

        match_format = QTextCharFormat()
        match_format.setBackground(QColor(144, 238, 144, 100)) # Very light green

        for start, end, word, line_idx in self.items_to_review:
            cursor.setPosition(start)
            cursor.setPosition(end, QTextCursor.KeepAnchor)
            cursor.mergeCharFormat(match_format)

        self.matches_list.clear()
        for start, end, word, line_idx in self.items_to_review:
            if self.line_numbers and line_idx < len(self.line_numbers):
                display_line_num = self.line_numbers[line_idx]
            else:
                display_line_num = self.starting_line_number + line_idx + 1
            
            # Show some context around the match
            full_line_text = self.current_text.split('\n')[line_idx]
            from utils.utils import convert_spaces_to_dots_for_display
            main_window = self._find_main_window()
            show_dots = getattr(main_window, 'show_multiple_spaces_as_dots', True) if main_window else True
            context = convert_spaces_to_dots_for_display(full_line_text, show_dots)
            self.matches_list.addItem(f"Line {display_line_num}: \"{word}\" in \"{context}\"")

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
        self.status_label.setText(f"Match {current} of {total}")

        cursor = self.text_edit.textCursor()
        cursor.setPosition(start)
        cursor.setPosition(end, QTextCursor.KeepAnchor)

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
            cursor.setPosition(end, QTextCursor.KeepAnchor)
            fmt = QTextCharFormat()
            fmt.setBackground(QColor(144, 238, 144, 100)) # Light green back
            cursor.mergeCharFormat(fmt)

    def jump_to_item_from_list(self, item):
        clicked_index = self.matches_list.row(item)
        if clicked_index != self.current_item_index:
            self.clear_current_item_highlight()
            self.current_item_index = clicked_index
            self.show_current_item()
            if clicked_index < len(self.items_to_review):
                _, _, _, line_idx = self.items_to_review[clicked_index]
                if self.line_numbers and line_idx < len(self.line_numbers):
                    self._navigate_to_string_in_main_window(self.line_numbers[line_idx])

    def skip_match(self):
        self.go_to_next_item()

    def replace_match(self):
        if self.current_item_index >= len(self.items_to_review): 
            return
        
        replacement = self.replace_input.text()
        start, end, word, line_idx = self.items_to_review[self.current_item_index]

        self.current_text = self.current_text[:start] + replacement + self.current_text[end:]
        self.text_edit.setPlainText(self.current_text)
        self._apply_zebra_striping()

        length_diff = len(replacement) - len(word)
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
        
        # Sort items in reverse order to replace without shifting offsets of previous ones
        sorted_items = sorted(self.items_to_review, key=lambda x: x[0], reverse=True)
        
        temp_text = self.current_text
        for start, end, word, _ in sorted_items:
            temp_text = temp_text[:start] + replacement + temp_text[end:]
            
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
                self._navigate_to_string_in_main_window(self.line_numbers[line_idx])

    def update_search_query(self):
        new_query = self.find_input.text()
        if new_query != self.query:
            self.clear_current_item_highlight()
            self.query = new_query
            self.find_matches()
            self.pre_highlight_all_matches()
            self.current_item_index = 0
            
            # Enable buttons for the new search
            for btn in [self.skip_button, self.replace_button, self.replace_all_button, self.prev_button, self.next_button]:
                btn.setEnabled(True)
                
            self.show_current_item()
