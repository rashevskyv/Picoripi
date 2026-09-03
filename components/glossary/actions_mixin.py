"""Glossary dialog actions, confirm flow, and window persistence."""
from __future__ import annotations

import json
from typing import Any, Dict, List, Optional

from PyQt6.QtCore import Qt, QRect
from PyQt6.QtWidgets import QMessageBox
from core.glossary_manager import STATUS_CONFIRMED
from core.i18n import tr


class ActionsMixin:
    """Glossary dialog actions, confirm flow, and window persistence."""

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
            tr('Clear Glossary'),
            tr(
                'Remove all {total} entries from the glossary?\n\n'
                'This cannot be undone from here. The glossary file is copied to '
                'glossary.json.bak first, so the entries can be restored by hand.',
                total=total,
            ),
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
        dialog.setWindowTitle(tr('Global Replace in Glossary'))
        dialog.resize(380, 160)
        dialog.setWindowFlag(Qt.WindowType.WindowContextHelpButtonHint, False)
        
        layout = QVBoxLayout(dialog)
        form = QFormLayout()
        
        find_edit = QLineEdit(dialog)
        find_edit.setPlaceholderText(tr('e.g. goron'))
        form.addRow(tr('Find word/phrase:'), find_edit)
        
        replace_edit = QLineEdit(dialog)
        replace_edit.setPlaceholderText(tr('e.g. goron new'))
        form.addRow(tr('Replace with:'), replace_edit)
        
        layout.addLayout(form)
        
        button_box = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel, parent=dialog)
        ok_btn = button_box.button(QDialogButtonBox.StandardButton.Ok)
        if ok_btn is not None:
            ok_btn.setText(tr('OK'))
        cancel_btn = button_box.button(QDialogButtonBox.StandardButton.Cancel)
        if cancel_btn is not None:
            cancel_btn.setText(tr('Cancel'))
        button_box.accepted.connect(dialog.accept)
        button_box.rejected.connect(dialog.reject)
        layout.addWidget(button_box)
        
        if dialog.exec() != QDialog.DialogCode.Accepted:
            return
            
        find_text = find_edit.text().strip()
        replace_text = replace_edit.text().strip()
        
        if not find_text:
            QMessageBox.warning(self, tr('Global Replace'), tr('Find word cannot be empty.'))
            return
            
        self._global_replace_callback(find_text, replace_text)

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

    def _next_visible_term_after(self, original: str) -> Optional[str]:
        """The next term in the current table, so Confirm can walk the list."""
        table = self._active_table()
        visible: List[str] = []
        for row in range(table.rowCount()):
            if table.isRowHidden(row):
                continue
            entry = self._entry_for_row(row)
            if entry:
                visible.append(entry.original)
        try:
            idx = visible.index(original)
        except ValueError:
            return visible[0] if visible else None
        if idx + 1 < len(visible):
            return visible[idx + 1]
        return None

    def _on_confirm_clicked(self, advance: bool = True) -> None:
        """Save the current translation, mark it decided, and optionally open the next term."""
        entry = self._current_entry
        if not entry or not self._update_callback:
            return
        next_term = self._next_visible_term_after(entry.original) if advance else None
        self._attempt_entry_update(
            entry,
            self._translation_edit.text(),
            self._notes_for_save(),
            self._profiled_checkbox.isChecked(),
            status=STATUS_CONFIRMED,
            select_after=next_term or entry.original,
        )
