from pathlib import Path
from typing import List
from PyQt6.QtWidgets import QMessageBox
from core.project_manager import ProjectManager
from utils.logging_utils import log_info
from core.i18n import tr


class RecentMixin:
    def _update_recent_projects_menu(self) -> None:
        """Update the Recent Projects submenu with current list."""
        if not hasattr(self.mw, 'recent_projects_menu'):
            return

        # Clear existing menu items
        self.mw.recent_projects_menu.clear()

        # Get recent projects list
        recent_projects: List[str] = getattr(self.mw, 'recent_projects', [])

        if not recent_projects:
            # Add "No recent projects" action
            no_recent_action = self.mw.recent_projects_menu.addAction(tr('No recent projects'))
            no_recent_action.setEnabled(False)
            return

        # Add action for each recent project
        for project_path in recent_projects:
            # Check if file exists
            p = Path(project_path)
            if p.exists():
                # Get project name from path
                project_name = p.stem
                if project_name == "project":
                    # Use directory name if file is named "project.uiproj"
                    project_name = p.parent.name

                action = self.mw.recent_projects_menu.addAction(project_name)
                action.setToolTip(project_path)
                # Use lambda with default argument to capture current project_path
                action.triggered.connect(lambda checked=False, path=project_path: self._open_recent_project(path))
            else:
                # Project file doesn't exist, show as unavailable
                action = self.mw.recent_projects_menu.addAction(f"{Path(project_path).name} (missing)")
                action.setEnabled(False)

        # Add separator and "Clear Recent Projects" action
        self.mw.recent_projects_menu.addSeparator()
        clear_action = self.mw.recent_projects_menu.addAction(tr('Clear Recent Projects'))
        clear_action.triggered.connect(self._clear_recent_projects)

    def _open_recent_project(self, project_path: str) -> None:
        """Open a project from the recent projects list."""
        log_info(f"Opening recent project: {project_path}")

        if not Path(project_path).exists():
            QMessageBox.critical(
                self.mw,
                tr('Project Not Found'),
                f"Project file not found:\n{project_path}\n\n"
                f"It may have been moved or deleted."
            )
            # Remove from recent projects
            if hasattr(self.mw, 'settings_manager'):
                self.mw.settings_manager.remove_recent_project(project_path)
                self.mw.settings_manager.save_settings()
                self._update_recent_projects_menu()
            return

        # Load project using ProjectManager
        self._report_startup(60, "Reading project metadata…")
        self.mw.project_manager = ProjectManager()

        success = self.mw.project_manager.load(project_path)

        if success:
            project = self.mw.project_manager.project
            log_info(f"Recent project '{project.name}' metadata loaded. Required plugin: '{project.plugin_name}'")

            # 1. Update global path tracking
            self.mw.last_opened_path = project_path
            if hasattr(self.mw, 'settings_manager'):
                self.mw.settings_manager.add_recent_project(project_path)
                self.mw.settings_manager.save_settings(save_project_settings=False)
                self._update_recent_projects_menu()

            # 2. FORCE correct plugin to load BEFORE any data parsing happens
            # Even if it's the same plugin, we reload it to ensure a clean state for this project
            target_plugin = project.plugin_name or self.mw.active_game_plugin
            log_info(f"Initializing project plugin: '{target_plugin}' (previous: '{self.mw.active_game_plugin}')")
            same_fresh_startup_plugin = (
                getattr(self.mw, '_startup_splash', None) is not None
                and target_plugin == self.mw.active_game_plugin
                and self.mw.current_game_rules is not None
            )
            self.mw.active_game_plugin = target_plugin
            if same_fresh_startup_plugin:
                log_info(f"Reusing freshly loaded startup plugin: '{target_plugin}'")
            else:
                self._report_startup(64, f"Loading {target_plugin} plugin…")
                self.mw.load_game_plugin() # SYNC CALL UPDATING current_game_rules
            self.ui_updater.update_plugin_status_label()

            # Load project-specific settings
            if hasattr(self.mw, 'settings_manager'):
                self.mw.settings_manager.plugin_settings.load(self.mw.settings_manager._settings)

            # 3. Restore last viewed state (block/string indices) from project metadata BEFORE populating UI
            self.mw.project_manager.load_settings_from_project(self.mw)
            if hasattr(self.mw, 'ui_handler'):
                self.mw.ui_handler.update_editor_rules_properties()
            if hasattr(self.mw, 'settings_manager'):
                self._report_startup(68, "Loading project fonts…")
                self.mw.settings_manager.load_all_font_maps()
            if hasattr(self.mw, 'string_settings_updater'):
                self.mw.string_settings_updater.update_font_combobox()

            # Fetch restored values for the timer
            restored_block = getattr(self.mw, 'last_block_idx', 0)
            restored_cat = getattr(self.mw, 'last_category_name', None)

            # 4. Enable project-related UI elements
            self._set_project_actions_enabled(True)

            # 5. Sync project files (extract archives, discover new blocks)
            self._report_startup(72, "Synchronizing project files…")
            self.mw.project_manager.sync_project_files(plugin=self.mw.current_game_rules)

            # 6. Populate UI components with the new project data
            self.ui_updater.update_title()

            def on_recent_opened(state_restored):
                if hasattr(self.mw, 'bookmark_handler'):
                    self.mw.bookmark_handler.update_bookmarks_menu()

                log_info(f"Project '{project.name}' open sequence complete. Total data blocks: {len(self.mw.data_store.data)}")

                if not state_restored:
                    log_info(f"Restoring UI state for block {restored_block}, category '{restored_cat}'")
                    self._pending_restore_block = restored_block
                    self._pending_restore_cat = restored_cat
                    self._finish_startup_after_restore_timer = (
                        getattr(self.mw, '_startup_splash', None) is not None
                    )
                    self._restore_view_timer.start(150)
                    if self._finish_startup_after_restore_timer:
                        return False

                return True

            self._report_startup(75, "Restoring cached project data…")
            self._populate_blocks_from_project(on_completed=on_recent_opened)
        else:
            QMessageBox.critical(
                self.mw,
                tr('Project Load Failed'),
                f"Failed to load project from:\n{project_path}"
            )

    def _on_restore_view_timer_timeout(self) -> None:
        """Handle deferred restore view safely."""
        self._restore_view_timer.stop()
        try:
            from PyQt6 import sip
            from PyQt6.QtCore import QObject
        except ImportError:
            import sip
            from PyQt6.QtCore import QObject

        try:
            if not self.mw or (isinstance(self.mw, QObject) and sip.isdeleted(self.mw)):
                return
        except (TypeError, RuntimeError):
            return

        restored_block = self._pending_restore_block
        restored_cat = self._pending_restore_cat
        self._pending_restore_cat = None

        try:
            is_deleted = sip.isdeleted(self.mw.block_list_widget)
        except (TypeError, ValueError, AttributeError, RuntimeError):
            is_deleted = False

        try:
            if hasattr(self.mw, 'block_list_widget') and not is_deleted:
                self.mw.block_list_widget.select_block_by_index(restored_block, restored_cat)

            # These calls refresh the string list and editors
            self.ui_updater.populate_strings_for_block(restored_block, restored_cat)
            self.ui_updater.update_statusbar_paths()
            self.ui_updater.update_plugin_status_label() # Ensure label is accurate
        finally:
            if self._finish_startup_after_restore_timer:
                self._finish_startup_after_restore_timer = False
                self._report_startup(99, "Finalizing the project view…")
                self.mw.finish_startup_loading()

    def _clear_recent_projects(self) -> None:
        """Clear all recent projects."""
        reply = QMessageBox.question(
            self.mw,
            tr('Clear Recent Projects'),
            tr('Are you sure you want to clear all recent projects?'),
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No
        )

        if reply == QMessageBox.StandardButton.Yes:
            if hasattr(self.mw, 'settings_manager'):
                self.mw.settings_manager.clear_recent_projects()
                self.mw.settings_manager.save_settings()
                self._update_recent_projects_menu()
            log_info("Recent projects cleared.")

