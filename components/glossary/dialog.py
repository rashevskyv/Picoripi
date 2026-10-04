"""GlossaryDialog composition and __init__."""
from __future__ import annotations

from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Sequence, Tuple

from PyQt6.QtCore import Qt, QTimer
from PyQt6.QtGui import QKeySequence, QShortcut
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
        external_reference_callback: Optional[Callable[[str], Optional[str]]] = None,
        force_retranslate_callback: Optional[Callable[[], None]] = None,
        reference_data: Optional[Dict[Tuple[int, int], str]] = None,
        reference_language: Optional[str] = None,
        source_data: Optional[Any] = None,
        transfer_callback: Optional[Callable[[List[GlossaryEntry]], None]] = None,
        transfer_label: str = "",
        series_menu_callback: Optional[Callable[[], None]] = None,
        embedded: bool = False,
    ) -> None:
        """Initialize a new instance.

        ``embedded`` builds the dialog as a page for another dialog's tab (the
        series glossary): no window of its own, no Close or Companion buttons.
        ``transfer_callback`` receives the selected entries for the button
        labelled ``transfer_label`` (copy to / promote into the other glossary).
        """
        super().__init__(None)
        self._embedded = embedded
        self.setWindowTitle(tr('Glossary'))
        if not embedded:
            show_as_independent_window(self)
        self.resize(840, 520)

        self._force_retranslate_callback = force_retranslate_callback
        self._parent = parent

        parent_settings = getattr(parent, 'settings_manager', None)
        import utils.constants as constants
        settings_path = getattr(parent_settings, 'settings_file_path', None) or constants.SETTINGS_FILE_PATH
        self._settings_path = Path(settings_path)
        self._restore_maximized_on_show = False
        self._current_entry: Optional[GlossaryEntry] = None
        self._suppress_editor_signals = False
        self._editor_dirty = False
        self._notes_collapsed = False
        self._ai_notes_collapsed = False
        self._occurrences_collapsed = False
        # Notes as stored (may hold the term placeholder); the editor shows them
        # rendered against the current translation.
        self._notes_template = ""

        if embedded:
            self.setWindowFlags(Qt.WindowType.Widget)
        else:
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
        self._external_reference_callback = external_reference_callback
        self._transfer_callback = transfer_callback
        # Canonical term key -> tooltip for terms the other glossary translates differently.
        self._conflicts: Dict[str, str] = {}
        self._series_page: Optional["GlossaryDialog"] = None
        self._series_tabs: Optional[QTabWidget] = None
        self._reference_data: Dict[Tuple[int, int], str] = dict(reference_data) if reference_data else {}
        self._reference_language: Optional[str] = reference_language
        self._source_data = source_data
        if self._source_data is None and parent is not None:
            data_store = getattr(parent, "data_store", None)
            if data_store is not None:
                self._source_data = getattr(data_store, "data", None)
        self._current_speaker_code = ""
        self._current_speaker_is_provisional = False
        self._initial_term = initial_term
        self._pending_select_term: Optional[str] = None
        self._is_populating = False

        self._tables: Dict[str, QTableWidget] = {}
        self._entry_table: Optional[QTableWidget] = None # Legacy compatibility

        # The content sits in its own widget so a linked series glossary can put
        # it in a tab next to its own page (set_series_page).
        self._outer_layout = QVBoxLayout(self)
        self._content = QWidget(self)
        self._outer_layout.addWidget(self._content)
        layout = QVBoxLayout(self._content)
        layout.setContentsMargins(0, 0, 0, 0)

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
        layout.addLayout(search_layout)

        self._unconfirmed_only_checkbox = QCheckBox(tr('Needs review'), self)
        self._unconfirmed_only_checkbox.setToolTip(
            tr('Show only entries still awaiting your decision — highlighted rows: several translation variants were proposed, or the entry has not been confirmed yet.')
        )
        self._unconfirmed_only_checkbox.stateChanged.connect(
            lambda _state: self._apply_filter(self._search_field.text())
        )

        self._main_splitter = QSplitter(Qt.Orientation.Horizontal, self)
        self._main_splitter.setHandleWidth(6)
        layout.addWidget(self._main_splitter, 1)

        left_panel = QWidget(self)
        left_layout = QVBoxLayout(left_panel)
        left_layout.setContentsMargins(0, 0, 0, 0)
        left_layout.setSpacing(4)

        self._tab_widget = QTabWidget(self)
        self._tab_widget.currentChanged.connect(self._on_tab_changed)
        left_layout.addWidget(self._tab_widget, 1)

        left_bottom_bar = QHBoxLayout()
        left_bottom_bar.setContentsMargins(2, 2, 2, 2)
        left_bottom_bar.addWidget(self._unconfirmed_only_checkbox)
        left_bottom_bar.addStretch()
        left_layout.addLayout(left_bottom_bar)

        self._main_splitter.addWidget(left_panel)

        right_panel = QWidget(self)
        right_layout = QVBoxLayout(right_panel)
        self._main_splitter.addWidget(right_panel)
        self._main_splitter.setStretchFactor(0, 1)
        self._main_splitter.setStretchFactor(1, 1)
        self._main_splitter.setSizes([360, 480])
        self._original_label = QLabel(tr(''), self)
        self._original_label.setWordWrap(True)
        self._original_label.setVisible(False)  # Preserved for backward compatibility

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

        # Term & Translation row: horizontal splitter allowing user to freely adjust boundary
        self._term_trans_splitter = QSplitter(Qt.Orientation.Horizontal, self)
        self._term_trans_splitter.setHandleWidth(6)
        self._term_trans_splitter.setChildrenCollapsible(False)

        # Left pane: Original (letter O with tooltip)
        orig_pane = QWidget(self)
        orig_box = QHBoxLayout(orig_pane)
        orig_box.setContentsMargins(0, 0, 4, 0)
        orig_box.setSpacing(4)

        self._orig_field_label = QLabel(tr("O:"), self)
        self._orig_field_label.setToolTip(tr("Original"))
        self._orig_field_label.setStyleSheet("font-weight: bold;")
        orig_box.addWidget(self._orig_field_label)

        self._original_edit = QLineEdit(self)
        self._original_edit.setReadOnly(True)
        self._original_edit.setFixedHeight(26)
        self._original_edit.setMinimumWidth(80)
        self._original_edit.setPlaceholderText(tr('Original term...'))
        self._original_edit.setStyleSheet("QLineEdit { font-weight: bold; }")
        orig_box.addWidget(self._original_edit, 1)

        self._term_trans_splitter.addWidget(orig_pane)

        # Right pane: Translation (letter T with tooltip)
        trans_pane = QWidget(self)
        trans_box = QHBoxLayout(trans_pane)
        trans_box.setContentsMargins(4, 0, 0, 0)
        trans_box.setSpacing(4)

        self._trans_field_label = QLabel(tr("T:"), self)
        self._trans_field_label.setToolTip(tr("Translation"))
        self._trans_field_label.setStyleSheet("font-weight: bold;")
        trans_box.addWidget(self._trans_field_label)

        self._translation_edit = QLineEdit(self)
        self._translation_edit.setFixedHeight(26)
        self._translation_edit.setMinimumWidth(80)
        trans_box.addWidget(self._translation_edit, 1)

        self._term_trans_splitter.addWidget(trans_pane)

        self._term_trans_splitter.setStretchFactor(0, 1)
        self._term_trans_splitter.setStretchFactor(1, 1)
        self._term_trans_splitter.setSizes([260, 260])

        right_layout.addWidget(self._term_trans_splitter)

        # Action buttons row: placed below term & translation splitter
        actions_box = QHBoxLayout()
        actions_box.setContentsMargins(0, 4, 0, 4)
        actions_box.setSpacing(4)

        self._wiki_link_button = QPushButton(tr('Wiki ↗'), self)
        self._wiki_link_button.setFixedHeight(26)
        self._wiki_link_button.setStyleSheet("QPushButton { padding: 2px 8px; }")
        self._wiki_link_button.setToolTip(tr('Open external wiki reference for this term'))
        self._wiki_link_button.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)
        self._wiki_link_button.setVisible(False)
        self._wiki_link_button.clicked.connect(self._on_open_wiki_link)
        actions_box.addWidget(self._wiki_link_button)

        self._save_term_button = QPushButton(tr('Save'), self)
        self._save_term_button.setFixedHeight(26)
        self._save_term_button.setStyleSheet("QPushButton { padding: 2px 8px; }")
        self._save_term_button.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)
        self._save_term_button.setToolTip(tr('Save changes to this term (Ctrl+S)'))
        self._save_term_button.setEnabled(False)
        self._save_term_button.clicked.connect(lambda: self._save_editor_changes())
        actions_box.addWidget(self._save_term_button)
        self._save_description_button = self._save_term_button
        self._save_notes_button = self._save_term_button

        self._confirm_button = QPushButton(tr('Confirm translation'), self)
        self._confirm_button.setFixedHeight(26)
        self._confirm_button.setStyleSheet("QPushButton { padding: 2px 8px; }")
        self._confirm_button.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)
        self._confirm_button.setToolTip(
            tr('Mark this translation as decided and move to the next term. Unreviewed rows stay pale yellow; several proposed variants stay orange until you pick one.')
        )
        self._confirm_button.clicked.connect(lambda: self._on_confirm_clicked(advance=True))
        actions_box.addWidget(self._confirm_button)

        self._discuss_variant_button = QPushButton(tr('Discuss with AI…'), self)
        self._discuss_variant_button.setFixedHeight(26)
        self._discuss_variant_button.setStyleSheet("QPushButton { padding: 2px 8px; }")
        self._discuss_variant_button.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)
        self._discuss_variant_button.setToolTip(
            tr('Open AI chat with term context to discuss this entry.')
        )
        self._discuss_variant_button.clicked.connect(self._on_discuss_variants_clicked)
        actions_box.addWidget(self._discuss_variant_button)
        self._discuss_entry_button = self._discuss_variant_button

        actions_box.addStretch()

        right_layout.addLayout(actions_box)

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
        self._variants_list.itemDoubleClicked.connect(self._on_variant_double_clicked)
        variants_layout.addWidget(self._variants_list, 1)
        self._detail_splitter.addWidget(self._variants_pane)
        self._set_variants_visible(False)

        lower_details_pane = _DetailPane(self)
        self._lower_details_pane = lower_details_pane
        self._lower_details_pane.setMinimumHeight(60)
        lower_details_layout = QVBoxLayout(lower_details_pane)
        lower_details_layout.setContentsMargins(0, 0, 0, 0)
        variants_btn_layout = QHBoxLayout()
        self._apply_variant_button = QPushButton(tr('Apply selected variant'), self)
        self._apply_variant_button.setToolTip(
            tr('Apply the selected variant translation to the editor.')
        )
        self._apply_variant_button.clicked.connect(self._on_apply_selected_variant)
        variants_btn_layout.addWidget(self._apply_variant_button)
        variants_btn_layout.addStretch()
        lower_details_layout.addLayout(variants_btn_layout)

        self._lower_detail_splitter = QSplitter(Qt.Orientation.Vertical, lower_details_pane)
        self._lower_detail_splitter.setHandleWidth(6)
        self._lower_detail_splitter.setChildrenCollapsible(False)
        lower_details_layout.addWidget(self._lower_detail_splitter, 1)
        self._detail_splitter.addWidget(lower_details_pane)

        notes_pane = _DetailPane(self)
        self._notes_pane = notes_pane
        notes_layout = QVBoxLayout(notes_pane)
        notes_layout.setContentsMargins(0, 0, 0, 0)
        notes_layout.setSpacing(2)

        notes_header = QHBoxLayout()
        notes_header.setContentsMargins(0, 0, 0, 0)
        notes_header.setSpacing(6)
        self._notes_collapse_button = QPushButton("▼", self)
        self._notes_collapse_button.setFixedSize(22, 22)
        self._notes_collapse_button.setCursor(Qt.CursorShape.PointingHandCursor)
        self._notes_collapse_button.setStyleSheet("QPushButton { font-size: 10px; font-weight: bold; padding: 0px; }")
        self._notes_collapse_button.setToolTip(tr("Collapse/Expand section"))
        notes_header.addWidget(self._notes_collapse_button)

        notes_label = QLabel(tr('Description:'), self)
        notes_label.setStyleSheet("font-weight: bold;")
        notes_header.addWidget(notes_label)

        self._notes_variation_default_text = tr('AI Variations')
        self._notes_variation_button = QPushButton(self._notes_variation_default_text, self)
        self._notes_variation_button.clicked.connect(self._on_notes_variation_clicked)
        self._notes_variation_busy = False
        notes_header.addWidget(self._notes_variation_button)

        notes_header.addStretch()

        self._profiled_checkbox = QCheckBox(tr('Profiled via AI (Speech Profile generated)'), self)
        self._profiled_checkbox.setToolTip(
            tr('Indicates that an AI speech profile has been generated for this character. Automated profiling workers will skip re-analyzing marked characters. Changes are saved with the entry.')
        )
        notes_header.addWidget(self._profiled_checkbox)
        notes_layout.addLayout(notes_header)

        if not self._ai_variation_callback:
            self._notes_variation_button.hide()

        self._notes_edit = QPlainTextEdit(self)
        notes_layout.addWidget(self._notes_edit, 1)

        self._notes_collapse_button.clicked.connect(self._toggle_notes)

        self._lower_detail_splitter.addWidget(notes_pane)

        ai_notes_pane = _DetailPane(self)
        self._ai_notes_pane = ai_notes_pane
        ai_notes_layout = QVBoxLayout(ai_notes_pane)
        ai_notes_layout.setContentsMargins(0, 0, 0, 0)
        ai_notes_layout.setSpacing(2)

        ai_notes_header = QHBoxLayout()
        ai_notes_header.setContentsMargins(0, 0, 0, 0)
        ai_notes_header.setSpacing(6)
        self._ai_notes_collapse_button = QPushButton("▼", self)
        self._ai_notes_collapse_button.setFixedSize(22, 22)
        self._ai_notes_collapse_button.setCursor(Qt.CursorShape.PointingHandCursor)
        self._ai_notes_collapse_button.setToolTip(tr("Collapse section"))
        self._ai_notes_collapse_button.setStyleSheet("QPushButton { font-size: 10px; font-weight: bold; padding: 0px; }")

        ai_notes_header.addWidget(self._ai_notes_collapse_button)

        ai_notes_label = QLabel(tr('AI notes and unresolved choices:'), self)
        ai_notes_label.setStyleSheet("font-weight: bold;")
        ai_notes_header.addWidget(ai_notes_label)
        ai_notes_header.addStretch()

        ai_notes_layout.addLayout(ai_notes_header)

        self._ai_notes_edit = QPlainTextEdit(self)
        self._ai_notes_edit.setReadOnly(False)
        self._ai_notes_edit.setUndoRedoEnabled(True)
        self._ai_notes_edit.setPlaceholderText(tr('Enter user notes or view AI remarks...'))
        ai_notes_layout.addWidget(self._ai_notes_edit, 1)

        self._ai_notes_collapse_button.clicked.connect(self._toggle_ai_notes)

        self._lower_detail_splitter.addWidget(ai_notes_pane)

        occurrences_pane = _DetailPane(self)
        self._occurrences_pane = occurrences_pane
        occurrences_layout = QVBoxLayout(occurrences_pane)
        occurrences_layout.setContentsMargins(0, 0, 0, 0)
        occurrences_layout.setSpacing(2)

        occ_header = QHBoxLayout()
        occ_header.setContentsMargins(0, 0, 0, 0)
        occ_header.setSpacing(6)
        self._occ_collapse_button = QPushButton("▼", self)
        self._occ_collapse_button.setFixedSize(22, 22)
        self._occ_collapse_button.setCursor(Qt.CursorShape.PointingHandCursor)
        self._occ_collapse_button.setToolTip(tr("Collapse section"))
        self._occ_collapse_button.setStyleSheet("QPushButton { font-size: 10px; font-weight: bold; padding: 0px; }")

        occ_header.addWidget(self._occ_collapse_button)

        occ_title = QLabel(tr('Occurrences:'), self)
        occ_title.setStyleSheet("font-weight: bold;")
        occ_header.addWidget(occ_title)

        self._show_mentions_checkbox = QCheckBox(tr('Mentions'), self)
        self._show_mentions_checkbox.setChecked(True)
        self._show_mentions_checkbox.setToolTip(tr('Show text occurrences where this term is mentioned'))
        self._show_mentions_checkbox.toggled.connect(lambda _checked: self._repopulate_occurrences_filter())
        occ_header.addWidget(self._show_mentions_checkbox)

        self._show_spoken_checkbox = QCheckBox(tr('Spoken'), self)
        self._show_spoken_checkbox.setChecked(True)
        self._show_spoken_checkbox.setToolTip(tr('Show dialogue lines spoken by this character'))
        self._show_spoken_checkbox.toggled.connect(lambda _checked: self._repopulate_occurrences_filter())
        occ_header.addWidget(self._show_spoken_checkbox)

        occ_header.addStretch()
        self._occurrence_label = QLabel(tr('Mentions: 0   Spoken: 0'), self)
        self._occurrence_label.setStyleSheet("color: #666;")
        occ_header.addWidget(self._occurrence_label)
        occurrences_layout.addLayout(occ_header)

        self._occurrence_list = QListWidget(self)
        self._occurrence_list.setSpacing(6)
        self._occurrence_list.setWordWrap(True)
        self._occurrence_list.setVerticalScrollMode(QListWidget.ScrollMode.ScrollPerPixel)
        self._occurrence_list.setTextElideMode(Qt.TextElideMode.ElideNone)
        self._occurrence_list.setItemDelegate(_RichTextItemDelegate(self._occurrence_list))
        self._occurrence_list.itemDoubleClicked.connect(self._activate_selected_occurrence)
        occurrences_layout.addWidget(self._occurrence_list, 1)

        self._occ_collapse_button.clicked.connect(self._toggle_occ)

        self._lower_detail_splitter.addWidget(occurrences_pane)
        self._detail_splitter.setStretchFactor(0, 1)
        self._detail_splitter.setStretchFactor(1, 3)
        self._detail_splitter.setSizes([120, 450])
        self._lower_detail_splitter.setStretchFactor(0, 1)
        self._lower_detail_splitter.setStretchFactor(1, 1)
        self._lower_detail_splitter.setStretchFactor(2, 1)
        self._lower_detail_splitter.setSizes([150, 150, 150])
        button_box = QDialogButtonBox(QDialogButtonBox.StandardButton.Close, parent=self)
        close_btn = button_box.button(QDialogButtonBox.StandardButton.Close)
        if close_btn is not None:
            close_btn.setText(tr('Close'))

        self._save_button = QPushButton(tr('Save Changes'), self)
        self._save_button.clicked.connect(lambda: self._save_editor_changes())
        button_box.addButton(self._save_button, QDialogButtonBox.ButtonRole.ActionRole)
        self._save_shortcut = QShortcut(QKeySequence.StandardKey.Save, self)
        self._save_shortcut.activated.connect(lambda: self._save_editor_changes())
        if self._update_callback is None:
            self._save_button.setVisible(False)
            self._save_shortcut.setEnabled(False)

        self._global_replace_button = QPushButton(tr('Global Replace...'), self)
        self._global_replace_button.setStyleSheet("QPushButton { background-color: #0d9488; color: white; font-weight: bold; }")
        self._global_replace_button.clicked.connect(self._on_global_replace_clicked)
        button_box.addButton(self._global_replace_button, QDialogButtonBox.ButtonRole.ActionRole)
        if self._update_callback is None or self._global_replace_callback is None:
            self._global_replace_button.setVisible(False)
            
        # Same single route as Tools and the pipeline wizard.
        self._build_button = QPushButton(tr('Run automatic glossary pass...'), self)
        self._build_button.setStyleSheet("QPushButton { background-color: #2563eb; color: white; font-weight: bold; }")
        self._build_button.setToolTip(
            tr('Seed, discover, describe, and propose translations in one uninterrupted pass.')
        )
        self._build_button.clicked.connect(self._on_build_clicked)
        button_box.addButton(self._build_button, QDialogButtonBox.ButtonRole.ActionRole)
        if self._build_callback is None:
            self._build_button.setVisible(False)

        self._retranslate_button = QPushButton(tr('Force Retranslate...'), self)
        self._retranslate_button.setStyleSheet("QPushButton { background-color: #ea580c; color: white; font-weight: bold; }")
        self._retranslate_button.setToolTip(
            tr('Retranslate all entries with AI using current rules, overwriting existing translations with newly proposed variants.')
        )
        self._retranslate_button.clicked.connect(self._on_force_retranslate_clicked)
        button_box.addButton(self._retranslate_button, QDialogButtonBox.ButtonRole.ActionRole)
        if self._force_retranslate_callback is None:
            self._retranslate_button.setVisible(False)

        self._ai_classify_button = QPushButton(tr('Organize via AI'), self)
        self._ai_classify_button.setStyleSheet("QPushButton { background-color: #8b5cf6; color: white; font-weight: bold; }")
        self._ai_classify_button.clicked.connect(self._on_ai_classify_clicked)
        button_box.addButton(self._ai_classify_button, QDialogButtonBox.ButtonRole.ActionRole)
        if self._ai_classify_callback is None:
            self._ai_classify_button.setVisible(False)

        self._companion_sync_button = QPushButton(tr('☁ Companion Sync...'), self)
        self._companion_sync_button.setStyleSheet("QPushButton { background-color: #6366f1; color: white; font-weight: bold; }")
        self._companion_sync_button.setToolTip(
            tr('Push glossary & occurrences to mobile Companion or pull reviewed translations from your phone.')
        )
        self._companion_sync_button.clicked.connect(self._on_companion_sync_clicked)
        button_box.addButton(self._companion_sync_button, QDialogButtonBox.ButtonRole.ActionRole)
            
        self._transfer_button = QPushButton(transfer_label, self)
        self._transfer_button.setToolTip(tr('Copy the selected terms into the other glossary. A term it already has takes this translation.'))
        self._transfer_button.clicked.connect(self._on_transfer_clicked)
        button_box.addButton(self._transfer_button, QDialogButtonBox.ButtonRole.ActionRole)
        self._transfer_button.setVisible(transfer_callback is not None and embedded)

        self._series_menu_button = QPushButton(tr('Series Glossary...'), self)
        self._series_menu_button.setToolTip(
            tr('Link this project to a glossary shared by the games of a series, create one, or import one from a JSON file.')
        )
        self._series_menu_button.clicked.connect(lambda: series_menu_callback and series_menu_callback())
        button_box.addButton(self._series_menu_button, QDialogButtonBox.ButtonRole.ActionRole)
        self._series_menu_button.setVisible(series_menu_callback is not None)

        self._clear_button = QPushButton(tr('Clear Glossary'), self)
        self._clear_button.setStyleSheet("QPushButton { background-color: #b91c1c; color: white; font-weight: bold; }")
        self._clear_button.setToolTip(tr('Remove every entry. The glossary file is backed up first.'))
        self._clear_button.clicked.connect(self._on_clear_clicked)
        button_box.addButton(self._clear_button, QDialogButtonBox.ButtonRole.DestructiveRole)
        if self._clear_callback is None:
            self._clear_button.setVisible(False)

        button_box.rejected.connect(self.reject)
        layout.addWidget(button_box)
        if embedded:
            if close_btn is not None:
                close_btn.setVisible(False)
            self._companion_sync_button.setVisible(False)
            self._save_shortcut.setContext(Qt.ShortcutContext.WidgetWithChildrenShortcut)
        self._translation_edit.textChanged.connect(self._on_editor_content_changed)
        self._notes_edit.textChanged.connect(self._on_editor_content_changed)
        self._ai_notes_edit.textChanged.connect(self._on_editor_content_changed)
        self._profiled_checkbox.stateChanged.connect(self._on_editor_content_changed)
        self._category_combo.currentTextChanged.connect(self._on_editor_content_changed)
        self._update_editor_enabled_state()
        self._load_dialog_state()
        if embedded:
            self._restore_maximized_on_show = False
        self._populate_entries(self._filtered_entries)

        if initial_term:
            QTimer.singleShot(0, lambda: self.focus_term(initial_term))
        elif self._filtered_entries:
            self._active_table().selectRow(0)
            self._show_entry_for_row(0)

    def _set_section_collapsed(self, section_name: str, collapsed: bool, update_splitter: bool = True) -> None:
        """Collapse or expand a detail section cleanly, updating splitter sizes."""
        section_map = {
            "notes": {
                "attr": "_notes_collapsed",
                "pane": getattr(self, "_notes_pane", None),
                "content": getattr(self, "_notes_edit", None),
                "button": getattr(self, "_notes_collapse_button", None),
                "idx": 0,
            },
            "ai_notes": {
                "attr": "_ai_notes_collapsed",
                "pane": getattr(self, "_ai_notes_pane", None),
                "content": getattr(self, "_ai_notes_edit", None),
                "button": getattr(self, "_ai_notes_collapse_button", None),
                "idx": 1,
            },
            "occurrences": {
                "attr": "_occurrences_collapsed",
                "pane": getattr(self, "_occurrences_pane", None),
                "content": getattr(self, "_occurrence_list", None),
                "button": getattr(self, "_occ_collapse_button", None),
                "idx": 2,
            },
        }
        info = section_map.get(section_name)
        if not info or info["pane"] is None or info["content"] is None or info["button"] is None:
            return

        setattr(self, info["attr"], collapsed)
        info["button"].setText("▶" if collapsed else "▼")
        info["button"].setToolTip(tr("Expand section") if collapsed else tr("Collapse section"))

        pane = info["pane"]
        content = info["content"]
        idx = info["idx"]

        if collapsed:
            content.setHidden(True)
            content.setMinimumHeight(0)
            pane.setMinimumHeight(0)
            pane.setMaximumHeight(32)
        else:
            content.setHidden(False)
            content.setMinimumHeight(50)
            pane.setMaximumHeight(16777215)
            pane.setMinimumHeight(80)

        if update_splitter and hasattr(self, "_lower_detail_splitter"):
            self._rebalance_lower_splitter(focus_idx=idx, just_expanded=not collapsed)

    def _rebalance_lower_splitter(self, focus_idx: int = -1, just_expanded: bool = False) -> None:
        """Rebalance splitter sizes across lower detail panes without squishing."""
        if not hasattr(self, "_lower_detail_splitter"):
            return
        sizes = list(self._lower_detail_splitter.sizes())
        if len(sizes) != 3:
            return

        total_h = sum(sizes)
        if total_h <= 0:
            total_h = self._lower_detail_splitter.height()
        if total_h <= 0:
            total_h = 450

        # If expanding and available height in lower_splitter is too constrained,
        # try to borrow space from _variants_pane in _detail_splitter if possible.
        if just_expanded and hasattr(self, "_detail_splitter"):
            ds = self._detail_splitter.sizes()
            if len(ds) == 2 and ds[0] > 160 and ds[1] < 280:
                needed = 280 - ds[1]
                can_take = ds[0] - 120
                shift = max(0, min(needed, can_take))
                if shift > 0:
                    self._detail_splitter.setSizes([ds[0] - shift, ds[1] + shift])
                    total_h = sum(self._lower_detail_splitter.sizes())
                    if total_h <= 0:
                        total_h = 450

        collapsed = [
            bool(getattr(self, "_notes_collapsed", False)),
            bool(getattr(self, "_ai_notes_collapsed", False)),
            bool(getattr(self, "_occurrences_collapsed", False)),
        ]
        num_expanded = 3 - sum(collapsed)

        if num_expanded == 0:
            self._lower_detail_splitter.setSizes([32, 32, 32])
            return

        # Target minimum height for expanded sections: at least 90px
        collapsed_cost = sum(32 for c in collapsed if c)
        available_expanded = max(90 * num_expanded, total_h - collapsed_cost)

        new_sizes = [32, 32, 32]
        if num_expanded == 1:
            for i in range(3):
                if not collapsed[i]:
                    new_sizes[i] = available_expanded
        elif num_expanded == 2:
            exp_indices = [i for i in range(3) if not collapsed[i]]
            half = available_expanded // 2
            new_sizes[exp_indices[0]] = half
            new_sizes[exp_indices[1]] = available_expanded - half
        else: # All 3 expanded
            third = available_expanded // 3
            new_sizes[0] = third
            new_sizes[1] = third
            new_sizes[2] = available_expanded - (2 * third)

        self._lower_detail_splitter.setSizes(new_sizes)

    def _toggle_notes(self) -> None:
        self._set_section_collapsed("notes", not getattr(self, "_notes_collapsed", False))

    def _toggle_ai_notes(self) -> None:
        self._set_section_collapsed("ai_notes", not getattr(self, "_ai_notes_collapsed", False))

    def _toggle_occ(self) -> None:
        self._set_section_collapsed("occurrences", not getattr(self, "_occurrences_collapsed", False))

    # ── Series glossary ────────────────────────────────────────────────

    def set_series_page(self, page: Optional["GlossaryDialog"], label: str = "") -> None:
        """Show ``page`` (the linked series glossary) as a tab next to this glossary; None removes it."""
        if self._series_page is not None and self._series_tabs is not None:
            self._series_tabs.removeTab(self._series_tabs.indexOf(self._series_page))
            self._series_page.deleteLater()
        self._series_page = page
        self._transfer_button.setVisible(self._transfer_callback is not None and page is not None)
        if page is None:
            return
        if self._series_tabs is None:
            self._outer_layout.removeWidget(self._content)
            self._series_tabs = QTabWidget(self)
            self._series_tabs.addTab(self._content, tr('Project Glossary'))
            self._outer_layout.addWidget(self._series_tabs)
        self._series_tabs.addTab(page, label)

    def set_conflicts(self, conflicts: Dict[str, str]) -> None:
        """Mark terms the other glossary translates differently: canonical key -> tooltip."""
        self._conflicts = dict(conflicts)
        self._populate_entries(self._filtered_entries)

    def _selected_entries(self) -> List[GlossaryEntry]:
        """Entries of the selected rows of the visible table, else the current entry."""
        table = self._active_table()
        rows = sorted({index.row() for index in table.selectionModel().selectedRows()}) if table.selectionModel() else []
        entries = [entry for entry in (self._entry_for_row(row) for row in rows) if entry is not None]
        return entries or ([self._current_entry] if self._current_entry else [])

    def _on_transfer_clicked(self) -> None:
        entries = self._selected_entries()
        if self._transfer_callback and entries:
            self._transfer_callback(entries)
