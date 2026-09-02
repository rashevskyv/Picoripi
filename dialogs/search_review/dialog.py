"""SearchReviewDialog composition, setup panels, and lifecycle."""
from __future__ import annotations

from typing import List

from PyQt6.QtWidgets import (
    QVBoxLayout,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QLineEdit,
    QListWidget,
)
from PyQt6.QtCore import Qt, QTimer

from utils.logging_utils import log_debug, log_error
from dialogs.base_text_review_dialog import BaseTextReviewDialog
from core.i18n import tr

from dialogs.search_review.search_mixin import SearchMixin
from dialogs.search_review.replace_mixin import ReplaceMixin
from dialogs.search_review.persist_mixin import PersistMixin
from dialogs.search_review.context_mixin import ContextMixin


class SearchReviewDialog(
    SearchMixin,
    ReplaceMixin,
    PersistMixin,
    ContextMixin,
    BaseTextReviewDialog,
):
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
        layout.addWidget(QLabel(tr('Search Matches:')))
        self.matches_list = QListWidget()
        self.matches_list.setToolTip(
            tr('<b>Matches</b><br>Click — review that match and jump the main editor to its string.<br>Ctrl-click or Shift-click — build a multi-selection without jumping.<br>Right-click — act on the whole selection: AI translate, spellcheck, move, set font/width, autofix, revert, restore.<br>Ctrl+right-click — the AI translate entry opens the prompt editor first.')
        )
        self.matches_list.setSelectionMode(QListWidget.SelectionMode.ExtendedSelection)
        self.matches_list.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.matches_list.customContextMenuRequested.connect(self.show_context_menu)
        self.matches_list.itemClicked.connect(self.jump_to_item_from_list)
        self.matches_list.itemDoubleClicked.connect(self._on_item_double_click)
        layout.addWidget(self.matches_list)

        self.selection_status_label = QLabel(tr('Selected: 0'))
        layout.addWidget(self.selection_status_label)
        self.matches_list.itemSelectionChanged.connect(self.update_selection_status)

        # Track Ctrl state at the moment of right-click for context menu
        self._ctrl_was_pressed_at_right_click = False
        self.matches_list.viewport().installEventFilter(self)

    def update_selection_status(self):
        count = len(self.matches_list.selectedItems())
        self.selection_status_label.setText(f"Selected: {count}")

    def setup_right_panel(self, layout: QVBoxLayout):
        from PyQt6.QtWidgets import QCheckBox
        layout.addWidget(QLabel(tr('Find:')))
        self.find_input = QLineEdit()
        self.find_input.setText(self.query)
        self.find_input.setPlaceholderText(tr('Enter search query...'))
        self.find_input.returnPressed.connect(self.perform_search)
        layout.addWidget(self.find_input)

        # Options checkboxes layout
        options_layout = QHBoxLayout()

        self.case_sensitive_checkbox = QCheckBox(tr('Aa'))
        self.case_sensitive_checkbox.setToolTip(tr('Case sensitive'))
        self.case_sensitive_checkbox.setChecked(self.case_sensitive)
        options_layout.addWidget(self.case_sensitive_checkbox)

        self.fuzzy_checkbox = QCheckBox(tr('Fuzzy'))
        self.fuzzy_checkbox.setToolTip(tr('Search for similar words (ignores endings)'))
        self.fuzzy_checkbox.setChecked(self.is_fuzzy)
        options_layout.addWidget(self.fuzzy_checkbox)

        self.original_checkbox = QCheckBox(tr('Original'))
        self.original_checkbox.setToolTip(tr('Search in original text'))
        self.original_checkbox.setChecked(self.search_in_original)
        options_layout.addWidget(self.original_checkbox)

        self.no_tags_checkbox = QCheckBox(tr('No Tags'))
        self.no_tags_checkbox.setToolTip(tr('Ignore tags {...} [...], newlines, and extra spaces'))
        self.no_tags_checkbox.setChecked(self.ignore_tags)
        options_layout.addWidget(self.no_tags_checkbox)

        layout.addLayout(options_layout)

        layout.addWidget(QLabel(tr('Replace with:')))
        self.replace_input = QLineEdit()
        self.replace_input.setPlaceholderText(tr('Enter replacement text...'))
        layout.addWidget(self.replace_input)

        self.match_case_replace_checkbox = QCheckBox(tr('Match case on replace'))
        self.match_case_replace_checkbox.setToolTip(tr("Preserve the casing of the original word (e.g., 'Word' -> 'Replacement', 'WORD' -> 'REPLACEMENT')"))
        self.match_case_replace_checkbox.setChecked(False)
        layout.addWidget(self.match_case_replace_checkbox)

        # Action buttons
        button_layout = QVBoxLayout()

        self.find_button = QPushButton(tr('Find'))
        self.find_button.setToolTip(
            tr('<b>Find</b><br>Click — search with the current term and options, and rebuild the match list on the left.')
        )
        self.find_button.clicked.connect(self.perform_search)
        button_layout.addWidget(self.find_button)

        self.replace_button = QPushButton(tr('Replace'))
        self.replace_button.setToolTip(
            tr('<b>Replace</b><br>Click — replace the current match only and move to the next one.')
        )
        self.replace_button.clicked.connect(self.replace_match)
        button_layout.addWidget(self.replace_button)

        self.replace_all_button = QPushButton(tr('Replace All'))
        self.replace_all_button.setToolTip(
            tr('<b>Replace all</b><br>Click — replace every match in the list at once. Undo with Ctrl+Z in the main editor, one string at a time.')
        )
        self.replace_all_button.clicked.connect(self.replace_all_matches)
        self.replace_all_button.setStyleSheet("background-color: #047857; color: white; font-weight: bold;")
        button_layout.addWidget(self.replace_all_button)

        self.skip_button = QPushButton(tr('Skip'))
        self.skip_button.setToolTip(
            tr('<b>Skip</b><br>Click — leave this match untouched and move to the next one.')
        )
        self.skip_button.clicked.connect(self.skip_match)
        button_layout.addWidget(self.skip_button)

        button_layout.addStretch()
        layout.addLayout(button_layout)

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

    def reject(self):
        if hasattr(self, 'search_worker') and self.search_worker and self.search_worker.isRunning():
            self._is_closing = True
            self.status_label.setText(tr('Cancelling and closing...'))
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
