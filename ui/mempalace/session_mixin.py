"""Session / settings / close-lifecycle mixin for MemePalaceBuilderDialog."""
import os
import sqlite3
from PyQt6.QtWidgets import QMessageBox, QTableWidgetItem
from PyQt6.QtCore import Qt, pyqtSlot

from core.mempalace_client import MemePalaceClient
from utils.logging_utils import log_error
from ui.mempalace.mempalace_sleep import prevent_sleep, restore_sleep
from core.i18n import tr
from ui.mempalace.constants import (
    _HIERARCHY_HASH_KEY,
    _HIERARCHY_PATH_KEY,
    _HIERARCHY_VERSION_KEY,
)


class MemePalaceSessionMixin:
    """Sleep toggles, settings persistence, logging, and close/cancel lifecycle."""

    def _init_composer_and_client(self):
        """Prepare local DB client and script composer."""
        project_dir = self.mw.project_manager.project_dir if (hasattr(self.mw, "project_manager") and self.mw.project_manager) else None
        if not project_dir:
            project_dir = os.path.dirname(self.mw.data_store.project_file) if (hasattr(self.mw, "data_store") and self.mw.data_store and getattr(self.mw.data_store, "project_file", None)) else os.getcwd()

        if project_dir:
            db_name = "mempalace_local.db"
            curr = project_dir
            for _ in range(4):
                tp_subdir = os.path.join(curr, "TwilightPrincess")
                if os.path.isdir(tp_subdir) and os.path.exists(os.path.join(tp_subdir, db_name)):
                    project_dir = tp_subdir
                    break
                if os.path.exists(os.path.join(curr, db_name)):
                    project_dir = curr
                    break
                parent = os.path.dirname(curr)
                if parent == curr:
                    break
                curr = parent

        self.client = MemePalaceClient(project_dir=project_dir)

        if hasattr(self.mw, 'translation_handler') and self.mw.translation_handler:
            self.composer = getattr(self.mw.translation_handler, 'prompt_composer', None)
        if not self.composer:
            from handlers.translation.ai_prompt_composer import AIPromptComposer
            class DummyHandler:
                def __init__(self, mw):
                    self.mw = mw
                    self.data_processor = mw.data_processor
                    self.ui_updater = mw.ui_updater
                    self._glossary_manager = None
                    if hasattr(mw, 'translation_handler') and mw.translation_handler:
                        self._glossary_manager = getattr(mw.translation_handler, '_glossary_manager', None)
                def __getattr__(self, name):
                    return getattr(self.mw, name)
            self.composer = AIPromptComposer(DummyHandler(self.mw))

    def _maybe_prevent_sleep(self):
        """Internal helper to maybe prevent sleep."""
        if self.prevent_sleep_checkbox.isChecked():
            prevent_sleep()

    def _finish_and_maybe_sleep(self, success: bool = True):
        """Internal helper to finish and maybe sleep."""
        restore_sleep()
        if self.sleep_after_checkbox.isChecked() and not getattr(self, "user_cancelled", False) and success:
            self.append_log("[System] All tasks completed! Idle sleep countdown scheduled...")
            delay = 300
            sm = getattr(self.mw, 'settings_manager', None)
            if sm:
                val = sm.get("auto_sleep_idle_delay_seconds", 300)
                if isinstance(val, int) and val > 0:
                    delay = val
            from core.auto_sleep_manager import AutoSleepManager
            AutoSleepManager.get_instance().schedule_sleep(
                task_name="MemePalace Pipeline",
                delay_seconds=delay,
                parent_widget=self
            )
        else:
            from core.auto_sleep_manager import AutoSleepManager
            AutoSleepManager.get_instance().cancel_sleep(reason="MemePalace pipeline finished without sleep condition")

    def _handle_prevent_sleep_toggled(self, checked: bool):
        """Internal helper to handle prevent sleep toggled."""
        self.save_builder_settings()
        if self.worker and self.worker.isRunning():
            if checked:
                prevent_sleep()
                self.append_log("[System] Sleep prevention activated dynamically during execution.")
            else:
                restore_sleep()
                self.append_log("[System] Sleep prevention deactivated dynamically during execution.")

    def _handle_sleep_after_toggled(self, checked: bool):
        """Internal helper to handle sleep after toggled."""
        self.save_builder_settings()
        if not checked:
            from core.auto_sleep_manager import AutoSleepManager
            AutoSleepManager.get_instance().cancel_sleep(reason="Sleep after finish unchecked")
        if self.worker and self.worker.isRunning():
            if checked:
                self.append_log("[System] Scheduled computer sleep upon task completion.")
            else:
                self.append_log("[System] Cancelled scheduled computer sleep upon task completion.")

    def refresh_chapters_list(self):
        """Reload chapters from local DB."""
        if not self.composer or not self.client:
            return
        wing_name = self.composer._get_wing_name()
        chapters = self.client.get_all_chapters(wing_name)
    
        self.table.setRowCount(0)
        for idx, ch in enumerate(chapters):
            self.table.insertRow(idx)
        
            num_item = QTableWidgetItem(f"Chapter {ch['num']}")
            num_item.setData(Qt.ItemDataRole.UserRole, ch['id'])
        
            title_item = QTableWidgetItem(ch['title'])
            lines_item = QTableWidgetItem(f"{ch['start_line']} - {ch['end_line']}")
            mapped_item = QTableWidgetItem(str(ch['mapped_count']))
        
            status_text = "Analyzed" if ch['ai_summary'] else "Not Analyzed"
            status_item = QTableWidgetItem(status_text)
        
            for item in (num_item, title_item, lines_item, mapped_item, status_item):
                item.setFlags(item.flags() & ~Qt.ItemFlag.ItemIsEditable)
            
            self.table.setItem(idx, 0, num_item)
            self.table.setItem(idx, 1, title_item)
            self.table.setItem(idx, 2, lines_item)
            self.table.setItem(idx, 3, mapped_item)
            self.table.setItem(idx, 4, status_item)

        self.table.resizeColumnsToContents()
        self.table.horizontalHeader().setStretchLastSection(True)
        if hasattr(self, "workflow_tabs"):
            self._refresh_wizard_state()

    def append_log(self, text: str):
        """Append log."""
        self.log_text.append(text)
        scrollbar = self.log_text.verticalScrollBar()
        scrollbar.setValue(scrollbar.maximum())

    @pyqtSlot()
    def _clear_database(self):
        """Clear mapped data from local database."""
        reply = QMessageBox.question(
            self, tr('Clear Database'), 
            tr('Are you sure you want to completely clear the local MemePalace database?\n\nThis will delete all mapped rooms, dialogues, relations, script chapters, and chapter summaries.'),
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No, QMessageBox.StandardButton.No
        )
        if reply != QMessageBox.StandardButton.Yes:
            return

        self.append_log("Clearing local database...")
        try:
            if self.client.clear_all_local_data():
                # Also delete chapters mapping records
                try:
                    conn = sqlite3.connect(self.client.db_path)
                    cursor = conn.cursor()
                    cursor.execute("DELETE FROM script_chapters")
                    cursor.execute("DELETE FROM script_mappings")
                    conn.commit()
                    conn.close()
                except Exception:
                    pass
                
                self.append_log("SUCCESS: Local database cleared successfully!")
                QMessageBox.information(self, tr('Clear Database'), tr('Local database cleared successfully.'))
                self.refresh_chapters_list()
            else:
                self.append_log("ERROR: Failed to clear the database.")
        except Exception as e:
            log_error(f"Error clearing database: {e}")
            self.append_log(f"ERROR: {e}")

    @pyqtSlot()
    def _handle_close_or_cancel(self):
        """Internal helper to handle close or cancel."""
        if self.worker and self.worker.isRunning():
            reply = QMessageBox.question(
                self,
                tr('Stop current AI operation?'),
                tr('The current request will stop after the active network step. Are you sure you want to continue?'),
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                QMessageBox.StandardButton.No,
            )
            if reply != QMessageBox.StandardButton.Yes:
                return

            self.should_sleep_after = False
            restore_sleep()
            self.user_cancelled = True
        
            if getattr(self, "pipeline_running", False) and getattr(self, "pipeline_step", 0) > 0:
                try:
                    sm = getattr(self.mw, 'settings_manager', None)
                    if sm:
                        sm.set("mempalace_pipeline_running", True)
                        sm.set("mempalace_pipeline_step", self.pipeline_step)
                        sm.set("mempalace_pipeline_wing", self.wing_edit.text().strip())
                        sm.set("mempalace_pipeline_script", self.file_path_edit.text().strip())
                        sm.save_settings()
                    
                        self.saved_pipeline_running = True
                        self.saved_pipeline_step = self.pipeline_step
                        self.saved_pipeline_wing = self.wing_edit.text().strip()
                        self.saved_pipeline_script = self.file_path_edit.text().strip()
                except Exception:
                    pass

            self.analysis_queue = []
            self.analysis_total_count = 0
            self.analysis_completed_count = 0
            self.worker.cancel()
            self.append_log("Worker cancellation requested...")
            self.cancel_btn.setEnabled(False)
            self._update_pipeline_btn_text()
        else:
            self.should_sleep_after = False
            restore_sleep()
            self.save_builder_settings()
            self.close()

    def load_builder_settings(self):
        """Load recent dialog preferences from settings.json."""
        try:
            sm = getattr(self.mw, 'settings_manager', None)
            if sm:
                imported_path = sm.get(_HIERARCHY_PATH_KEY, "")
                imported_hash = sm.get(_HIERARCHY_HASH_KEY, "")
                imported_version = sm.get(_HIERARCHY_VERSION_KEY, None)
                self.imported_hierarchy_project_path = (
                    imported_path if isinstance(imported_path, str) else ""
                )
                self.imported_hierarchy_project_hash = (
                    imported_hash if isinstance(imported_hash, str) else ""
                )
                self.imported_hierarchy_project_version = (
                    imported_version
                    if isinstance(imported_version, int) and not isinstance(imported_version, bool)
                    else None
                )
                script_path = sm.get("mempalace_script_path", "")
                wing_name = sm.get("mempalace_wing_name", "")
                if isinstance(script_path, str) and script_path:
                    self.file_path_edit.setText(script_path)
                if isinstance(wing_name, str) and wing_name:
                    self.wing_edit.setText(wing_name)
                prevent_sleep_val = sm.get("mempalace_prevent_sleep", True)
                if isinstance(prevent_sleep_val, bool):
                    self.prevent_sleep_checkbox.setChecked(prevent_sleep_val)
                sleep_after_val = sm.get("mempalace_sleep_after_finish", False)
                if isinstance(sleep_after_val, bool):
                    self.sleep_after_checkbox.setChecked(sleep_after_val)
            
                self.saved_pipeline_running = sm.get("mempalace_pipeline_running", False)
                self.saved_pipeline_step = sm.get("mempalace_pipeline_step", 0)
                self.saved_pipeline_wing = sm.get("mempalace_pipeline_wing", "")
                self.saved_pipeline_script = sm.get("mempalace_pipeline_script", "")
                self._update_pipeline_btn_text()
                splitter_sizes = sm.get("mempalace_chapters_splitter_sizes", None)
                if (
                    isinstance(splitter_sizes, list)
                    and len(splitter_sizes) == 2
                    and all(isinstance(size, int) and size > 0 for size in splitter_sizes)
                ):
                    self._saved_chapters_splitter_sizes = splitter_sizes
                if self.imported_hierarchy_project_path:
                    self._load_hierarchy_project_preview(self.imported_hierarchy_project_path)
                    self.story_document_id = self.client.get_story_document_id(
                        self.imported_hierarchy_project_path
                    )
                    self._refresh_story_tree()
                    self._restore_dialogue_mapping_state()
        except Exception as e:
            log_error(f"Failed to load builder settings: {e}")

    def save_builder_settings(self):
        """Save dialog preferences into settings.json."""
        try:
            sm = getattr(self.mw, 'settings_manager', None)
            if sm:
                sm.set("mempalace_script_path", self.file_path_edit.text().strip())
                sm.set("mempalace_wing_name", self.wing_edit.text().strip())
                sm.set("mempalace_prevent_sleep", self.prevent_sleep_checkbox.isChecked())
                sm.set("mempalace_sleep_after_finish", self.sleep_after_checkbox.isChecked())
                splitter_sizes = self.chapters_splitter.sizes()
                if not self.story_group.isVisible() or not all(size > 0 for size in splitter_sizes):
                    splitter_sizes = getattr(
                        self, "_saved_chapters_splitter_sizes", [390, 260]
                    )
                else:
                    self._saved_chapters_splitter_sizes = splitter_sizes
                sm.set("mempalace_chapters_splitter_sizes", splitter_sizes)
                sm.save_settings()
        except Exception as e:
            log_error(f"Failed to save builder settings: {e}")

    def reject(self):
        """Handle dialog rejection (e.g. Escape key) via guarded close."""
        self.close()

    def closeEvent(self, event):
        """Handle builder close event by safely shutting down the worker thread."""
        if self.worker and self.worker.isRunning():
            reply = QMessageBox.question(
                self,
                tr('Stop current AI operation and close the builder?'),
                tr('The current request will stop after the active network step. Are you sure you want to continue?'),
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                QMessageBox.StandardButton.No,
            )
            if reply != QMessageBox.StandardButton.Yes:
                event.ignore()
                return

        self.should_sleep_after = False
        restore_sleep()
        from core.auto_sleep_manager import AutoSleepManager
        AutoSleepManager.get_instance().cancel_sleep(reason="MemePalace builder closed")
        if self.worker:
            from utils.thread_utils import safe_shutdown_thread
            self.append_log("Shutting down worker thread...")
            safe_shutdown_thread(self.worker, self.worker)
            self.worker = None
        self.save_builder_settings()
        event.accept()

