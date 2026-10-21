"""Project actions: create, open, close."""
from pathlib import Path
from typing import Dict
from PyQt6.QtWidgets import QMessageBox, QFileDialog
from core.project_library import build
from core.project_manager import ProjectManager
from utils.logging_utils import log_info, log_debug, log_error, log_warning
from core.i18n import tr


class LifecycleMixin:
    def create_new_project_action(self) -> None:
        """Ctrl+N and every New Project entry: the new-project wizard. The project is created by finish_new_project."""
        log_info("Create New Project action triggered.")
        self.open_new_project_wizard()

    def finish_new_project(self, info: Dict) -> None:
        """Create the project described by ``info`` and open it. Shared by the old dialog and the Project Manager wizard.

        ``info`` has the keys the Project Manager wizard passes and may add ``platform``, ``metadata`` (stored in the
        project's metadata and in the Project Manager's row) and ``entries_before`` (the names the project folder held
        before the create). All or nothing: the project becomes the last opened one only after it has opened. A create
        or an open that fails removes what the create made.
        """
        self.mw.project_manager = ProjectManager()

        success = self.mw.project_manager.create_new_project(
            project_dir=info['directory'],
            name=info['name'],
            plugin_name=info['plugin'],
            description=info['description'],
            source_path=info['source_path'],
            translation_path=info['translation_path'],
            is_directory_mode=info['is_directory_mode'],
            auto_create_translations=info['auto_create_translations']
        )
        self._close_font_editor_of_old_project()

        if not success:
            self._discard_new_project(info)
            QMessageBox.critical(self.mw, tr('Project Creation Failed'), tr('Failed to create project.'))
            return

        project = self.mw.project_manager.project
        if info.get('metadata'):
            project.metadata.update(info['metadata'])
            self.mw.project_manager.save()
        log_info(f"Project '{project.name}' created at {info['directory']}; opening it.")
        self._begin_open_dialog()   # shown at once: the file sync and the block load below take a while

        # Switch plugin if needed
        if info['plugin'] != self.mw.active_game_plugin:
            log_info(f"Switching plugin to '{info['plugin']}'")
            self.mw.active_game_plugin = info['plugin']
            self.mw.load_game_plugin()
            self.ui_updater.update_plugin_status_label()
        else:
            if hasattr(self.mw, 'translation_handler') and self.mw.translation_handler:
                self.mw.translation_handler.initialize_glossary_highlighting()

        project_file = str(Path(info['directory']) / "project.uiproj")

        def on_created(_state_restored):
            if self._populate_failed:
                self._abandon_new_project(info)
                return
            if info.get('icon_source'):
                self.copy_project_icon(info['directory'], info['icon_source'])
            self.note_project_opened(project_file, platform=info.get('platform', ''))
            self.record_project_counts()
            QMessageBox.information(
                self.mw,
                tr('Project Created'),
                tr("Project '{0}' has been created successfully.", project.name)
            )

        def created_synced():
            self._set_project_actions_enabled(True)
            if hasattr(self.mw, 'ui_handler'):
                self.mw.ui_handler.update_editor_rules_properties()
            self.ui_updater.update_title()
            self._register_opened(project_file, save_project_settings=True)   # undone by _abandon_new_project
            self._populate_blocks_from_project(on_completed=on_created)

        # Match the blocks with the files on disk on a worker (a big game has thousands), then load them.
        self._sync_project_files_then(created_synced)

    def _register_opened(self, project_file: str, save_project_settings: bool = False) -> None:
        """The project is the last one opened and in the recent list. A failed open undoes it (_forget_opened)."""
        self.mw.last_opened_path = project_file
        if hasattr(self.mw, 'settings_manager'):
            if project_file not in (getattr(self.mw, 'recent_projects', None) or []):
                self._added_to_recent.add(project_file)
            self.mw.settings_manager.add_recent_project(project_file)
            self.mw.settings_manager.save_settings(save_project_settings=save_project_settings)
            self._update_recent_projects_menu()

    def _forget_opened(self, project_file: str) -> None:
        """Undo _register_opened: not the last one any more; it leaves the recent list if this open added it."""
        if getattr(self.mw, 'last_opened_path', '') == project_file:
            self.mw.last_opened_path = ""
        if project_file in self._added_to_recent:
            self._added_to_recent.discard(project_file)
            if hasattr(self.mw, 'settings_manager'):
                self.mw.settings_manager.remove_recent_project(project_file)
                self.mw.settings_manager.save_settings(save_project_settings=False)
                self._update_recent_projects_menu()

    def _abandon_new_project(self, info: Dict) -> None:
        """A created project that did not open: close it, remove the files the create made, register nothing."""
        log_error(f"Project '{info['name']}' did not open after its create; its files are removed.")
        self.close_project_action()
        self._forget_opened(str(Path(info['directory']) / "project.uiproj"))
        self._discard_new_project(info)
        QMessageBox.critical(self.mw, tr('Project Creation Failed'),
                             tr('The project did not open, so it was removed. Its files were deleted.'))

    def _discard_new_project(self, info: Dict) -> None:
        """Remove what a create added to its folder. Needs ``entries_before``; without it nothing is removed."""
        if 'entries_before' not in info:
            log_warning(f"Project '{info.get('name', '')}' failed; its folder is kept (no record of what was made).")
            return
        try:
            build.remove_new_entries(info['directory'], info['entries_before'])
        except OSError as exc:
            log_error(f"Could not remove the files of the failed project in {info['directory']}: {exc}")

    def open_project_action(self) -> None:
        """Open project action."""
        log_info("Open Project action triggered.")

        # Open file dialog directly
        start_dir = str(Path.home())
        project_path, _ = QFileDialog.getOpenFileName(
            self.mw,
            "Open Project",
            start_dir,
            "Project Files (*.uiproj);;All Files (*)"
        )

        if not project_path:
            log_info("Open project cancelled.")
            return

        # Load project using ProjectManager
        self.mw.project_manager = ProjectManager()

        success = self.mw.project_manager.load(project_path)
        self._close_font_editor_of_old_project()

        if not success:
            QMessageBox.critical(
                self.mw,
                tr('Project Load Failed'),
                f"Failed to load project from:\n{project_path}"
            )
            return

        project = self.mw.project_manager.project
        log_info(f"Project '{project.name}' loaded; opening it.")
        self._begin_open_dialog()   # shown at once: the file sync and the block load below take a while

        # Switch plugin if needed
        if project.plugin_name and project.plugin_name != self.mw.active_game_plugin:
            log_info(f"Switching plugin to '{project.plugin_name}'")
            self.mw.active_game_plugin = project.plugin_name
            self.mw.load_game_plugin()
            self.ui_updater.update_plugin_status_label()
        else:
            if hasattr(self.mw, 'translation_handler') and self.mw.translation_handler:
                self.mw.translation_handler.initialize_glossary_highlighting()

        # Load project-specific settings
        if hasattr(self.mw, 'settings_manager'):
            self.mw.settings_manager.plugin_settings.load(self.mw.settings_manager._settings)

        # Load project-specific settings from metadata
        if self.mw.project_manager:
            self.mw.project_manager.load_settings_from_project(self.mw)
            if hasattr(self.mw, 'ui_handler'):
                self.mw.ui_handler.update_editor_rules_properties()
            if hasattr(self.mw, 'settings_manager'):
                self.mw.settings_manager.load_all_font_maps()
            if hasattr(self.mw, 'string_settings_updater'):
                self.mw.string_settings_updater.update_font_combobox()

        def on_opened(_state_restored):
            if self._populate_failed:
                self._project_open_failed(project_path, tr("The project files could not be read."))
                return
            self.note_project_opened(project_path)
            self.record_project_counts()
            if hasattr(self.mw, 'bookmark_handler'):
                self.mw.bookmark_handler.update_bookmarks_menu()
            log_info(f"Project '{project.name}' opened with {len(project.blocks)} blocks.")
            try:
                from core.companion_sync import smart_sync_in_background
                smart_sync_in_background(self.mw)
            except Exception as exc:
                log_debug(f"Failed to auto-sync companion on open: {exc}")

        def opened_synced():
            self._set_project_actions_enabled(True)
            self.ui_updater.update_title()
            self._register_opened(project_path)   # a failed open undoes it (_project_open_failed)
            self._populate_blocks_from_project(on_completed=on_opened)

        # Match the blocks with the files on disk on a worker (a big game has thousands), then load them.
        self._sync_project_files_then(opened_synced)

    def close_project_action(self) -> None:
        """Close project action."""
        log_info("Close Project action triggered.")

        # Cancel active pre-caching immediately
        if hasattr(self.ui_updater, 'preview_updater') and self.ui_updater.preview_updater:
            self.ui_updater.preview_updater.cancel_idle_caching()

        # Force save session before closing so current edits are saved in .picoripi_session
        if hasattr(self.data_processor, '_autosave_session'):
            self.data_processor._autosave_session(force=True)

        # Auto-push companion glossary before clearing project
        try:
            from core.companion_sync import sync_push_on_close
            sync_push_on_close(self.mw)
        except Exception as exc:
            log_debug(f"Failed to auto-push companion on project close: {exc}")

        self.record_project_counts()

        # Clear project
        if self.mw.project_manager:
            self.mw.project_manager.cleanup_temp_dir()
        self.mw.project_manager = None

        self.mw.data_store.json_path = None
        self.mw.data_store.edited_json_path = None
        self.mw.last_opened_path = ""

        self._close_font_editor_of_old_project()
        # Reset plugin
        self.mw.active_game_plugin = ""
        self.mw.load_game_plugin()

        # The glossary belongs to the project, so drop it when the project closes;
        # otherwise its terms would keep highlighting in the next project.
        if hasattr(self.mw, 'translation_handler') and self.mw.translation_handler:
            try:
                self.mw.translation_handler.initialize_glossary_highlighting()
            except Exception as exc:
                log_error(f"Failed to reset glossary on project close: {exc}")

        if hasattr(self.mw, 'settings_manager'):
            self.mw.settings_manager.set("last_opened_path", "")
            self.mw.settings_manager.set("active_game_plugin", "")
            self.mw.settings_manager.save_settings(save_project_settings=False)

        if hasattr(self.mw, 'bookmark_handler'):
            self.mw.bookmarks = []
            self.mw.bookmark_handler.update_bookmarks_menu()

        # Reset plugin settings to defaults
        if hasattr(self.mw, 'settings_manager'):
            self.mw.settings_manager.plugin_settings.load(self.mw.settings_manager._settings)

        # Clear UI
        self.mw.data_store.data = []
        self.mw.data_store.edited_data = {}
        self.mw.data_store.block_names = {}
        self.mw.data_store.current_block_idx = -1
        self.mw.data_store.current_string_idx = -1
        self.mw.data_store.unsaved_changes = False

        # Disable project-specific actions
        self._set_project_actions_enabled(False)

        # Update UI
        self.mw.block_list_widget.clear()
        self.ui_updater.populate_strings_for_block(-1)
        self.ui_updater.update_text_views()
        self.ui_updater.update_title()
        self.ui_updater.update_statusbar_paths()
        self.ui_updater.update_plugin_status_label()

        log_info("Project closed.")

