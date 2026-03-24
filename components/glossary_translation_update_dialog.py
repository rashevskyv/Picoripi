# --- START OF FILE components/glossary_translation_update_dialog.py ---
"""Dialog for reviewing translations after a glossary change."""
from __future__ import annotations

from typing import Callable, Dict, List, Optional, Sequence

from PyQt5.QtCore import Qt
from PyQt5.QtWidgets import (
    QDialog,
    QDialogButtonBox,
    QHBoxLayout,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QMessageBox,
    QPushButton,
    QSplitter,
    QVBoxLayout,
    QWidget,
    QPlainTextEdit,
)

from core.glossary_manager import GlossaryOccurrence


class GlossaryTranslationUpdateDialog(QDialog):
    """Manual updater for strings affected by a glossary translation change."""

    def __init__(
        self,
        *,
        parent: QWidget,
        term: str,
        old_translation: str,
        new_translation: str,
        occurrences: Sequence[GlossaryOccurrence],
        get_original_text: Callable[[GlossaryOccurrence], str],
        get_current_translation: Callable[[GlossaryOccurrence], str],
        apply_translation: Callable[[GlossaryOccurrence, str], None],
        ai_request_single: Optional[Callable[[GlossaryOccurrence], None]] = None,
        ai_request_all: Optional[Callable[[List[GlossaryOccurrence]], None]] = None,
    ) -> None:
        super().__init__(parent)
        self.setWindowTitle(f"Update \"{term}\" translations")
        self.resize(880, 560)

        self._term = term
        self._old_translation = old_translation or ''
        self._new_translation = new_translation or ''
        self._occurrences: List[GlossaryOccurrence] = list(occurrences)
        self._get_original = get_original_text
        self._get_current_translation = get_current_translation
        self._apply_translation_cb = apply_translation
        self._ai_request_single = ai_request_single
        self._ai_request_all = ai_request_all

        self._status: Dict[int, str] = {}
        self._ai_busy = False
        self._batch_mode = False

        self._build_ui()
        self._populate_occurrences()
        if self._occurrences:
            self._occurrence_list.setCurrentRow(0)
            self._load_occurrence(0)

    # ------------------------------------------------------------------
    # UI building
    # ------------------------------------------------------------------
    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)
        self.setLayout(layout)

        header = QLabel(
            f"<b>{self._term}</b>: replace "
            f"<i>{self._old_translation or '[empty]'}</i>" 
            f" → <i>{self._new_translation or '[empty]'}</i>"
        )
        header.setWordWrap(True)
        layout.addWidget(header)

        splitter = QSplitter(Qt.Horizontal, self)
        layout.addWidget(splitter, 1)

        left_panel = QWidget(splitter)
        left_layout = QVBoxLayout(left_panel)
        left_panel.setLayout(left_layout)
        left_layout.addWidget(QLabel("Occurrences", left_panel))

        self._occurrence_list = QListWidget(left_panel)
        self._occurrence_list.currentRowChanged.connect(self._load_occurrence)
        left_layout.addWidget(self._occurrence_list, 1)

        right_panel = QWidget(splitter)
        right_layout = QVBoxLayout(right_panel)
        right_panel.setLayout(right_layout)

        self._context_label = QLabel(right_panel)
        self._context_label.setWordWrap(True)
        right_layout.addWidget(self._context_label)

        self._original_view = QPlainTextEdit(right_panel)
        self._original_view.setReadOnly(True)
        right_layout.addWidget(QLabel("Original text", right_panel))
        right_layout.addWidget(self._original_view, 1)

        self._translation_edit = QPlainTextEdit(right_panel)
        right_layout.addWidget(QLabel("Translation", right_panel))
        right_layout.addWidget(self._translation_edit, 1)

        button_row = QHBoxLayout()
        right_layout.addLayout(button_row)

        apply_button = QPushButton("Apply", right_panel)
        apply_button.clicked.connect(lambda: self._apply_current(next_item=True))
        button_row.addWidget(apply_button)

        skip_button = QPushButton("Skip", right_panel)
        skip_button.clicked.connect(self._skip_current)
        button_row.addWidget(skip_button)

        button_row.addStretch(1)

        self._ai_current_button = QPushButton("AI Suggest", right_panel)
        self._ai_current_button.clicked.connect(self._run_ai_for_current)
        button_row.addWidget(self._ai_current_button)

        self._ai_all_button = QPushButton("AI All", right_panel)
        self._ai_all_button.clicked.connect(self._run_ai_for_all)
        button_row.addWidget(self._ai_all_button)

        self._ai_current_button.setVisible(self._ai_request_single is not None)
        self._ai_current_button.setEnabled(bool(self._ai_request_single) and not self._ai_busy)

        self._ai_all_button.setVisible(self._ai_request_all is not None)
        self._ai_all_button.setEnabled(bool(self._ai_request_all) and not self._ai_busy)

        footer = QDialogButtonBox(QDialogButtonBox.Close, right_panel)
        footer.rejected.connect(self.close)
        right_layout.addWidget(footer)

        self._status_label = QLabel(right_panel)
        self._status_label.setWordWrap(True)
        right_layout.addWidget(self._status_label)

    # ------------------------------------------------------------------
    # Occurrence helpers
    # ------------------------------------------------------------------
    def _populate_occurrences(self) -> None:
        self._occurrence_list.clear()
        for idx, occ in enumerate(self._occurrences, start=1):
            item = QListWidgetItem(self._format_occurrence_label(idx, occ))
            self._occurrence_list.addItem(item)

    def _format_occurrence_label(self, number: int, occ: GlossaryOccurrence) -> str:
        status = self._status.get(id(occ))
        suffix = ""
        if status == 'applied':
            suffix = " ✓"
        elif status == 'skipped':
            suffix = " –"
        return f"#{number} | Block {occ.block_idx} | Row {occ.string_idx}{suffix}"

    def _refresh_occurrence_item(self, occ: GlossaryOccurrence) -> None:
        occ_id = id(occ)
        for row in range(self._occurrence_list.count()):
            data_occ = self._occurrences[row]
            if id(data_occ) == occ_id:
                self._occurrence_list.item(row).setText(
                    self._format_occurrence_label(row + 1, data_occ)
                )
                break

    def _load_occurrence(self, row: int) -> None:
        if not (0 <= row < len(self._occurrences)):
            self._original_view.clear()
            self._translation_edit.clear()
            self._context_label.clear()
            return

        occ = self._occurrences[row]
        original_text = self._get_original(occ) or ""
        current_translation = self._get_current_translation(occ) or ""
        suggested = self._suggest_translation(current_translation)

        self._context_label.setText(
            f"Block {occ.block_idx} • String {occ.string_idx} • Line {occ.line_idx + 1}"
        )
        self._original_view.setPlainText(original_text)
        self._translation_edit.setPlainText(suggested)
        self._status_label.clear()
        
        # Update highlights after loading text
        self._update_text_highlights()

    # ------------------------------------------------------------------
    # Actions
    # ------------------------------------------------------------------
    def _current_occurrence(self) -> Optional[GlossaryOccurrence]:
        row = self._occurrence_list.currentRow()
        if 0 <= row < len(self._occurrences):
            return self._occurrences[row]
        return None

    def _suggest_translation(self, current_text: str) -> str:
        if not current_text:
            return current_text
        if self._old_translation and self._old_translation in current_text:
            return current_text.replace(self._old_translation, self._new_translation)
        return current_text

    def _apply_current(self, next_item: bool = False) -> None:
        occ = self._current_occurrence()
        if not occ:
            return
        candidate = self._translation_edit.toPlainText().rstrip('\n')
        if not candidate:
            QMessageBox.warning(self, "Update", "Translation cannot be empty.")
            return
        
        # Apply changes
        self._apply_translation_cb(occ, candidate)
        
        self._status[id(occ)] = 'applied'
        self._refresh_occurrence_item(occ)
        self._status_label.setText("Applied.")
        
        if next_item:
            self._select_next()
        else:
            # If staying on the same item, update highlight
            self._update_text_highlights()

    def _update_text_highlights(self) -> None:
        """Applies green background highlighting to the target terms in both editors using fuzzy matching."""
        from PyQt5.QtWidgets import QTextEdit
        from PyQt5.QtGui import QColor, QTextCursor
        import re
        from utils.utils import is_fuzzy_match
        
        highlight_color = QColor(0, 255, 0, 80) # Light green background

        def get_selections_for_term(editor, term_phrase):
            selections = []
            if not term_phrase:
                return selections
            
            text = editor.toPlainText()
            
            # Split target phrase into words, ignoring short ones (conjunctions etc.)
            # If word is shorter than 4 chars, it must match exactly, so fuzzy is not applied
            search_tokens = [t for t in re.split(r'\W+', term_phrase) if t]
            
            if not search_tokens:
                return selections

            # Find all words in editor's text
            # Use iterator to get positions
            word_iter = re.finditer(r'\w+', text)
            
            for match in word_iter:
                word_in_text = match.group(0)
                
                # Check if this word is similar to any word from target phrase
                is_match = False
                for token in search_tokens:
                    # If word is short, require exact match (case-insensitive)
                    if len(token) < 4:
                        if token.lower() == word_in_text.lower():
                            is_match = True
                            break
                    # For longer words use fuzzy search
                    else:
                        # Threshold 0.75 allows "Islands" and "Island" to be similar enough
                        if is_fuzzy_match(token, word_in_text, threshold=0.75):
                            is_match = True
                            break
                
                if is_match:
                    sel = QTextEdit.ExtraSelection()
                    sel.format.setBackground(highlight_color)
                    cursor = editor.textCursor()
                    cursor.setPosition(match.start())
                    cursor.setPosition(match.end(), QTextCursor.KeepAnchor)
                    sel.cursor = cursor
                    selections.append(sel)
                    
            return selections

        # 1. Highlight original term in original text view
        orig_selections = get_selections_for_term(self._original_view, self._term)
        self._original_view.setExtraSelections(orig_selections)
        
        # 2. Highlight translated terms in edit field
        trans_selections = []
        
        # Highlight new value
        trans_selections.extend(get_selections_for_term(self._translation_edit, self._new_translation))
        
        # Highlight old value (if present and different)
        if self._old_translation and self._old_translation.strip() != self._new_translation.strip():
            trans_selections.extend(get_selections_for_term(self._translation_edit, self._old_translation))
            
        self._translation_edit.setExtraSelections(trans_selections)

    def _skip_current(self) -> None:
        occ = self._current_occurrence()
        if not occ:
            return
        self._status[id(occ)] = 'skipped'
        self._refresh_occurrence_item(occ)
        self._status_label.setText("Skipped.")
        self._select_next()

    def _select_next(self) -> None:
        row = self._occurrence_list.currentRow()
        if row + 1 < self._occurrence_list.count():
            self._occurrence_list.setCurrentRow(row + 1)

    def _run_ai_for_current(self) -> None:
        if not self._ai_request_single or self._ai_busy:
            return
        occ = self._current_occurrence()
        if not occ:
            return
        self.set_ai_busy(True)
        self._ai_request_single(occ)

    def _run_ai_for_all(self) -> None:
        if not self._ai_request_all or self._ai_busy:
            return
        remaining = [occ for occ in self._occurrences if self._status.get(id(occ)) != 'applied']
        if not remaining:
            QMessageBox.information(self, "AI Update", "All occurrences already applied.")
            return
        reply = QMessageBox.question(
            self,
            "AI Update",
            "Run AI suggestions for all remaining occurrences?",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No,
        )
        if reply != QMessageBox.Yes:
            return
        self.set_batch_active(True)
        self.set_ai_busy(True)
        self._ai_request_all(remaining)

    def set_ai_busy(self, busy: bool) -> None:
        self._ai_busy = busy
        if getattr(self, '_ai_current_button', None):
            self._ai_current_button.setEnabled(bool(self._ai_request_single) and not busy)
        if getattr(self, '_ai_all_button', None):
            self._ai_all_button.setEnabled(bool(self._ai_request_all) and not busy and not self._batch_mode)

    def set_batch_active(self, active: bool) -> None:
        self._batch_mode = bool(active)
        if getattr(self, '_ai_all_button', None):
            self._ai_all_button.setEnabled(bool(self._ai_request_all) and not self._ai_busy and not self._batch_mode)

    def on_ai_result(self, occurrence: GlossaryOccurrence, new_translation: str) -> None:
        self._apply_translation_cb(occurrence, new_translation)
        self._status[id(occurrence)] = 'applied'
        self._refresh_occurrence_item(occurrence)
        if self._current_occurrence() is occurrence:
            self._translation_edit.setPlainText(new_translation)
            self._status_label.setText("AI applied.")
        if not self._batch_mode:
            self._select_next()

    def on_ai_error(self, message: str) -> None:
        if message:
            QMessageBox.warning(self, "AI Update", message)
        self.set_batch_active(False)
        self.set_ai_busy(False)
