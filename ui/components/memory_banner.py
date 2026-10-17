"""A bar above the editor: this source text already has a translation elsewhere, or sits in other places too."""
from __future__ import annotations

from typing import Any, List, Optional, Tuple

from PyQt6.QtWidgets import QFrame, QHBoxLayout, QLabel, QPushButton

from core.i18n import tr
from core.translation.layout_contract import text_fits_place

# How much of a remembered translation the bar shows.
PREVIEW_CHARS = 80


def _short(text: str) -> str:
    text = " ".join(str(text).split())
    return text if len(text) <= PREVIEW_CHARS else text[: PREVIEW_CHARS - 1] + "…"


class MemoryBanner(QFrame):
    """Shows, for the current string, what the project or the series already translated for the same text.

    Two buttons: apply that translation here, or apply the current translation
    to every place of this project with the same source text.
    """

    def __init__(self, main_window: Any, parent=None):
        super().__init__(parent)
        self.mw = main_window
        self.setObjectName("memory_banner")
        self.setFrameShape(QFrame.Shape.StyledPanel)
        self._position: Optional[Tuple[int, int]] = None
        self._suggestion: Optional[str] = None
        self._same_source: List[Tuple[int, int]] = []

        layout = QHBoxLayout(self)
        layout.setContentsMargins(6, 2, 6, 2)
        layout.setSpacing(6)
        self.label = QLabel(self)
        self.label.setWordWrap(True)
        layout.addWidget(self.label, 1)
        self.apply_button = QPushButton(tr('Apply here'), self)
        self.apply_button.setToolTip(tr('Put the remembered translation into this string (an unsaved edit you can undo).'))
        self.apply_button.clicked.connect(self.apply_here)
        layout.addWidget(self.apply_button)
        self.apply_all_button = QPushButton(self)
        self.apply_all_button.setToolTip(
            tr('Put this translation into every string of the project with the same source text, speaker and window, where it fits (unsaved edits you can undo).')
        )
        self.apply_all_button.clicked.connect(self.apply_everywhere)
        layout.addWidget(self.apply_all_button)
        self.hide()

    # ── state ───────────────────────────────────────────────────────────

    def refresh(self, block_idx: int, string_idx: int) -> None:
        """Look the current string up in the project and series memories; show or hide the bar."""
        self._position = (block_idx, string_idx)
        self._suggestion = None
        self._same_source = []
        saved_mgr = getattr(self.mw, 'saved_translations_manager', None)
        data_processor = getattr(self.mw, 'data_processor', None)
        if saved_mgr is None or data_processor is None or block_idx < 0 or string_idx < 0:
            self.hide()
            return
        source = saved_mgr._source_text(block_idx, string_idx)
        if not isinstance(source, str) or not source.strip():
            self.hide()
            return
        current, _ = data_processor.get_current_string_text(block_idx, string_idx)
        current = current or ""
        translated = data_processor.is_string_translated(block_idx, string_idx)
        self._same_source = [p for p in saved_mgr.positions_of_source(source) if p != (block_idx, string_idx)]

        where = ""
        own_rows, series_rows = saved_mgr.acceptable_rows(block_idx, string_idx, source)
        for row in own_rows:
            if row["translation"].strip() and row["translation"] != current:
                self._suggestion, where = row["translation"], tr('this project')
                break
        if self._suggestion is None:
            for row in series_rows:
                if row["translation"].strip() and row["translation"] != current:
                    self._suggestion, where = row["translation"], row["project"]
                    break
        if self._suggestion is not None:
            self.label.setText(
                tr('Translated in {where}: "{translation}"', where=where, translation=_short(self._suggestion))
            )
            self.apply_button.show()
        elif translated and self._same_source:
            self.label.setText(tr('The same text is in {count} other place(s) of this project.', count=len(self._same_source)))
            self.apply_button.hide()
        else:
            self.hide()
            return
        self.apply_all_button.setVisible(bool(self._same_source))
        self.apply_all_button.setText(tr('Apply to places with the same context'))
        self.show()

    # ── actions ─────────────────────────────────────────────────────────

    def apply_here(self) -> None:
        """Put the remembered translation into the current string."""
        if self._position is None or self._suggestion is None:
            return
        block_idx, string_idx = self._position
        self.mw.data_processor.update_edited_data(block_idx, string_idx, self._suggestion, action_type="MEMORY_APPLY")
        self.mw.ui_updater.update_text_views()

    def apply_everywhere(self) -> None:
        """Put the current string's translation (or the remembered one) into every place with the same source text."""
        if self._position is None:
            return
        block_idx, string_idx = self._position
        text = self._suggestion
        if text is None:
            text, _ = self.mw.data_processor.get_current_string_text(block_idx, string_idx)
        if not text or not text.strip():
            return
        # Only the places said under the same context (the speaker and window the fold uses), and only where the text fits.
        source = self.mw.saved_translations_manager._source_text(block_idx, string_idx)
        places = [(block_idx, string_idx)]
        skipped = 0
        for b_idx, s_idx in self.mw.saved_translations_manager.places_with_same_context(block_idx, string_idx, source):
            if text_fits_place(self.mw, source, text, b_idx, s_idx):
                places.append((b_idx, s_idx))
            else:
                skipped += 1
        touched = set()
        for b_idx, s_idx in places:
            self.mw.data_processor.update_edited_data(b_idx, s_idx, text, action_type="MEMORY_APPLY", skip_ui_refresh=True)
            text_operation = getattr(self.mw, "text_operation_handler", None)
            if text_operation is not None:
                text_operation._rescan_issues_for_current_string(b_idx, s_idx, text)
            touched.add(b_idx)
        for b_idx in touched:
            self.mw.ui_updater.update_block_item_text_with_problem_count(b_idx)
        self.mw.ui_updater.update_text_views()
        status_bar = getattr(self.mw, "statusBar", None)
        if status_bar is not None and skipped:
            status_bar.showMessage(tr('{count} other places did not take the text: it does not fit their window.', count=skipped), 4000)
