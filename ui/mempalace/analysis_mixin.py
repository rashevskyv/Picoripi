"""Timeline / chapter / character analysis mixin for MemePalaceBuilderDialog."""
import os
import sqlite3
from PyQt6.QtWidgets import QMessageBox
from PyQt6.QtCore import Qt, pyqtSlot

from core.mempalace.timeline_ai_analyzer import StoryTimelineAIAnalyzerWorker
from core.mempalace.normalized_character_profiler import NormalizedCharacterProfilerWorker
from core.mempalace_worker import (
    MemePalaceScriptAnalyzerWorker,
    MemePalaceChapterMapperWorker,
    MemePalaceChapterAIAnalyzerWorker,
    MemePalaceCharacterProfilerWorker,
)
from utils.logging_utils import log_error
from core.i18n import tr


class MemePalaceAnalysisMixin:
    """Story timeline, chapter mapping/analysis queue, and character mining/speech."""

    @pyqtSlot()
    def _start_story_timeline_analysis(self):
        if self.worker and self.worker.isRunning():
            QMessageBox.information(self, tr('MemPalace'), tr('Another MemPalace task is still running.'))
            return
        if not self.story_document_id:
            QMessageBox.warning(self, tr('Timeline'), tr('Import a marked Script Markup Studio project first.'))
            return
        ai_provider = None
        if getattr(self.mw, "translation_handler", None):
            ai_provider = self.mw.translation_handler._prepare_provider()
        if not ai_provider:
            QMessageBox.warning(self, tr('Timeline'), tr('Configure an AI provider before building the timeline.'))
            return
        self.analyze_story_timeline_btn.setEnabled(False)
        self.story_timeline_progress.setVisible(True)
        self.story_timeline_progress.setRange(0, 0)
        self.story_timeline_status_label.setText(tr('Analyzing marked dialogue…'))
        self.worker = StoryTimelineAIAnalyzerWorker(
            self.client,
            ai_provider,
            self.story_document_id,
            getattr(self.mw, "target_language", "Ukrainian"),
            self.mw,
        )
        self.worker.progress.connect(self._handle_story_timeline_progress)
        self.worker.log.connect(self.append_log)
        self.worker.finished.connect(self._handle_story_timeline_finished)
        self.worker.finished.connect(self.worker.deleteLater)
        self.worker.start()

    def _handle_story_timeline_progress(self, current: int, total: int, message: str):
        self.story_timeline_progress.setRange(0, max(total, 1))
        self.story_timeline_progress.setValue(current)
        self.story_timeline_status_label.setText(message)

    def _handle_story_timeline_finished(self, success: bool, message: str):
        self.worker = None
        self.analyze_story_timeline_btn.setEnabled(bool(self.story_document_id))
        self.story_timeline_progress.setVisible(False)
        self.story_timeline_status_label.setText(message)
        self.story_timeline_status_label.setStyleSheet(
            "color: #137333;" if success else "color: #a80000;"
        )
        self.append_log(message)
        if success:
            QMessageBox.information(self, tr('Timeline Ready'), message)
        else:
            QMessageBox.warning(self, tr('Timeline'), message)

    @pyqtSlot()
    def _start_normalized_character_profiling(self):
        if self.worker and self.worker.isRunning():
            QMessageBox.information(self, tr('MemPalace'), tr('Another MemPalace task is still running.'))
            return
        if not self.story_document_id:
            QMessageBox.warning(self, tr('Characters'), tr('Import a marked Script Markup Studio project first.'))
            return
        ai_provider = None
        if getattr(self.mw, "translation_handler", None):
            ai_provider = self.mw.translation_handler._prepare_provider()
        if not ai_provider:
            QMessageBox.warning(self, tr('Characters'), tr('Configure an AI provider before analyzing characters.'))
            return
        self.analyze_character_voices_btn.setEnabled(False)
        self.character_profiles_progress.setVisible(True)
        self.character_profiles_progress.setRange(0, 0)
        self.character_profiles_status_label.setText(tr('Analyzing character dialogue…'))
        self.worker = NormalizedCharacterProfilerWorker(
            self.client,
            ai_provider,
            self.story_document_id,
            getattr(self.mw, "target_language", "Ukrainian"),
            self.mw,
        )
        self.worker.progress.connect(self._handle_character_profiles_progress)
        self.worker.log.connect(self.append_log)
        self.worker.finished.connect(self._handle_character_profiles_finished)
        self.worker.finished.connect(self.worker.deleteLater)
        self.worker.start()

    def _handle_character_profiles_progress(self, current: int, total: int, message: str):
        self.character_profiles_progress.setRange(0, max(total, 1))
        self.character_profiles_progress.setValue(current)
        self.character_profiles_status_label.setText(message)

    def _handle_character_profiles_finished(self, success: bool, message: str):
        self.worker = None
        self.analyze_character_voices_btn.setEnabled(bool(self.story_document_id))
        self.character_profiles_progress.setVisible(False)
        self.character_profiles_status_label.setText(message)
        self.character_profiles_status_label.setStyleSheet(
            "color: #137333;" if success else "color: #a80000;"
        )
        self.append_log(message)
        if success:
            QMessageBox.information(self, tr('Character Voices Ready'), message)
        else:
            QMessageBox.warning(self, tr('Characters'), message)

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
                self, tr('AI Provider Error'), 
                tr('No active AI Provider configured. Please check your API settings.')
            )
        return ai_provider

    @pyqtSlot()
    def _pre_analyze_script_via_ai(self):
        """Mine characters and terminology from script introduction."""
        self.save_builder_settings()
        self._maybe_prevent_sleep()
    
        file_path = self.file_path_edit.text().strip()
        if not file_path or not os.path.exists(file_path):
            QMessageBox.warning(self, tr('Validation Error'), tr('Please select a valid game script file first.'))
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
                QMessageBox.information(self, tr('Success'), f"Character profiling completed!\n\n{message}")
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
                    QMessageBox.warning(self, tr('Failed'), f"Character profiling failed:\n{message}")

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
                QMessageBox.information(self, tr('Success'), f"Character speech profiling completed!\n\n{message}")
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
                    QMessageBox.warning(self, tr('Failed'), f"Character speech profiling failed:\n{message}")

    @pyqtSlot()
    def _start_chapters_mapping(self):
        """Map BMG text items to chapters."""
        self.save_builder_settings()
    
        file_path = self.file_path_edit.text().strip()
        if not file_path or not os.path.exists(file_path):
            QMessageBox.warning(self, tr('Validation Error'), tr('Please select a valid game script file first.'))
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
                QMessageBox.information(self, tr('Success'), f"Chapters mapped successfully!\n\n{message}")
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
                    QMessageBox.warning(self, tr('Failed'), f"Chapters mapping failed:\n{message}")

    @pyqtSlot()
    def _analyze_selected_chapter(self):
        """Generate AI overview for the selected chapters."""
        selected_items = self.table.selectedItems()
        selected_rows = sorted(list(set(item.row() for item in selected_items)))
        if not selected_rows:
            QMessageBox.warning(self, tr('No selection'), tr('Please select one or more chapters to analyze from the table.'))
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
                    QMessageBox.information(self, tr('Finished'), tr('All selected chapters successfully analyzed via AI!'))
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
                    QMessageBox.warning(self, tr('AI Error'), f"Chapter analysis failed:\n{message}")
                    self._finish_and_maybe_sleep()
            self.analysis_queue = []
            self.analysis_total_count = 0
            self.analysis_completed_count = 0

    @pyqtSlot()
    def _analyze_all_chapters(self):
        """Setup queue to analyze all chapters."""
        reply = QMessageBox.question(
            self, tr('Analyze All Chapters'),
            tr('This will analyze all chapters one by one using the AI provider. It may take several minutes.\n\nDo you want to proceed?'),
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
                QMessageBox.information(self, tr('Finished'), tr('No chapters found to analyze.'))
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
            QMessageBox.information(self, tr('Finished'), tr('All chapters successfully analyzed via AI!'))
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

