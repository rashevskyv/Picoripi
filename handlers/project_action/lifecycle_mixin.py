import json
from pathlib import Path
from typing import Dict
from PyQt6.QtWidgets import QMessageBox, QFileDialog, QDialog
from core.project_manager import ProjectManager
from utils.logging_utils import log_info, log_debug, log_error
from core.i18n import tr


class LifecycleMixin:
    def create_new_project_action(self) -> None:
        """Create new project action."""
        from components.project_dialogs import NewProjectDialog
        log_info("Create New Project action triggered.")

        # Get available plugins
        plugins: Dict[str, str] = {}
        plugins_dir = Path("plugins")
        if plugins_dir.is_dir():
            for item_path in plugins_dir.iterdir():
                config_path = item_path / "config.json"
                if item_path.is_dir() and config_path.exists():
                    try:
                        with config_path.open('r', encoding='utf-8') as f:
                            config_data = json.load(f)
                        display_name = config_data.get("display_name", item_path.name)
                        plugins[display_name] = item_path.name
                    except Exception as e:
                        log_debug(f"Could not read config for plugin '{item_path.name}': {e}")

        dialog = NewProjectDialog(self.mw, available_plugins=plugins)
        if dialog.exec() != QDialog.DialogCode.Accepted:
            log_info("New project dialog cancelled.")
            return

        info = dialog.get_project_info()
        if not info:
            return

        # Create project using ProjectManager
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

        if success:
            project = self.mw.project_manager.project
            log_info(f"Project '{project.name}' created successfully at {info['directory']}.")

            # Update recent projects
            project_file = str(Path(info['directory']) / "project.uiproj")
            self.mw.last_opened_path = project_file
            if hasattr(self.mw, 'settings_manager'):
                self.mw.settings_manager.add_recent_project(project_file)
                self.mw.settings_manager.save_settings()
                self._update_recent_projects_menu()

            # Switch plugin if needed
            if info['plugin'] != self.mw.active_game_plugin:
                log_info(f"Switching plugin to '{info['plugin']}'")
                self.mw.active_game_plugin = info['plugin']
                self.mw.load_game_plugin()
                self.ui_updater.update_plugin_status_label()
            else:
                if hasattr(self.mw, 'translation_handler') and self.mw.translation_handler:
                    self.mw.translation_handler.initialize_glossary_highlighting()

            # Now sync with plugin awareness
            if self.mw.project_manager:
                self.mw.project_manager.sync_project_files(plugin=self.mw.current_game_rules)

            # Enable project-specific actions
            self._set_project_actions_enabled(True)
            if hasattr(self.mw, 'ui_handler'):
                self.mw.ui_handler.update_editor_rules_properties()

            # Update UI
            self.ui_updater.update_title()

            def on_created(state_restored):
                QMessageBox.information(
                    self.mw,
                    tr('Project Created'),
                    f"Project '{project.name}' has been created successfully."
                )
            self._populate_blocks_from_project(on_completed=on_created)
        else:
            QMessageBox.critical(self.mw, tr('Project Creation Failed'), tr('Failed to create project.'))

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

        if success:
            project = self.mw.project_manager.project
            log_info(f"Project '{project.name}' loaded successfully.")

            # Update recent projects
            if hasattr(self.mw, 'settings_manager'):
                self.mw.last_opened_path = project_path
                self.mw.settings_manager.add_recent_project(project_path)
                self.mw.settings_manager.save_settings(save_project_settings=False)
                self._update_recent_projects_menu()

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
                self.mw.project_manager.sync_project_files(plugin=self.mw.current_game_rules)

            # Enable project-specific actions
            self._set_project_actions_enabled(True)

            # Update UI
            self.ui_updater.update_title()

            def on_opened(state_restored):
                if hasattr(self.mw, 'bookmark_handler'):
                    self.mw.bookmark_handler.update_bookmarks_menu()
                log_info(f"Project '{project.name}' opened with {len(project.blocks)} blocks.")

            self._populate_blocks_from_project(on_completed=on_opened)
        else:
            QMessageBox.critical(
                self.mw,
                tr('Project Load Failed'),
                f"Failed to load project from:\n{project_path}"
            )

    def close_project_action(self) -> None:
        """Close project action."""
        log_info("Close Project action triggered.")

        # Cancel active pre-caching immediately
        if hasattr(self.ui_updater, 'preview_updater') and self.ui_updater.preview_updater:
            self.ui_updater.preview_updater.cancel_idle_caching()

        # Force save session before closing so current edits are saved in .picoripi_session
        if hasattr(self.data_processor, '_autosave_session'):
            self.data_processor._autosave_session(force=True)

        # Clear project
        if self.mw.project_manager:
            self.mw.project_manager.cleanup_temp_dir()
        self.mw.project_manager = None

        self.mw.data_store.json_path = None
        self.mw.data_store.edited_json_path = None
        self.mw.last_opened_path = ""

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

