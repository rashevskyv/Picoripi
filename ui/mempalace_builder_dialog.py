import os
import sqlite3
from PyQt6.QtWidgets import QDialog, QFileDialog, QMessageBox, QTableWidgetItem
from PyQt6.QtCore import Qt, pyqtSlot

from core.mempalace_client import MemePalaceClient
from core.mempalace_worker import (
    MemePalaceScriptAnalyzerWorker, MemePalaceChapterMapperWorker, 
    MemePalaceChapterAIAnalyzerWorker, MemePalaceCharacterProfilerWorker
)
from utils.logging_utils import log_info, log_error

# Import decomposed elements
from ui.mempalace.mempalace_sleep import prevent_sleep, restore_sleep, put_to_sleep
from ui.mempalace.mempalace_ui import MemePalaceBuilderUiMixin
from ui.mempalace.mempalace_pipeline import MemePalacePipelineMixin

class MemePalaceBuilderDialog(QDialog, MemePalaceBuilderUiMixin, MemePalacePipelineMixin):
    """Dialog class for meme palace builder."""

    def __init__(self, main_window, parent=None):
        """Initialize a new instance."""
        super().__init__(parent or main_window)
        self.mw = main_window
        self.setWindowTitle("MemePalace Context Builder")
        self.resize(750, 600)
        self.setMinimumSize(650, 500)
        self.setAttribute(Qt.WidgetAttribute.WA_DeleteOnClose)
        
        self.worker = None
        self.client = None
        self.composer = None
        self.analysis_queue = []
        self.analysis_total_count = 0
        self.analysis_completed_count = 0
        self.current_analysis_idx = -1
        self.user_cancelled = False
        self.should_sleep_after = False
        self.pipeline_running = False
        self.pipeline_step = 0
        self.saved_pipeline_running = False
        self.saved_pipeline_step = 0
        self.saved_pipeline_wing = ""
        self.saved_pipeline_script = ""

        self._init_composer_and_client()
        self._setup_ui()
        self.load_builder_settings()
        
        # Auto-fill script path if empty
        if not self.file_path_edit.text().strip():
            script_path = self.composer._find_script_path() if self.composer else None
            if isinstance(script_path, str) and script_path:
                self.file_path_edit.setText(script_path)
                self.append_log(f"Auto-discovered game script file: {os.path.basename(script_path)}")
                
        self.refresh_chapters_list()

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

    def _finish_and_maybe_sleep(self):
        """Internal helper to finish and maybe sleep."""
        restore_sleep()
        if self.sleep_after_checkbox.isChecked() and not getattr(self, "user_cancelled", False):
            self.append_log("[System] All tasks completed! Suspending system in 5 seconds...")
            from PyQt6.QtCore import QTimer
            QTimer.singleShot(5000, put_to_sleep)

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

    @pyqtSlot()
    def _browse_script_file(self):
        """Internal helper to browse script file."""
        path, _ = QFileDialog.getOpenFileName(
            self, "Select Game Script File", "", "Text Files (*.txt);;All Files (*)"
        )
        if path:
            self.file_path_edit.setText(path)
            self.append_log(f"Selected script file: {os.path.basename(path)}")

    def append_log(self, text: str):
        """Append log."""
        self.log_text.append(text)
        scrollbar = self.log_text.verticalScrollBar()
        scrollbar.setValue(scrollbar.maximum())

    def _get_ai_provider_or_warn(self):
        """Internal helper to get the ai provider or warn."""
        ai_provider = None
        if hasattr(self.mw, "translation_handler") and self.mw.translation_handler:
            try:
                ai_provider = self.mw.translation_handler._prepare_provider()
            except Exception as e:
                log_error(f"Failed to prepare AI provider: {e}")
                
        if not ai_provider:
            QMessageBox.warning(
                self, "AI Provider Error", 
                "No active AI Provider configured. Please check your API settings."
            )
        return ai_provider

    @pyqtSlot()
    def _pre_analyze_script_via_ai(self):
        """Mine characters and terminology from script introduction."""
        self.save_builder_settings()
        self._maybe_prevent_sleep()
        
        file_path = self.file_path_edit.text().strip()
        if not file_path or not os.path.exists(file_path):
            QMessageBox.warning(self, "Validation Error", "Please select a valid game script file first.")
            return

        ai_provider = self._get_ai_provider_or_warn()
        if not ai_provider:
            return

        self._pre_analyze_script_via_ai_core(file_path, ai_provider)

    def _pre_analyze_script_via_ai_core(self, file_path, ai_provider):
        """Internal helper to pre analyze script via ai core."""
        self.append_log("Starting pre-analysis of script characters via AI...")
        self._set_ui_enabled(False)

        wing_name = self.wing_edit.text().strip()
        
        gm = getattr(self.mw, 'glossary_manager', None)
        if not gm:
            gm = getattr(self.mw, '_glossary_manager', None)
        if not gm and hasattr(self.mw, 'translation_handler') and self.mw.translation_handler:
            gm = getattr(self.mw.translation_handler, '_glossary_manager', None)

        target_lang = getattr(self.mw, 'target_language', 'Ukrainian')

        self.worker = MemePalaceScriptAnalyzerWorker(
            client=self.client,
            file_path=file_path,
            ai_provider=ai_provider,
            wing_name=wing_name,
            glossary_manager=gm,
            target_lang=target_lang,
            plugin_name=getattr(self.mw, "active_game_plugin", None),
            mw=self.mw
        )

        self.worker.progress.connect(self._handle_worker_progress)
        self.worker.log.connect(self.append_log)
        self.worker.finished.connect(self._handle_char_mining_finished)
        self.worker.finished.connect(self.worker.deleteLater)
        self.worker.start()

    def _handle_char_mining_finished(self, success, message):
        """Internal helper to handle char mining finished."""
        self._set_ui_enabled(True)
        self.worker = None
        self.progress_bar.setValue(100 if success else 0)

        if success:
            self.append_log("CHARACTER MINING COMPLETED SUCCESSFULLY!")
            try:
                gh = None
                if hasattr(self.mw, 'translation_handler') and self.mw.translation_handler:
                    gh = getattr(self.mw.translation_handler, 'glossary_handler', None)
                if gh:
                    gh.glossary_manager.refresh_from_disk()
                    gh._update_glossary_highlighting()
            except Exception as e:
                log_error(f"Failed to refresh glossary after mining: {e}")

            if getattr(self, "pipeline_running", False):
                self._advance_pipeline()
            else:
                self._finish_and_maybe_sleep()
                QMessageBox.information(self, "Success", f"Character profiling completed!\n\n{message}")
        else:
            if getattr(self, "user_cancelled", False):
                self.append_log("Character mining stopped by user.")
                self.pipeline_running = False
                self._finish_and_maybe_sleep()
                self.user_cancelled = False
                self._update_pipeline_btn_text()
            else:
                self.append_log("CHARACTER MINING FAILED.")
                if getattr(self, "pipeline_running", False):
                    self._abort_pipeline(message)
                else:
                    self._finish_and_maybe_sleep()
                    QMessageBox.warning(self, "Failed", f"Character profiling failed:\n{message}")

    @pyqtSlot()
    def _profile_characters_speech_via_ai(self):
        """Analyze character speech patterns and build rich glossary profiles via AI."""
        self.save_builder_settings()
        self._maybe_prevent_sleep()

        ai_provider = self._get_ai_provider_or_warn()
        if not ai_provider:
            return

        self._profile_characters_speech_via_ai_core(ai_provider)

    def _profile_characters_speech_via_ai_core(self, ai_provider):
        """Internal helper to profile characters speech via ai core."""
        self.append_log("Starting AI character speech profiling...")
        self._set_ui_enabled(False)

        wing_name = self.wing_edit.text().strip()

        gm = getattr(self.mw, 'glossary_manager', None)
        if not gm:
            gm = getattr(self.mw, '_glossary_manager', None)
        if not gm and hasattr(self.mw, 'translation_handler') and self.mw.translation_handler:
            gm = getattr(self.mw.translation_handler, '_glossary_manager', None)

        target_lang = getattr(self.mw, 'target_language', 'Ukrainian')

        self.worker = MemePalaceCharacterProfilerWorker(
            client=self.client,
            ai_provider=ai_provider,
            wing_name=wing_name,
            glossary_manager=gm,
            target_lang=target_lang,
            plugin_name=getattr(self.mw, "active_game_plugin", None),
            composer=self.composer,
            mw=self.mw
        )

        self.worker.progress.connect(self._handle_worker_progress)
        self.worker.log.connect(self.append_log)
        self.worker.finished.connect(self._handle_speech_profiling_finished)
        self.worker.finished.connect(self.worker.deleteLater)
        self.worker.start()

    def _handle_speech_profiling_finished(self, success, message):
        """Internal helper to handle speech profiling finished."""
        self._set_ui_enabled(True)
        self.worker = None
        self.progress_bar.setValue(100 if success else 0)

        if success:
            self.append_log("CHARACTER SPEECH PROFILING COMPLETED SUCCESSFULLY!")
            try:
                gh = None
                if hasattr(self.mw, 'translation_handler') and self.mw.translation_handler:
                    gh = getattr(self.mw.translation_handler, 'glossary_handler', None)
                if gh:
                    gh.glossary_manager.refresh_from_disk()
                    gh._update_glossary_highlighting()
                    if gh.dialog and gh.dialog.isVisible():
                        entries = sorted(gh.glossary_manager.get_entries(), key=lambda e: e.original.lower())
                        data_source = getattr(self.mw.data_store, "data", [])
                        occurrence_map = gh.glossary_manager.build_occurrence_index(data_source)
                        gh.dialog.reload_data(entries, occurrence_map)
            except Exception as e:
                log_error(f"Failed to refresh glossary after speech profiling: {e}")

            if getattr(self, "pipeline_running", False):
                self._advance_pipeline()
            else:
                self._finish_and_maybe_sleep()
                QMessageBox.information(self, "Success", f"Character speech profiling completed!\n\n{message}")
        else:
            if getattr(self, "user_cancelled", False):
                self.append_log("Character speech profiling stopped by user.")
                self.pipeline_running = False
                self._finish_and_maybe_sleep()
                self.user_cancelled = False
                self._update_pipeline_btn_text()
            else:
                self.append_log("CHARACTER SPEECH PROFILING FAILED.")
                if getattr(self, "pipeline_running", False):
                    self._abort_pipeline(message)
                else:
                    self._finish_and_maybe_sleep()
                    QMessageBox.warning(self, "Failed", f"Character speech profiling failed:\n{message}")

    @pyqtSlot()
    def _start_chapters_mapping(self):
        """Map BMG text items to chapters."""
        self.save_builder_settings()
        
        file_path = self.file_path_edit.text().strip()
        if not file_path or not os.path.exists(file_path):
            QMessageBox.warning(self, "Validation Error", "Please select a valid game script file first.")
            return

        self._start_chapters_mapping_core(file_path)

    def _start_chapters_mapping_core(self, file_path):
        """Internal helper to start chapters mapping core."""
        wing_name = self.wing_edit.text().strip()
        self._set_ui_enabled(False)

        self.worker = MemePalaceChapterMapperWorker(
            client=self.client,
            composer=self.composer,
            wing_name=wing_name
        )
        self.worker.progress.connect(self._handle_worker_progress)
        self.worker.log.connect(self.append_log)
        self.worker.finished.connect(self._handle_chapters_mapping_finished)
        self.worker.finished.connect(self.worker.deleteLater)
        self.worker.start()

    def _handle_chapters_mapping_finished(self, success, message):
        """Internal helper to handle chapters mapping finished."""
        self._set_ui_enabled(True)
        self.worker = None
        self.progress_bar.setValue(100 if success else 0)

        if success:
            self.refresh_chapters_list()
            if getattr(self, "pipeline_running", False):
                self._advance_pipeline()
            else:
                QMessageBox.information(self, "Success", f"Chapters mapped successfully!\n\n{message}")
        else:
            if getattr(self, "user_cancelled", False):
                self.append_log("Chapters mapping stopped by user.")
                self.user_cancelled = False
                self.pipeline_running = False
                self._update_pipeline_btn_text()
            else:
                if getattr(self, "pipeline_running", False):
                    self._abort_pipeline(message)
                else:
                    QMessageBox.warning(self, "Failed", f"Chapters mapping failed:\n{message}")

    @pyqtSlot()
    def _analyze_selected_chapter(self):
        """Generate AI overview for the selected chapters."""
        selected_items = self.table.selectedItems()
        selected_rows = sorted(list(set(item.row() for item in selected_items)))
        if not selected_rows:
            QMessageBox.warning(self, "No selection", "Please select one or more chapters to analyze from the table.")
            return

        self.save_builder_settings()
        self._maybe_prevent_sleep()

        self.analysis_queue = []
        for row in selected_rows:
            chapter_id = self.table.item(row, 0).data(Qt.ItemDataRole.UserRole)
            self.analysis_queue.append(chapter_id)

        self.analysis_total_count = len(self.analysis_queue)
        self.analysis_completed_count = 0

        self._set_ui_enabled(False)
        self._process_analysis_queue()

    def _handle_chapter_analysis_finished(self, success, message):
        """Internal helper to handle chapter analysis finished."""
        self.worker = None

        if success:
            self.append_log(message)
            self.refresh_chapters_list()
            self.analysis_completed_count += 1
            if self.analysis_queue:
                self._process_analysis_queue()
            else:
                self._set_ui_enabled(True)
                self.progress_bar.setValue(100)
                if getattr(self, "pipeline_running", False):
                    self._advance_pipeline()
                else:
                    QMessageBox.information(self, "Finished", "All selected chapters successfully analyzed via AI!")
                    self._finish_and_maybe_sleep()
        else:
            self._set_ui_enabled(True)
            self.refresh_chapters_list()
            if getattr(self, "user_cancelled", False):
                self.append_log("Chapter analysis stopped by user.")
                self.pipeline_running = False
                self._finish_and_maybe_sleep()
                self.user_cancelled = False
                self._update_pipeline_btn_text()
            else:
                if getattr(self, "pipeline_running", False):
                    self._abort_pipeline(message)
                else:
                    QMessageBox.warning(self, "AI Error", f"Chapter analysis failed:\n{message}")
                    self._finish_and_maybe_sleep()
            self.analysis_queue = []
            self.analysis_total_count = 0
            self.analysis_completed_count = 0

    @pyqtSlot()
    def _analyze_all_chapters(self):
        """Setup queue to analyze all chapters."""
        reply = QMessageBox.question(
            self, "Analyze All Chapters",
            "This will analyze all chapters one by one using the AI provider. It may take several minutes.\n\n"
            "Do you want to proceed?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No, QMessageBox.StandardButton.No
        )
        if reply != QMessageBox.StandardButton.Yes:
            return

        self.save_builder_settings()
        self._maybe_prevent_sleep()
        self._analyze_all_chapters_core()

    def _analyze_all_chapters_core(self):
        """Internal helper to analyze all chapters core."""
        self.analysis_queue = []
        wing_name = self.composer._get_wing_name()
        chapters = self.client.get_all_chapters(wing_name)
        
        for ch in chapters:
            self.analysis_queue.append(ch['id'])

        if not self.analysis_queue:
            self.append_log("No chapters found to analyze. Proceeding in pipeline...")
            if getattr(self, "pipeline_running", False):
                self._advance_pipeline()
            else:
                QMessageBox.information(self, "Finished", "No chapters found to analyze.")
            return

        self.analysis_total_count = len(self.analysis_queue)
        self.analysis_completed_count = 0

        self.current_analysis_idx = 0
        self._set_ui_enabled(False)
        self._process_analysis_queue()

    def _process_analysis_queue(self):
        """Process queue sequentially."""
        if not self.analysis_queue:
            self._set_ui_enabled(True)
            self.progress_bar.setValue(100)
            QMessageBox.information(self, "Finished", "All chapters successfully analyzed via AI!")
            self._finish_and_maybe_sleep()
            return

        chapter_id = self.analysis_queue.pop(0)
        
        try:
            conn_db = sqlite3.connect(self.client.db_path)
            cursor = conn_db.cursor()
            cursor.execute("SELECT num, title, start_line, content FROM script_chapters WHERE id = ?", (chapter_id,))
            row_data = cursor.fetchone()
            conn_db.close()
        except Exception as e:
            self.append_log(f"Failed to fetch chapter {chapter_id}: {e}")
            self.analysis_completed_count += 1
            self._process_analysis_queue()
            return

        if not row_data:
            self.analysis_completed_count += 1
            self._process_analysis_queue()
            return

        num, title, start_line, content = row_data
        
        ai_provider = None
        if hasattr(self.mw, "translation_handler") and self.mw.translation_handler:
            ai_provider = self.mw.translation_handler._prepare_provider()

        if not ai_provider:
            self.append_log("AI provider missing, stopping queue.")
            self._set_ui_enabled(True)
            return

        target_lang = getattr(self.mw, 'target_language', 'Ukrainian')

        self.worker = MemePalaceChapterAIAnalyzerWorker(
            client=self.client,
            ai_provider=ai_provider,
            chapter_id=chapter_id,
            num=num,
            title=title,
            content=content,
            start_line=start_line,
            target_lang=target_lang,
            mw=self.mw
        )
        self.worker.progress.connect(self._handle_worker_progress)
        self.worker.log.connect(self.append_log)
        self.worker.finished.connect(self._handle_chapter_analysis_finished)
        self.worker.finished.connect(self.worker.deleteLater)
        self.worker.start()

    def _handle_worker_progress(self, current, total, text):
        """Internal helper to handle worker progress."""
        if total > 0:
            if getattr(self, "analysis_total_count", 0) > 0:
                completed = getattr(self, "analysis_completed_count", 0)
                sub_progress = current / total
                overall_progress = int(((completed + sub_progress) / self.analysis_total_count) * 100)
                self.progress_bar.setValue(min(overall_progress, 100))
            else:
                self.progress_bar.setValue(int((current / total) * 100))
        self.append_log(text)

    @pyqtSlot()
    def _clear_database(self):
        """Clear mapped data from local database."""
        reply = QMessageBox.question(
            self, "Clear Database", 
            "Are you sure you want to completely clear the local MemePalace database?\n\n"
            "This will delete all mapped rooms, dialogues, relations, script chapters, and chapter summaries.",
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
                QMessageBox.information(self, "Clear Database", "Local database cleared successfully.")
                self.refresh_chapters_list()
            else:
                self.append_log("ERROR: Failed to clear the database.")
        except Exception as e:
            log_error(f"Error clearing database: {e}")
            self.append_log(f"ERROR: {e}")

    @pyqtSlot()
    def _handle_close_or_cancel(self):
        """Internal helper to handle close or cancel."""
        self.should_sleep_after = False
        restore_sleep()
        if self.worker and self.worker.isRunning():
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
            self.save_builder_settings()
            self.close()

    def load_builder_settings(self):
        """Load recent dialog preferences from settings.json."""
        try:
            sm = getattr(self.mw, 'settings_manager', None)
            if sm:
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
                sm.save_settings()
        except Exception as e:
            log_error(f"Failed to save builder settings: {e}")

    def closeEvent(self, event):
        """Handle builder close event by safely shutting down the worker thread."""
        self.should_sleep_after = False
        restore_sleep()
        if self.worker:
            from utils.thread_utils import safe_shutdown_thread
            self.append_log("Shutting down worker thread...")
            safe_shutdown_thread(self.worker, self.worker)
            self.worker = None
        self.save_builder_settings()
        event.accept()
