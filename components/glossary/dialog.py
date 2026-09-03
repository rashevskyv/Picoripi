"""GlossaryDialog composition and __init__."""
from __future__ import annotations

from pathlib import Path
from typing import Callable, Dict, List, Optional, Sequence, Tuple

from PyQt6.QtCore import Qt, QTimer
from PyQt6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QPushButton,
    QSplitter,
    QTableWidget,
    QPlainTextEdit,
    QSizePolicy,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)
from core.glossary_manager import (
    GlossaryEntry,
    GlossaryOccurrence,
    possible_duplicate_pairs,
)
from utils.window_utils import show_as_independent_window
from core.i18n import tr

from components.glossary.widgets import (
    _DetailPane,
    _RichTextItemDelegate,
    _VariantItemDelegate,
)
from components.glossary.table_mixin import TableMixin
from components.glossary.editor_mixin import EditorMixin
from components.glossary.details_mixin import DetailsMixin
from components.glossary.actions_mixin import ActionsMixin


class GlossaryDialog(
    TableMixin,
    EditorMixin,
    DetailsMixin,
    ActionsMixin,
    QDialog,
):
    """Show glossary entries with occurrences and allow navigation."""
    def __init__(
        self,
        *,
        parent: Optional[QWidget],
        entries: Sequence[GlossaryEntry],
        occurrence_map: Dict[str, List[GlossaryOccurrence]],
        jump_callback: Callable[[GlossaryOccurrence], None],
        update_callback: Optional[
            Callable[[str, str, str], Optional[Tuple[Sequence[GlossaryEntry], Dict[str, List[GlossaryOccurrence]]]]]
        ] = None,
        delete_callback: Optional[
            Callable[[str], Optional[Tuple[Sequence[GlossaryEntry], Dict[str, List[GlossaryOccurrence]]]]]
        ] = None,
        ai_variation_callback: Optional[Callable[[GlossaryEntry], None]] = None,
        ai_classify_callback: Optional[Callable[[], None]] = None,
        build_callback: Optional[Callable[[], None]] = None,
        clear_callback: Optional[
            Callable[[], Optional[Tuple[Sequence[GlossaryEntry], Dict[str, List[GlossaryOccurrence]]]]]
        ] = None,
        global_replace_callback: Optional[Callable[[str, str], None]] = None,
        apply_speaker_name_callback: Optional[Callable[[str, str], None]] = None,
        reassign_speaker_callback: Optional[Callable[[str, str, str], None]] = None,
        speaker_codes_callback: Optional[Callable[[str], Sequence[str]]] = None,
        initial_term: Optional[str] = None,
        placeholder_speaker_callback: Optional[Callable[[str], bool]] = None,
        discuss_variant_callback: Optional[Callable[[GlossaryEntry], None]] = None,
    ) -> None:
        """Initialize a new instance."""
        super().__init__(None)
        self.setWindowTitle(tr('Glossary'))
        show_as_independent_window(self)
        self.resize(840, 520)

        parent_settings = getattr(parent, 'settings_manager', None)
        settings_path = getattr(parent_settings, 'settings_file_path', 'settings.json')
        self._settings_path = Path(settings_path)
        self._restore_maximized_on_show = False
        self._current_entry: Optional[GlossaryEntry] = None
        self._suppress_editor_signals = False
        self._editor_dirty = False
        # Notes as stored (may hold the term placeholder); the editor shows them
        # rendered against the current translation.
        self._notes_template = ""

        self.setWindowFlag(Qt.WindowType.WindowContextHelpButtonHint, False)
        self.setWindowFlag(Qt.WindowType.WindowMinimizeButtonHint, True)
        self.setWindowFlag(Qt.WindowType.WindowMaximizeButtonHint, True)
        self.setWindowFlag(Qt.WindowType.WindowCloseButtonHint, True)

        self._all_entries = list(entries)
        self._duplicate_pairs = possible_duplicate_pairs(self._all_entries)
        self._filtered_entries: List[GlossaryEntry] = list(entries)
        self._occurrences = occurrence_map
        self._jump_callback = jump_callback
        self._update_callback = update_callback
        self._delete_callback = delete_callback
        self._ai_variation_callback = ai_variation_callback
        self._ai_classify_callback = ai_classify_callback
        self._build_callback = build_callback
        self._clear_callback = clear_callback
        self._global_replace_callback = global_replace_callback
        self._apply_speaker_name_callback = apply_speaker_name_callback
        self._reassign_speaker_callback = reassign_speaker_callback
        self._speaker_codes_callback = speaker_codes_callback
        self._placeholder_speaker_callback = placeholder_speaker_callback
        self._discuss_variant_callback = discuss_variant_callback
        self._current_speaker_code = ""
        self._current_speaker_is_provisional = False
        self._initial_term = initial_term
        self._pending_select_term: Optional[str] = None
        self._is_populating = False

        self._tables: Dict[str, QTableWidget] = {}
        self._entry_table: Optional[QTableWidget] = None # Legacy compatibility

        layout = QVBoxLayout(self)

        header = QLabel(tr('Select a term to review occurrences. Double-click an occurrence to jump to the editor.'), self)
        header.setWordWrap(True)
        layout.addWidget(header)

        search_layout = QHBoxLayout()
        search_layout.addWidget(QLabel(tr('Search:'), self))
        self._search_field = QLineEdit(self)
        self._search_field.setPlaceholderText(tr('Type a term or translation...'))
        self._search_field.setProperty("selectAllOnClick", True)
        self._filter_timer = QTimer(self)
        self._filter_timer.setSingleShot(True)
        self._filter_timer.setInterval(120)
        self._filter_timer.timeout.connect(lambda: self._apply_filter(self._search_field.text()))
        self._search_field.textChanged.connect(self._filter_timer.start)
        search_layout.addWidget(self._search_field, 1)
        self._unconfirmed_only_checkbox = QCheckBox(tr('Needs review'), self)
        self._unconfirmed_only_checkbox.setToolTip(
            tr('Show only entries still awaiting your decision — highlighted rows: several translation variants were proposed, or the entry has not been confirmed yet.')
        )
        self._unconfirmed_only_checkbox.stateChanged.connect(
            lambda _state: self._apply_filter(self._search_field.text())
        )
        search_layout.addWidget(self._unconfirmed_only_checkbox)
        layout.addLayout(search_layout)

        self._main_splitter = QSplitter(Qt.Orientation.Horizontal, self)
        self._main_splitter.setHandleWidth(6)
        layout.addWidget(self._main_splitter, 1)

        self._tab_widget = QTabWidget(self)
        self._tab_widget.currentChanged.connect(self._on_tab_changed)
        self._main_splitter.addWidget(self._tab_widget)

        right_panel = QWidget(self)
        right_layout = QVBoxLayout(right_panel)
        self._main_splitter.addWidget(right_panel)
        self._main_splitter.setStretchFactor(0, 1)
        self._main_splitter.setStretchFactor(1, 1)
        self._main_splitter.setSizes([360, 480])
        self._original_label = QLabel(tr(''), self)
        self._original_label.setWordWrap(True)
        right_layout.addWidget(self._original_label)

        category_row = QHBoxLayout()
        category_row.addWidget(QLabel(tr('Category:'), self))
        self._category_combo = QComboBox(self)
        self._category_combo.setEditable(True)
        self._category_combo.setPlaceholderText(tr('Select or type a new category...'))
        category_row.addWidget(self._category_combo, 1)
        right_layout.addLayout(category_row)

        # Speaker identity resolution pane (shown for provisional Character entries)
        self._speaker_identity_pane = QWidget(self)
        speaker_layout = QVBoxLayout(self._speaker_identity_pane)
        speaker_layout.setContentsMargins(0, 4, 0, 8)

        self._speaker_identity_title = QLabel(self)
        speaker_layout.addWidget(self._speaker_identity_title)

        self._speaker_evidence_label = QLabel(self)
        self._speaker_evidence_label.setWordWrap(True)
        self._speaker_evidence_label.setStyleSheet(
            "color: #444; font-style: italic; background-color: #f0f0f5; padding: 6px; border-radius: 4px;"
        )
        speaker_layout.addWidget(self._speaker_evidence_label)

        combo_row = QHBoxLayout()
        self._speaker_name_combo = QComboBox(self)
        self._speaker_name_combo.setEditable(True)
        self._speaker_name_combo.setPlaceholderText(tr('Enter or select permanent character name...'))
        self._speaker_name_combo.editTextChanged.connect(lambda _text: self._validate_speaker_name())
        self._speaker_name_combo.currentIndexChanged.connect(lambda _idx: self._validate_speaker_name())
        combo_row.addWidget(self._speaker_name_combo, 1)

        self._apply_speaker_name_button = QPushButton(tr('Apply speaker name'), self)
        self._apply_speaker_name_button.clicked.connect(self._on_apply_speaker_name_clicked)
        combo_row.addWidget(self._apply_speaker_name_button)

        speaker_layout.addLayout(combo_row)
        right_layout.addWidget(self._speaker_identity_pane)
        self._speaker_identity_pane.setVisible(False)

        translation_label = QLabel(tr('Translation:'), self)
        right_layout.addWidget(translation_label)
        self._translation_edit = QLineEdit(self)
        right_layout.addWidget(self._translation_edit)

        self._confirm_button = QPushButton(tr('Confirm translation'), self)
        self._confirm_button.setToolTip(
            tr('Mark this translation as decided and move to the next term. Unreviewed rows stay pale yellow; several proposed variants stay orange until you pick one.')
        )
        self._confirm_button.clicked.connect(self._on_confirm_clicked)
        right_layout.addWidget(self._confirm_button)

        # The variants list has its own top-level splitter handle, so the
        # divider sits directly below the list rather than below its actions.
        self._detail_splitter = QSplitter(Qt.Orientation.Vertical, self)
        self._detail_splitter.setHandleWidth(6)
        right_layout.addWidget(self._detail_splitter, 1)

        # Proposed variants: shown only when the AI offered a real choice.
        self._variants_pane = _DetailPane(self)
        self._variants_pane.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Expanding)
        variants_layout = QVBoxLayout(self._variants_pane)
        variants_layout.setContentsMargins(0, 0, 0, 0)
        self._variants_label = QLabel(tr('Proposed variants (pick one):'), self)
        variants_layout.addWidget(self._variants_label)
        self._variants_list = QListWidget(self)
        self._variants_list.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        self._variants_list.setWordWrap(True)
        self._variants_list.setItemDelegate(_VariantItemDelegate(self._variants_list))
        self._variants_list.currentItemChanged.connect(lambda _cur, _prev: self._update_variant_buttons_state())
        variants_layout.addWidget(self._variants_list, 1)
        self._detail_splitter.addWidget(self._variants_pane)
        self._set_variants_visible(False)

        lower_details_pane = _DetailPane(self)
        lower_details_layout = QVBoxLayout(lower_details_pane)
        lower_details_layout.setContentsMargins(0, 0, 0, 0)
        variants_btn_layout = QHBoxLayout()
        self._apply_variant_button = QPushButton(tr('Apply selected variant'), self)
        self._apply_variant_button.setToolTip(
            tr('Apply the selected variant translation, confirm the term, and move to the next entry.')
        )
        self._apply_variant_button.clicked.connect(self._on_apply_selected_variant)
        variants_btn_layout.addWidget(self._apply_variant_button)

        self._discuss_variant_button = QPushButton(tr('Discuss with AI…'), self)
        self._discuss_variant_button.setToolTip(
            tr('Open AI chat with term context to discuss the proposed variants.')
        )
        self._discuss_variant_button.clicked.connect(self._on_discuss_variants_clicked)
        variants_btn_layout.addWidget(self._discuss_variant_button)
        variants_btn_layout.addStretch()
        lower_details_layout.addLayout(variants_btn_layout)

        self._lower_detail_splitter = QSplitter(Qt.Orientation.Vertical, lower_details_pane)
        self._lower_detail_splitter.setHandleWidth(6)
        lower_details_layout.addWidget(self._lower_detail_splitter, 1)
        self._detail_splitter.addWidget(lower_details_pane)

        notes_pane = _DetailPane(self)
        notes_layout = QVBoxLayout(notes_pane)
        notes_layout.setContentsMargins(0, 0, 0, 0)
        self._profiled_checkbox = QCheckBox(tr('Profiled via AI (Speech Profile generated)'), self)
        notes_layout.addWidget(self._profiled_checkbox)
        notes_row = QHBoxLayout()
        notes_label = QLabel(tr('Description:'), self)
        notes_row.addWidget(notes_label)
        self._notes_variation_default_text = tr('AI Variations')
        self._notes_variation_button = QPushButton(self._notes_variation_default_text, self)
        self._notes_variation_button.clicked.connect(self._on_notes_variation_clicked)
        self._notes_variation_busy = False
        notes_row.addWidget(self._notes_variation_button)
        notes_row.addStretch()
        notes_layout.addLayout(notes_row)
        if not self._ai_variation_callback:
            self._notes_variation_button.hide()
        self._notes_edit = QPlainTextEdit(self)
        notes_layout.addWidget(self._notes_edit, 1)
        self._lower_detail_splitter.addWidget(notes_pane)

        ai_notes_pane = _DetailPane(self)
        ai_notes_layout = QVBoxLayout(ai_notes_pane)
        ai_notes_layout.setContentsMargins(0, 0, 0, 0)
        ai_notes_label = QLabel(tr('AI notes and unresolved choices:'), self)
        ai_notes_layout.addWidget(ai_notes_label)
        self._ai_notes_edit = QPlainTextEdit(self)
        self._ai_notes_edit.setReadOnly(True)
        self._ai_notes_edit.setUndoRedoEnabled(False)
        self._ai_notes_edit.setPlaceholderText(tr('No AI doubts or alternative choices recorded.'))
        ai_notes_layout.addWidget(self._ai_notes_edit, 1)
        self._lower_detail_splitter.addWidget(ai_notes_pane)

        occurrences_pane = _DetailPane(self)
        occurrences_layout = QVBoxLayout(occurrences_pane)
        occurrences_layout.setContentsMargins(0, 0, 0, 0)
        self._occurrence_label = QLabel(tr('Mentions: 0   Spoken: 0'), self)
        occurrences_layout.addWidget(self._occurrence_label)
        self._occurrence_list = QListWidget(self)
        self._occurrence_list.setSpacing(6)
        self._occurrence_list.setWordWrap(True)
        self._occurrence_list.setTextElideMode(Qt.TextElideMode.ElideNone)
        self._occurrence_list.setItemDelegate(_RichTextItemDelegate(self._occurrence_list))
        self._occurrence_list.itemDoubleClicked.connect(self._activate_selected_occurrence)
        occurrences_layout.addWidget(self._occurrence_list, 1)
        self._lower_detail_splitter.addWidget(occurrences_pane)
        self._detail_splitter.setStretchFactor(0, 1)
        self._detail_splitter.setStretchFactor(1, 3)
        self._detail_splitter.setSizes([140, 540])
        self._lower_detail_splitter.setStretchFactor(0, 1)
        self._lower_detail_splitter.setStretchFactor(1, 1)
        self._lower_detail_splitter.setStretchFactor(2, 1)
        self._lower_detail_splitter.setSizes([180, 160, 200])
        button_box = QDialogButtonBox(QDialogButtonBox.StandardButton.Close, parent=self)
        close_btn = button_box.button(QDialogButtonBox.StandardButton.Close)
        if close_btn is not None:
            close_btn.setText(tr('Close'))

        self._save_button = QPushButton(tr('Save Changes'), self)
        self._save_button.clicked.connect(self._save_editor_changes)
        button_box.addButton(self._save_button, QDialogButtonBox.ButtonRole.ActionRole)
        if self._update_callback is None:
            self._save_button.setVisible(False)

        self._global_replace_button = QPushButton(tr('Global Replace...'), self)
        self._global_replace_button.setStyleSheet("background-color: #0d9488; color: white; font-weight: bold;")
        self._global_replace_button.clicked.connect(self._on_global_replace_clicked)
        button_box.addButton(self._global_replace_button, QDialogButtonBox.ButtonRole.ActionRole)
        if self._update_callback is None or self._global_replace_callback is None:
            self._global_replace_button.setVisible(False)
            
        # Same single route as Tools and the pipeline wizard.
        self._build_button = QPushButton(tr('Run automatic glossary pass...'), self)
        self._build_button.setStyleSheet("background-color: #2563eb; color: white; font-weight: bold;")
        self._build_button.setToolTip(
            tr('Seed, discover, describe, and propose translations in one uninterrupted pass.')
        )
        self._build_button.clicked.connect(self._on_build_clicked)
        button_box.addButton(self._build_button, QDialogButtonBox.ButtonRole.ActionRole)
        if self._build_callback is None:
            self._build_button.setVisible(False)

        self._ai_classify_button = QPushButton(tr('Organize via AI'), self)
        self._ai_classify_button.setStyleSheet("background-color: #8b5cf6; color: white; font-weight: bold;")
        self._ai_classify_button.clicked.connect(self._on_ai_classify_clicked)
        button_box.addButton(self._ai_classify_button, QDialogButtonBox.ButtonRole.ActionRole)
        if self._ai_classify_callback is None:
            self._ai_classify_button.setVisible(False)
            
        self._clear_button = QPushButton(tr('Clear Glossary'), self)
        self._clear_button.setStyleSheet("background-color: #b91c1c; color: white; font-weight: bold;")
        self._clear_button.setToolTip(tr('Remove every entry. The glossary file is backed up first.'))
        self._clear_button.clicked.connect(self._on_clear_clicked)
        button_box.addButton(self._clear_button, QDialogButtonBox.ButtonRole.DestructiveRole)
        if self._clear_callback is None:
            self._clear_button.setVisible(False)

        button_box.rejected.connect(self.reject)
        layout.addWidget(button_box)
        self._translation_edit.textChanged.connect(self._on_editor_content_changed)
        self._notes_edit.textChanged.connect(self._on_editor_content_changed)
        self._profiled_checkbox.stateChanged.connect(self._on_editor_content_changed)
        self._category_combo.currentTextChanged.connect(self._on_editor_content_changed)
        self._update_editor_enabled_state()
        self._load_dialog_state()
        self._populate_entries(self._filtered_entries)

        if initial_term:
            QTimer.singleShot(0, lambda: self.focus_term(initial_term))
        elif self._filtered_entries:
            self._active_table().selectRow(0)
            self._show_entry_for_row(0)
