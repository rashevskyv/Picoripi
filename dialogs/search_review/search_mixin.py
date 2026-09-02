"""Search worker lifecycle, find/highlight, and perform_search."""
from __future__ import annotations

import re

from PyQt6.QtWidgets import QListWidgetItem
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QTextCursor, QTextCharFormat, QColor

from utils.logging_utils import log_debug, log_error
from utils.utils import prepare_text_for_tagless_search, is_fuzzy_match, find_smart_matches
from dialogs.search.search_worker import SearchWorker
from dialogs.search.search_utils import prepare_text_for_tagless_search_with_mapping
from core.i18n import tr


class SearchMixin:
    """Search worker lifecycle, find/highlight, and perform_search."""

    def _load_content(self):
        try:
            log_debug("SearchReviewDialog: _load_content started")
            self.status_label.setText(tr('Searching text...'))

            import sys
            parent = self.parentWidget()
            is_test = ('pytest' in sys.modules or parent is None or bool(getattr(parent, '_is_test_mode', False))) and not getattr(self, 'force_async', False)

            if is_test:
                log_debug("SearchReviewDialog: Running in test mode, using synchronous loading")
                self.find_matches()
                self.status_label.setText(tr('Highlighting matches...'))
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
            self.cancel_analysis_button.clicked.connect(lambda: self.status_label.setText(tr('Cancelling...')))

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

            self.status_label.setText(tr('Highlighting matches...'))
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
            self.status_label.setText(tr('Search cancelled.'))
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
        self.cancel_analysis_button.clicked.connect(lambda: self.status_label.setText(tr('Cancelling...')))

        self.search_worker.start()
