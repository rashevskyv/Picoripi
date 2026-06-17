# Dialog for interactive spellchecking of selected text
from PyQt6.QtWidgets import (QVBoxLayout, QLabel, QPushButton, QListWidget, QDialogButtonBox, QApplication)
from PyQt6.QtCore import Qt, QTimer
from PyQt6.QtGui import QTextCursor, QTextCharFormat, QColor
from typing import List
import re
from utils.logging_utils import log_debug, log_error
from dialogs.base_text_review_dialog import BaseTextReviewDialog

class SpellcheckDialog(BaseTextReviewDialog):
    """Interactive dialog for spellchecking text with suggestions."""

    def __init__(self, parent, text: str, spellchecker_manager, starting_line_number: int = 0, line_numbers: List[int] = None, block_idx: int = -1, block_indices: List[int] = None):
        log_debug("SpellcheckDialog: __init__ started")
        self.spellchecker_manager = spellchecker_manager
        self.starting_line_number = starting_line_number # Deprecated, kept for compatibility
        self.block_indices = block_indices if block_indices is not None else ([block_idx] * len(line_numbers) if line_numbers else [])
        
        super().__init__(parent, "Spellcheck", text, line_numbers, block_idx)
        
        # Mapping base class variables to spellcheck specific names for easier logic
        # misspelled_words will be used as items_to_review
        self.misspelled_words = self.items_to_review 

        log_debug("SpellcheckDialog: Starting content loading")
        # Load content after a small delay to let dialog appear
        QTimer.singleShot(50, self._load_content)

    def _get_block_name(self, block_idx: int) -> str:
        if block_idx is None:
            return "Unknown Block"
        main_window = self._find_main_window()
        if main_window and hasattr(main_window, 'data_store') and getattr(main_window.data_store, 'block_names', None):
            return main_window.data_store.block_names.get(str(block_idx), f"Block {block_idx}")
        return f"Block {block_idx}"

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
        cursor.select(QTextCursor.SelectionType.Document)
        clear_format = QTextCharFormat()
        clear_format.setUnderlineStyle(QTextCharFormat.UnderlineStyle.NoUnderline)
        cursor.mergeCharFormat(clear_format)

        misspell_format = QTextCharFormat()
        misspell_format.setUnderlineStyle(QTextCharFormat.UnderlineStyle.SpellCheckUnderline)
        misspell_format.setUnderlineColor(QColor("red"))

        for start, end, word, line_idx in self.items_to_review:
            cursor.setPosition(start)
            cursor.setPosition(end, QTextCursor.MoveMode.KeepAnchor)
            cursor.mergeCharFormat(misspell_format)

        self.misspelled_list.clear()
        for start, end, word, line_idx in self.items_to_review:
            if self.line_numbers and line_idx < len(self.line_numbers):
                display_line_num = self.line_numbers[line_idx] + 1
            else:
                display_line_num = self.starting_line_number + line_idx + 1
            
            if self.block_indices and line_idx < len(self.block_indices):
                b_name = self._get_block_name(self.block_indices[line_idx])
            else:
                b_name = self.block_name
            self.misspelled_list.addItem(f"[{b_name}] String {display_line_num}: {word}")

    def show_current_item(self, from_click=False):
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

        if self.line_numbers and line_idx < len(self.line_numbers):
            display_line_num = self.line_numbers[line_idx] + 1
        else:
            display_line_num = self.starting_line_number + line_idx + 1
            
            
        if self.block_indices and line_idx < len(self.block_indices):
            b_name = self._get_block_name(self.block_indices[line_idx])
        else:
            b_name = self.block_name
            
        self.status_label.setText(f"Word {current} of {total} | Block: {b_name} | String: {display_line_num}")
        self.word_label.setText(f"[{b_name}] String {display_line_num}: \"{word}\"")

        cursor = self.text_edit.textCursor()
        cursor.setPosition(start)
        cursor.setPosition(end, QTextCursor.MoveMode.KeepAnchor)

        fmt = QTextCharFormat()
        fmt.setBackground(QColor("#FFFF00"))
        fmt.setUnderlineStyle(QTextCharFormat.UnderlineStyle.SpellCheckUnderline)
        fmt.setUnderlineColor(QColor("red"))
        cursor.mergeCharFormat(fmt)

        self.text_edit.setTextCursor(cursor)
        self.text_edit.ensureCursorVisible()
        if not from_click:
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
            cursor.setPosition(end, QTextCursor.MoveMode.KeepAnchor)
            fmt = QTextCharFormat()
            fmt.setBackground(Qt.GlobalColor.transparent)
            fmt.setUnderlineStyle(QTextCharFormat.UnderlineStyle.SpellCheckUnderline)
            fmt.setUnderlineColor(QColor("red"))
            cursor.mergeCharFormat(fmt)

    def jump_to_item_from_list(self, item):
        modifiers = QApplication.keyboardModifiers()
        if bool(modifiers & (Qt.KeyboardModifier.ControlModifier | Qt.KeyboardModifier.ShiftModifier)):
            return
            
        clicked_index = self.misspelled_list.row(item)
        if clicked_index != self.current_item_index:
            self.clear_current_item_highlight()
            self.current_item_index = clicked_index
            self.show_current_item(from_click=True)
            
            if clicked_index < len(self.items_to_review):
                _, _, _, line_idx = self.items_to_review[clicked_index]
                if self.line_numbers and line_idx < len(self.line_numbers):
                    b_idx = self.block_indices[line_idx] if (self.block_indices and line_idx < len(self.block_indices)) else self.block_idx
                    self._navigate_to_block_and_string(b_idx, self.line_numbers[line_idx])

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
                b_idx = self.block_indices[line_idx] if (self.block_indices and line_idx < len(self.block_indices)) else self.block_idx
                self._navigate_to_block_and_string(b_idx, self.line_numbers[line_idx])

    def save_changes_to_project(self):
        parent = self.parentWidget()
        from dialogs.search_review_dialog import SearchReviewDialog
        search_dialog = None
        p = parent
        while p:
            if isinstance(p, SearchReviewDialog):
                search_dialog = p
                break
            p = p.parentWidget() if hasattr(p, 'parentWidget') else None

        corrected_text = self.get_corrected_text()
        
        if search_dialog:
            search_dialog.current_text = corrected_text
            search_dialog.text_edit.setPlainText(corrected_text)
            search_dialog._apply_zebra_striping()
            search_dialog.save_changes_to_project()
        else:
            if not self.mw or not hasattr(self.mw, 'data_processor'):
                return
            
            corrected_lines = corrected_text.split('\n')
            changes_made = False
            changed_blocks = set()
            
            undo_manager = getattr(self.mw, 'undo_manager', None)
            if undo_manager:
                undo_manager.begin_group()
                
            try:
                for i, line_num in enumerate(self.line_numbers):
                    if line_num is not None and i < len(corrected_lines):
                        b_idx = self.block_idx
                        if hasattr(self, 'block_indices') and self.block_indices and i < len(self.block_indices):
                            b_idx = self.block_indices[i]
                            if b_idx is None:
                                b_idx = self.block_idx
                                
                        old_text, _ = self.mw.data_processor.get_current_string_text(b_idx, line_num)
                        new_line_text = corrected_lines[i]
                        
                        if new_line_text != old_text:
                            self.mw.data_processor.update_edited_data(b_idx, line_num, new_line_text, action_type="SPELLCHECK", skip_ui_refresh=True)
                            changes_made = True
                            changed_blocks.add(b_idx)
                            
                            if b_idx == self.mw.data_store.current_block_idx and line_num == self.mw.data_store.current_string_idx:
                                if hasattr(self.mw, 'text_operation_handler'):
                                    self.mw.text_operation_handler.sync_subline_asterisks(
                                        b_idx, line_num, new_line_text
                                    )
            finally:
                if undo_manager:
                    undo_manager.end_group("SPELLCHECK")
                    
            if changes_made:
                for b_idx in changed_blocks:
                    if hasattr(self.mw, 'data_store'):
                        self.mw.data_store.mark_dirty(b_idx)
                    if hasattr(self.mw, 'ui_updater'):
                        self.mw.ui_updater.update_block_item_text_with_problem_count(b_idx)
                
                current_block_idx = getattr(self.mw.data_store, 'current_block_idx', -1)
                if hasattr(self.mw, 'ui_updater') and current_block_idx in changed_blocks:
                    self.mw.ui_updater.populate_strings_for_block(current_block_idx, force=True)
                    self.mw.ui_updater.update_text_views()
                    
                if hasattr(self.mw, 'editor_operation_handler') and self.mw.editor_operation_handler:
                    self.mw.editor_operation_handler.text_edited()

    def done(self, r):
        self.save_changes_to_project()
        super().done(r)
