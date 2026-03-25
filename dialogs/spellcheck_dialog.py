# --- START OF FILE dialogs/spellcheck_dialog.py ---
# Dialog for interactive spellchecking of selected text
from PyQt5.QtWidgets import (QVBoxLayout, QLabel, QPushButton, QListWidget, QDialogButtonBox, QApplication)
from PyQt5.QtCore import Qt, QTimer
from PyQt5.QtGui import QTextCursor, QTextCharFormat, QColor
from typing import List
import re
from utils.logging_utils import log_debug, log_error
from dialogs.base_text_review_dialog import BaseTextReviewDialog

class SpellcheckDialog(BaseTextReviewDialog):
    """Interactive dialog for spellchecking text with suggestions."""

    def __init__(self, parent, text: str, spellchecker_manager, starting_line_number: int = 0, line_numbers: List[int] = None):
        log_debug("SpellcheckDialog: __init__ started")
        self.spellchecker_manager = spellchecker_manager
        self.starting_line_number = starting_line_number # Deprecated, kept for compatibility
        
        super().__init__(parent, "Spellcheck", text, line_numbers)
        
        # Mapping base class variables to spellcheck specific names for easier logic
        # misspelled_words will be used as items_to_review
        self.misspelled_words = self.items_to_review 

        log_debug("SpellcheckDialog: Starting content loading")
        # Load content after a small delay to let dialog appear
        QTimer.singleShot(50, self._load_content)

    def setup_left_panel(self, layout: QVBoxLayout):
        layout.addWidget(QLabel("Misspelled Words:"))
        self.misspelled_list = QListWidget()
        self.misspelled_list.itemClicked.connect(self.jump_to_item_from_list)
        self.misspelled_list.itemDoubleClicked.connect(self._on_item_double_click)
        layout.addWidget(self.misspelled_list)

    def setup_right_panel(self, layout: QVBoxLayout):
        self.word_label = QLabel("Word:")
        layout.addWidget(self.word_label)

        layout.addWidget(QLabel("Suggestions:"))
        self.suggestions_list = QListWidget()
        self.suggestions_list.itemDoubleClicked.connect(self.replace_with_suggestion)
        layout.addWidget(self.suggestions_list)

        # Action buttons
        button_layout = QVBoxLayout()
        self.ignore_button = QPushButton("Ignore")
        self.ignore_button.clicked.connect(self.ignore_word)
        button_layout.addWidget(self.ignore_button)

        self.ignore_all_button = QPushButton("Ignore All")
        self.ignore_all_button.clicked.connect(self.ignore_all_word)
        button_layout.addWidget(self.ignore_all_button)

        self.replace_button = QPushButton("Replace")
        self.replace_button.clicked.connect(self.replace_word)
        button_layout.addWidget(self.replace_button)

        self.add_to_dict_button = QPushButton("Add to Dictionary")
        self.add_to_dict_button.clicked.connect(self.add_to_dictionary)
        button_layout.addWidget(self.add_to_dict_button)

        button_layout.addStretch()
        layout.addLayout(button_layout)

    def _load_content(self):
        """Load spellcheck content after dialog is shown."""
        try:
            log_debug("SpellcheckDialog: _load_content started")
            self.status_label.setText("Analyzing text...")
            QApplication.processEvents()

            self.find_misspelled_words()
            
            self.status_label.setText("Highlighting errors...")
            QApplication.processEvents()

            self.pre_highlight_all_misspelled_words()
            self.show_current_item()
            log_debug("SpellcheckDialog: Content loading complete")
        except Exception as e:
            log_error(f"SpellcheckDialog: Error in _load_content: {e}", exc_info=True)
            self.status_label.setText(f"Error loading spellchecker: {e}")

    def find_misspelled_words(self):
        """Find all misspelled words and populate items_to_review."""
        self.items_to_review.clear()
        word_pattern = re.compile(r'[a-zA-Zа-яА-ЯіїІїЄєґҐ\']+')

        ignore_pattern = None
        main_window = self._find_main_window()
        if main_window and hasattr(main_window, 'current_game_rules'):
            ignore_pattern = main_window.current_game_rules.get_spellcheck_ignore_pattern()
        
        ignore_re = re.compile(ignore_pattern) if ignore_pattern else None
        lines = self.current_text.split('\n')
        char_offset = 0
        
        for line_idx, line in enumerate(lines):
            line_cleaned = line
            if ignore_re:
                line_cleaned = ignore_re.sub(lambda m: ' ' * len(m.group(0)), line)
            
            line_for_detection = line_cleaned.replace('·', ' ')
            for match in word_pattern.finditer(line_for_detection):
                word = match.group(0)
                if self.spellchecker_manager.is_misspelled(word):
                    start_pos = char_offset + match.start()
                    end_pos = char_offset + match.end()
                    self.items_to_review.append((start_pos, end_pos, word, line_idx))
                    
            char_offset += len(line) + 1

    def pre_highlight_all_misspelled_words(self):
        """Highlight all misspelled words with red wavy underline."""
        cursor = self.text_edit.textCursor()
        cursor.select(QTextCursor.Document)
        clear_format = QTextCharFormat()
        clear_format.setUnderlineStyle(QTextCharFormat.NoUnderline)
        cursor.mergeCharFormat(clear_format)

        misspell_format = QTextCharFormat()
        misspell_format.setUnderlineStyle(QTextCharFormat.SpellCheckUnderline)
        misspell_format.setUnderlineColor(QColor("red"))

        for start, end, word, line_idx in self.items_to_review:
            cursor.setPosition(start)
            cursor.setPosition(end, QTextCursor.KeepAnchor)
            cursor.mergeCharFormat(misspell_format)

        self.misspelled_list.clear()
        for start, end, word, line_idx in self.items_to_review:
            if self.line_numbers and line_idx < len(self.line_numbers):
                display_line_num = self.line_numbers[line_idx]
            else:
                display_line_num = self.starting_line_number + line_idx + 1
            self.misspelled_list.addItem(f"Line {display_line_num}: {word}")

    def show_current_item(self):
        """Display current misspelled word and its suggestions."""
        if self.current_item_index >= len(self.items_to_review):
            self.status_label.setText("Spellcheck complete!")
            self.word_label.setText("No more misspelled words.")
            self.suggestions_list.clear()
            for btn in [self.ignore_button, self.ignore_all_button, self.replace_button, self.add_to_dict_button, self.prev_button, self.next_button]:
                btn.setEnabled(False)
            return

        start, end, word, line_idx = self.items_to_review[self.current_item_index]
        total = len(self.items_to_review)
        current = self.current_item_index + 1
        self.status_label.setText(f"Word {current} of {total}")

        if self.line_numbers and line_idx < len(self.line_numbers):
            display_line_num = self.line_numbers[line_idx]
        else:
            display_line_num = self.starting_line_number + line_idx + 1
        self.word_label.setText(f"Line {display_line_num}: \"{word}\"")

        cursor = self.text_edit.textCursor()
        cursor.setPosition(start)
        cursor.setPosition(end, QTextCursor.KeepAnchor)

        fmt = QTextCharFormat()
        fmt.setBackground(QColor("#FFFF00"))
        fmt.setUnderlineStyle(QTextCharFormat.SpellCheckUnderline)
        fmt.setUnderlineColor(QColor("red"))
        cursor.mergeCharFormat(fmt)

        self.text_edit.setTextCursor(cursor)
        self.text_edit.ensureCursorVisible()
        self.misspelled_list.setCurrentRow(self.current_item_index)

        self.suggestions_list.clear()
        suggestions = self.spellchecker_manager.get_suggestions(word)
        for suggestion in suggestions[:10]:
            self.suggestions_list.addItem(suggestion)
        if suggestions:
            self.suggestions_list.setCurrentRow(0)

        self.prev_button.setEnabled(self.current_item_index > 0)
        self.next_button.setEnabled(self.current_item_index < len(self.items_to_review) - 1)

    def clear_current_item_highlight(self):
        """Remove yellow highlight from current word."""
        if self.current_item_index < len(self.items_to_review):
            start, end, _, _ = self.items_to_review[self.current_item_index]
            cursor = self.text_edit.textCursor()
            cursor.setPosition(start)
            cursor.setPosition(end, QTextCursor.KeepAnchor)
            fmt = QTextCharFormat()
            fmt.setBackground(Qt.transparent)
            fmt.setUnderlineStyle(QTextCharFormat.SpellCheckUnderline)
            fmt.setUnderlineColor(QColor("red"))
            cursor.mergeCharFormat(fmt)

    def jump_to_item_from_list(self, item):
        clicked_index = self.misspelled_list.row(item)
        if clicked_index != self.current_item_index:
            self.clear_current_item_highlight()
            self.current_item_index = clicked_index
            self.show_current_item()
            if clicked_index < len(self.items_to_review):
                _, _, _, line_idx = self.items_to_review[clicked_index]
                if self.line_numbers and line_idx < len(self.line_numbers):
                    self._navigate_to_string_in_main_window(self.line_numbers[line_idx])

    def ignore_word(self):
        self.go_to_next_item()

    def ignore_all_word(self):
        if self.current_item_index >= len(self.items_to_review): return
        _, _, word, _ = self.items_to_review[self.current_item_index]
        self.items_to_review[:] = [item for item in self.items_to_review if item[2].lower() != word.lower()]
        self.pre_highlight_all_misspelled_words()
        self.show_current_item()

    def replace_word(self):
        item = self.suggestions_list.currentItem()
        if item: self.replace_with_suggestion(item)

    def replace_with_suggestion(self, item):
        if self.current_item_index >= len(self.items_to_review): return
        start, end, word, _ = self.items_to_review[self.current_item_index]
        replacement = item.text()

        self.current_text = self.current_text[:start] + replacement + self.current_text[end:]
        self.text_edit.setPlainText(self.current_text)
        self._apply_zebra_striping()

        length_diff = len(replacement) - len(word)
        self.items_to_review.pop(self.current_item_index)
        for i in range(self.current_item_index, len(self.items_to_review)):
            s, e, w, l = self.items_to_review[i]
            self.items_to_review[i] = (s + length_diff, e + length_diff, w, l)

        self.pre_highlight_all_misspelled_words()
        self.show_current_item()

    def add_to_dictionary(self):
        if self.current_item_index >= len(self.items_to_review): return
        _, _, word, _ = self.items_to_review[self.current_item_index]
        self.spellchecker_manager.add_to_custom_dictionary(word)
        self.items_to_review[:] = [item for item in self.items_to_review if item[2].lower() != word.lower()]
        self.pre_highlight_all_misspelled_words()
        self.show_current_item()

    def _on_item_double_click(self, item):
        index = self.misspelled_list.row(item)
        if index < len(self.items_to_review):
            _, _, _, line_idx = self.items_to_review[index]
            if self.line_numbers and line_idx < len(self.line_numbers):
                self._navigate_to_string_in_main_window(self.line_numbers[line_idx])
