# handlers/project_action_handler.py
import os
import json
import uuid
import shutil
from pathlib import Path
from typing import Dict, Any, List, Optional, Union, Tuple
from PyQt6.QtWidgets import QMessageBox, QFileDialog, QInputDialog, QTreeWidgetItem, QDialog
from PyQt6.QtCore import Qt, QThread, pyqtSignal
from core.project_manager import ProjectManager
from core.data_manager import load_json_file, load_text_file
from .base_handler import BaseHandler
from utils.logging_utils import log_info, log_warning, log_error, log_debug
from components.folder_delete_dialog import FolderDeleteDialog

class ProjectLoadWorker(QThread):
    """Worker thread for loading project files asynchronously."""
    finished = pyqtSignal(dict)
    progress = pyqtSignal(int, int)

    def __init__(self, project_manager, current_game_rules):
        super().__init__()
        self.project_manager = project_manager
        self.current_game_rules = current_game_rules
        self.blocks = list(project_manager.project.blocks) if project_manager and project_manager.project else []
        self.error_occurred = None

    def run(self):
        try:
            self.project_manager.clear_archive_cache()
            
            data = []
            block_names = {}
            block_to_project_file_map = {}
            source_parsed_counts = []
            
            total_blocks = len(self.blocks)
            
            # Load block source data
            for project_block_idx, block in enumerate(self.blocks):
                self.progress.emit(project_block_idx, total_blocks * 2)
                
                is_archive = block.metadata.get('is_archive_member', False)
                archive_rel_path = block.metadata.get('archive_rel_path')
                inner_path = block.metadata.get('archive_file_name')

                # Fallback for old projects where metadata isn't set, but path points to .extracted
                if not is_archive and '.extracted/sources/' in block.source_file:
                    parts = block.source_file.split('.extracted/sources/')
                    if len(parts) > 1:
                        sub_path = parts[1]
                        for ext in ['.arc/', '.rarc/', '.ark/']:
                            if ext in sub_path:
                                idx = sub_path.find(ext)
                                archive_rel_path = sub_path[:idx + len(ext) - 1]
                                inner_path = sub_path[idx + len(ext):]
                                is_archive = True
                                block.metadata['is_archive_member'] = True
                                block.metadata['archive_rel_path'] = archive_rel_path
                                block.metadata['archive_file_name'] = inner_path
                                break

                file_content = None
                error = None

                if is_archive:
                    try:
                        container = self.project_manager.get_archive_container(archive_rel_path, is_translation=False)
                        file_content = container.read_file(inner_path)
                    except Exception as e:
                        error = f"Failed to read archive member {archive_rel_path}/{inner_path}: {e}"
                else:
                    source_path = self.project_manager.get_absolute_path(block.source_file)
                    if Path(source_path).exists():
                        file_extension = Path(source_path).suffix.lower()
                        if file_extension == '.json':
                            file_content, error = load_json_file(source_path)
                        elif file_extension in {'.bmg', '.bfn', '.arc', '.rarc'}:
                            try:
                                file_content = Path(source_path).read_bytes()
                                error = None
                            except Exception as e:
                                file_content = None
                                error = f"Failed to read binary file: {e}"
                        else:
                            file_content, error = load_text_file(source_path)
                    else:
                        error = "File does not exist"

                if not error and file_content is not None:
                    if not self.current_game_rules:
                        parsed_data, names = [], {}
                    else:
                        parsed_data, names = self.current_game_rules.load_data_from_json_obj(file_content)
                    
                    if block.internal_key:
                        sub_idx = -1
                        for i, name in names.items():
                            if name == block.internal_key:
                                sub_idx = int(i)
                                break
                        
                        if sub_idx != -1 and sub_idx < len(parsed_data):
                            data_block_idx = len(data)
                            data.append(parsed_data[sub_idx])
                            block_to_project_file_map[data_block_idx] = project_block_idx
                            block_names[str(data_block_idx)] = block.name
                            source_parsed_counts.append(1)
                        else:
                            source_parsed_counts.append(1)
                            data_block_idx = len(data)
                            data.append([])
                            block_to_project_file_map[data_block_idx] = project_block_idx
                            block_names[str(data_block_idx)] = f"{block.name} (Missing)"
                    else:
                        count = len(parsed_data) if parsed_data else 1
                        source_parsed_counts.append(count)
                        
                        for sub_block_idx, block_content in enumerate(parsed_data):
                            data_block_idx = len(data)
                            data.append(block_content)
                            block_to_project_file_map[data_block_idx] = project_block_idx
                            
                            if count > 1:
                                p_name = names.get(str(sub_block_idx), f"{block.name} (Part {sub_block_idx+1})")
                                block_names[str(data_block_idx)] = p_name
                            else:
                                block_names[str(data_block_idx)] = block.name
                else:
                    source_parsed_counts.append(1)
                    data_block_idx = len(data)
                    data.append([])
                    block_to_project_file_map[data_block_idx] = project_block_idx
                    block_names[str(data_block_idx)] = block.name

            # Backup authoritative original keys from source files
            plugin_keys_backup = None
            if hasattr(self.current_game_rules, 'original_keys'):
                plugin_keys_backup = list(self.current_game_rules.original_keys)

            # Load edited_file_data
            edited_file_data = []
            for project_block_idx, block in enumerate(self.blocks):
                self.progress.emit(total_blocks + project_block_idx, total_blocks * 2)
                
                is_archive = block.metadata.get('is_archive_member', False)
                archive_rel_path = block.metadata.get('archive_rel_path')
                inner_path = block.metadata.get('archive_file_name')
                
                expected_count = source_parsed_counts[project_block_idx]
                file_content = None
                error = None

                if is_archive:
                    try:
                        container = self.project_manager.get_archive_container(archive_rel_path, is_translation=True)
                        file_content = container.read_file(inner_path)
                    except Exception as e:
                        error = f"Failed to read translation archive member {archive_rel_path}/{inner_path}: {e}"
                else:
                    translation_path = self.project_manager.get_absolute_path(block.translation_file, is_translation=True)
                    if Path(translation_path).exists():
                        file_extension = Path(translation_path).suffix.lower()
                        if file_extension == '.json':
                            file_content, error = load_json_file(translation_path)
                        elif file_extension in {'.bmg', '.bfn', '.arc', '.rarc'}:
                            try:
                                file_content = Path(translation_path).read_bytes()
                                error = None
                            except Exception as e:
                                file_content = None
                                error = f"Failed to read binary file: {e}"
                        else:
                            file_content, error = load_text_file(translation_path)
                    else:
                        error = "Translation file does not exist"

                parsed_edited_data = None
                if not error and file_content is not None and self.current_game_rules:
                    try:
                        parsed_edited_data, _ = self.current_game_rules.load_data_from_json_obj(file_content)
                    except Exception as parse_err:
                        log_error(f"CORRUPT BMG: Failed to parse translation for {block.name} (archive {archive_rel_path}/{inner_path}): {parse_err}. Falling back to source.", category="file_ops")
                        file_content_src = None
                        try:
                            if is_archive:
                                container_src = self.project_manager.get_archive_container(archive_rel_path, is_translation=False)
                                file_content_src = container_src.read_file(inner_path)
                            else:
                                source_path = self.project_manager.get_absolute_path(block.source_file)
                                if Path(source_path).exists():
                                    file_content_src = Path(source_path).read_bytes()
                        except Exception:
                            pass
                        
                        if file_content_src is not None:
                            try:
                                parsed_edited_data, _ = self.current_game_rules.load_data_from_json_obj(file_content_src)
                            except Exception:
                                parsed_edited_data = None

                if parsed_edited_data is not None:
                    if block.internal_key:
                        sub_idx_edit = -1
                        try:
                            _, trans_names = self.current_game_rules.load_data_from_json_obj(file_content)
                        except Exception:
                            trans_names = {}
                        for i_n, name_n in trans_names.items():
                            if name_n == block.internal_key:
                                sub_idx_edit = int(i_n)
                                break
                        if sub_idx_edit != -1 and sub_idx_edit < len(parsed_edited_data):
                            edited_file_data.append(parsed_edited_data[sub_idx_edit])
                        elif parsed_edited_data:
                            edited_file_data.append(parsed_edited_data[0])
                        else:
                            edited_file_data.append([])
                    else:
                        for i in range(expected_count):
                            if i < len(parsed_edited_data):
                                edited_file_data.append(parsed_edited_data[i])
                            else:
                                edited_file_data.append([])
                else:
                    for _ in range(expected_count):
                        edited_file_data.append([])

            self.project_manager.clear_archive_cache()

            self.finished.emit({
                'data': data,
                'edited_file_data': edited_file_data,
                'block_names': block_names,
                'block_to_project_file_map': block_to_project_file_map,
                'plugin_keys_backup': plugin_keys_backup
            })
        except Exception as e:
            self.error_occurred = e
            log_error(f"ProjectLoadWorker error: {e}", exc_info=True)
            self.finished.emit({})

