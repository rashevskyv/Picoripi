"""Dialog for viewing glossary entries and navigating to occurrences."""
from __future__ import annotations
import json
from html import escape
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Sequence, Tuple
from PyQt6.QtCore import Qt, QRect, QSize, QTimer
from PyQt6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QMenu,
    QMessageBox,
    QPushButton,
    QSplitter,
    QTableWidget,
    QTableWidgetItem,
    QPlainTextEdit,
    QStyledItemDelegate,
    QStyle,
    QTabWidget,
    QVBoxLayout,
    QWidget,
    QAbstractItemView,
)
from PyQt6.QtGui import QPalette, QTextDocument, QAbstractTextDocumentLayout, QColor, QBrush
from core.glossary_manager import (
    STATUS_CONFIRMED,
    STATUS_TRANSLATED,
    TERM_PLACEHOLDER,
    GlossaryEntry,
    GlossaryOccurrence,
    render_notes,
)

# Rows awaiting a human decision. Translucent so it tints the row without
# fighting the selection highlight or the light/dark palette.
_NEEDS_REVIEW_BRUSH = QBrush(QColor(255, 200, 0, 60))
# Foreground color for provisional game-code character rows, matching
# Merge Speakers "Unmatched manual rows".
_PROVISIONAL_FOREGROUND = QBrush(QColor("#6a1b9a"))
class _RichTextItemDelegate(QStyledItemDelegate):
    """Render rich-text list items (e.g., occurrences list)."""

    def paint(self, painter, option, index):  # type: ignore[override]
        """Paint."""
        text = index.data(Qt.ItemDataRole.DisplayRole)
        if not text:
            super().paint(painter, option, index)
            return

        doc = QTextDocument()
        doc.setDefaultFont(option.font)
        doc.setHtml(str(text))
        
        # Add 6px padding on left/right
        text_rect = option.rect.adjusted(6, 6, -6, -6)
        doc.setTextWidth(text_rect.width())

        painter.save()
        paint_context = QAbstractTextDocumentLayout.PaintContext()

        color_group = QPalette.ColorGroup.Active if option.state & QStyle.StateFlag.State_Active else QPalette.ColorGroup.Inactive
        if option.state & QStyle.StateFlag.State_Selected:
            painter.fillRect(option.rect, option.palette.highlight())
            paint_context.palette.setColor(
                QPalette.ColorRole.Text,
                option.palette.color(color_group, QPalette.ColorRole.HighlightedText),
            )
        else:
            paint_context.palette.setColor(
                QPalette.ColorRole.Text,
                option.palette.color(color_group, QPalette.ColorRole.Text),
            )

        painter.translate(text_rect.topLeft())
        painter.setClipRect(text_rect.translated(-text_rect.topLeft()))
        doc.documentLayout().draw(painter, paint_context)
        painter.restore()

        # Draw light gray separating line at the bottom
        painter.save()
        painter.setPen(QColor(220, 220, 220))
        painter.drawLine(option.rect.left(), option.rect.bottom(), option.rect.right(), option.rect.bottom())
        painter.restore()

    def sizeHint(self, option, index):  # type: ignore[override]
        """Sizehint."""
        text = index.data(Qt.ItemDataRole.DisplayRole)
        if not text:
            return super().sizeHint(option, index)

        doc = QTextDocument()
        doc.setDefaultFont(option.font)
        doc.setHtml(str(text))
        width = option.rect.width()
        if width <= 0 and option.widget is not None:
            viewport = getattr(option.widget, 'viewport', None)
            if callable(viewport):
                width = viewport().width()
        if width > 0:
            doc.setTextWidth(width - 12) # Subtract 12px for padding (6px left, 6px right)
        size = doc.documentLayout().documentSize()
        return QSize(int(size.width()), int(size.height()) + 14) # 6px top, 6px bottom + 2px line space


