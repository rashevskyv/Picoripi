"""Create/load/save and project settings persistence for ProjectManager."""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Optional, Union

from utils.logging_utils import log_info, log_warning, log_error, log_debug

from core.project_models import Project


class PersistMixin:
    """Create/load/save, settings to/from project, bookmark migrate."""

    def create_new_project(self, project_dir: Union[str, Path], name: str, plugin_name: str, description: str = "",
                           source_path: str = "", translation_path: Optional[str] = None,
                           is_directory_mode: bool = True, auto_create_translations: bool = False) -> bool:
        """
        Create a new project structure on disk.

        Args:
            project_dir: Directory where project file will be created
            name: Project name
            plugin_name: Active game plugin
            description: Optional project description
            source_path: External source file or directory
            translation_path: External translation file or directory (optional if auto_create is True)
            is_directory_mode: True if source_path/translation_path are directories
            auto_create_translations: True to auto-create missing translation files

        Returns:
            True if successful, False otherwise
        """
        try:
            # Create project directory
            project_path = Path(project_dir)
            project_path.mkdir(parents=True, exist_ok=True)

            # Create project metadata
            from datetime import datetime
            now = datetime.now().isoformat()

            self.project = Project(
                name=name,
                description=description,
                plugin_name=plugin_name,
                created_at=now,
                modified_at=now
            )
            
            # Store external path settings
            self.project.metadata['source_path'] = source_path
            self.project.metadata['translation_path'] = translation_path
            self.project.metadata['is_directory_mode'] = is_directory_mode
            self.project.metadata['auto_create_translations'] = auto_create_translations

            self.project_dir = str(project_path)
            self.project_file_path = str(project_path / self.PROJECT_FILE_NAME)

            # Save project file
            self.save()

            log_info(f"Created new project '{name}' at {project_dir}")
            return True

        except Exception as e:
            log_error(f"Failed to create project: {e}", exc_info=True)
            return False

    def load(self, path: Union[str, Path]) -> bool:
        """
        Load a project from disk.

        Args:
            path: Path to project directory or .uiproj file

        Returns:
            True if successful, False otherwise
        """
        try:
            path_obj = Path(path)

            # Determine if path is directory or file
            if path_obj.is_dir():
                self.project_dir = str(path_obj)
                self.project_file_path = str(path_obj / self.PROJECT_FILE_NAME)
            elif path_obj.is_file() and path_obj.name.endswith('.uiproj'):
                self.project_dir = str(path_obj.parent)
                self.project_file_path = str(path_obj)
            else:
                log_error(f"Invalid project path: {path}")
                return False

            # Load project file
            p_file = Path(self.project_file_path)
            if not p_file.exists():
                log_error(f"Project file not found: {self.project_file_path}")
                return False

            with p_file.open('r', encoding='utf-8') as f:
                data = json.load(f)

            self.project = Project.from_dict(data)
            
            # Migration: if no virtual folders exist (or version < 1.1 or virtual folders are empty of blocks), create them from file structure
            def has_any_blocks(folders) -> bool:
                for f in folders:
                    if f.block_ids:
                        return True
                    if has_any_blocks(f.children):
                        return True
                return False

            if (self.project.version < "1.1" or not self.project.virtual_folders or not has_any_blocks(self.project.virtual_folders)) and self.project.blocks:
                self._migrate_file_structure_to_virtual_folders()

            log_info(f"Loaded project '{self.project.name}' from {self.project_dir}")
            return True

        except Exception as e:
            log_error(f"Failed to load project: {e}", exc_info=True)
            return False

    def save(self) -> bool:
        """
        Save the current project to disk.

        Returns:
            True if successful, False otherwise
        """
        if not self.project or not self.project_file_path:
            log_warning("No project to save")
            return False

        try:
            # Update modification time
            from datetime import datetime
            self.project.modified_at = datetime.now().isoformat()

            # Save project file
            p_file = Path(self.project_file_path)
            with p_file.open('w', encoding='utf-8') as f:
                json.dump(self.project.to_dict(), f, indent=4, ensure_ascii=False)

            log_debug(f"Saved project '{self.project.name}' to {self.project_file_path}")
            return True

        except Exception as e:
            log_error(f"Failed to save project: {e}", exc_info=True)
            return False

    def save_settings_to_project(self, main_window: Any) -> bool:
        """
        Save project-specific settings from MainWindow to project.metadata.

        Args:
            main_window: MainWindow instance with settings to save

        Returns:
            True if successful, False otherwise
        """
        if not self.project:
            log_warning("No project to save settings to")
            return False

        try:
            # Save each project-specific setting to metadata
            settings_saved = {}
            for setting_name in self.PROJECT_SETTINGS:
                if hasattr(main_window, setting_name):
                    value = getattr(main_window, setting_name)
                    settings_saved[setting_name] = value

            self.project.metadata['settings'] = settings_saved
            log_info(f"Saved {len(settings_saved)} project settings to metadata")

            # Save project to disk
            return self.save()

        except Exception as e:
            log_error(f"Failed to save settings to project: {e}", exc_info=True)
            return False

    def load_settings_from_project(self, main_window: Any) -> bool:
        """
        Load project-specific settings from project.metadata to MainWindow.

        Args:
            main_window: MainWindow instance to apply settings to

        Returns:
            True if successful, False otherwise
        """
        if not self.project:
            log_warning("No project to load settings from")
            return False

        try:
            settings = self.project.metadata.get('settings', {})
            if not settings:
                log_info("No project settings found in metadata, using current settings")
                self._maybe_migrate_legacy_bookmarks(main_window)
                return False

            # Apply each project-specific setting to MainWindow
            settings_loaded = 0
            for setting_name, value in settings.items():
                if setting_name == 'default_tag_mappings':
                    if isinstance(value, dict):
                        if not hasattr(main_window, 'default_tag_mappings') or not main_window.default_tag_mappings:
                            main_window.default_tag_mappings = {}
                        main_window.default_tag_mappings.update(value)
                        settings_loaded += 1
                else:
                    if hasattr(main_window, setting_name):
                        setattr(main_window, setting_name, value)
                        settings_loaded += 1

            log_info(f"Loaded {settings_loaded} project settings from metadata")
            self._maybe_migrate_legacy_bookmarks(main_window)
            return True

        except Exception as e:
            log_error(f"Failed to load settings from project: {e}", exc_info=True)
            return False

    def _maybe_migrate_legacy_bookmarks(self, main_window: Any) -> None:
        """Copy this project's leftover global bookmarks into the .uiproj once."""
        if not self.project:
            return
        settings = self.project.metadata.get('settings', {})
        if not isinstance(settings, dict):
            settings = {}
        if 'bookmarks' in settings:
            if not isinstance(getattr(main_window, 'bookmarks', None), list):
                main_window.bookmarks = settings.get('bookmarks') or []
            return

        matching = []
        path = getattr(getattr(main_window, 'settings_manager', None), 'settings_file_path', None)
        if path:
            try:
                with open(path, 'r', encoding='utf-8') as handle:
                    data = json.load(handle)
                legacy = data.get('bookmarks')
                if isinstance(legacy, list):
                    name = self.project.name
                    matching = [
                        item for item in legacy
                        if isinstance(item, dict) and item.get('project_name') == name
                    ]
            except Exception as exc:
                log_debug(f"No legacy global bookmarks to migrate: {exc}")

        main_window.bookmarks = matching
        if matching:
            self.save_settings_to_project(main_window)
            log_info(
                f"Migrated {len(matching)} bookmarks from global settings into project '{self.project.name}'"
            )
