# Dialog for interactive searching and replacing of text in a block
from PyQt6.QtWidgets import (QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QLineEdit, QListWidget, QApplication, QListWidgetItem, QMenu)
from PyQt6.QtCore import Qt, QTimer, QThread, pyqtSignal
from PyQt6.QtGui import QTextCursor, QTextCharFormat, QColor
from typing import List, Tuple
import re
from utils.logging_utils import log_debug, log_error
from dialogs.base_text_review_dialog import BaseTextReviewDialog
from utils.utils import ALL_TAGS_PATTERN, FORCED_ALIAS_PATTERN, prepare_text_for_tagless_search, is_fuzzy_match, find_smart_matches, clean_and_map_punctuation, is_control_modifier_pressed

from dialogs.search.search_worker import SearchWorker
from dialogs.search.search_utils import (
    map_forced_aliases,
    map_remove_all_tags,
    prepare_text_for_tagless_search_with_mapping,
    adjust_replacement_case
)

class SearchReviewDialog(BaseTextReviewDialog):
    """Interactive dialog for reviewing search results in a block with a replace option."""

    def __init__(self, parent, text: str, query: str, starting_line_number: int = 0, line_numbers: List[int] = None, case_sensitive: bool = False, is_fuzzy: bool = False, search_in_original: bool = False, ignore_tags: bool = True, block_idx: int = -1, block_indices: List[int] = None, force_async: bool = False):
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
        self.force_async = force_async

        # Mapping base class variables
        self.matches = self.items_to_review
        self._is_closing = False

        # Rebuild text if we are searching in the original source
        if self.search_in_original:
            self.rebuild_text_by_options()

        log_debug("SearchReviewDialog: Starting content loading")
        is_test = (parent is None or bool(getattr(parent, '_is_test_mode', False))) and not self.force_async
        if not is_test:
            QTimer.singleShot(50, self._load_content)

    def setup_left_panel(self, layout: QVBoxLayout):
        layout.addWidget(QLabel("Search Matches:"))
        self.matches_list = QListWidget()
        self.matches_list.setSelectionMode(QListWidget.SelectionMode.ExtendedSelection)
        self.matches_list.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.matches_list.customContextMenuRequested.connect(self.show_context_menu)
        self.matches_list.itemClicked.connect(self.jump_to_item_from_list)
        self.matches_list.itemDoubleClicked.connect(self._on_item_double_click)
        layout.addWidget(self.matches_list)

        self.selection_status_label = QLabel("Selected: 0")
        layout.addWidget(self.selection_status_label)
        self.matches_list.itemSelectionChanged.connect(self.update_selection_status)

        # Track Ctrl state at the moment of right-click for context menu
        self._ctrl_was_pressed_at_right_click = False
        self.matches_list.viewport().installEventFilter(self)

    def update_selection_status(self):
        count = len(self.matches_list.selectedItems())
        self.selection_status_label.setText(f"Selected: {count}")

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

            import sys
            parent = self.parentWidget()
            is_test = ('pytest' in sys.modules or parent is None or bool(getattr(parent, '_is_test_mode', False))) and not getattr(self, 'force_async', False)

            if is_test:
                log_debug("SearchReviewDialog: Running in test mode, using synchronous loading")
                self.find_matches()
                self.status_label.setText("Highlighting matches...")
                self.pre_highlight_all_matches()
                self.show_current_item()
                if not self.query:
                    self.find_input.setFocus()
                log_debug("SearchReviewDialog: Content loading complete")
                return

            self.set_controls_enabled(False)
            self.show_progress_ui(True)

            params = {
                'text': self.current_text,
                'query': self.query,
                'ignore_tags': self.ignore_tags,
                'is_fuzzy': self.is_fuzzy,
                'case_sensitive': self.case_sensitive,
                'line_numbers': self.line_numbers,
                'block_idx': self.block_idx,
                'block_indices': self.block_indices
            }

            self.search_worker = SearchWorker('local', params)
            self.search_worker.progress.connect(self.progress_bar.setValue)
            self.search_worker.finished.connect(self._on_search_finished)
            self.search_worker.cancelled.connect(self._on_search_cancelled)
            self.search_worker.error.connect(self._on_search_error)

            try:
                self.cancel_analysis_button.clicked.disconnect()
            except TypeError:
                pass
            self.cancel_analysis_button.clicked.connect(self.search_worker.cancel)
            self.cancel_analysis_button.clicked.connect(lambda: self.status_label.setText("Cancelling..."))

            self.search_worker.start()
        except Exception as e:
            log_error(f"SearchReviewDialog: Error in _load_content: {e}", exc_info=True)
            self.status_label.setText(f"Error loading search results: {e}")
            self.show_progress_ui(False)
            self.set_controls_enabled(True)

    def _on_search_finished(self, items_to_review, current_text, line_numbers, block_indices, unique_string_indices):
        try:
            log_debug(f"SearchReviewDialog: search finished, found {len(items_to_review)} matches.")
            if getattr(self, '_is_closing', False):
                self._shutdown_worker()
                super().reject()
                return

            self.items_to_review = items_to_review
            self.matches = self.items_to_review

            self.current_text = current_text
            self.line_numbers = line_numbers
            self.block_indices = block_indices
            if unique_string_indices:
                self.unique_string_indices = unique_string_indices

            self.text_edit.setPlainText(self.current_text)
            self._process_text_spacing_and_line_numbers()
            self._apply_zebra_striping()

            self.status_label.setText("Highlighting matches...")
            self.pre_highlight_all_matches()
            self.show_current_item()
            if not self.query:
                self.find_input.setFocus()

            self.show_progress_ui(False)
            self.set_controls_enabled(True)
            log_debug("SearchReviewDialog: Search operation finished successfully")
        except Exception as e:
            log_error(f"SearchReviewDialog: Error in _on_search_finished: {e}", exc_info=True)
            self.status_label.setText(f"Error displaying results: {e}")
            self.show_progress_ui(False)
            self.set_controls_enabled(True)

    def _on_search_cancelled(self):
        try:
            log_debug("SearchReviewDialog: Search cancelled by user.")
            if getattr(self, '_is_closing', False):
                self._shutdown_worker()
                super().reject()
                return
            self.status_label.setText("Search cancelled.")
            self.show_progress_ui(False)
            self.set_controls_enabled(True)
        except Exception as e:
            log_error(f"SearchReviewDialog: Error in _on_search_cancelled: {e}", exc_info=True)

    def _on_search_error(self, err_msg):
        log_error(f"SearchReviewDialog: Search worker error: {err_msg}")
        if getattr(self, '_is_closing', False):
            self._shutdown_worker()
            super().reject()
            return
        self.status_label.setText(f"Error: {err_msg}")
        self.show_progress_ui(False)
        self.set_controls_enabled(True)

    def set_controls_enabled(self, enabled: bool):
        super().set_controls_enabled(enabled)
        self.matches_list.setEnabled(enabled)
        self.find_input.setEnabled(enabled)
        self.case_sensitive_checkbox.setEnabled(enabled)
        self.fuzzy_checkbox.setEnabled(enabled)
        self.original_checkbox.setEnabled(enabled)
        self.no_tags_checkbox.setEnabled(enabled)
        self.replace_input.setEnabled(enabled)
        self.match_case_replace_checkbox.setEnabled(enabled)
        self.find_button.setEnabled(enabled)
        self.replace_button.setEnabled(enabled)
        self.replace_all_button.setEnabled(enabled)
        self.skip_button.setEnabled(enabled)

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
                matches = find_smart_matches(clean_line, effective_query, self.case_sensitive)
                for start_in_clean, end_in_clean in matches:
                    raw_start = mapping[start_in_clean]
                    raw_end = mapping[end_in_clean - 1] + 1

                    start_pos = char_offset + raw_start
                    end_pos = char_offset + raw_end
                    matched_text = line[raw_start:raw_end]
                    self.items_to_review.append((start_pos, end_pos, matched_text, line_idx))

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
                raw_string_idx = self.line_numbers[line_idx]
                display_line_num = raw_string_idx + 1
            else:
                raw_string_idx = self.starting_line_number + line_idx
                display_line_num = raw_string_idx + 1

            b_idx = self.block_idx
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

            item_text = f"[{block_name}] String {display_line_num}: \"{word}\" in \"{context}\""
            item = QListWidgetItem(item_text)
            item.setData(Qt.ItemDataRole.UserRole, (b_idx, raw_string_idx))
            self.matches_list.addItem(item)

    def show_current_item(self, from_click=False):
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
            display_line_num = self.line_numbers[line_idx] + 1
        elif not self.line_numbers:
            display_line_num = self.starting_line_number + line_idx + 1

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
        if not from_click:
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
        modifiers = QApplication.keyboardModifiers()
        if bool(modifiers & (Qt.KeyboardModifier.ControlModifier | Qt.KeyboardModifier.ShiftModifier)):
            return

        clicked_index = self.matches_list.row(item)
        if clicked_index != self.current_item_index:
            self.clear_current_item_highlight()
            self.current_item_index = clicked_index
            self.show_current_item(from_click=True)

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
                    self._navigate_to_block_and_string(b_idx, string_number - 1)

        from PyQt6.QtWidgets import QPlainTextEdit
        QPlainTextEdit.mouseDoubleClickEvent(self.text_edit, event)

    def perform_search(self):
        # Save changes from current search view state back to project
        self.save_changes_to_project()

        # Update search parameters from checkboxes
        self.query = self.find_input.text()
        main_window = self._find_main_window()
        if main_window and self.query:
            main_window.last_advanced_search_query = self.query

        self.case_sensitive = self.case_sensitive_checkbox.isChecked()
        self.is_fuzzy = self.fuzzy_checkbox.isChecked()
        self.search_in_original = self.original_checkbox.isChecked()
        self.ignore_tags = self.no_tags_checkbox.isChecked()

        import sys
        parent = self.parentWidget()
        is_test = 'pytest' in sys.modules or parent is None or bool(getattr(parent, '_is_test_mode', False))

        if is_test:
            log_debug("SearchReviewDialog.perform_search: running synchronously in test mode")
            self.rebuild_text_from_project()
            self.clear_current_item_highlight()
            self.find_matches()
            self.pre_highlight_all_matches()
            self.current_item_index = 0
            for btn in [self.skip_button, self.replace_button, self.replace_all_button, self.prev_button, self.next_button]:
                btn.setEnabled(True)
            self.show_current_item()
            return

        self.set_controls_enabled(False)
        self.show_progress_ui(True)

        params = {
            'data': main_window.data_store.data if main_window else [],
            'data_processor': main_window.data_processor if main_window else None,
            'query': self.query,
            'case_sensitive': self.case_sensitive,
            'search_in_original': self.search_in_original,
            'ignore_tags': self.ignore_tags,
            'is_fuzzy': self.is_fuzzy
        }

        self.search_worker = SearchWorker('global', params)
        self.search_worker.progress.connect(self.progress_bar.setValue)
        self.search_worker.finished.connect(self._on_search_finished)
        self.search_worker.cancelled.connect(self._on_search_cancelled)
        self.search_worker.error.connect(self._on_search_error)

        try:
            self.cancel_analysis_button.clicked.disconnect()
        except TypeError:
            pass
        self.cancel_analysis_button.clicked.connect(self.search_worker.cancel)
        self.cancel_analysis_button.clicked.connect(lambda: self.status_label.setText("Cancelling..."))

        self.search_worker.start()

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
                    display_line_numbers.append(current_line_num + 1 if current_line_num is not None else None)
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
            res = main_window.data_processor.get_current_string_text(b_idx, string_idx)
            old_text = res[0] if (isinstance(res, tuple) and len(res) == 2) else ""
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
                if hasattr(main_window, 'data_store'):
                    main_window.data_store.mark_dirty(b_idx)
            if hasattr(main_window, 'ui_updater'):
                main_window.ui_updater.update_text_views()
                main_window.ui_updater.populate_blocks()

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

    def refresh_from_project(self):
        """Re-read current text from data store and update matching display."""
        self.rebuild_text_by_options()
        self.text_edit.setPlainText(self.current_text)
        self._process_text_spacing_and_line_numbers()
        self._apply_zebra_striping()
        self.find_matches()
        self.pre_highlight_all_matches()
        self.show_current_item()

    def eventFilter(self, obj, event):
        """Capture Ctrl state at the moment of right mouse button press for context menu."""
        from PyQt6.QtCore import QEvent as _QEvent
        from PyQt6.QtCore import Qt as _Qt
        if hasattr(self, 'matches_list') and obj is self.matches_list.viewport():
            if event.type() == _QEvent.Type.MouseButtonPress:
                if event.button() == _Qt.MouseButton.RightButton:
                    self._ctrl_was_pressed_at_right_click = bool(
                        event.modifiers() & _Qt.KeyboardModifier.ControlModifier
                    )
        return super().eventFilter(obj, event)

    def show_context_menu(self, pos):
        selected_items = self.matches_list.selectedItems()
        if not selected_items:
            item = self.matches_list.itemAt(pos)
            if item:
                selected_items = [item]

        if not selected_items:
            return

        is_ctrl_at_populate = getattr(self, '_ctrl_was_pressed_at_right_click', False)
        self._ctrl_was_pressed_at_right_click = False  # Reset after reading

        def check_ctrl_now():
            return is_control_modifier_pressed()

        pairs = []
        seen = set()
        for item in selected_items:
            data = item.data(Qt.ItemDataRole.UserRole)
            if data and isinstance(data, tuple) and len(data) >= 2:
                b_idx, string_idx = data[0], data[1]
                pair = (b_idx, string_idx)
                if pair not in seen:
                    seen.add(pair)
                    pairs.append(pair)

        if not pairs:
            return

        menu = QMenu(self)
        count = len(pairs)

        # Define icons using theme with a style-based standardIcon fallback
        from PyQt6.QtGui import QIcon
        from PyQt6.QtWidgets import QStyle

        def get_icon(theme_name, fallback_pixmap):
            ico = QIcon.fromTheme(theme_name)
            if ico.isNull() or ico.name() == "":
                return self.style().standardIcon(fallback_pixmap)
            return ico

        icon_translate = self.style().standardIcon(QStyle.StandardPixmap.SP_MessageBoxInformation)
        icon_spellcheck = get_icon("tools-check-spelling", QStyle.StandardPixmap.SP_DialogHelpButton)
        icon_move = get_icon("go-jump", QStyle.StandardPixmap.SP_ArrowForward)
        icon_font = get_icon("preferences-desktop-font", QStyle.StandardPixmap.SP_FileDialogListView)
        icon_width = get_icon("format-justify-fill", QStyle.StandardPixmap.SP_FileDialogListView)
        icon_autofix = get_icon("document-edit", QStyle.StandardPixmap.SP_DialogYesButton)
        icon_revert = get_icon("document-revert", QStyle.StandardPixmap.SP_BrowserReload)
        icon_restore = get_icon("edit-redo", QStyle.StandardPixmap.SP_ArrowForward)

        # Build user-friendly action texts depending on the count (singular/plural)
        if count > 1:
            txt_translate = f"AI Translate {count} Selected Lines (UA)"
            txt_spellcheck = f"Spellcheck {count} Selected Lines"
            txt_move = f"Move {count} Selected Lines to Virtual Block..."
            txt_font = f"Set Font for {count} Selected Lines..."
            txt_width = f"Set Width for {count} Selected Lines..."
            txt_autofix = f"AutoFix {count} Selected Lines..."
            txt_revert = f"Revert {count} Selected Lines to Original"
            txt_restore = f"Restore Translated for {count} Selected Lines"
        else:
            txt_translate = "AI Translate Selected Line (UA)"
            txt_spellcheck = "Spellcheck Selected Line"
            txt_move = "Move Selected Line to Virtual Block..."
            txt_font = "Set Font for Selected Line..."
            txt_width = "Set Width for Selected Line..."
            txt_autofix = "AutoFix Selected Line..."
            txt_revert = "Revert Selected Line to Original"
            txt_restore = "Restore Translated for Selected Line"

        # 1. AI Translate
        action_translate = menu.addAction(icon_translate, txt_translate)
        action_translate.triggered.connect(lambda checked=False: self._ctx_ai_translate(pairs, force_prompt=is_ctrl_at_populate or check_ctrl_now()))

        # 2. Spellcheck
        action_spellcheck = menu.addAction(icon_spellcheck, txt_spellcheck)
        action_spellcheck.triggered.connect(lambda: self._ctx_spellcheck(pairs))

        # 3. Move
        action_move = menu.addAction(icon_move, txt_move)
        action_move.triggered.connect(lambda: self._ctx_move_to_category(pairs))

        menu.addSeparator()

        # 4. Set Font
        action_set_font = menu.addAction(icon_font, txt_font)
        action_set_font.triggered.connect(lambda: self._ctx_set_font(pairs))

        # 5. Set Width
        action_set_width = menu.addAction(icon_width, txt_width)
        action_set_width.triggered.connect(lambda: self._ctx_set_width(pairs))

        menu.addSeparator()

        # 6. AutoFix
        action_autofix = menu.addAction(icon_autofix, txt_autofix)
        action_autofix.triggered.connect(lambda: self._ctx_autofix(pairs))

        # 7. Revert
        action_revert = menu.addAction(icon_revert, txt_revert)
        action_revert.triggered.connect(lambda: self._ctx_revert(pairs))

        # 8. Restore
        action_restore = menu.addAction(icon_restore, txt_restore)
        action_restore.triggered.connect(lambda: self._ctx_restore(pairs))

        menu.exec(self.matches_list.viewport().mapToGlobal(pos))

    def _ctx_ai_translate(self, pairs, force_prompt=False):
        main_window = self._find_main_window()
        if main_window and hasattr(main_window, 'translation_handler'):
            desc = "Selected search lines"
            main_window.translation_handler.translate_specific_strings(pairs, desc, force_prompt=force_prompt)

    def _ctx_spellcheck(self, pairs):
        main_window = self._find_main_window()
        spellchecker_manager = getattr(main_window, 'spellchecker_manager', None)
        if not spellchecker_manager or not spellchecker_manager.enabled:
            return

        text_parts = []
        block_indices = []
        line_numbers = []
        for b_idx, s_idx in pairs:
            text, _ = main_window.data_processor.get_current_string_text(b_idx, s_idx)
            if text is None:
                text = ""
            text_parts.append(text)
            block_indices.append(b_idx)
            line_numbers.append(s_idx)

        text_to_check = '\n'.join(text_parts)
        if not text_to_check.strip():
            return

        from dialogs.spellcheck_dialog import SpellcheckDialog
        dialog = SpellcheckDialog(
            self,
            text_to_check,
            spellchecker_manager,
            line_numbers=line_numbers,
            block_idx=self.block_idx,
            block_indices=block_indices
        )

        if dialog.exec():
            corrected_text = dialog.get_corrected_text()
            corrected_lines = corrected_text.split('\n')

            has_undo = hasattr(main_window, 'undo_manager')
            if has_undo:
                main_window.undo_manager.begin_group()

            try:
                for i, (b_idx, s_idx) in enumerate(pairs):
                    if i < len(corrected_lines):
                        new_text = corrected_lines[i]
                        main_window.data_processor.update_edited_data(
                            b_idx, s_idx, new_text, action_type="SPELLCHECK", skip_ui_refresh=True
                        )
                        if hasattr(main_window, 'text_operation_handler') and main_window.text_operation_handler:
                            main_window.text_operation_handler._rescan_issues_for_current_string(b_idx, s_idx, new_text)
            finally:
                if has_undo:
                    main_window.undo_manager.end_group("SPELLCHECK")

            modified_blocks = {b_idx for b_idx, _ in pairs}
            for m_block in modified_blocks:
                main_window.ui_updater.update_block_item_text_with_problem_count(m_block)

            current_view_block = main_window.data_store.current_block_idx
            if main_window.data_store.current_chapter_id is not None:
                current_view_block = -2
            main_window.ui_updater.populate_strings_for_block(
                current_view_block, getattr(main_window.data_store, 'current_category_name', None), force=True
            )
            main_window.ui_updater.update_text_views()
            main_window.ui_updater.update_title()

            self.refresh_from_project()

    def _ctx_move_to_category(self, pairs):
        main_window = self._find_main_window()
        pm = main_window.project_manager
        if not pm or not pm.project:
            return

        from PyQt6.QtWidgets import QInputDialog
        name, ok = QInputDialog.getText(self, "Move to Virtual Block", "Enter Category Name:", text="New Category")
        if not ok or not name.strip():
            return

        category_name = name.strip()

        by_block = {}
        for b_idx, s_idx in pairs:
            if b_idx not in by_block:
                by_block[b_idx] = []
            by_block[b_idx].append(s_idx)

        has_undo = hasattr(main_window, 'undo_manager')
        if has_undo:
            main_window.undo_manager.begin_group()

        try:
            block_map = getattr(main_window, 'block_to_project_file_map', {})
            for b_idx, s_indices in by_block.items():
                proj_b_idx = block_map.get(b_idx, b_idx)
                if proj_b_idx < len(pm.project.blocks):
                    pm.move_strings_to_category(proj_b_idx, s_indices, category_name)
        finally:
            if has_undo:
                main_window.undo_manager.end_group("MOVE_TO_CATEGORY")

        main_window.ui_updater.populate_blocks()
        current_view_block = main_window.data_store.current_block_idx
        if main_window.data_store.current_chapter_id is not None:
            current_view_block = -2
        main_window.ui_updater.populate_strings_for_block(
            current_view_block, getattr(main_window.data_store, 'current_category_name', None), force=True
        )
        main_window.ui_updater.update_text_views()
        self.refresh_from_project()

    def _ctx_set_font(self, pairs):
        main_window = self._find_main_window()
        from components.editor.mass_font_dialog import MassFontDialog
        dialog = MassFontDialog(main_window)
        if dialog.exec():
            font_file = dialog.get_selected_font()
            for b_idx, s_idx in pairs:
                key = (b_idx, s_idx)
                if font_file == "default":
                    if key in main_window.string_metadata:
                        if "font_file" in main_window.string_metadata[key]:
                            del main_window.string_metadata[key]["font_file"]
                        if not main_window.string_metadata[key]:
                            del main_window.string_metadata[key]
                else:
                    if key not in main_window.string_metadata:
                        main_window.string_metadata[key] = {}
                    main_window.string_metadata[key]["font_file"] = font_file

            if hasattr(main_window, 'settings_manager'):
                main_window.settings_manager.save_settings()

            if hasattr(main_window.string_settings_handler, '_apply_and_rescan'):
                main_window.string_settings_handler._apply_and_rescan()
            self.refresh_from_project()

    def _ctx_set_width(self, pairs):
        main_window = self._find_main_window()
        from components.editor.mass_width_dialog import MassWidthDialog
        dialog = MassWidthDialog(main_window)
        if dialog.exec():
            is_auto = dialog.is_auto_width()
            width = dialog.get_width()

            for b_idx, s_idx in pairs:
                key = (b_idx, s_idx)
                if is_auto:
                    original_text = main_window.data_processor._get_string_from_source(b_idx, s_idx, main_window.data_store.data, "original")
                    calculated_width = main_window.text_analysis_handler.calculate_text_width(original_text) if hasattr(main_window, 'text_analysis_handler') else 0
                    if calculated_width > 0:
                        if key not in main_window.string_metadata:
                            main_window.string_metadata[key] = {}
                        main_window.string_metadata[key]["width"] = calculated_width
                else:
                    is_default = (width == 0 or width == main_window.game_dialog_max_width_pixels)
                    if is_default:
                        if key in main_window.string_metadata:
                            if "width" in main_window.string_metadata[key]:
                                del main_window.string_metadata[key]["width"]
                            if not main_window.string_metadata[key]:
                                del main_window.string_metadata[key]
                    else:
                        if key not in main_window.string_metadata:
                            main_window.string_metadata[key] = {}
                        main_window.string_metadata[key]["width"] = width

            if hasattr(main_window, 'settings_manager'):
                main_window.settings_manager.save_settings()

            if hasattr(main_window.string_settings_handler, '_apply_and_rescan'):
                main_window.string_settings_handler._apply_and_rescan()
            self.refresh_from_project()

    def _ctx_autofix(self, pairs):
        main_window = self._find_main_window()
        if hasattr(main_window, 'text_operation_handler') and main_window.text_operation_handler:
            main_window.text_operation_handler.fix_all_strings(pairs)
            self.refresh_from_project()

    def _ctx_revert(self, pairs):
        main_window = self._find_main_window()
        if main_window and hasattr(main_window, 'data_processor'):
            main_window.data_processor.perform_revert_strings(-2, pairs)
            self.refresh_from_project()

    def _ctx_restore(self, pairs):
        main_window = self._find_main_window()
        if not main_window or not hasattr(main_window, 'saved_translations_handler'):
            return

        by_block = {}
        for b_idx, s_idx in pairs:
            if b_idx not in by_block:
                by_block[b_idx] = []
            by_block[b_idx].append(s_idx)

        has_undo = hasattr(main_window, 'undo_manager')
        if has_undo:
            main_window.undo_manager.begin_group()

        try:
            for b_idx, s_indices in by_block.items():
                main_window.saved_translations_handler.restore_translations_for_strings(b_idx, s_indices)
        finally:
            if has_undo:
                main_window.undo_manager.end_group("RESTORE_STRINGS")

        self.refresh_from_project()

    def reject(self):
        if hasattr(self, 'search_worker') and self.search_worker and self.search_worker.isRunning():
            self._is_closing = True
            self.status_label.setText("Cancelling and closing...")
            self.set_controls_enabled(False)
            self.search_worker.cancel()
            return
        self._shutdown_worker()
        super().reject()

    def done(self, r):
        self._shutdown_worker()
        self.save_changes_to_project()
        super().done(r)

    def _shutdown_worker(self):
        if hasattr(self, 'search_worker') and self.search_worker:
            from utils.thread_utils import safe_shutdown_thread
            try:
                self.search_worker.cancel()
                safe_shutdown_thread(self.search_worker)
            except Exception as e:
                log_error(f"SearchReviewDialog: Error shutting down worker: {e}")
            self.search_worker = None