class GlossaryDialog(QDialog):
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
        initial_term: Optional[str] = None,
    ) -> None:
        """Initialize a new instance."""
        super().__init__(parent)
        self.setWindowTitle("Glossary")
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
        self._initial_term = initial_term
        self._pending_select_term: Optional[str] = None
        self._is_populating = False

        self._tables: Dict[str, QTableWidget] = {}
        self._entry_table: Optional[QTableWidget] = None # Legacy compatibility

        layout = QVBoxLayout(self)

        header = QLabel("Select a term to review occurrences. Double-click an occurrence to jump to the editor.", self)
        header.setWordWrap(True)
        layout.addWidget(header)

        search_layout = QHBoxLayout()
        search_layout.addWidget(QLabel("Search:", self))
        self._search_field = QLineEdit(self)
        self._search_field.setPlaceholderText("Type a term or translation...")
        self._search_field.setProperty("selectAllOnClick", True)
        self._search_field.textChanged.connect(self._apply_filter)
        search_layout.addWidget(self._search_field, 1)
        self._unconfirmed_only_checkbox = QCheckBox("Needs review", self)
        self._unconfirmed_only_checkbox.setToolTip(
            "Show only entries still awaiting your decision — highlighted rows: several "
            "translation variants were proposed, or the entry has not been confirmed yet."
        )
        self._unconfirmed_only_checkbox.stateChanged.connect(
            lambda _state: self._apply_filter(self._search_field.text())
        )
        search_layout.addWidget(self._unconfirmed_only_checkbox)
        layout.addLayout(search_layout)

        splitter = QSplitter(Qt.Orientation.Horizontal, self)
        layout.addWidget(splitter, 1)

        self._tab_widget = QTabWidget(self)
        self._tab_widget.currentChanged.connect(self._on_tab_changed)
        splitter.addWidget(self._tab_widget)

        right_panel = QWidget(self)
        right_layout = QVBoxLayout(right_panel)
        splitter.addWidget(right_panel)
        self._original_label = QLabel("", self)
        self._original_label.setWordWrap(True)
        right_layout.addWidget(self._original_label)

        # Speaker identity resolution pane (shown for provisional Character entries)
        self._speaker_identity_pane = QWidget(self)
        speaker_layout = QVBoxLayout(self._speaker_identity_pane)
        speaker_layout.setContentsMargins(0, 4, 0, 8)

        self._speaker_identity_title = QLabel("<b>Speaker identity (provisional game code):</b>", self)
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
        self._speaker_name_combo.setPlaceholderText("Enter or select permanent character name...")
        self._speaker_name_combo.editTextChanged.connect(lambda _text: self._validate_speaker_name())
        self._speaker_name_combo.currentIndexChanged.connect(lambda _idx: self._validate_speaker_name())
        combo_row.addWidget(self._speaker_name_combo, 1)

        self._apply_speaker_name_button = QPushButton("Apply speaker name", self)
        self._apply_speaker_name_button.clicked.connect(self._on_apply_speaker_name_clicked)
        combo_row.addWidget(self._apply_speaker_name_button)

        speaker_layout.addLayout(combo_row)
        right_layout.addWidget(self._speaker_identity_pane)
        self._speaker_identity_pane.setVisible(False)

        translation_label = QLabel("Translation:", self)
        right_layout.addWidget(translation_label)
        self._translation_edit = QLineEdit(self)
        right_layout.addWidget(self._translation_edit)

        self._confirm_button = QPushButton("Confirm translation", self)
        self._confirm_button.setToolTip(
            "Mark this entry as decided. It stops being highlighted for review."
        )
        self._confirm_button.clicked.connect(self._on_confirm_clicked)
        right_layout.addWidget(self._confirm_button)

        # The three variable-height areas share a draggable splitter: a long
        # rationale or a long description needs room, and a fixed cap cannot
        # know which one the user is reading.
        detail_splitter = QSplitter(Qt.Orientation.Vertical, self)
        right_layout.addWidget(detail_splitter, 1)

        # Proposed variants: shown only when the AI offered a real choice.
        self._variants_pane = QWidget(self)
        variants_layout = QVBoxLayout(self._variants_pane)
        variants_layout.setContentsMargins(0, 0, 0, 0)
        self._variants_label = QLabel("Proposed variants (pick one):", self)
        variants_layout.addWidget(self._variants_label)
        self._variants_list = QListWidget(self)
        self._variants_list.setWordWrap(True)
        self._variants_list.itemClicked.connect(self._on_variant_chosen)
        variants_layout.addWidget(self._variants_list, 1)
        detail_splitter.addWidget(self._variants_pane)
        self._set_variants_visible(False)

        notes_pane = QWidget(self)
        notes_layout = QVBoxLayout(notes_pane)
        notes_layout.setContentsMargins(0, 0, 0, 0)
        self._profiled_checkbox = QCheckBox("Profiled via AI (Speech Profile generated)", self)
        notes_layout.addWidget(self._profiled_checkbox)
        notes_row = QHBoxLayout()
        notes_label = QLabel("Notes:", self)
        notes_row.addWidget(notes_label)
        self._notes_variation_default_text = "AI Variations"
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
        detail_splitter.addWidget(notes_pane)

        occurrences_pane = QWidget(self)
        occurrences_layout = QVBoxLayout(occurrences_pane)
        occurrences_layout.setContentsMargins(0, 0, 0, 0)
        self._occurrence_label = QLabel("Occurrences: 0", self)
        occurrences_layout.addWidget(self._occurrence_label)
        self._occurrence_list = QListWidget(self)
        self._occurrence_list.setSpacing(6)
        self._occurrence_list.setWordWrap(True)
        self._occurrence_list.setTextElideMode(Qt.TextElideMode.ElideNone)
        self._occurrence_list.setItemDelegate(_RichTextItemDelegate(self._occurrence_list))
        self._occurrence_list.itemDoubleClicked.connect(self._activate_selected_occurrence)
        occurrences_layout.addWidget(self._occurrence_list, 1)
        detail_splitter.addWidget(occurrences_pane)
        detail_splitter.setSizes([150, 200, 200])
        button_box = QDialogButtonBox(QDialogButtonBox.StandardButton.Close, parent=self)
        
        self._save_button = QPushButton("Save Changes", self)
        self._save_button.clicked.connect(self._save_editor_changes)
        button_box.addButton(self._save_button, QDialogButtonBox.ButtonRole.ActionRole)
        if self._update_callback is None:
            self._save_button.setVisible(False)

        self._global_replace_button = QPushButton("Global Replace...", self)
        self._global_replace_button.setStyleSheet("background-color: #0d9488; color: white; font-weight: bold;")
        self._global_replace_button.clicked.connect(self._on_global_replace_clicked)
        button_box.addButton(self._global_replace_button, QDialogButtonBox.ButtonRole.ActionRole)
        if self._update_callback is None or self._global_replace_callback is None:
            self._global_replace_button.setVisible(False)
            
        # Same launcher as Tools > Build Glossary from Text: it already offers
        # every mode (thorough / draft / augment / translate-only), so the
        # glossary needs a door to it, not its own copy of the buttons.
        self._build_button = QPushButton("Build / Translate via AI...", self)
        self._build_button.setStyleSheet("background-color: #2563eb; color: white; font-weight: bold;")
        self._build_button.setToolTip(
            "Sweep the project text for terms, describe them, or propose translations "
            "for entries that have a description but no translation yet."
        )
        self._build_button.clicked.connect(self._on_build_clicked)
        button_box.addButton(self._build_button, QDialogButtonBox.ButtonRole.ActionRole)
        if self._build_callback is None:
            self._build_button.setVisible(False)

        self._ai_classify_button = QPushButton("Organize via AI", self)
        self._ai_classify_button.setStyleSheet("background-color: #8b5cf6; color: white; font-weight: bold;")
        self._ai_classify_button.clicked.connect(self._on_ai_classify_clicked)
        button_box.addButton(self._ai_classify_button, QDialogButtonBox.ButtonRole.ActionRole)
        if self._ai_classify_callback is None:
            self._ai_classify_button.setVisible(False)
            
        self._clear_button = QPushButton("Clear Glossary", self)
        self._clear_button.setStyleSheet("background-color: #b91c1c; color: white; font-weight: bold;")
        self._clear_button.setToolTip("Remove every entry. The glossary file is backed up first.")
        self._clear_button.clicked.connect(self._on_clear_clicked)
        button_box.addButton(self._clear_button, QDialogButtonBox.ButtonRole.DestructiveRole)
        if self._clear_callback is None:
            self._clear_button.setVisible(False)

        button_box.rejected.connect(self.reject)
        layout.addWidget(button_box)
        self._translation_edit.textChanged.connect(self._on_editor_content_changed)
        self._notes_edit.textChanged.connect(self._on_editor_content_changed)
        self._profiled_checkbox.stateChanged.connect(self._on_editor_content_changed)
        self._update_editor_enabled_state()
        self._load_dialog_state()
        self._populate_entries(self._filtered_entries)

        if initial_term:
            QTimer.singleShot(0, lambda: self.focus_term(initial_term))
        elif self._filtered_entries:
            self._active_table().selectRow(0)
            self._show_entry_for_row(0)

    def _active_table(self) -> QTableWidget:
        """Internal helper to active table."""
        if not hasattr(self, '_tab_widget') or self._tab_widget.count() == 0:
            # Fallback legacy table if it somehow exists
            return self._entry_table if self._entry_table else QTableWidget(self)
        widget = self._tab_widget.currentWidget()
        if isinstance(widget, QTableWidget):
            return widget
        return self._entry_table if self._entry_table else QTableWidget(self)

    def _on_tab_changed(self, index: int) -> None:
        """Internal helper to handle the tab changed event."""
        if self._is_populating:
            return
        active_table = self._active_table()
        row = active_table.currentRow()
        self._show_entry_for_row(row)

    def _on_ai_classify_clicked(self) -> None:
        """Internal helper to handle the ai classify clicked event."""
        if self._ai_classify_callback:
            self._ai_classify_callback()

    def _on_build_clicked(self) -> None:
        """Internal helper to handle the build clicked event."""
        if self._build_callback:
            self._build_callback()

    def _on_clear_clicked(self) -> None:
        """Internal helper to handle the clear glossary clicked event."""
        if not self._clear_callback:
            return
        total = len(self._all_entries)
        if not total:
            return
        response = QMessageBox.question(
            self,
            "Clear Glossary",
            f"Remove all {total} entries from the glossary?\n\n"
            "This cannot be undone from here. The glossary file is copied to "
            "glossary.json.bak first, so the entries can be restored by hand.",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        if response != QMessageBox.StandardButton.Yes:
            return
        result = self._clear_callback()
        if not result:
            return
        new_entries, new_occurrence_map = result
        self._all_entries = list(new_entries)
        self._occurrences = new_occurrence_map
        self._current_entry = None
        self._pending_select_term = None
        self._mark_editor_dirty(False)
        self._apply_filter(self._search_field.text())

    def _on_global_replace_clicked(self) -> None:
        """Internal helper to handle the global replace clicked event."""
        if not self._global_replace_callback:
            return
            
        from PyQt6.QtWidgets import QDialog, QFormLayout, QLineEdit, QDialogButtonBox, QVBoxLayout
        
        dialog = QDialog(self)
        dialog.setWindowTitle("Global Replace in Glossary")
        dialog.resize(380, 160)
        dialog.setWindowFlag(Qt.WindowType.WindowContextHelpButtonHint, False)
        
        layout = QVBoxLayout(dialog)
        form = QFormLayout()
        
        find_edit = QLineEdit(dialog)
        find_edit.setPlaceholderText("e.g. goron")
        form.addRow("Find word/phrase:", find_edit)
        
        replace_edit = QLineEdit(dialog)
        replace_edit.setPlaceholderText("e.g. goron new")
        form.addRow("Replace with:", replace_edit)
        
        layout.addLayout(form)
        
        button_box = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel, parent=dialog)
        button_box.accepted.connect(dialog.accept)
        button_box.rejected.connect(dialog.reject)
        layout.addWidget(button_box)
        
        if dialog.exec() != QDialog.DialogCode.Accepted:
            return
            
        find_text = find_edit.text().strip()
        replace_text = replace_edit.text().strip()
        
        if not find_text:
            QMessageBox.warning(self, "Global Replace", "Find word cannot be empty.")
            return
            
        self._global_replace_callback(find_text, replace_text)

    def _populate_entries(self, entries: Sequence[GlossaryEntry]) -> None:
        """Internal helper to populate entries."""
        self._is_populating = True
        
        # Save current selected term and tab to restore after population
        selected_term = self._current_entry.original if self._current_entry else None
        current_tab_text = self._tab_widget.tabText(self._tab_widget.currentIndex()) if hasattr(self, '_tab_widget') and self._tab_widget.count() > 0 else "All"
        
        if hasattr(self, '_tab_widget'):
            self._tab_widget.blockSignals(True)
            self._tab_widget.clear()
            self._tables.clear()
        
        # Gather all sections present in self._all_entries
        sections = sorted(list({entry.section for entry in self._all_entries if entry.section}))
        
        has_unassigned = any(not entry.section for entry in entries)
        
        tabs_to_create = ["All"] + sections
        if has_unassigned:
            tabs_to_create.append("Unassigned")
            
        for tab_name in tabs_to_create:
            if tab_name == "All":
                tab_entries = [e for e in entries]
            elif tab_name == "Unassigned":
                tab_entries = [e for e in entries if not e.section]
            else:
                tab_entries = [e for e in entries if e.section == tab_name]
                
            table = QTableWidget(self)
            table.setColumnCount(4)
            table.setHorizontalHeaderLabels(["Term", "Translation", "Notes", "Count"])
            table.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
            table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
            
            header = table.horizontalHeader()
            header.setSectionResizeMode(0, QHeaderView.ResizeMode.Interactive)
            header.setSectionResizeMode(1, QHeaderView.ResizeMode.Interactive)
            header.setSectionResizeMode(2, QHeaderView.ResizeMode.Stretch)
            header.setSectionResizeMode(3, QHeaderView.ResizeMode.ResizeToContents)
            
            table.cellClicked.connect(self._on_entry_selected)
            table.currentCellChanged.connect(self._on_entry_current_changed)
            table.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
            table.customContextMenuRequested.connect(self._on_entry_context_menu)
            
            if self._update_callback:
                table.setEditTriggers(
                    QAbstractItemView.EditTrigger.DoubleClicked
                    | QAbstractItemView.EditTrigger.EditKeyPressed
                    | QAbstractItemView.EditTrigger.AnyKeyPressed
                )
                table.itemChanged.connect(self._on_entry_edited)
            else:
                table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
                
            # Populate this table
            table.setSortingEnabled(False)
            table.blockSignals(True)
            table.setRowCount(len(tab_entries))
            
            for row, entry in enumerate(tab_entries):
                occurrences = self._occurrences.get(entry.original, [])
                values = [
                    entry.original,
                    entry.translation,
                    render_notes(
                        entry.notes,
                        translation=entry.translation,
                        original=entry.original,
                    ),
                    str(len(occurrences)),
                ]
                needs_review = self._needs_review(entry)
                provisional = bool(getattr(entry, "provisional", False))
                for col, value in enumerate(values):
                    item = QTableWidgetItem(value)
                    if col == 3:
                        item.setTextAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
                    if col == 0:
                        item.setData(Qt.ItemDataRole.UserRole, entry)
                        item.setFlags(item.flags() & ~Qt.ItemFlag.ItemIsEditable)
                    if col == 3:
                        item.setFlags(item.flags() & ~Qt.ItemFlag.ItemIsEditable)
                    if needs_review:
                        item.setBackground(_NEEDS_REVIEW_BRUSH)
                        item.setToolTip(self._review_reason(entry))
                    if provisional:
                        item.setForeground(_PROVISIONAL_FOREGROUND)
                        item.setToolTip(
                            "Provisional speaker identity.\n\n"
                            f"\"{entry.original}\" was extracted from game data as a temporary speaker identifier. "
                            "Select this term in the Glossary to assign its permanent character name, "
                            "or use Merge Speakers to match it against a script."
                        )
                    table.setItem(row, col, item)
                    
            table.resizeColumnToContents(0)
            table.resizeColumnToContents(1)
            table.resizeColumnToContents(3)
            table.setSortingEnabled(True)
            table.blockSignals(False)
            
            self._tables[tab_name] = table
            self._tab_widget.addTab(table, tab_name)
            
        restore_idx = 0
        for idx in range(self._tab_widget.count()):
            if self._tab_widget.tabText(idx) == current_tab_text:
                restore_idx = idx
                break
        self._tab_widget.setCurrentIndex(restore_idx)
        self._tab_widget.blockSignals(False)
        self._is_populating = False
        
        if selected_term:
            self._select_initial_term(selected_term, switch_tab=False)
        elif self._active_table().rowCount() > 0:
            self._active_table().selectRow(0)
            self._show_entry_for_row(0)
        else:
            self._clear_entry_details()

    def _select_initial_term(self, term: str, switch_tab: bool = True) -> None:
        """Internal helper to select initial term."""
        if not term:
            return
        
        term_to_find = term.strip()
        
        # 1. Find which section this term belongs to
        target_section = "All"
        for entry in self._all_entries:
            if entry.original.strip() == term_to_find:
                target_section = entry.section if entry.section else "Unassigned"
                break
                
        # 2. Switch to the corresponding tab if requested
        if switch_tab and hasattr(self, '_tab_widget'):
            self._tab_widget.blockSignals(True)
            found_tab = False
            for idx in range(self._tab_widget.count()):
                if self._tab_widget.tabText(idx) == target_section:
                    self._tab_widget.setCurrentIndex(idx)
                    found_tab = True
                    break
            if not found_tab:
                for idx in range(self._tab_widget.count()):
                    if self._tab_widget.tabText(idx) == "All":
                        self._tab_widget.setCurrentIndex(idx)
                        break
            self._tab_widget.blockSignals(False)
            
        # 3. Select inside active table
        active_table = self._active_table()
        for row in range(active_table.rowCount()):
            item = active_table.item(row, 0)
            if not item: continue
            
            entry = item.data(Qt.ItemDataRole.UserRole)
            if isinstance(entry, GlossaryEntry) and entry.original.strip() == term_to_find:
                active_table.setCurrentCell(row, 0)
                active_table.scrollToItem(item, QTableWidget.ScrollHint.PositionAtCenter)
                self._show_entry_for_row(row)
                return

    def focus_term(self, term: str) -> None:
        """Filter the list to ``term`` and select its entry (public entry point).

        Robust for both a freshly created dialog and one that is already open:
        it narrows the search box to the term (matching original or translation,
        so the entry is always visible) and selects the exact original if present.
        """
        term = (term or "").strip()
        if not term:
            return
        if self._search_field.text().strip() != term:
            self._search_field.setText(term)  # emits textChanged -> _apply_filter
        else:
            self._apply_filter(term)
        self._select_initial_term(term, switch_tab=True)
    def _show_entry_for_row(self, row: int) -> None:
        """Internal helper to show entry for row."""
        if row < 0:
            self._clear_entry_details()
            return
        entry = self._entry_for_row(row)
        if entry:
            self._populate_entry_details(entry)
            self._update_occurrences(entry)
        else:
            self._clear_entry_details()

    def _on_entry_current_changed(self, row: int, _column: int, _prev_row: int, _prev_column: int) -> None:
        """Internal helper to handle the entry current changed event."""
        if self._is_populating:
            return
        self._show_entry_for_row(row)
    def _on_entry_selected(self, row: int, _column: int) -> None:
        """Internal helper to handle the entry selected event."""
        self._show_entry_for_row(row)
    def _on_entry_edited(self, item: QTableWidgetItem) -> None:
        """Internal helper to handle the entry edited event."""
        if self._is_populating or not self._update_callback:
            return
        row = item.row()
        column = item.column()
        if column not in (1, 2):
            return
        entry = self._entry_for_row(row)
        if not entry:
            return
        translation_item = self._active_table().item(row, 1)
        notes_item = self._active_table().item(row, 2)
        new_translation = translation_item.text().strip() if translation_item else ''
        new_notes = notes_item.text().strip() if notes_item else ''
        if new_translation == entry.translation and new_notes == entry.notes:
            if self._current_entry and self._current_entry.original == entry.original:
                self._mark_editor_dirty(False)
            return
        if self._attempt_entry_update(entry, new_translation, new_notes):
            if self._current_entry and self._current_entry.original == entry.original:
                self._mark_editor_dirty(False)
            return
        self._is_populating = True
        self._active_table().blockSignals(True)
        if translation_item:
            translation_item.setText(entry.translation)
        if notes_item:
            notes_item.setText(entry.notes)
        self._active_table().blockSignals(False)
        self._is_populating = False
        if self._current_entry and self._current_entry.original == entry.original:
            self._populate_entry_details(entry)
    def _activate_selected_occurrence(self, item: Optional[QListWidgetItem] = None) -> None:
        """Internal helper to activate selected occurrence."""
        if not item:
            item = self._occurrence_list.currentItem()
        if not item:
            if self._occurrence_list.count() == 1:
                self._occurrence_list.setCurrentRow(0)
                item = self._occurrence_list.currentItem()
            else:
                return
        occurrence = item.data(Qt.ItemDataRole.UserRole)
        if occurrence:
            self._jump_callback(occurrence)

    def _set_notes_variation_busy(self, busy: bool) -> None:
        """Internal helper to set the notes variation busy."""
        if not hasattr(self, '_notes_variation_button'):
            return
        self._notes_variation_busy = busy
        has_callback = self._ai_variation_callback is not None
        if busy:
            self._notes_variation_button.setText(f"{self._notes_variation_default_text} (working...)")
        else:
            self._notes_variation_button.setText(self._notes_variation_default_text)
        should_enable = has_callback and not busy and self._current_entry is not None
        self._notes_variation_button.setEnabled(should_enable)

    def apply_notes_variation(self, new_notes: str) -> None:
        """Apply notes variation."""
        if not self._current_entry:
            return
        self._suppress_editor_signals = True
        self._notes_edit.setPlainText(new_notes or '')
        self._suppress_editor_signals = False
        self._on_editor_content_changed()

    def _on_notes_variation_clicked(self) -> None:
        """Internal helper to handle the notes variation clicked event."""
        if not self._ai_variation_callback or not self._current_entry:
            return
        self._ai_variation_callback(self._current_entry)

    def _on_editor_content_changed(self) -> None:
        """Internal helper to handle the editor content changed event."""
        if self._suppress_editor_signals or not self._update_callback or not self._current_entry:
            return
        current_translation = self._translation_edit.text().strip()
        current_notes = self._notes_for_save()
        current_profiled = self._profiled_checkbox.isChecked()
        has_changes = (
            current_translation != self._current_entry.translation
            or current_notes != self._current_entry.notes
            or current_profiled != self._current_entry.profiled
        )
        self._mark_editor_dirty(has_changes)
    def _mark_editor_dirty(self, dirty: bool) -> None:
        """Internal helper to mark editor dirty."""
        self._editor_dirty = bool(dirty) if self._update_callback else False
        self._update_editor_enabled_state()
    def _update_editor_enabled_state(self) -> None:
        """Internal helper to update the editor enabled state."""
        can_edit = self._update_callback is not None and self._current_entry is not None
        self._translation_edit.setReadOnly(not can_edit)
        self._notes_edit.setReadOnly(not can_edit)
        self._profiled_checkbox.setEnabled(can_edit)
        if hasattr(self, '_notes_variation_button'):
            has_callback = self._ai_variation_callback is not None
            self._notes_variation_button.setVisible(has_callback)
            should_enable = has_callback and self._current_entry is not None and not getattr(self, '_notes_variation_busy', False)
            self._notes_variation_button.setEnabled(should_enable)
        if hasattr(self, '_save_button'):
            if self._update_callback is None:
                self._save_button.setVisible(False)
                self._save_button.setEnabled(False)
            else:
                self._save_button.setVisible(True)
                self._save_button.setEnabled(can_edit)
    def _save_editor_changes(self) -> None:
        """Internal helper to save editor changes."""
        if self._is_populating or not self._update_callback or not self._current_entry:
            return
        new_translation = self._translation_edit.text().strip()
        new_notes = self._notes_for_save()
        new_profiled = self._profiled_checkbox.isChecked()
        entry = self._current_entry
        if not self._attempt_entry_update(entry, new_translation, new_notes, new_profiled):
            self._populate_entry_details(entry)
            return
        self._mark_editor_dirty(False)
    def _attempt_entry_update(self, entry: GlossaryEntry, new_translation: str, new_notes: str, profiled: Optional[bool] = None, status: Optional[str] = None) -> bool:
        """Internal helper to attempt entry update.

        ``status`` moves the entry's lifecycle state -- STATUS_CONFIRMED to
        settle it and clear the review highlight, or an unconfirmed status to
        put it back under review. Passed as a keyword so older callbacks that
        do not accept it stay compatible when it is not needed.
        """
        if not self._update_callback:
            return False
        if status:
            result = self._update_callback(
                entry.original, new_translation, new_notes, profiled, status=status
            )
        else:
            result = self._update_callback(entry.original, new_translation, new_notes, profiled)
        if not result:
            return False
        new_entries, new_occurrence_map = result
        self._all_entries = list(new_entries)
        self._occurrences = new_occurrence_map
        self._pending_select_term = entry.original
        self._apply_filter(self._search_field.text())
        return True
    def _attempt_entry_delete(self, entry: GlossaryEntry) -> None:
        """Internal helper to attempt entry delete."""
        if not self._delete_callback:
            return
        response = QMessageBox.question(
            self,
            "Delete Glossary Entry",
            f"Remove term \"{entry.original}\" from the glossary?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        if response != QMessageBox.StandardButton.Yes:
            return
        result = self._delete_callback(entry.original)
        if not result:
            return
        new_entries, new_occurrence_map = result
        self._all_entries = list(new_entries)
        self._occurrences = new_occurrence_map
        self._current_entry = None
        self._mark_editor_dirty(False)
        self._update_editor_enabled_state()
        self._pending_select_term = None
        self._apply_filter(self._search_field.text())
    def _on_entry_context_menu(self, pos) -> None:
        """Internal helper to handle the entry context menu event."""
        row = self._active_table().rowAt(pos.y())
        if row < 0:
            return
        entry = self._entry_for_row(row)
        if not entry:
            return
        menu = QMenu(self)
        settled = not self._needs_review(entry)
        review_action = menu.addAction(
            "Mark for review" if settled else "Mark as reviewed"
        )
        review_action.setEnabled(self._update_callback is not None)
        menu.addSeparator()
        delete_action = menu.addAction("Delete Entry")
        delete_action.setEnabled(self._delete_callback is not None)
        selected_action = menu.exec(self._active_table().viewport().mapToGlobal(pos))
        if selected_action == delete_action:
            self._active_table().selectRow(row)
            self._attempt_entry_delete(entry)
        elif selected_action == review_action:
            self._active_table().selectRow(row)
            self._set_entry_review_state(entry, needs_review=settled)

    def _set_entry_review_state(self, entry: GlossaryEntry, *, needs_review: bool) -> None:
        """Flag an entry for review again, or settle it, from the context menu."""
        status = STATUS_TRANSLATED if needs_review else STATUS_CONFIRMED
        self._attempt_entry_update(
            entry, entry.translation, entry.notes, entry.profiled, status=status
        )
    def _load_dialog_state(self) -> None:
        """Internal helper to load dialog state."""
        data = self._read_settings_file()
        state = data.get('glossary_dialog_state')
        if not isinstance(state, dict):
            return
        geometry_data = state.get('geometry')
        if isinstance(geometry_data, dict):
            rect = QRect(
                geometry_data.get('x', self.x()),
                geometry_data.get('y', self.y()),
                geometry_data.get('width', self.width()),
                geometry_data.get('height', self.height()),
            )
            self.setGeometry(rect)
        self._restore_maximized_on_show = bool(state.get('is_maximized', False))
    def _save_dialog_state(self) -> None:
        """Internal helper to save dialog state."""
        data = self._read_settings_file()
        state = data.get('glossary_dialog_state', {})
        geometry_source = self.normalGeometry() if self.isMaximized() else self.geometry()
        state['geometry'] = self._geometry_to_dict(geometry_source)
        state['is_maximized'] = bool(self.isMaximized())
        data['glossary_dialog_state'] = state
        self._write_settings_file(data)
    def _read_settings_file(self) -> Dict[str, Any]:
        """Internal helper to read settings file."""
        try:
            if not self._settings_path.exists():
                return {}
            with self._settings_path.open('r', encoding='utf-8') as handle:
                return json.load(handle)
        except Exception:
            return {}
    def _write_settings_file(self, data: Dict[str, Any]) -> None:
        """Internal helper to write settings file."""
        try:
            if self._settings_path.parent and not self._settings_path.parent.exists():
                self._settings_path.parent.mkdir(parents=True, exist_ok=True)
            with self._settings_path.open('w', encoding='utf-8') as handle:
                json.dump(data, handle, indent=4, ensure_ascii=False)
        except Exception:
            pass
    @staticmethod
    def _geometry_to_dict(rect: QRect) -> Dict[str, int]:
        """Internal helper to geometry to dict."""
        return {
            'x': rect.x(),
            'y': rect.y(),
            'width': rect.width(),
            'height': rect.height(),
        }
    def showEvent(self, event) -> None:
        """Showevent."""
        super().showEvent(event)
        if self._restore_maximized_on_show:
            self._restore_maximized_on_show = False
            self.showMaximized()
    def closeEvent(self, event) -> None:
        """Closeevent."""
        self._save_dialog_state()
        super().closeEvent(event)

    def keyPressEvent(self, event) -> None:
        """Keypressevent."""
        if event.key() == Qt.Key.Key_Escape:
            self.reject()
            event.accept()
            return
        super().keyPressEvent(event)

    def _update_occurrences(self, entry: GlossaryEntry) -> None:
        """Internal helper to update the occurrences."""
        occ_list = self._occurrences.get(entry.original, [])
        self._occurrence_list.clear()
        for index, occ in enumerate(occ_list, start=1):
            preview = occ.line_text.strip()
            if len(preview) > 120:
                preview = f"{preview[:117]}…"
            preview_html = escape(preview).replace('\n', '<br>')
            header_html = (
                f"<b>#{index}</b> | block <b>{occ.block_idx}</b> | "
                f"string <b>{occ.string_idx}</b> | line <b>{occ.line_idx + 1}</b>"
            )
            item = QListWidgetItem()
            item.setData(Qt.ItemDataRole.DisplayRole, f"{header_html}<br>{preview_html}")
            item.setData(Qt.ItemDataRole.UserRole, occ)
            self._occurrence_list.addItem(item)
        self._occurrence_label.setText(f"Occurrences: {len(occ_list)}")
    def _entry_for_row(self, row: int) -> Optional[GlossaryEntry]:
        """Internal helper to entry for row."""
        if row < 0:
            return None
        active_table = self._active_table()
        if row >= active_table.rowCount():
            return None
        item = active_table.item(row, 0)
        if not item:
            return None
        entry = item.data(Qt.ItemDataRole.UserRole)
        if isinstance(entry, GlossaryEntry):
            return entry
        if 0 <= row < len(self._filtered_entries):
            return self._filtered_entries[row]
        return None
    def _populate_entry_details(self, entry: GlossaryEntry) -> None:
        """Internal helper to populate entry details."""
        self._current_entry = entry
        self._suppress_editor_signals = True
        self._original_label.setText(f"Term: {entry.original}")
        self._translation_edit.setText(entry.translation or '')
        self._notes_template = entry.notes or ''
        self._notes_edit.setPlainText(self._rendered_notes())
        self._profiled_checkbox.setChecked(entry.profiled)
        self._populate_variants(entry)

        is_provisional_char = (
            bool(entry)
            and bool(getattr(entry, "provisional", False))
            and ((getattr(entry, "section", "") or "").strip().lower() == "characters")
        )
        if is_provisional_char:
            self._speaker_identity_pane.setVisible(True)
            candidates = self._build_speaker_candidates(entry)
            self._speaker_name_combo.blockSignals(True)
            self._speaker_name_combo.clear()
            for cand in candidates:
                self._speaker_name_combo.addItem(cand)

            sug_name = str(getattr(entry, "suggested_name", "") or "").strip()
            if sug_name:
                idx = self._speaker_name_combo.findText(sug_name, Qt.MatchFlag.MatchExactly)
                if idx >= 0:
                    self._speaker_name_combo.setCurrentIndex(idx)
                else:
                    self._speaker_name_combo.setEditText(sug_name)
            else:
                self._speaker_name_combo.setEditText("")
                self._speaker_name_combo.setCurrentIndex(-1)
            self._speaker_name_combo.blockSignals(False)

            sug_ev = str(getattr(entry, "suggested_name_evidence", "") or "").strip()
            if sug_name or sug_ev:
                parts = []
                if sug_name:
                    parts.append(f"<b>AI Proposal:</b> {escape(sug_name)}")
                if sug_ev:
                    parts.append(f"<b>Evidence:</b> {escape(sug_ev)}")
                self._speaker_evidence_label.setText("<br>".join(parts))
                self._speaker_evidence_label.setVisible(True)
            else:
                self._speaker_evidence_label.setText("")
                self._speaker_evidence_label.setVisible(False)

            self._validate_speaker_name()
        else:
            if hasattr(self, '_speaker_identity_pane'):
                self._speaker_identity_pane.setVisible(False)
                self._apply_speaker_name_button.setEnabled(False)

        self._suppress_editor_signals = False
        if hasattr(self, '_notes_variation_button'):
            self._notes_variation_busy = False
            self._notes_variation_button.setText(self._notes_variation_default_text)
        self._mark_editor_dirty(False)
        self._update_editor_enabled_state()

    def _clear_entry_details(self) -> None:
        """Internal helper to remove entry details."""
        self._current_entry = None
        self._suppress_editor_signals = True
        self._original_label.setText('Nothing selected')
        self._translation_edit.clear()
        self._notes_template = ''
        self._notes_edit.clear()
        self._profiled_checkbox.setChecked(False)
        self._populate_variants(None)
        if hasattr(self, '_speaker_identity_pane'):
            self._speaker_identity_pane.setVisible(False)
            self._apply_speaker_name_button.setEnabled(False)
        self._suppress_editor_signals = False
        if hasattr(self, '_notes_variation_button'):
            self._notes_variation_busy = False
            self._notes_variation_button.setText(self._notes_variation_default_text)
            self._notes_variation_button.setEnabled(False)
        self._update_editor_enabled_state()

    def _build_speaker_candidates(self, entry: GlossaryEntry) -> List[str]:
        """Build list of candidate permanent speaker names for a provisional character entry."""
        excluded_lower = set()
        selected_code = (getattr(entry, "original", "") or "").strip().lower()
        if selected_code:
            excluded_lower.add(selected_code)

        for e in self._all_entries:
            orig = (getattr(e, "original", "") or "").strip().lower()
            if getattr(e, "provisional", False) and orig:
                excluded_lower.add(orig)

        candidates: List[str] = []
        seen_lower = set()

        def add_candidate(val: str) -> None:
            clean_val = val.strip()
            if not clean_val:
                return
            low = clean_val.lower()
            if low in excluded_lower or low in seen_lower:
                return
            seen_lower.add(low)
            candidates.append(clean_val)

        # 1. Saved suggested_name of selected entry as initial proposal when present
        sug_name = str(getattr(entry, "suggested_name", "") or "").strip()
        if sug_name:
            add_candidate(sug_name)

        # 2. Known permanent speaker names (non-provisional Characters glossary originals)
        for e in self._all_entries:
            if not getattr(e, "provisional", False) and (getattr(e, "section", "") or "").strip().lower() == "characters":
                orig = str(getattr(e, "original", "") or "").strip()
                if orig:
                    add_candidate(orig)

        # 3. Distinct non-empty suggested_name values from other entries
        for e in self._all_entries:
            sug = str(getattr(e, "suggested_name", "") or "").strip()
            if sug:
                add_candidate(sug)

        return candidates

    def _validate_speaker_name(self) -> bool:
        """Enable Apply speaker name button only when callback and text form a valid permanent mapping."""
        if not self._current_entry or self._apply_speaker_name_callback is None:
            self._apply_speaker_name_button.setEnabled(False)
            return False

        provisional = bool(getattr(self._current_entry, "provisional", False))
        section = (getattr(self._current_entry, "section", "") or "").strip().lower()
        if not provisional or section != "characters":
            self._apply_speaker_name_button.setEnabled(False)
            return False

        proposed = self._speaker_name_combo.currentText().strip()
        if not proposed:
            self._apply_speaker_name_button.setEnabled(False)
            return False

        code_lower = self._current_entry.original.strip().lower()
        proposed_lower = proposed.lower()

        if proposed_lower == code_lower:
            self._apply_speaker_name_button.setEnabled(False)
            return False

        provisional_codes_lower = {
            e.original.strip().lower() for e in self._all_entries if getattr(e, "provisional", False)
        }
        if proposed_lower in provisional_codes_lower:
            self._apply_speaker_name_button.setEnabled(False)
            return False

        self._apply_speaker_name_button.setEnabled(True)
        return True

    def _on_apply_speaker_name_clicked(self) -> None:
        """Handle explicit Apply speaker name button click."""
        if not self._validate_speaker_name() or not self._apply_speaker_name_callback or not self._current_entry:
            return
        provisional_code = self._current_entry.original.strip()
        permanent_name = self._speaker_name_combo.currentText().strip()
        self._apply_speaker_name_callback(provisional_code, permanent_name)

    def _set_variants_visible(self, visible: bool) -> None:
        """Show the variant picker only when there is a decision to make."""
        self._variants_pane.setVisible(visible)
        self._variants_label.setVisible(visible)
        self._variants_list.setVisible(visible)

    def _populate_variants(self, entry: Optional[GlossaryEntry]) -> None:
        """Fill the variant picker and the confirm button for this entry."""
        self._variants_list.clear()
        variants = list(getattr(entry, "translation_variants", ()) or ()) if entry else []
        # One variant means the AI saw no real ambiguity; nothing to choose.
        self._set_variants_visible(len(variants) > 1)
        for variant in variants:
            label = variant.translation
            if variant.rationale:
                label = f"{variant.translation} — {variant.rationale}"
            item = QListWidgetItem(label)
            item.setData(Qt.ItemDataRole.UserRole, variant.translation)
            if entry and variant.translation == entry.translation:
                font = item.font()
                font.setBold(True)
                item.setFont(font)
            self._variants_list.addItem(item)

        can_confirm = bool(entry) and self._needs_review(entry) and bool(self._update_callback)
        self._confirm_button.setVisible(bool(entry) and self._needs_review(entry))
        self._confirm_button.setEnabled(can_confirm)

    def _rendered_notes(self) -> str:
        """The stored notes with the term placeholder filled in."""
        entry = self._current_entry
        return render_notes(
            self._notes_template,
            translation=self._translation_edit.text(),
            original=entry.original if entry else "",
        )

    def _refresh_rendered_notes(self) -> None:
        """Re-render the notes after the translation changed."""
        if TERM_PLACEHOLDER not in (self._notes_template or ""):
            return
        was_suppressed = self._suppress_editor_signals
        self._suppress_editor_signals = True
        self._notes_edit.setPlainText(self._rendered_notes())
        self._suppress_editor_signals = was_suppressed

    def _notes_for_save(self) -> str:
        """What to store: the template if untouched, else what the user typed.

        Keeping the placeholder means a later change of variant still updates the
        note; once the user edits the text by hand, their wording wins.
        """
        typed = self._notes_edit.toPlainText().strip()
        template = (self._notes_template or "").strip()
        if template and typed == self._rendered_notes().strip():
            return template
        return typed

    def _on_variant_chosen(self, item: QListWidgetItem) -> None:
        """Pick a variant: fill the translation, re-render notes, and settle it.

        Choosing from the list IS the decision the highlight is asking for, so
        the entry stops being flagged immediately rather than needing a second
        click on Confirm.
        """
        translation = item.data(Qt.ItemDataRole.UserRole)
        if not translation:
            return
        self._translation_edit.setText(str(translation))
        self._refresh_rendered_notes()
        self._on_confirm_clicked()

    def _on_confirm_clicked(self) -> None:
        """Save the current translation and mark the entry as decided."""
        entry = self._current_entry
        if not entry or not self._update_callback:
            return
        self._attempt_entry_update(
            entry,
            self._translation_edit.text(),
            self._notes_for_save(),
            self._profiled_checkbox.isChecked(),
            status=STATUS_CONFIRMED,
        )

    @staticmethod
    def _review_reason(entry: GlossaryEntry) -> str:
        """Why this entry is flagged — shown as the row tooltip."""
        variants = getattr(entry, "translation_variants", ()) or ()
        if len(variants) > 1:
            listed = "\n".join(
                f"  • {v.translation}" + (f" — {v.rationale}" if v.rationale else "")
                for v in variants
            )
            return f"{len(variants)} translation variants proposed:\n{listed}"
        status = getattr(entry, "status", "") or "unconfirmed"
        return f"Awaiting review (status: {status})."

    @staticmethod
    def _needs_review(entry: GlossaryEntry) -> bool:
        """Whether the entry still awaits a human decision.

        A confirmed entry is settled and never flagged -- the proposed variants
        stay on record so the choice can be revisited, but their presence is not
        an open question any more. Otherwise: several defensible translations, or
        a status that has not been confirmed yet. Legacy entries carry no status
        and are not flagged, so the marker stays meaningful instead of colouring
        everything.
        """
        if getattr(entry, "status", "") == STATUS_CONFIRMED:
            return False
        if len(getattr(entry, "translation_variants", ()) or ()) > 1:
            return True
        return bool(getattr(entry, "is_unconfirmed", False))

    def _apply_filter(self, text: str) -> None:
        """Internal helper to apply filter."""
        pattern = text.strip().lower()
        if not pattern:
            self._filtered_entries = list(self._all_entries)
        else:
            def matches(entry: GlossaryEntry) -> bool:
                haystack = " ".join(
                     filter(None, [entry.original, entry.translation, entry.notes])
                ).lower()
                return pattern in haystack
            self._filtered_entries = [entry for entry in self._all_entries if matches(entry)]
        if self._unconfirmed_only_checkbox.isChecked():
            self._filtered_entries = [
                entry for entry in self._filtered_entries if self._needs_review(entry)
            ]
        self._populate_entries(self._filtered_entries)
        if self._pending_select_term:
            self._select_initial_term(self._pending_select_term, switch_tab=False)
            self._pending_select_term = None
            return
        if self._filtered_entries:
            self._active_table().selectRow(0)
            self._show_entry_for_row(0)
        else:
            self._clear_entry_details()
            self._occurrence_list.clear()
            self._occurrence_label.setText("Occurrences: 0")
 
    def reload_data(
        self,
        entries: Sequence[GlossaryEntry],
        occurrence_map: Dict[str, List[GlossaryOccurrence]]
    ) -> None:
        """Hot-reload entries and occurrences from external source and refresh UI."""
        self._all_entries = list(entries)
        self._occurrences = occurrence_map
        
        # Save currently selected term name to restore selection after reload
        selected_term = None
        if self._current_entry:
            selected_term = self._current_entry.original
            
        # Apply filters to re-populate the table
        self._apply_filter(self._search_field.text())
        
        # Restore selection if possible, otherwise select first row
        if selected_term:
            self._select_initial_term(selected_term, switch_tab=False)
        elif self._filtered_entries:
            self._active_table().selectRow(0)
            self._show_entry_for_row(0)


