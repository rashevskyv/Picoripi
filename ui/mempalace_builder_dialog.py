import html
import os
import sqlite3
from PyQt6.QtWidgets import QDialog, QFileDialog, QMessageBox, QTableWidgetItem, QTreeWidgetItem
from PyQt6.QtCore import Qt, pyqtSlot

from core.mempalace_client import MemePalaceClient
from core.mempalace.dialogue_alignment import GameMessage
from core.mempalace.dialogue_mapping import DialogueMappingInput
from core.mempalace.dialogue_mapping_worker import DialogueAlignmentWorker
from core.mempalace.timeline_ai_analyzer import StoryTimelineAIAnalyzerWorker
from core.mempalace.normalized_character_profiler import NormalizedCharacterProfilerWorker
from core.script_markup import (
    HierarchyImportStatus,
    HierarchyProjectError,
    hierarchy_import_status,
    load_hierarchy_project,
)
from core.mempalace_worker import (
    MemePalaceScriptAnalyzerWorker, MemePalaceChapterMapperWorker, 
    MemePalaceChapterAIAnalyzerWorker, MemePalaceCharacterProfilerWorker
)
from utils.logging_utils import log_error

# Import decomposed elements
from ui.mempalace.mempalace_sleep import prevent_sleep, restore_sleep
from ui.mempalace.mempalace_ui import (
    MemePalaceBuilderUiMixin,
    SECONDARY_BUTTON_STYLE,
    WORKFLOW_BUTTON_STYLE,
    set_workflow_enabled,
)
from ui.mempalace.mempalace_pipeline import MemePalacePipelineMixin


_HIERARCHY_PATH_KEY = "mempalace_hierarchy_project_path"
_HIERARCHY_HASH_KEY = "mempalace_hierarchy_project_hash"
_HIERARCHY_VERSION_KEY = "mempalace_hierarchy_project_version"

