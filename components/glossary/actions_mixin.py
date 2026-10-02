"""Glossary dialog actions, confirm flow, and window persistence."""
from __future__ import annotations
from utils.atomic_io import atomic_write_json

import json
from pathlib import Path
from typing import Any, Dict, List, Optional

from PyQt6.QtCore import Qt, QRect
from PyQt6.QtWidgets import QMessageBox
from core.glossary_manager import STATUS_CONFIRMED
from core.i18n import tr
from utils.logging_utils import log_debug


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

    def _on_force_retranslate_clicked(self) -> None:
        """Internal helper to handle the force retranslate clicked event."""
        if not getattr(self, "_force_retranslate_callback", None):
            return
        total = len(self._all_entries)
        if not total:
            QMessageBox.information(
                self,
                tr('Force Retranslate'),
                tr('Glossary is empty. There are no terms to retranslate.'),
            )
            return
        response = QMessageBox.question(
            self,
            tr('Force Retranslate Glossary'),
            tr(
                'Retranslate all {total} entries with AI using current transcription and translation rules?\n\n'
                'Existing translations and variants will be overwritten with newly generated suggestions from the model.\n\n'
                'A backup copy (glossary.json.bak) will be created automatically before proceeding.',
                total=total,
            ),
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        if response != QMessageBox.StandardButton.Yes:
            return
        self._force_retranslate_callback()

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
        notes_collapsed = state.get('notes_collapsed')
        ai_notes_collapsed = state.get('ai_notes_collapsed')
        occ_collapsed = state.get('occurrences_collapsed')

        lower_splitter_sizes = state.get('lower_detail_splitter_sizes')
        if isinstance(lower_splitter_sizes, list) and len(lower_splitter_sizes) == 3:
            if notes_collapsed is None and lower_splitter_sizes[0] <= 34:
                notes_collapsed = True
            if ai_notes_collapsed is None and lower_splitter_sizes[1] <= 34:
                ai_notes_collapsed = True
            if occ_collapsed is None and lower_splitter_sizes[2] <= 34:
                occ_collapsed = True

        if hasattr(self, '_set_section_collapsed'):
            self._set_section_collapsed('notes', bool(notes_collapsed), update_splitter=False)
            self._set_section_collapsed('ai_notes', bool(ai_notes_collapsed), update_splitter=False)
            self._set_section_collapsed('occurrences', bool(occ_collapsed), update_splitter=False)

        if hasattr(self, '_main_splitter'):
            splitter_sizes = state.get('main_splitter_sizes')
            if isinstance(splitter_sizes, list) and len(splitter_sizes) == 2 and all(isinstance(x, int) and x > 0 for x in splitter_sizes):
                self._main_splitter.setSizes(splitter_sizes)
        if hasattr(self, '_term_trans_splitter'):
            splitter_sizes = state.get('term_trans_splitter_sizes')
            if isinstance(splitter_sizes, list) and len(splitter_sizes) == 2 and all(isinstance(x, int) and x > 0 for x in splitter_sizes):
                self._term_trans_splitter.setSizes(splitter_sizes)
        if hasattr(self, '_detail_splitter'):
            splitter_sizes = state.get('detail_splitter_sizes')
            if isinstance(splitter_sizes, list) and len(splitter_sizes) == 2 and all(isinstance(x, int) and x > 0 for x in splitter_sizes):
                if splitter_sizes[0] > 220 and splitter_sizes[1] < 450:
                    tot = sum(splitter_sizes)
                    var_h = min(splitter_sizes[0], 180)
                    self._detail_splitter.setSizes([var_h, tot - var_h])
                else:
                    self._detail_splitter.setSizes(splitter_sizes)
        if hasattr(self, '_lower_detail_splitter'):
            splitter_sizes = state.get('lower_detail_splitter_sizes')
            if isinstance(splitter_sizes, list) and len(splitter_sizes) == 3 and all(isinstance(x, int) and x > 0 for x in splitter_sizes):
                col_states = [
                    getattr(self, '_notes_collapsed', False),
                    getattr(self, '_ai_notes_collapsed', False),
                    getattr(self, '_occurrences_collapsed', False),
                ]
                validated = []
                for idx, size in enumerate(splitter_sizes):
                    if col_states[idx]:
                        validated.append(32)
                    else:
                        validated.append(max(80, size))
                self._lower_detail_splitter.setSizes(validated)

    def _save_dialog_state(self) -> None:
        """Internal helper to save dialog state."""
        data = self._read_settings_file()
        state = data.get('glossary_dialog_state', {})
        geometry_source = self.normalGeometry() if self.isMaximized() else self.geometry()
        state['geometry'] = self._geometry_to_dict(geometry_source)
        state['is_maximized'] = bool(self.isMaximized())
        if hasattr(self, '_main_splitter'):
            state['main_splitter_sizes'] = self._main_splitter.sizes()
        if hasattr(self, '_term_trans_splitter'):
            state['term_trans_splitter_sizes'] = self._term_trans_splitter.sizes()
        if hasattr(self, '_detail_splitter'):
            state['detail_splitter_sizes'] = self._detail_splitter.sizes()
        if hasattr(self, '_notes_collapsed'):
            state['notes_collapsed'] = bool(self._notes_collapsed)
        if hasattr(self, '_ai_notes_collapsed'):
            state['ai_notes_collapsed'] = bool(self._ai_notes_collapsed)
        if hasattr(self, '_occurrences_collapsed'):
            state['occurrences_collapsed'] = bool(self._occurrences_collapsed)
        if hasattr(self, '_lower_detail_splitter'):
            state['lower_detail_splitter_sizes'] = self._lower_detail_splitter.sizes()
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
            atomic_write_json(self._settings_path, data, indent=4, ensure_ascii=False)
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
        if hasattr(self, '_maybe_prompt_unsaved_changes') and not self._maybe_prompt_unsaved_changes():
            event.ignore()
            return
        self._save_dialog_state()
        parent = getattr(self, "_parent", None)
        if parent:
            try:
                from core.companion_sync import smart_sync_in_background
                smart_sync_in_background(parent)
            except Exception as exc:
                log_debug(f"Failed to auto-sync on glossary close: {exc}")
        super().closeEvent(event)

    def reject(self) -> None:
        """Reject (Close/Esc)."""
        if hasattr(self, '_maybe_prompt_unsaved_changes') and not self._maybe_prompt_unsaved_changes():
            return
        self._save_dialog_state()
        parent = getattr(self, "_parent", None)
        if parent:
            try:
                from core.companion_sync import smart_sync_in_background
                smart_sync_in_background(parent)
            except Exception as exc:
                log_debug(f"Failed to auto-sync on glossary reject: {exc}")
        super().reject()


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
        if hasattr(self, "_unconfirmed_only_checkbox") and self._unconfirmed_only_checkbox.isChecked() and idx - 1 >= 0:
            return visible[idx - 1]
        return None

    def _on_confirm_clicked(self, *args, advance: bool = True, **kwargs) -> None:
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
            user_notes=self._user_notes_for_save(),
        )

    def _on_companion_sync_clicked(self) -> None:
        """Show companion sync options (Push to mobile / Pull from mobile)."""
        from PyQt6.QtWidgets import QMenu, QMessageBox
        from core.companion_sync import CompanionSyncClient

        parent = getattr(self, "_parent", None)
        settings_mgr = getattr(parent, "settings_manager", None)
        server_url = (settings_mgr.get("companion_server_url", "") if settings_mgr else "") or getattr(parent, "companion_server_url", "")
        token = (settings_mgr.get("companion_api_token", "") if settings_mgr else "") or getattr(parent, "companion_api_token", "picoripi")

        if not server_url:
            try:
                import json
                from utils.constants import SETTINGS_FILE_PATH
                if Path(SETTINGS_FILE_PATH).exists():
                    with open(SETTINGS_FILE_PATH, "r", encoding="utf-8") as f:
                        disk_data = json.load(f)
                        server_url = disk_data.get("companion_server_url", "")
                        token = disk_data.get("companion_api_token", token or "picoripi")
            except Exception:
                pass

        if not server_url:
            ans = QMessageBox.question(
                self,
                tr("Companion Server"),
                tr(
                    "Companion server is not configured yet.\n\n"
                    "Would you like to open Settings to specify your remote Companion server URL and token?"
                ),
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                QMessageBox.StandardButton.Yes,
            )
            if ans == QMessageBox.StandardButton.Yes:
                if hasattr(parent, "open_settings_dialog") and callable(parent.open_settings_dialog):
                    parent.open_settings_dialog()
                elif hasattr(parent, "actions") and hasattr(parent.actions, "open_settings_dialog"):
                    parent.actions.open_settings_dialog()
                elif hasattr(parent, "open_settings_action"):
                    parent.open_settings_action.trigger()

                # Re-check settings after user closes Settings dialog
                server_url = (settings_mgr.get("companion_server_url", "") if settings_mgr else "") or getattr(parent, "companion_server_url", "")
                token = (settings_mgr.get("companion_api_token", "") if settings_mgr else "") or getattr(parent, "companion_api_token", "picoripi")
                if not server_url:
                    try:
                        import json
                        from utils.constants import SETTINGS_FILE_PATH
                        if Path(SETTINGS_FILE_PATH).exists():
                            with open(SETTINGS_FILE_PATH, "r", encoding="utf-8") as f:
                                disk_data = json.load(f)
                                server_url = disk_data.get("companion_server_url", "")
                                token = disk_data.get("companion_api_token", token or "picoripi")
                    except Exception:
                        pass
                if not server_url:
                    return
            else:
                return

        client = CompanionSyncClient(server_url, token)

        menu = QMenu(self)
        smart_sync_action = menu.addAction(tr("🔄 Smart Sync with Companion..."))
        menu.addSeparator()
        push_action = menu.addAction(tr("⬆ Push Glossary & Context to Mobile Companion"))
        pull_action = menu.addAction(tr("⬇ Pull Reviewed Glossary from Mobile Companion"))
        menu.addSeparator()
        test_action = menu.addAction(tr("⚙ Test Server Connection..."))

        selected = menu.exec(self._companion_sync_button.mapToGlobal(self._companion_sync_button.rect().bottomLeft()))
        if not selected:
            return

        if selected == test_action:
            ok, msg = client.test_connection()
            if ok:
                QMessageBox.information(self, tr("Companion Server"), f"✓ {msg}")
            else:
                QMessageBox.warning(self, tr("Companion Server"), f"✗ {msg}")
            return

        project_mgr = getattr(parent, "project_manager", None)
        project_obj = getattr(project_mgr, "project", None)
        project_name = getattr(project_obj, "name", "DefaultProject") if project_obj else "DefaultProject"
        glossary_mgr = getattr(parent, "glossary_manager", None)
        glossary_path = getattr(glossary_mgr, "glossary_path", None)

        if selected == smart_sync_action:
            from components.companion.sync_dialog import CompanionSyncDialog

            sync_dlg = CompanionSyncDialog(
                parent=self,
                client=client,
                project_name=project_name,
                glossary_path=glossary_path,
                entries=self._all_entries,
                occurrence_map=self._occurrences,
                reference_data=self._reference_data,
            )
            sync_dlg.exec()
            if sync_dlg.terms_pulled > 0:
                if glossary_mgr:
                    glossary_mgr.refresh_from_disk()
                self.reload_data()
            return

        if selected == push_action:
            ok, msg, count = client.push_project(
                project_name=project_name,
                glossary_path=glossary_path,
                entries=self._all_entries,
                occurrence_map=self._occurrences,
                reference_data=self._reference_data,
            )
            if ok:
                QMessageBox.information(self, tr("Companion Sync"), f"✓ {msg}")
            else:
                QMessageBox.critical(self, tr("Companion Sync"), f"✗ {msg}")
        elif selected == pull_action:
            ok, msg, count = client.pull_project(
                project_name=project_name,
                glossary_path=glossary_path,
            )
            if ok:
                if glossary_mgr:
                    glossary_mgr.refresh_from_disk()
                glossary_handler = getattr(parent, "glossary_handler", None)
                if glossary_handler and hasattr(glossary_handler, "refresh_open_dialog"):
                    glossary_handler.refresh_open_dialog()
                QMessageBox.information(
                    self,
                    tr("Companion Sync"),
                    f"✓ {msg}\n\nLocal glossary updated and view refreshed.",
                )
            else:
                QMessageBox.critical(self, tr("Companion Sync"), f"✗ {msg}")
