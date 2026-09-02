"""Hierarchy project / wizard-state mixin for MemePalaceBuilderDialog."""
import os
from PyQt6.QtWidgets import QFileDialog, QMessageBox, QTreeWidgetItem
from PyQt6.QtCore import pyqtSlot

from core.script_markup import (
    HierarchyImportStatus,
    HierarchyProjectError,
    hierarchy_import_status,
    load_hierarchy_project,
)
from utils.logging_utils import log_error
from ui.mempalace.mempalace_ui import set_workflow_enabled
from core.i18n import tr
from ui.mempalace.constants import (
    _HIERARCHY_HASH_KEY,
    _HIERARCHY_PATH_KEY,
    _HIERARCHY_VERSION_KEY,
)


class MemePalaceHierarchyMixin:
    """Browse/load hierarchy projects, wizard gating, and story-tree sync."""

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
                QMessageBox.warning(self, tr('Hierarchy project import error'), str(exc))
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
                tr('Run step 1 first: story events are attached to the lines it links.')
            )
            self.character_profiles_status_label.setText(
                tr("Run step 1 first: a character's voice is learned from their linked lines.")
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
                tr('Hierarchy project required'),
                tr('Select and validate a Markup Studio project first.'),
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
                tr('Hierarchy project import error'),
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
                tr('Import a Markup Studio project to build the tree.')
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