class MemePalaceBuilderDialog(QDialog, MemePalaceBuilderUiMixin, MemePalacePipelineMixin):
    """Dialog class for meme palace builder."""

    def __init__(self, main_window, parent=None):
        """Initialize a new instance."""
        super().__init__(parent or main_window)
        self.mw = main_window
        self.setWindowTitle("MemPalace Context Builder")
        self.resize(1080, 800)
        self.setMinimumSize(900, 800)
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
        self.hierarchy_project = None
        self.imported_hierarchy_project_path = ""
        self.imported_hierarchy_project_hash = ""
        self.imported_hierarchy_project_version = None
        self.hierarchy_selection_error = ""
        self.story_document_id = None

        self._init_composer_and_client()
        self._setup_ui()
        self.load_builder_settings()
        self._load_active_markup_studio_project()
        
        # Auto-fill script path if empty
        if not self.file_path_edit.text().strip():
            script_path = self.composer._find_script_path() if self.composer else None
            if isinstance(script_path, str) and script_path:
                self.file_path_edit.setText(script_path)
                self.append_log(f"Auto-discovered game script file: {os.path.basename(script_path)}")
                
        self._refresh_wizard_state()

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

    @pyqtSlot()
    def _start_story_timeline_analysis(self):
        if self.worker and self.worker.isRunning():
            QMessageBox.information(self, "MemPalace", "Another MemPalace task is still running.")
            return
        if not self.story_document_id:
            QMessageBox.warning(self, "Timeline", "Import a marked Script Markup Studio project first.")
            return
        ai_provider = None
        if getattr(self.mw, "translation_handler", None):
            ai_provider = self.mw.translation_handler._prepare_provider()
        if not ai_provider:
            QMessageBox.warning(self, "Timeline", "Configure an AI provider before building the timeline.")
            return
        self.analyze_story_timeline_btn.setEnabled(False)
        self.story_timeline_progress.setVisible(True)
        self.story_timeline_progress.setRange(0, 0)
        self.story_timeline_status_label.setText("Analyzing marked dialogue…")
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
            QMessageBox.information(self, "Timeline Ready", message)
        else:
            QMessageBox.warning(self, "Timeline", message)

    @pyqtSlot()
    def _start_normalized_character_profiling(self):
        if self.worker and self.worker.isRunning():
            QMessageBox.information(self, "MemPalace", "Another MemPalace task is still running.")
            return
        if not self.story_document_id:
            QMessageBox.warning(self, "Characters", "Import a marked Script Markup Studio project first.")
            return
        ai_provider = None
        if getattr(self.mw, "translation_handler", None):
            ai_provider = self.mw.translation_handler._prepare_provider()
        if not ai_provider:
            QMessageBox.warning(self, "Characters", "Configure an AI provider before analyzing characters.")
            return
        self.analyze_character_voices_btn.setEnabled(False)
        self.character_profiles_progress.setVisible(True)
        self.character_profiles_progress.setRange(0, 0)
        self.character_profiles_status_label.setText("Analyzing character dialogue…")
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
            QMessageBox.information(self, "Character Voices Ready", message)
        else:
            QMessageBox.warning(self, "Characters", message)

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

    @pyqtSlot()
    def _browse_script_file(self):
        """Internal helper to browse script file."""
        path, _ = QFileDialog.getOpenFileName(
            self,
            "Select Legacy Game Script File",
            "",
            "Legacy Script Files (*.txt *.md);;Text Files (*.txt);;Markdown Files (*.md);;All Files (*)",
        )
        if path:
            self.file_path_edit.setText(path)
            self.append_log(f"Selected script file: {os.path.basename(path)}")

    @pyqtSlot()
    def _browse_hierarchy_project(self):
        """Select and validate a Markup Studio hierarchy project."""
        path, _ = QFileDialog.getOpenFileName(
            self,
            "Select Markup Studio Project",
            "",
            "Markup Studio Project (script_markup_project.json);;JSON Files (*.json)",
        )
        if path:
            self._load_hierarchy_project_preview(path, show_error=True)

    def _active_markup_studio_project_path(self) -> str:
        studio = getattr(self.mw, "script_markup_studio_dialog", None)
        live_path = getattr(studio, "current_hierarchy_project_path", "")
        if isinstance(live_path, str) and live_path and os.path.exists(live_path):
            return live_path
        shared_path = getattr(self.mw, "script_markup_studio_project_path", "")
        if isinstance(shared_path, str) and shared_path and os.path.exists(shared_path):
            return shared_path
        return ""

    def _load_active_markup_studio_project(self) -> bool:
        """Preview the live Markup Studio project without silently importing it."""
        path = self._active_markup_studio_project_path()
        if not path:
            return False
        current_path = getattr(self.hierarchy_project, "source_path", "")
        if current_path and os.path.normcase(current_path) == os.path.normcase(path):
            return True
        if not self._load_hierarchy_project_preview(path):
            return False
        self.append_log(
            f"Selected active Markup Studio project automatically: {os.path.basename(path)}"
        )
        return True

    def apply_saved_markup_studio_project(self, path: str) -> bool:
        """Synchronize a newly saved Studio snapshot and refresh existing matches."""
        if not path or not self._load_hierarchy_project_preview(path, show_error=True):
            return False
        previous_document_id = self.client.get_story_document_id(
            self.hierarchy_project.source_path
        )
        previous_state = (
            self.client.get_dialogue_mapping_state(previous_document_id)
            if previous_document_id is not None else None
        )
        if not self._import_sync_hierarchy_project():
            return False
        if previous_state is not None and previous_state.has_results:
            self._start_dialogue_node_mapping()
        else:
            self._refresh_main_story_folders()
            updater = getattr(self.mw, "string_settings_updater", None)
            if updater is not None:
                updater.update_string_settings_panel()
        return True

    def _load_hierarchy_project_preview(self, path: str, *, show_error: bool = False) -> bool:
        """Load a validated project and show its deterministic node summary."""
        try:
            project = load_hierarchy_project(path)
        except HierarchyProjectError as exc:
            self.hierarchy_selection_error = str(exc)
            retained = self.hierarchy_project is not None
            detail = str(exc)
            if retained:
                detail += " Previous valid project remains selected."
            self._set_hierarchy_project_status(HierarchyImportStatus.IMPORT_ERROR, detail)
            self.hierarchy_project_preview_label.setText(
                f"Import error: {exc}"
                + (" Previous valid project was not replaced." if retained else "")
            )
            self.hierarchy_project_preview_label.setStyleSheet("color: #a80000; font-size: 11px;")
            self._refresh_wizard_state()
            if show_error:
                QMessageBox.warning(self, "Hierarchy project import error", str(exc))
            return False

        self.hierarchy_project = project
        self.hierarchy_selection_error = ""
        self.hierarchy_project_path_edit.setText(project.source_path)
        if (
            project.raw_source_path
            and os.path.exists(project.raw_source_path)
            and not self.file_path_edit.text().strip()
        ):
            self.file_path_edit.setText(project.raw_source_path)
        self.hierarchy_project_import_btn.setEnabled(True)
        counts = project.node_counts()
        summary = (
            f"Validated v{project.version}: "
            f"Act {counts['act']}, Chapter {counts['chapter']}, Scene {counts['scene']}, "
            f"Speaker {counts['speaker']}, Dialogue {counts['dialogue']}, "
            f"Glossary {counts['glossary']}, Items {counts['item']}"
        )
        if counts["structure"]:
            summary += f", Other structure {counts['structure']}"
        if project.unapproved_marks:
            summary += f". Not approved (excluded): {len(project.unapproved_marks)}"
        self.hierarchy_project_preview_label.setText(summary)
        self.hierarchy_project_preview_label.setStyleSheet("color: #107c41; font-size: 11px;")
        self._update_hierarchy_project_status()
        self.append_log(
            f"Validated Markup Studio project: {os.path.basename(project.source_path)} "
            f"(SHA-256 {project.source_hash[:12]}...)"
        )
        return True

    def _set_hierarchy_project_status(
        self,
        status: HierarchyImportStatus,
        detail: str = "",
    ) -> None:
        colors = {
            HierarchyImportStatus.NOT_IMPORTED: "#666666",
            HierarchyImportStatus.UP_TO_DATE: "#107c41",
            HierarchyImportStatus.SOURCE_CHANGED: "#ca5010",
            HierarchyImportStatus.IMPORT_ERROR: "#a80000",
        }
        text = f"Status: {status.value}"
        if detail:
            text += f" — {detail}"
        self.hierarchy_project_status_label.setText(text)
        self.hierarchy_project_status_label.setStyleSheet(
            f"color: {colors[status]}; font-weight: bold;"
        )

    def _update_hierarchy_project_status(self) -> HierarchyImportStatus:
        status = hierarchy_import_status(
            self.hierarchy_project,
            imported_path=self.imported_hierarchy_project_path,
            imported_hash=self.imported_hierarchy_project_hash,
            imported_version=self.imported_hierarchy_project_version,
        )
        detail = ""
        if self.hierarchy_project is not None:
            if status == HierarchyImportStatus.UP_TO_DATE:
                detail = f"SHA-256 {self.hierarchy_project.source_hash[:12]}…"
            elif status == HierarchyImportStatus.SOURCE_CHANGED:
                detail = (
                    f"imported {self.imported_hierarchy_project_hash[:12]}…; "
                    f"current {self.hierarchy_project.source_hash[:12]}…"
                )
        self._set_hierarchy_project_status(status, detail)
        if hasattr(self, "workflow_tabs"):
            self._refresh_wizard_state()
        return status

    def _on_legacy_fallback_toggled(self, checked: bool) -> None:
        self.file_path_edit.setEnabled(checked)
        self.browse_btn.setEnabled(checked)
        self._refresh_wizard_state()

    def _source_is_ready(self) -> bool:
        wing_ready = bool(self.wing_edit.text().strip())
        imported_ready = self._current_hierarchy_status() == HierarchyImportStatus.UP_TO_DATE
        return wing_ready and imported_ready

    def _current_hierarchy_status(self) -> HierarchyImportStatus:
        return hierarchy_import_status(
            self.hierarchy_project,
            imported_path=self.imported_hierarchy_project_path,
            imported_hash=self.imported_hierarchy_project_hash,
            imported_version=self.imported_hierarchy_project_version,
        )

    def _dialogue_search_has_results(self) -> bool:
        """Whether step 1 has linked any game text to the script yet."""
        if self.story_document_id is None:
            return False
        try:
            return bool(
                self.client.get_dialogue_mapping_state(self.story_document_id).has_results
            )
        except Exception:
            return False

    def _refresh_wizard_state(self) -> None:
        if not hasattr(self, "workflow_tabs"):
            return
        source_ready = self._source_is_ready()
        context_found = self._dialogue_search_has_results()
        self.workflow_tabs.setTabEnabled(1, source_ready)
        set_workflow_enabled(self.source_next_btn, source_ready)

        # Steps 2 and 3 both read the links step 1 saves, so neither is a thing
        # the user can do until that search has produced some. Gating on the
        # imported document alone let all three sit there blue and unordered.
        busy = bool(self.worker and self.worker.isRunning())
        set_workflow_enabled(self.analyze_story_timeline_btn, context_found and not busy)
        set_workflow_enabled(self.analyze_character_voices_btn, context_found and not busy)
        if not context_found:
            self.story_timeline_status_label.setText(
                "Run step 1 first: story events are attached to the lines it links."
            )
            self.character_profiles_status_label.setText(
                "Run step 1 first: a character's voice is learned from their linked lines."
            )

        if not self.wing_edit.text().strip():
            message = "Enter a Wing name to continue."
        elif self.hierarchy_selection_error and source_ready:
            message = (
                "The new selection was rejected. The previous imported source remains ready."
            )
        elif self.hierarchy_selection_error:
            message = "The selected JSON is invalid. Choose another project file."
        elif self._current_hierarchy_status() == HierarchyImportStatus.UP_TO_DATE:
            message = "Source is ready. Continue to Story Context to link lines, then timeline and voices."
        elif self.hierarchy_project is not None:
            message = "Review the preview and click Import/Sync to continue."
        else:
            message = "Select a Markup Studio project to begin."
        self.source_readiness_label.setText(message)
        if self.hierarchy_selection_error:
            readiness_style = "color: #ca5010; font-weight: bold;"
        elif source_ready:
            readiness_style = "color: #107c41; font-weight: bold;"
        else:
            readiness_style = "color: #666666;"
        self.source_readiness_label.setStyleSheet(readiness_style)

        current = self.workflow_tabs.currentIndex()
        if current > 0 and not self.workflow_tabs.isTabEnabled(current):
            self.workflow_tabs.setCurrentIndex(0)

    def _go_to_wizard_step(self, index: int) -> None:
        if self.workflow_tabs.isTabEnabled(index):
            self.workflow_tabs.setCurrentIndex(index)

    def _refresh_main_story_folders(self) -> None:
        """Expose saved story changes immediately in the main project tree."""
        ui_updater = getattr(self.mw, "ui_updater", None)
        refresh = getattr(ui_updater, "refresh_mempalace_story_folders", None)
        if callable(refresh):
            refresh()

    @pyqtSlot()
    def _import_sync_hierarchy_project(self) -> bool:
        """Persist one validated source snapshot as the current import baseline."""
        if self.hierarchy_project is None:
            QMessageBox.warning(
                self,
                "Hierarchy project required",
                "Select and validate a Markup Studio project first.",
            )
            return False

        path = self.hierarchy_project.source_path
        if not self._load_hierarchy_project_preview(path, show_error=True):
            return False
        project = self.hierarchy_project
        try:
            sync_result = self.client.sync_story_timeline(project)
        except Exception as exc:
            log_error(f"Failed to synchronize hierarchy story timeline: {exc}", exc_info=True)
            self._set_hierarchy_project_status(HierarchyImportStatus.IMPORT_ERROR, str(exc))
            QMessageBox.warning(
                self,
                "Hierarchy project import error",
                f"The project was validated but could not be saved to MemPalace:\n{exc}",
            )
            return False
        self.story_document_id = sync_result.document_id
        self._invalidate_dialogue_review_cache()
        self._refresh_story_tree()
        self._restore_dialogue_mapping_state()
        self.imported_hierarchy_project_path = project.source_path
        self.imported_hierarchy_project_hash = project.source_hash
        self.imported_hierarchy_project_version = project.version

        sm = getattr(self.mw, "settings_manager", None)
        if sm:
            sm.set(_HIERARCHY_PATH_KEY, project.source_path)
            sm.set(_HIERARCHY_HASH_KEY, project.source_hash)
            sm.set(_HIERARCHY_VERSION_KEY, project.version)
            sm.save_settings()

        self._update_hierarchy_project_status()
        self.append_log(
            f"Imported Markup Studio story timeline: {sync_result.inserted_or_updated} nodes "
            f"({sync_result.removed} removed), v{project.version}, "
            f"{sync_result.reference_items} reference items "
            f"({sync_result.reference_items_removed} removed), "
            f"SHA-256 {project.source_hash[:12]}..."
        )
        self._refresh_main_story_folders()
        return True

    def _refresh_story_tree(self) -> None:
        if not hasattr(self, "story_tree"):
            return
        self.story_tree.clear()
        if self.story_document_id is None:
            self.story_tree_status_label.setText(
                "Import a Markup Studio project to build the tree."
            )
            self.story_tree_status_label.setStyleSheet("color: #666666;")
            return
        nodes = self.client.get_story_timeline(self.story_document_id)
        if hasattr(self, "story_timeline_status_label"):
            analyzed_events = self.client.get_story_events(self.story_document_id)
            if analyzed_events:
                self.story_timeline_status_label.setText(
                    f"Timeline ready: {len(analyzed_events)} story events."
                )
                self.story_timeline_status_label.setStyleSheet("color: #137333;")
        if hasattr(self, "character_profiles_status_label"):
            profiles = self.client.get_character_profiles(self.story_document_id)
            if profiles:
                self.character_profiles_status_label.setText(
                    f"Character voices ready: {len(profiles)} profiles."
                )
                self.character_profiles_status_label.setStyleSheet("color: #137333;")
        reference_items = self.client.get_reference_items(self.story_document_id)
        items = {}
        for node in nodes:
            content = node.title or node.text or "(empty)"
            line_range = ""
            if node.start_line is not None:
                start = node.start_line + 1
                end = (node.end_line if node.end_line is not None else node.start_line) + 1
                line_range = str(start) if start == end else f"{start}–{end}"
            item = QTreeWidgetItem([
                node.node_type.replace("_", " ").title(),
                content,
                line_range,
            ])
            parent = items.get(node.parent_id)
            if parent is None:
                self.story_tree.addTopLevelItem(item)
            else:
                parent.addChild(item)
            items[node.id] = item
        if reference_items:
            reference_group = QTreeWidgetItem([
                "Reference Items",
                f"{len(reference_items)} items",
                "",
            ])
            self.story_tree.addTopLevelItem(reference_group)
            for reference in reference_items:
                line_range = ""
                if reference.start_line is not None:
                    start = reference.start_line + 1
                    end = (
                        reference.end_line
                        if reference.end_line is not None
                        else reference.start_line
                    ) + 1
                    line_range = str(start) if start == end else f"{start}–{end}"
                item_node = QTreeWidgetItem(["Item", reference.name or "(empty)", line_range])
                reference_group.addChild(item_node)
                if reference.description:
                    item_node.addChild(QTreeWidgetItem([
                        "Item Description",
                        " ".join(reference.description.split()),
                        line_range,
                    ]))
        self.story_tree.expandToDepth(2)
        self.story_tree_status_label.setText(
            f"Imported {len(nodes)} story nodes and {len(reference_items)} reference items "
            "from the validated Markup Studio project."
        )
        self.story_tree_status_label.setStyleSheet("color: #107c41; font-weight: bold;")
        self.match_dialogue_btn.setEnabled(bool(getattr(self.mw.data_store, "data", None)))

    def _game_messages_for_story_alignment(self, data) -> list[GameMessage]:
        """Build alignment inputs while honoring plugin window-type exclusions."""
        game_messages = []
        store = getattr(self.mw, "data_store", None)
        block_names = getattr(store, "block_names", {}) or {}
        rules = getattr(self.mw, "current_game_rules", None)
        eligible = getattr(rules, "should_auto_match_story_context", None)
        for block_index, block in enumerate(data):
            if not isinstance(block, list):
                continue
            try:
                block_name = str(self.composer._get_block_label(block_index))
            except Exception:
                block_name = str(
                    block_names.get(
                        str(block_index),
                        block_names.get(block_index, f"Block_{block_index}"),
                    )
                )
            for string_index, value in enumerate(block):
                text = str(value or "")
                if not text.strip():
                    continue
                if callable(eligible):
                    try:
                        if eligible(block_index, string_index) is False:
                            continue
                    except Exception:
                        pass
                game_messages.append(GameMessage(
                    message_id=len(game_messages),
                    block_id=str(block_index),
                    block_name=block_name,
                    string_index=string_index,
                    stable_id=f"{block_name}_Str_{string_index}",
                    text=text,
                ))
        return game_messages

    @pyqtSlot()
    def _start_dialogue_node_mapping(self) -> None:
        if self.story_document_id is None:
            QMessageBox.warning(
                self,
                "Story tree required",
                "Import a Markup Studio Project before matching game strings.",
            )
            return
        store = getattr(self.mw, "data_store", None)
        data = getattr(store, "data", None)
        if not isinstance(data, list) or not data:
            QMessageBox.warning(self, "Open project required", "Open a game project first.")
            return
        game_messages = self._game_messages_for_story_alignment(data)
        if not game_messages:
            QMessageBox.information(
                self, "Nothing to match", "The open project has no eligible dialogue strings."
            )
            return

        self.match_dialogue_btn.setEnabled(False)
        self.dialogue_mapping_progress.setRange(0, 0)
        self.dialogue_mapping_progress.setVisible(True)
        self.dialogue_mapping_summary_label.setText(
            "Aligning marked dialogue with the open game project…"
        )
        self.worker = DialogueAlignmentWorker(
            self.client,
            self.story_document_id,
            game_messages,
            parent=self,
        )
        self.worker.completed.connect(self._handle_dialogue_mapping_completed)
        self.worker.finished.connect(self.worker.deleteLater)
        self.worker.start()

    @pyqtSlot(int, int)
    def _handle_dialogue_mapping_progress(self, current: int, total: int) -> None:
        self.dialogue_mapping_progress.setRange(0, total)
        self.dialogue_mapping_progress.setValue(current)

    @pyqtSlot(bool, object, str)
    def _handle_dialogue_mapping_completed(self, success: bool, summary, error: str) -> None:
        self.worker = None
        self.dialogue_mapping_progress.setVisible(False)
        self.match_dialogue_btn.setEnabled(True)
        if not success:
            self.dialogue_mapping_summary_label.setText(error or "Matching stopped.")
            self.dialogue_mapping_summary_label.setStyleSheet("color: #a80000;")
            if error and "cancelled" not in error.lower():
                QMessageBox.warning(self, "Dialogue matching failed", error)
            return
        spoken = summary["spoken_only"]
        coverage = spoken["supported_relation_coverage"]
        review_count = len(self.client.get_dialogue_mappings(
            self.story_document_id, review_status="needs_review"
        ))
        self.dialogue_mapping_summary_label.setText(
            f"Marked dialogue coverage: {coverage:.1f}% "
            f"({spoken['confident_tokens']} directly confirmed tokens; "
            f"{spoken['recoverable_tokens']} found with candidates). "
            f"Saved context links: {summary.get('saved_relations', 0)}. "
            f"Need your decision: {review_count}. "
            f"Stage directions kept separate: {summary['stage_direction_nodes']}. "
            f"Tag meanings inferred: {len(summary['inferred_tag_equivalents'])}."
        )
        color = "#107c41" if coverage >= 95.0 else "#a15c00"
        self.dialogue_mapping_summary_label.setStyleSheet(
            f"color: {color}; font-weight: bold;"
        )
        self._refresh_dialogue_review_table()
        self._set_saved_dialogue_search_actions(review_count == 0)
        self._refresh_main_story_folders()
        updater = getattr(self.mw, "string_settings_updater", None)
        if updater is not None:
            updater.update_string_settings_panel()

    def _set_saved_dialogue_search_actions(self, complete: bool) -> None:
        """Make rerunning secondary once durable search results exist."""
        self.match_dialogue_btn.setText("Recheck After Changes")
        self.match_dialogue_btn.setStyleSheet(SECONDARY_BUTTON_STYLE)
        self.story_context_done_btn.setVisible(complete)
        if complete:
            self.story_context_completion_label.setText(
                "All context decisions are saved. These links are already available to AI "
                "translation; rerun the search only after the script or game text changes."
            )

    def _restore_dialogue_mapping_state(self) -> None:
        """Restore persisted context-search status when Builder is reopened."""
        if self.story_document_id is None:
            return
        state = self.client.get_dialogue_mapping_state(self.story_document_id)
        if not state.has_results:
            self.match_dialogue_btn.setText("Find Context Automatically")
            self.match_dialogue_btn.setStyleSheet(WORKFLOW_BUTTON_STYLE)
            self.story_context_done_btn.setVisible(False)
            return
        self._refresh_dialogue_review_table()
        if state.needs_review:
            self.dialogue_mapping_summary_label.setText(
                f"Saved search restored: {state.automatic} automatically matched; "
                f"{state.reviewed} reviewed; {state.context_links} active context links. "
                f"Need your decision: {state.needs_review}."
            )
            self.dialogue_mapping_summary_label.setStyleSheet(
                "color: #a15c00; font-weight: bold;"
            )
        else:
            self.dialogue_mapping_summary_label.setText(
                f"Story context is ready. Saved results: {state.automatic} automatically "
                f"matched; {state.reviewed} reviewed; "
                f"{state.context_links} active context links."
            )
            self.dialogue_mapping_summary_label.setStyleSheet(
                "color: #107c41; font-weight: bold;"
            )
        self._set_saved_dialogue_search_actions(state.is_complete)

    def _invalidate_dialogue_review_cache(self) -> None:
        self._dialogue_review_cache_document_id = None
        self._dialogue_review_nodes = {}
        self._dialogue_review_dialogues = ()
        self._dialogue_review_index_by_id = {}

    def _ensure_dialogue_review_cache(self):
        if (
            getattr(self, "_dialogue_review_cache_document_id", None)
            == self.story_document_id
        ):
            return self._dialogue_review_nodes
        timeline = self.client.get_story_timeline(self.story_document_id)
        nodes = {node.id: node for node in timeline}
        dialogues = tuple(node for node in timeline if node.node_type == "dialogue")
        self._dialogue_review_cache_document_id = self.story_document_id
        self._dialogue_review_nodes = nodes
        self._dialogue_review_dialogues = dialogues
        self._dialogue_review_index_by_id = {
            node.id: index for index, node in enumerate(dialogues)
        }

        self.mapping_dialogue_combo.blockSignals(True)
        self.mapping_dialogue_combo.clear()
        for node in dialogues:
            speaker, path = self._dialogue_metadata(node, nodes)
            line = node.start_line + 1 if node.start_line is not None else "?"
            text = " ".join((node.text or "(empty dialogue)").split())
            if len(text) > 110:
                text = text[:107] + "…"
            details = " › ".join(path)
            label = f"Line {line} · {speaker}: {text}"
            if details:
                label += f" · {details}"
            self.mapping_dialogue_combo.addItem(label, node.id)
        self.mapping_dialogue_combo.setCurrentIndex(-1)
        self.mapping_dialogue_combo.setEditText("")
        self.mapping_dialogue_combo.blockSignals(False)
        return nodes

    @staticmethod
    def _short_story_node_text(node) -> str:
        value = node.title or node.text or node.node_type.replace("_", " ").title()
        return value.splitlines()[0].strip()

    def _dialogue_metadata(self, dialogue, nodes) -> tuple[str, tuple[str, ...]]:
        speaker = "Unknown speaker"
        structural = []
        current = dialogue
        visited = set()
        while current is not None and current.id not in visited:
            visited.add(current.id)
            if current.node_type == "speaker":
                speaker = self._short_story_node_text(current)
            elif current.node_type in {"act", "chapter", "scene"}:
                structural.append(self._short_story_node_text(current))
            current = nodes.get(current.parent_id)
        structural.reverse()
        return speaker, tuple(structural)

    def _set_dialogue_candidate(self, candidate) -> None:
        if candidate is None:
            self._current_candidate_node_id = None
            self.mapping_review_candidate_label.setText("No reliable script place selected")
            self.mapping_review_location_label.setText(
                "Choose a marked line below to compare its surrounding dialogue."
            )
            self.mapping_context_preview.setHtml(
                "<p><b>No context selected.</b></p>"
                "<p>The program could not prove which repeated occurrence is correct. "
                "It has not selected the first occurrence automatically.</p>"
            )
            self.approve_mapping_btn.setEnabled(False)
            self.open_mapping_in_studio_btn.setEnabled(False)
            return

        nodes = self._dialogue_review_nodes
        speaker, path = self._dialogue_metadata(candidate, nodes)
        self._current_candidate_node_id = candidate.id
        self.mapping_review_candidate_label.setText(
            candidate.text or candidate.title or "(empty script line)"
        )
        location_parts = [*path, f"Speaker: {speaker}"]
        if candidate.start_line is not None:
            location_parts.append(f"source line {candidate.start_line + 1}")
        self.mapping_review_location_label.setText(
            "Location: " + " › ".join(location_parts)
        )

        index = self._dialogue_review_index_by_id.get(candidate.id)
        if index is None:
            nearby = (candidate,)
        else:
            nearby = self._dialogue_review_dialogues[
                max(0, index - 2):min(len(self._dialogue_review_dialogues), index + 3)
            ]
        rows = []
        for node in nearby:
            row_speaker, _row_path = self._dialogue_metadata(node, nodes)
            selected = node.id == candidate.id
            background = "#dff0ff" if selected else "transparent"
            marker = "▶ " if selected else ""
            line = node.start_line + 1 if node.start_line is not None else "?"
            text = html.escape(node.text or "(empty dialogue)").replace("\n", "<br>")
            rows.append(
                f'<div style="background:{background}; padding:6px; margin:2px 0;">'
                f'<b>{marker}{html.escape(row_speaker)}</b> '
                f'<span style="color:#666;">(line {line})</span><br>{text}</div>'
            )
        self.mapping_context_preview.setHtml("".join(rows))
        self.approve_mapping_btn.setEnabled(True)
        self.open_mapping_in_studio_btn.setEnabled(candidate.start_line is not None)

    def _refresh_dialogue_review_table(self) -> None:
        if self.story_document_id is None:
            return
        mappings = [
            *self.client.get_dialogue_mappings(
                self.story_document_id, review_status="needs_review"
            ),
        ]
        nodes = self._ensure_dialogue_review_cache()
        self._review_mappings = mappings
        current_index = min(
            getattr(self, "_current_review_index", 0),
            max(0, len(mappings) - 1),
        )
        self._current_review_index = current_index
        self.mapping_review_actions.setVisible(bool(mappings))
        self.story_context_completion_label.setVisible(not mappings)
        self.mapping_review_table.setVisible(False)
        if mappings:
            self._show_dialogue_review(current_index, nodes=nodes)
        else:
            self.approve_mapping_btn.setEnabled(False)
            self.open_mapping_in_studio_btn.setEnabled(False)
            self.mapping_dialogue_choice_widget.setVisible(False)

    def _show_dialogue_review(self, index: int, *, nodes=None) -> None:
        mappings = getattr(self, "_review_mappings", [])
        if not mappings:
            self.approve_mapping_btn.setEnabled(False)
            return
        index = max(0, min(index, len(mappings) - 1))
        self._current_review_index = index
        mapping = mappings[index]
        if nodes is None:
            nodes = self._ensure_dialogue_review_cache()
        candidate = nodes.get(mapping.dialogue_node_id)
        self.mapping_review_counter_label.setText(
            f"Decision {index + 1} of {len(mappings)}"
        )
        self.mapping_review_source_label.setText(mapping.source_text_snapshot or "(empty text)")
        self.mapping_review_explanation_label.setText(
            "The text is similar to this marked line, but the match is not certain."
            if candidate is not None
            else "This text appears in more than one marked place, and its neighbors did not "
                 "prove which occurrence is correct."
        )
        if mapping.dialogue_node_id is not None:
            combo_index = self.mapping_dialogue_combo.findData(mapping.dialogue_node_id)
            if combo_index >= 0:
                self.mapping_dialogue_combo.setCurrentIndex(combo_index)
        else:
            self.mapping_dialogue_combo.setCurrentIndex(-1)
            self.mapping_dialogue_combo.setEditText("")
        self.mapping_dialogue_choice_widget.setVisible(False)
        self._set_dialogue_candidate(candidate)
        self.mapping_review_previous_btn.setEnabled(index > 0)
        self.mapping_review_next_btn.setEnabled(index + 1 < len(mappings))

    @pyqtSlot(int)
    def _on_dialogue_choice_changed(self, _index: int) -> None:
        if not getattr(self, "_review_mappings", []):
            return
        node_id = self.mapping_dialogue_combo.currentData()
        if not isinstance(node_id, int):
            self._set_dialogue_candidate(None)
            return
        nodes = self._ensure_dialogue_review_cache()
        candidate = nodes.get(node_id)
        self._set_dialogue_candidate(candidate)

    @pyqtSlot()
    def _show_dialogue_candidate_picker(self) -> None:
        self.mapping_dialogue_choice_widget.setVisible(True)
        if self.mapping_dialogue_combo.currentIndex() < 0:
            mappings = getattr(self, "_review_mappings", [])
            index = getattr(self, "_current_review_index", 0)
            if 0 <= index < len(mappings):
                self.mapping_dialogue_combo.setEditText(
                    mappings[index].source_text_snapshot
                )
        self.mapping_dialogue_combo.setFocus()
        if self.mapping_dialogue_combo.lineEdit() is not None:
            self.mapping_dialogue_combo.lineEdit().selectAll()
        self.mapping_dialogue_combo.completer().complete()

    @pyqtSlot()
    def _open_current_dialogue_in_markup_studio(self) -> None:
        node_id = getattr(self, "_current_candidate_node_id", None)
        node = self._dialogue_review_nodes.get(node_id)
        if node is None or node.start_line is None:
            QMessageBox.information(
                self,
                "Choose a script place",
                "Choose a marked script line before opening Markup Studio.",
            )
            return
        actions = getattr(self.mw, "actions", None)
        open_studio = getattr(actions, "open_script_markup_studio", None)
        if not callable(open_studio):
            QMessageBox.warning(
                self, "Markup Studio unavailable", "Could not open Script Markup Studio."
            )
            return
        open_studio()
        studio = getattr(self.mw, "script_markup_studio_dialog", None)
        navigate = getattr(studio, "open_hierarchy_project_at_line", None)
        project_path = self.hierarchy_project_path_edit.text().strip()
        if studio is None or not callable(navigate) or not navigate(
            project_path, node.start_line
        ):
            QMessageBox.warning(
                self,
                "Could not show script line",
                "Markup Studio opened, but the selected source line could not be shown.",
            )
            return
        studio.show()
        studio.raise_()
        studio.activateWindow()

    @pyqtSlot()
    def _show_previous_dialogue_review(self) -> None:
        self._show_dialogue_review(getattr(self, "_current_review_index", 0) - 1)

    @pyqtSlot()
    def _show_next_dialogue_review(self) -> None:
        self._show_dialogue_review(getattr(self, "_current_review_index", 0) + 1)

    @pyqtSlot(bool)
    def _toggle_story_structure(self, checked: bool) -> None:
        self.story_group.setVisible(checked)
        if checked:
            self.chapters_splitter.setSizes(
                getattr(self, "_saved_chapters_splitter_sizes", [390, 260])
            )
        self.toggle_story_btn.setText(
            "Hide imported structure" if checked else "Show imported structure"
        )

    @pyqtSlot()
    def _approve_selected_dialogue_mapping(self) -> None:
        mappings = getattr(self, "_review_mappings", [])
        index = getattr(self, "_current_review_index", 0)
        if index < 0 or index >= len(mappings):
            return
        dialogue_node_id = self.mapping_dialogue_combo.currentData()
        if not isinstance(dialogue_node_id, int):
            return
        mapping = mappings[index]
        self.client.upsert_dialogue_mapping(
            DialogueMappingInput(
                document_id=mapping.document_id,
                game_block_id=mapping.game_block_id,
                game_block_name=mapping.game_block_name,
                string_index=mapping.string_index,
                game_string_id=mapping.game_string_id,
                source_text_snapshot=mapping.source_text_snapshot,
                dialogue_node_id=dialogue_node_id,
                match_method="manual",
                confidence=1.0,
                review_status="approved",
                reviewed_by="user",
                locked=True,
            ),
            allow_locked_override=True,
        )
        self.client.lock_dialogue_relation_choice(
            mapping.document_id,
            mapping.game_block_id,
            mapping.string_index,
            dialogue_node_id,
        )
        self._restore_dialogue_mapping_state()
        self._refresh_main_story_folders()

    @pyqtSlot()
    def _reject_selected_dialogue_mapping(self) -> None:
        mappings = getattr(self, "_review_mappings", [])
        index = getattr(self, "_current_review_index", 0)
        if index < 0 or index >= len(mappings):
            return
        mapping = mappings[index]
        self.client.upsert_dialogue_mapping(
            DialogueMappingInput(
                document_id=mapping.document_id,
                game_block_id=mapping.game_block_id,
                game_block_name=mapping.game_block_name,
                string_index=mapping.string_index,
                game_string_id=mapping.game_string_id,
                source_text_snapshot=mapping.source_text_snapshot,
                dialogue_node_id=None,
                match_method="manual",
                confidence=1.0,
                review_status="rejected",
                reviewed_by="user",
                locked=True,
            ),
            allow_locked_override=True,
        )
        self.client.lock_dialogue_relation_choice(
            mapping.document_id,
            mapping.game_block_id,
            mapping.string_index,
            None,
        )
        self._restore_dialogue_mapping_state()
        self._refresh_main_story_folders()

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
        if self.worker and self.worker.isRunning():
            reply = QMessageBox.question(
                self,
                "Stop current AI operation?",
                "The current request will stop after the active network step. Are you sure you want to continue?",
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
                "Stop current AI operation and close the builder?",
                "The current request will stop after the active network step. Are you sure you want to continue?",
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
