"""Dialog for choosing among AI translation variations."""
from __future__ import annotations

import base64
from typing import Iterable, List, Optional

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (
    QDialog,
    QDialogButtonBox,
    QListWidget,
    QListWidgetItem,
    QPushButton,
    QVBoxLayout,
    QLabel,
    QSplitter,
    QAbstractItemView,
)

from components.editor.line_numbered_text_edit import LineNumberedTextEdit
from utils.logging_utils import log_warning


class TranslationVariationsDialog(QDialog):
    """Show multiple translation options and allow the user to pick one."""

    def __init__(self, parent=None, variations: Optional[Iterable[str]] = None, show_refresh: bool = False) -> None:
        super().__init__(parent)
        self.mw = parent
        self.setWindowTitle("AI Translation Variations")
        self.selected_translation: Optional[str] = None

        layout = QVBoxLayout(self)

        layout.addWidget(QLabel("Select a translation option and double-click or press 'Apply'."))

        self.splitter = QSplitter(Qt.Orientation.Horizontal, self)
        
        self._list = QListWidget(self)
        self._list.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self._list.itemSelectionChanged.connect(self._update_preview)
        self._list.itemDoubleClicked.connect(self._apply_current_selection)
        self.splitter.addWidget(self._list)

        self._preview = LineNumberedTextEdit(self.mw)
        self._preview.setReadOnly(True)
        self._preview.setObjectName("variations_preview_text_edit")

        # Load glossary manager to enable glossary highlighting in preview
        if self.mw and hasattr(self.mw, 'translation_handler') and self.mw.translation_handler:
            gm = getattr(self.mw.translation_handler, '_glossary_manager', None)
            if gm:
                self._preview.set_glossary_manager(gm)

        self.splitter.addWidget(self._preview)

        # Set default stretch factors
        self.splitter.setStretchFactor(0, 1)
        self.splitter.setStretchFactor(1, 2)
        
        layout.addWidget(self.splitter, 1)

        self._buttons = QDialogButtonBox(self)
        
        if show_refresh:
            self._refresh_button = QPushButton("Refresh", self)
            self._refresh_button.clicked.connect(self._on_refresh)
            self._buttons.addButton(self._refresh_button, QDialogButtonBox.ButtonRole.ActionRole)

        self._apply_button = QPushButton("Apply", self)
        self._apply_button.clicked.connect(self._apply_current_selection)
        self._buttons.addButton(self._apply_button, QDialogButtonBox.ButtonRole.AcceptRole)
        self._buttons.addButton("Cancel", QDialogButtonBox.ButtonRole.RejectRole)
        self._buttons.rejected.connect(self.reject)
        layout.addWidget(self._buttons)

        # Load saved size and splitter state
        self._load_state()

        if variations:
            self._populate_variations(list(variations))

    def _load_state(self) -> None:
        if not self.mw:
            self.resize(720, 520)
            return
        
        # Restore window geometry
        geom = getattr(self.mw, "variations_window_geometry", None)
        if isinstance(geom, dict):
            x = geom.get("x")
            y = geom.get("y")
            w = geom.get("width")
            h = geom.get("height")
            if all(v is not None for v in (x, y, w, h)):
                self.setGeometry(x, y, w, h)
        else:
            self.resize(720, 520)
        
        # Restore splitter state
        splitter_state = getattr(self.mw, "variations_splitter_state", None)
        if splitter_state and hasattr(self, "splitter"):
            try:
                self.splitter.restoreState(base64.b64decode(splitter_state.encode('ascii')))
            except Exception as e:
                log_warning(f"Failed to restore variations splitter state: {e}")

    def _save_state(self) -> None:
        if not self.mw:
            return
        
        # Save geometry
        geom = self.geometry()
        geom_dict = {
            "x": geom.x(),
            "y": geom.y(),
            "width": geom.width(),
            "height": geom.height()
        }
        self.mw.variations_window_geometry = geom_dict

        # Save splitter state
        if hasattr(self, "splitter"):
            try:
                state_bytes = self.splitter.saveState().data()
                self.mw.variations_splitter_state = base64.b64encode(state_bytes).decode('ascii')
            except Exception as e:
                log_warning(f"Failed to save variations splitter state: {e}")
                
        # Trigger save settings if settings_manager is available
        sm = getattr(self.mw, "settings_manager", None)
        if sm:
            try:
                sm._settings["variations_window_geometry"] = geom_dict
                if hasattr(self, "splitter"):
                    sm._settings["variations_splitter_state"] = self.mw.variations_splitter_state
                sm.save_settings()
            except Exception as e:
                log_warning(f"Failed to save settings in variations dialog: {e}")

    def done(self, r: int) -> None:
        self._save_state()
        super().done(r)

    def _on_refresh(self) -> None:
        self.done(2)

    def _populate_variations(self, variations: List[str]) -> None:
        self._list.clear()
        for index, option in enumerate(variations, start=1):
            display = option.replace("\n", " ⏎ ")
            if len(display) > 120:
                display = f"{display[:117]}…"
            item = QListWidgetItem(f"#{index}: {display}")
            item.setData(Qt.UserRole, option)
            self._list.addItem(item)
        if self._list.count() > 0:
            self._list.setCurrentRow(0)

    def _update_preview(self) -> None:
        current = self._list.currentItem()
        text = current.data(Qt.UserRole) if current else ""
        if text and self.mw and getattr(self.mw, 'current_game_rules', None):
            text = self.mw.current_game_rules.get_text_representation_for_editor(str(text))
        self._preview.setPlainText(text or "")

    def _apply_current_selection(self) -> None:
        current = self._list.currentItem()
        if not current:
            return
        selected = current.data(Qt.UserRole)
        if not isinstance(selected, str):
            return
        self.selected_translation = selected
        self.accept()