class ProjectActionHandler(BaseHandler):
    """Handler for project action operations."""
    def __init__(self, main_window: Any, data_processor: Any, ui_updater: Any):
        """Initialize a new instance."""
        super().__init__(main_window, data_processor, ui_updater)
        # Ensure ProjectManager is initialized on the main window
        if not hasattr(self.mw, 'project_manager') or self.mw.project_manager is None:
            self.mw.project_manager = ProjectManager()

    def _set_project_actions_enabled(self, enabled: bool):
        """Enable or disable project-specific UI actions and update their tooltips."""
        actions_map = {
            'close_project_action': {
                'enabled_tip': "Close the current project or file",
                'disabled_tip': "No project or file open to close"
            },
            'import_block_action': {
                'enabled_tip': "Import Block...",
                'disabled_tip': "This action is only available in Project mode (within a .uiproj project)."
            },
            'import_directory_action': {
                'enabled_tip': "Import Directory...",
                'disabled_tip': "This action is only available in Project mode (within a .uiproj project)."
            },
            'add_block_button': {
                'enabled_tip': "Add new block (import file)",
                'disabled_tip': "Adding blocks is only available in Project mode (within a .uiproj project)."
            },
            'add_folder_button': {
                'enabled_tip': "Create new virtual folder",
                'disabled_tip': "Creating folders is only available in Project mode (within a .uiproj project)."
            },
            'export_bmg_json_action': {
                'enabled_tip': "Export the currently selected BMG file's text content to JSON",
                'disabled_tip': "Export BMG to JSON is only available when a project is open."
            },
            'import_bmg_json_action': {
                'enabled_tip': "Import BMG text content from an exported JSON file into the currently selected block",
                'disabled_tip': "Import BMG from JSON is only available when a project is open."
            },
            'save_translated_action': {
                'enabled_tip': "Save current translation to local backup database",
                'disabled_tip': "No project or file is open"
            },
            'restore_translated_action': {
                'enabled_tip': "Restore last saved translation for this string",
                'disabled_tip': "No project or file is open"
            },
            'export_translations_action': {
                'enabled_tip': "Export all current project/file translations to a JSON file",
                'disabled_tip': "No project or file is open"
            },
            'import_translations_action': {
                'enabled_tip': "Import translations from an exported JSON file",
                'disabled_tip': "No project or file is open"
            }
        }
        for action_name, tips in actions_map.items():
            action = getattr(self.mw, action_name, None)
            if action:
                action.setEnabled(enabled)
                action.setToolTip(tips['enabled_tip'] if enabled else tips['disabled_tip'])


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
                    "Project Created",
                    f"Project '{project.name}' has been created successfully."
                )
            self._populate_blocks_from_project(on_completed=on_created)
        else:
            QMessageBox.critical(self.mw, "Project Creation Failed", "Failed to create project.")

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
                "Project Load Failed",
                f"Failed to load project from:\n{project_path}"
            )

    def close_project_action(self) -> None:
        """Close project action."""
        log_info("Close Project action triggered.")

        if self.mw.data_store.unsaved_changes:
            reply = QMessageBox.question(
                self.mw,
                'Unsaved Changes',
                "Save changes before closing project?",
                QMessageBox.StandardButton.Save | QMessageBox.StandardButton.Discard | QMessageBox.StandardButton.Cancel,
                QMessageBox.StandardButton.Cancel
            )
            if reply == QMessageBox.StandardButton.Save:
                if hasattr(self.mw, 'app_action_handler'):
                    if not self.mw.app_action_handler.save_data_action(ask_confirmation=False):
                        return
            elif reply == QMessageBox.StandardButton.Cancel:
                return

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

        if hasattr(self.mw, 'settings_manager'):
            self.mw.settings_manager.set("last_opened_path", "")
            self.mw.settings_manager.set("active_game_plugin", "")
            self.mw.settings_manager.save_settings(save_project_settings=False)
        
        if hasattr(self.mw, 'bookmark_handler'):
            self.mw.bookmarks = self.mw.settings_manager.get('bookmarks', [])
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

    def import_block_action(self) -> None:
        """Import block action."""
        from components.project_dialogs import ImportBlockDialog
        log_info("Import Block action triggered.")

        if not self.mw.project_manager or not self.mw.project_manager.project:
            QMessageBox.warning(self.mw, "No Project", "Please open or create a project first.")
            return

        dialog = ImportBlockDialog(self.mw, project_manager=self.mw.project_manager)
        if dialog.exec() != QDialog.DialogCode.Accepted:
            log_info("Import block dialog cancelled.")
            return

        info = dialog.get_block_info()
        if not info:
            return

        # Import block using ProjectManager
        block = self.mw.project_manager.add_block(
            name=info['name'],
            source_file_path=info['source_file'],
            translation_file_path=info.get('translation_file'),
            description=info['description']
        )

        if block:
            log_info(f"Block '{info['name']}' imported successfully.")
            # Update UI
            def on_imported(state_restored):
                QMessageBox.information(self.mw, "Block Imported", f"Block '{info['name']}' has been imported.")
            self._populate_blocks_from_project(on_completed=on_imported)
        else:
            QMessageBox.critical(self.mw, "Import Failed", "Failed to import block.")

    def import_directory_action(self) -> None:
        """Import directory action."""
        log_info("Import Directory action triggered.")

        if not self.mw.project_manager or not self.mw.project_manager.project:
            QMessageBox.warning(self.mw, "No Project", "Please open or create a project first.")
            return

        start_dir = str(Path.home())
        directory_path = QFileDialog.getExistingDirectory(
            self.mw,
            "Select Directory to Import",
            start_dir,
            QFileDialog.Option.ShowDirsOnly | QFileDialog.Option.DontResolveSymlinks
        )

        if not directory_path:
            log_info("Import directory cancelled.")
            return

        # Import directory using ProjectManager
        blocks = self.mw.project_manager.import_directory(directory_path)

        if blocks:
            log_info(f"{len(blocks)} blocks imported successfully from '{directory_path}'.")
            def on_dir_imported(state_restored):
                QMessageBox.information(self.mw, "Directory Imported", f"{len(blocks)} blocks have been imported.")
            self._populate_blocks_from_project(on_completed=on_dir_imported)
        else:
            QMessageBox.information(self.mw, "Import Result", "No supported files found or failed to import.")

    def delete_block_action(self) -> None:
        """Remove block action."""
        log_info("Delete Item action triggered.")

        if not self.mw.project_manager or not self.mw.project_manager.project:
            return

        current_item = self.mw.block_list_widget.currentItem()
        if not current_item:
            return

        block_idx = current_item.data(0, Qt.UserRole)
        folder_id = current_item.data(0, Qt.UserRole + 1)
        pm = self.mw.project_manager
        
        # Determine what we are deleting
        if block_idx is not None:
            # IT IS A BLOCK
            block = pm.project.blocks[block_idx]
            block_name = block.name

            reply = QMessageBox.question(
                self.mw,
                'Delete Block',
                f"Are you sure you want to remove block '{block_name}' from the project?\n\n"
                "This will NOT delete the physical files, only the reference in the project.",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                QMessageBox.StandardButton.No
            )

            if reply != QMessageBox.StandardButton.Yes:
                return

            undo_mgr = getattr(self.mw, 'undo_manager', None)
            before = undo_mgr.get_project_snapshot() if undo_mgr else None

            # PREPARE SELECTION RECOVERY
            parent_item = current_item.parent() or self.mw.block_list_widget.invisibleRootItem()
            idx = parent_item.indexOfChild(current_item)
            neighbor = None
            if parent_item.childCount() > 1:
                if idx < parent_item.childCount() - 1: neighbor = parent_item.child(idx + 1)
                else: neighbor = parent_item.child(idx - 1)
            else:
                neighbor = parent_item if parent_item != self.mw.block_list_widget.invisibleRootItem() else None

            success = pm.project.remove_block(block.id)
            if success:
                pm.save()
                if undo_mgr and before is not None:
                    undo_mgr.record_structural_action(before, 'DELETE_BLOCK', f"Delete block '{block_name}'")
                log_info(f"Block '{block_name}' removed from project.")
                
                if neighbor:
                    self.mw.block_list_widget.setCurrentItem(neighbor)
                
                self._populate_blocks_from_project()
            else:
                QMessageBox.critical(self.mw, "Delete Error", "Failed to remove block.")
                
        elif folder_id is not None:
            self.mw.virtual_folder_handler.delete_folder_action(folder_id, current_item)

    def move_block_action(self, direction: int) -> None:
        """direction: -1 for up, +1 for down."""
        log_info(f"Move Block {'Up' if direction < 0 else 'Down'} action triggered.")
        if hasattr(self.mw, 'block_list_widget'):
            self.mw.block_list_widget.move_current_item(direction)

    def add_folder_action(self) -> None:
        """Add folder action."""
        self.mw.virtual_folder_handler.add_folder_action()

    def add_items_to_folder_action(self) -> None:
        """Add items to folder action."""
        self.mw.virtual_folder_handler.add_items_to_folder_action()


    def _populate_blocks_from_project(self, on_completed=None) -> None:
        """Populate block list from current project and load data asynchronously."""
        if not self.mw.project_manager or not self.mw.project_manager.project:
            if on_completed:
                on_completed(False)
            return

        # Reset block/string selection state to avoid stale index issues
        self.mw.data_store.current_block_idx = -1
        self.mw.data_store.current_string_idx = -1

        # Clear current data
        self.mw.block_list_widget.clear()
        self.mw.data_store.data = []
        self.mw.data_store.edited_data = {}
        self.mw.data_store.block_names = {}
        self.mw.block_to_project_file_map = {} # Mapping data_block_idx -> project_block_idx
        
        # Reset plugin state if it tracks keys (like pokemon_fr)
        if hasattr(self.mw.current_game_rules, 'original_keys'):
            self.mw.current_game_rules.original_keys = []

        # Setup loading thread and progress dialog
        worker = ProjectLoadWorker(self.mw.project_manager, self.mw.current_game_rules)
        
        import sys
        progress_dialog = None
        if 'pytest' not in sys.modules:
            from PyQt6.QtWidgets import QProgressDialog
            from PyQt6.QtCore import Qt
            total_steps = len(worker.blocks) * 2
            progress_dialog = QProgressDialog("Loading project blocks...", None, 0, total_steps, self.mw)
            progress_dialog.setWindowTitle("Loading Project")
            progress_dialog.setWindowModality(Qt.WindowModality.WindowModal)
            progress_dialog.setMinimumDuration(0) # show immediately
            progress_dialog.setValue(0)
            worker.progress.connect(progress_dialog.setValue)

        def on_finished(result):
            if 'pytest' not in sys.modules and progress_dialog:
                progress_dialog.close()

            if not result:
                if worker.error_occurred:
                    QMessageBox.critical(self.mw, "Load Error", f"An error occurred while loading project files:\n{worker.error_occurred}")
                if on_completed:
                    on_completed(False)
                return

            self.mw.data_store.data = result['data']
            self.mw.data_store.edited_file_data = result['edited_file_data']
            self.mw.data_store.block_names = result['block_names']
            self.mw.block_to_project_file_map = result['block_to_project_file_map']

            plugin_keys_backup = result['plugin_keys_backup']
            if plugin_keys_backup is not None and hasattr(self.mw.current_game_rules, 'original_keys'):
                self.mw.current_game_rules.original_keys = plugin_keys_backup

            # Update paths for old-style save/load compatibility
            if self.mw.project_manager.project.blocks:
                first_block = self.mw.project_manager.project.blocks[0]
                self.mw.data_store.json_path = self.mw.project_manager.get_absolute_path(first_block.source_file)
                self.mw.data_store.edited_json_path = self.mw.project_manager.get_absolute_path(first_block.translation_file, is_translation=True)

            self.mw.project_manager.clear_archive_cache()

            if hasattr(self.mw, 'translation_handler') and self.mw.translation_handler:
                self.mw.translation_handler.load_progress_from_metadata()

            # Perform initial scan
            if hasattr(self.mw, 'app_action_handler'):
                self.mw.issue_scan_handler._perform_initial_silent_scan_all_issues()

            # Pre-cache preview data for all blocks
            if hasattr(self.ui_updater, 'preview_updater'):
                self.ui_updater.preview_updater.schedule_pre_cache()

            # Update UI
            self.ui_updater.populate_blocks()
            self.ui_updater.update_statusbar_paths()

            state_restored = False
            # Restore UI Session state for project
            if self.mw.project_manager and self.mw.project_manager.project_file_path:
                p_path = str(self.mw.project_manager.project_file_path)
                state = None
                if self.mw.project_manager.project:
                    state = self.mw.project_manager.project.metadata.get("session_state")
                if not state:
                    state = self.mw.settings_manager.session_state.get_state_for_file(p_path)
                    
                if state and (state.get("selected_id") or state.get("expanded_ids")):
                    log_info(f"Restoring project UI state for {p_path}")
                    self.ui_updater.apply_tree_state(state)
                    state_restored = True

            if on_completed:
                on_completed(state_restored)

        # Store worker reference to prevent garbage collection
        self._active_load_worker = worker
        worker.finished.connect(on_finished)
        
        if 'pytest' in sys.modules:
            worker.run()
        else:
            worker.start()

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
            no_recent_action = self.mw.recent_projects_menu.addAction("No recent projects")
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
        clear_action = self.mw.recent_projects_menu.addAction("Clear Recent Projects")
        clear_action.triggered.connect(self._clear_recent_projects)

    def _open_recent_project(self, project_path: str) -> None:
        """Open a project from the recent projects list."""
        log_info(f"Opening recent project: {project_path}")

        if not Path(project_path).exists():
            QMessageBox.critical(
                self.mw,
                "Project Not Found",
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
            self.mw.active_game_plugin = target_plugin
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
                self.mw.settings_manager.load_all_font_maps()
            if hasattr(self.mw, 'string_settings_updater'):
                self.mw.string_settings_updater.update_font_combobox()
            
            # Fetch restored values for the timer
            restored_block = getattr(self.mw, 'last_block_idx', 0)
            restored_cat = getattr(self.mw, 'last_category_name', None)

            # 4. Enable project-related UI elements
            self._set_project_actions_enabled(True)

            # 5. Sync project files (extract archives, discover new blocks)
            self.mw.project_manager.sync_project_files(plugin=self.mw.current_game_rules)

            # 6. Populate UI components with the new project data
            self.ui_updater.update_title()
            
            def on_recent_opened(state_restored):
                if hasattr(self.mw, 'bookmark_handler'):
                    self.mw.bookmark_handler.update_bookmarks_menu()
                
                log_info(f"Project '{project.name}' open sequence complete. Total data blocks: {len(self.mw.data_store.data)}")

                # 6. Final UI polish: select the last block/category after QTreeWidget has settled
                # Only fallback to default block selection if no session state was restored!
                if not state_restored:
                    def restore_view():
                        log_info(f"Restoring UI state for block {restored_block}, category '{restored_cat}'")
                        if hasattr(self.mw, 'block_list_widget'):
                            self.mw.block_list_widget.select_block_by_index(restored_block, restored_cat)
                        
                        # These calls refresh the string list and editors
                        self.ui_updater.populate_strings_for_block(restored_block, restored_cat)
                        self.ui_updater.update_statusbar_paths()
                        self.ui_updater.update_plugin_status_label() # Ensure label is accurate

                    from PyQt6.QtCore import QTimer
                    QTimer.singleShot(150, restore_view) # Increased delay to 150ms for stability

            self._populate_blocks_from_project(on_completed=on_recent_opened)
        else:
            QMessageBox.critical(
                self.mw,
                "Project Load Failed",
                f"Failed to load project from:\n{project_path}"
            )

    def _clear_recent_projects(self) -> None:
        """Clear all recent projects."""
        reply = QMessageBox.question(
            self.mw,
            'Clear Recent Projects',
            "Are you sure you want to clear all recent projects?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No
        )

        if reply == QMessageBox.StandardButton.Yes:
            if hasattr(self.mw, 'settings_manager'):
                self.mw.settings_manager.clear_recent_projects()
                self.mw.settings_manager.save_settings()
                self._update_recent_projects_menu()
            log_info("Recent projects cleared.")

    def expand_all_action(self) -> None:
        """Expand all nodes in the tree."""
        if hasattr(self.mw, 'block_list_widget'):
            # Set flag to avoid recursive signals during bulk update
            self.mw.block_list_widget._is_programmatic_expansion = True
            try:
                # Update folder state in project manager
                self._update_all_folder_expansion_state(True)
                # Re-populate to update compaction labels
                self.mw.block_list_widget.setUpdatesEnabled(False)
                try:
                    self.ui_updater.populate_blocks()
                finally:
                    self.mw.block_list_widget.setUpdatesEnabled(True)
            finally:
                self.mw.block_list_widget._is_programmatic_expansion = False
            log_debug("Tree expanded all.")

    def collapse_all_action(self) -> None:
        """Collapse all nodes in the tree."""
        if hasattr(self.mw, 'block_list_widget'):
            self.mw.block_list_widget._is_programmatic_expansion = True
            try:
                self._update_all_folder_expansion_state(False)
                self.mw.block_list_widget.setUpdatesEnabled(False)
                try:
                    self.ui_updater.populate_blocks()
                finally:
                    self.mw.block_list_widget.setUpdatesEnabled(True)
            finally:
                self.mw.block_list_widget._is_programmatic_expansion = False
            log_debug("Tree collapsed all.")

    def _update_all_folder_expansion_state(self, expanded: bool) -> None:
        """Internal helper to update the all folder expansion state."""
        self.mw.virtual_folder_handler.update_all_folder_expansion_state(expanded)
