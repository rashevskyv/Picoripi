"""Speaker merge dialog composition and __init__."""
from __future__ import annotations

from typing import List

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (
    QDialog,
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPlainTextEdit,
    QPushButton,
    QSplitter,
    QTreeWidget,
    QVBoxLayout,
    QWidget,
)

from utils.window_utils import show_as_independent_window
from core.i18n import tr

from components.speaker_merge.widgets import NameOnlyDelegate
from components.speaker_merge.tree_mixin import TreeMixin
from components.speaker_merge.inspector_mixin import InspectorMixin


class SpeakerMergeDialog(TreeMixin, InspectorMixin, QDialog):
    """Merged names on the left; the lines behind the selected one on the right."""

    def __init__(self, result, parent=None, on_apply=None):
        super().__init__(None)
        self.setWindowTitle(tr('Merge Speakers'))
        show_as_independent_window(self)
        self.resize(1080, 680)
        self._result = result
        self._on_apply = on_apply
        self._updating_checks = False
        self._candidate_buttons: List[QPushButton] = []

        layout = QVBoxLayout(self)
        layout.setSpacing(8)

        # Header summary & hint
        layout.addWidget(QLabel(result.summary, self))
        hint = QLabel(
            tr('Select which speaker names to apply using checkboxes or choose candidates in the inspector. Double-click a Name cell to edit inline.'),
            self,
        )
        hint.setWordWrap(True)
        hint.setStyleSheet("color: #666666;")
        layout.addWidget(hint)

        splitter = QSplitter(Qt.Orientation.Horizontal, self)

        # --- Left panel: Filter + Tree ---
        left_widget = QWidget(splitter)
        left_layout = QVBoxLayout(left_widget)
        left_layout.setContentsMargins(0, 0, 0, 0)
        left_layout.setSpacing(6)

        search_layout = QHBoxLayout()
        self.search_edit = QLineEdit(left_widget)
        self.search_edit.setPlaceholderText(tr('Filter voices or names...'))
        self.search_edit.setClearButtonEnabled(True)
        self.search_edit.textChanged.connect(self._filter_tree)
        search_layout.addWidget(self.search_edit, 1)

        self.check_all_btn = QPushButton(tr('Check All'), left_widget)
        self.check_all_btn.clicked.connect(self._check_all)
        search_layout.addWidget(self.check_all_btn)

        self.uncheck_all_btn = QPushButton(tr('Uncheck All'), left_widget)
        self.uncheck_all_btn.clicked.connect(self._uncheck_all)
        search_layout.addWidget(self.uncheck_all_btn)
        left_layout.addLayout(search_layout)

        self.tree = QTreeWidget(left_widget)
        self.tree.setHeaderLabels(["Voice", "Name", "Votes / Source"])
        self.tree.setColumnWidth(0, 160)
        self.tree.setColumnWidth(1, 200)
        self.tree.setRootIsDecorated(True)
        self.tree.setItemDelegate(NameOnlyDelegate(self.tree))
        self.tree.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.tree.customContextMenuRequested.connect(self._show_context_menu)
        self.tree.itemChanged.connect(self._on_item_changed)
        left_layout.addWidget(self.tree, 1)

        # --- Right panel: Inspector + Evidence ---
        right_widget = QWidget(splitter)
        right_layout = QVBoxLayout(right_widget)
        right_layout.setContentsMargins(0, 0, 0, 0)
        right_layout.setSpacing(6)

        # Inspector Card
        self.inspector_card = QFrame(right_widget)
        self.inspector_card.setFrameShape(QFrame.Shape.StyledPanel)
        self.inspector_card.setStyleSheet(
            "QFrame { background-color: rgba(0, 0, 0, 0.02); border: 1px solid rgba(0, 0, 0, 0.1); border-radius: 4px; padding: 6px; }"
        )
        card_layout = QVBoxLayout(self.inspector_card)
        card_layout.setSpacing(6)

        title_layout = QHBoxLayout()
        self.inspector_title = QLabel(tr('Select a speaker'), self.inspector_card)
        title_font = self.inspector_title.font()
        title_font.setBold(True)
        self.inspector_title.setFont(title_font)
        title_layout.addWidget(self.inspector_title)

        self.inspector_badge = QLabel(tr(''), self.inspector_card)
        title_layout.addWidget(self.inspector_badge)
        title_layout.addStretch()
        card_layout.addLayout(title_layout)

        # Candidate chips area
        self.candidates_widget = QWidget(self.inspector_card)
        cand_outer = QVBoxLayout(self.candidates_widget)
        cand_outer.setContentsMargins(0, 0, 0, 0)
        cand_outer.setSpacing(4)
        cand_outer.addWidget(QLabel(tr('Choose Candidate Name:'), self.candidates_widget))

        self.candidates_layout = QHBoxLayout()
        self.candidates_layout.setSpacing(6)
        cand_outer.addLayout(self.candidates_layout)
        card_layout.addWidget(self.candidates_widget)

        # Name edit row
        name_layout = QHBoxLayout()
        name_layout.addWidget(QLabel(tr('Name:'), self.inspector_card))
        self.name_edit = QLineEdit(self.inspector_card)
        self.name_edit.setPlaceholderText(tr('Enter or select speaker name...'))
        self.name_edit.textChanged.connect(self._on_name_edit_changed)
        name_layout.addWidget(self.name_edit, 1)

        self.reset_button = QPushButton(tr('Clear'), self.inspector_card)
        self.reset_button.setToolTip(
            tr('Restore the suggested name. Delete the text to leave this voice unnamed.')
        )
        self.reset_button.clicked.connect(self._reset_current_name)
        name_layout.addWidget(self.reset_button)

        self.apply_single_button = QPushButton(tr('Apply This Speaker'), self.inspector_card)
        self.apply_single_button.setToolTip(tr('Apply and save only this speaker mapping now'))
        self.apply_single_button.clicked.connect(self._apply_current_speaker)
        name_layout.addWidget(self.apply_single_button)
        card_layout.addLayout(name_layout)

        self.feedback_label = QLabel(tr(''), self.inspector_card)
        self.feedback_label.setStyleSheet("color: #2e7d32; font-weight: bold;")
        card_layout.addWidget(self.feedback_label)

        right_layout.addWidget(self.inspector_card)

        # Evidence details
        self.details = QPlainTextEdit(right_widget)
        self.details.setReadOnly(True)
        self.details.setUndoRedoEnabled(False)
        right_layout.addWidget(self.details, 1)

        splitter.setSizes([580, 480])
        layout.addWidget(splitter, 1)

        # --- Bottom bar ---
        bottom_layout = QHBoxLayout()
        self.status_label = QLabel(self)
        self.status_label.setStyleSheet("color: #555555;")
        bottom_layout.addWidget(self.status_label)
        bottom_layout.addStretch()

        self.apply_button = QPushButton(tr('Apply checked names'), self)
        self.apply_button.setDefault(True)
        self.apply_button.clicked.connect(self._apply_checked)
        bottom_layout.addWidget(self.apply_button)

        self.apply_all_button = QPushButton(tr('Apply All Valid'), self)
        self.apply_all_button.setToolTip(tr('Apply all non-empty speaker names regardless of checkbox state'))
        self.apply_all_button.clicked.connect(self._apply_all)
        bottom_layout.addWidget(self.apply_all_button)

        self.close_button = QPushButton(tr('Close'), self)
        self.close_button.clicked.connect(self.reject)
        bottom_layout.addWidget(self.close_button)

        layout.addLayout(bottom_layout)

        self._populate()
        self.tree.currentItemChanged.connect(self._on_selection)
        self._select_first()
        self._update_counts_and_buttons()
