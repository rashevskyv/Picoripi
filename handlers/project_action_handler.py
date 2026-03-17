# handlers/project_action_handler.py
import os
import json
import uuid
import shutil
from pathlib import Path
from typing import Dict, Any, List, Optional, Union, Tuple
from PyQt5.QtWidgets import QMessageBox, QFileDialog, QInputDialog, QTreeWidgetItem
from PyQt5.QtCore import Qt
from core.project_manager import ProjectManager
from core.data_manager import load_json_file, load_text_file
from .base_handler import BaseHandler
from utils.logging_utils import log_info, log_warning, log_error, log_debug
from components.folder_delete_dialog import FolderDeleteDialog

class ProjectActionHandler(BaseHandler):
    def __init__(self, main_window: Any, data_processor: Any, ui_updater: Any):
        super().__init__(main_window, data_processor, ui_updater)

    def create_new_project_action(self) -> None:
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
        if dialog.exec_() != dialog.Accepted:
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

            # Now sync with plugin awareness
            if self.mw.project_manager:
                self.mw.project_manager.sync_project_files(plugin=self.mw.current_game_rules)

            # Enable project-specific actions
            if hasattr(self.mw, 'close_project_action'):
                self.mw.close_project_action.setEnabled(True)
            if hasattr(self.mw, 'import_block_action'):
                self.mw.import_block_action.setEnabled(True)
            if hasattr(self.mw, 'import_directory_action'):
                self.mw.import_directory_action.setEnabled(True)
            if hasattr(self.mw, 'add_block_button'):
                self.mw.add_block_button.setEnabled(True)

            # Update UI
            self.ui_updater.update_title()
            self._populate_blocks_from_project()

            QMessageBox.information(
                self.mw,
                "Project Created",
                f"Project '{project.name}' has been created successfully."
            )
        else:
            QMessageBox.critical(self.mw, "Project Creation Failed", "Failed to create project.")

    def open_project_action(self) -> None:
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
                self.mw.settings_manager.add_recent_project(project_path)
                self.mw.settings_manager.save_settings()
                self._update_recent_projects_menu()

            # Switch plugin if needed
            if project.plugin_name and project.plugin_name != self.mw.active_game_plugin:
                log_info(f"Switching plugin to '{project.plugin_name}'")
                self.mw.active_game_plugin = project.plugin_name
                self.mw.load_game_plugin()
                self.ui_updater.update_plugin_status_label()

            # Load project-specific settings from metadata
            if self.mw.project_manager:
                self.mw.project_manager.load_settings_from_project(self.mw)
                self.mw.project_manager.sync_project_files(plugin=self.mw.current_game_rules)

            # Enable project-specific actions
            if hasattr(self.mw, 'close_project_action'):
                self.mw.close_project_action.setEnabled(True)
            if hasattr(self.mw, 'import_block_action'):
                self.mw.import_block_action.setEnabled(True)
            if hasattr(self.mw, 'import_directory_action'):
                self.mw.import_directory_action.setEnabled(True)
            if hasattr(self.mw, 'add_block_button'):
                self.mw.add_block_button.setEnabled(True)

            # Update UI
            self.ui_updater.update_title()
            self._populate_blocks_from_project()

            log_info(f"Project '{project.name}' opened with {len(project.blocks)} blocks.")
        else:
            QMessageBox.critical(
                self.mw,
                "Project Load Failed",
                f"Failed to load project from:\n{project_path}"
            )

    def close_project_action(self) -> None:
        log_info("Close Project action triggered.")

        if self.mw.unsaved_changes:
            reply = QMessageBox.question(
                self.mw,
                'Unsaved Changes',
                "Save changes before closing project?",
                QMessageBox.Save | QMessageBox.Discard | QMessageBox.Cancel,
                QMessageBox.Cancel
            )
            if reply == QMessageBox.Save:
                if hasattr(self.mw, 'app_action_handler'):
                    if not self.mw.app_action_handler.save_data_action(ask_confirmation=False):
                        return
            elif reply == QMessageBox.Cancel:
                return

        # Clear project
        self.mw.project_manager = None

        # Clear UI
        self.mw.data = []
        self.mw.edited_data = {}
        self.mw.block_names = {}
        self.mw.current_block_idx = -1
        self.mw.current_string_idx = -1
        self.mw.unsaved_changes = False

        # Disable project-specific actions
        if hasattr(self.mw, 'close_project_action'):
            self.mw.close_project_action.setEnabled(False)
        if hasattr(self.mw, 'import_block_action'):
            self.mw.import_block_action.setEnabled(False)
        if hasattr(self.mw, 'import_directory_action'):
            self.mw.import_directory_action.setEnabled(False)
        if hasattr(self.mw, 'add_block_button'):
            self.mw.add_block_button.setEnabled(False)
        if hasattr(self.mw, 'add_folder_button'):
            self.mw.add_folder_button.setEnabled(False)

        # Update UI
        self.mw.block_list_widget.clear()
        self.ui_updater.populate_strings_for_block(-1)
        self.ui_updater.update_text_views()
        self.ui_updater.update_title()
        self.ui_updater.update_statusbar_paths()

        log_info("Project closed.")

    def import_block_action(self) -> None:
        from components.project_dialogs import ImportBlockDialog
        log_info("Import Block action triggered.")

        if not self.mw.project_manager or not self.mw.project_manager.project:
            QMessageBox.warning(self.mw, "No Project", "Please open or create a project first.")
            return

        dialog = ImportBlockDialog(self.mw, project_manager=self.mw.project_manager)
        if dialog.exec_() != dialog.Accepted:
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
            self._populate_blocks_from_project()
            QMessageBox.information(self.mw, "Block Imported", f"Block '{info['name']}' has been imported.")
        else:
            QMessageBox.critical(self.mw, "Import Failed", "Failed to import block.")

    def import_directory_action(self) -> None:
        log_info("Import Directory action triggered.")

        if not self.mw.project_manager or not self.mw.project_manager.project:
            QMessageBox.warning(self.mw, "No Project", "Please open or create a project first.")
            return

        start_dir = str(Path.home())
        directory_path = QFileDialog.getExistingDirectory(
            self.mw,
            "Select Directory to Import",
            start_dir,
            QFileDialog.ShowDirsOnly | QFileDialog.DontResolveSymlinks
        )

        if not directory_path:
            log_info("Import directory cancelled.")
            return

        # Import directory using ProjectManager
        blocks = self.mw.project_manager.import_directory(directory_path)

        if blocks:
            log_info(f"{len(blocks)} blocks imported successfully from '{directory_path}'.")
            self._populate_blocks_from_project()
            QMessageBox.information(self.mw, "Directory Imported", f"{len(blocks)} blocks have been imported.")
        else:
            QMessageBox.information(self.mw, "Import Result", "No supported files found or failed to import.")

    def delete_block_action(self) -> None:
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
                QMessageBox.Yes | QMessageBox.No,
                QMessageBox.No
            )

            if reply != QMessageBox.Yes:
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
            # IT IS A VIRTUAL FOLDER
            folder = pm.find_virtual_folder(folder_id)
            if not folder: return
            
            # If folder is empty, don't show the complex dialog
            is_empty = not folder.block_ids and not folder.children
            action = 0
            
            if is_empty:
                reply = QMessageBox.question(
                    self.mw, 'Delete Folder',
                    f"Are you sure you want to delete the empty folder '{folder.name}'?",
                    QMessageBox.Yes | QMessageBox.No, QMessageBox.No
                )
                if reply == QMessageBox.Yes:
                    action = 2 # Delete all (which is none)
            else:
                dialog = FolderDeleteDialog(folder.name, self.mw)
                dialog.exec_()
                action = dialog.result_action
            
            if action == 0: return # Cancel
            
            # PREPARE SELECTION RECOVERY
            # Find a neighbor to select after deletion so we don't jump to the bottom
            new_selection_block_idx = None
            new_selection_folder_id = None
            
            parent_item = current_item.parent() or self.mw.block_list_widget.invisibleRootItem()
            idx = parent_item.indexOfChild(current_item)
            neighbor = None
            if parent_item.childCount() > 1:
                if idx < parent_item.childCount() - 1:
                    neighbor = parent_item.child(idx + 1)
                else:
                    neighbor = parent_item.child(idx - 1)
            else:
                neighbor = parent_item if parent_item != self.mw.block_list_widget.invisibleRootItem() else None
            
            if neighbor:
                new_selection_block_idx = neighbor.data(0, Qt.UserRole)
                new_selection_folder_id = neighbor.data(0, Qt.UserRole + 1)

            undo_mgr = getattr(self.mw, 'undo_manager', None)
            before = undo_mgr.get_project_snapshot() if undo_mgr else None
            
            if action == 1:
                # 1. DELETE FOLDER ONLY (Keep contents)
                children_folders = list(folder.children)
                children_blocks = list(folder.block_ids)
                parent_id = folder.parent_id
                
                pm._remove_folder_from_anywhere(folder_id)
                
                # Move everything up
                if parent_id:
                    parent_folder = pm.find_virtual_folder(parent_id)
                    if parent_folder:
                        for child_f in children_folders:
                            child_f.parent_id = parent_id
                            parent_folder.children.append(child_f)
                        parent_folder.block_ids.extend(children_blocks)
                else: # Move to root
                    for child_f in children_folders:
                        child_f.parent_id = None
                        pm.project.virtual_folders.append(child_f)
                    
                    if 'root_block_ids' not in pm.project.metadata:
                        pm.project.metadata['root_block_ids'] = []
                    pm.project.metadata['root_block_ids'].extend(children_blocks)
                
                pm.save()
                if undo_mgr and before is not None:
                    undo_mgr.record_structural_action(before, 'DELETE_FOLDER_ONLY', f"Delete folder '{folder.name}' (keep contents)")
                
                # Apply suggested selection
                if new_selection_block_idx is not None or new_selection_folder_id is not None:
                    self.mw.block_list_widget.setCurrentItem(neighbor)

                self.ui_updater.populate_blocks()

            elif action == 2:
                # 2. DELETE FOLDER AND CONTENTS
                # Recursively delete all items in folder
                all_block_ids: List[str] = []
                def collect_blocks(f: Any) -> None:
                    all_block_ids.extend(f.block_ids)
                    for child in f.children:
                        collect_blocks(child)
                        
                collect_blocks(folder)
                
                pm._remove_folder_from_anywhere(folder_id)
                for bid in all_block_ids:
                    pm.project.remove_block(bid)
                    
                pm.save()
                if undo_mgr and before is not None:
                    undo_mgr.record_structural_action(before, 'DELETE_FOLDER_ALL', f"Delete folder '{folder.name}' AND its contents")
                
                if neighbor:
                    self.mw.block_list_widget.setCurrentItem(neighbor)
                
                if all_block_ids:
                    self._populate_blocks_from_project()
                else:
                    self.ui_updater.populate_blocks()

    def move_block_up_action(self) -> None:
        log_info("Move Block Up action triggered.")
        if hasattr(self.mw, 'block_list_widget'):
            self.mw.block_list_widget.move_current_item_up()

    def move_block_down_action(self) -> None:
        log_info("Move Block Down action triggered.")
        if hasattr(self.mw, 'block_list_widget'):
            self.mw.block_list_widget.move_current_item_down()

    def add_folder_action(self) -> None:
        log_info("Add Folder action triggered.")
        if hasattr(self.mw, 'block_list_widget'):
            self.mw.block_list_widget._create_folder_at_cursor()


    def add_items_to_folder_action(self) -> None:
        """Move multiple selected items into a folder."""
        if not self.mw.project_manager or not self.mw.project_manager.project:
            return

        selected_items = self.mw.block_list_widget.selectedItems()
        if not selected_items:
            return

        pm = self.mw.project_manager
        
        # 1. Use new MoveToFolderDialog
        from components.project_dialogs import MoveToFolderDialog
        
        # Try to find current parent folder ID if items are in a folder
        current_parent_id: Optional[str] = None
        if selected_items[0].parent():
            current_parent_id = selected_items[0].parent().data(0, Qt.UserRole + 1)

        from PyQt5.QtWidgets import QDialog
        dialog = MoveToFolderDialog(self.mw, pm, current_folder_id=current_parent_id)
        if dialog.exec_() != QDialog.Accepted:
            return
            
        target_folder_id = dialog.get_selected_folder_id()

        # 2. Perform the Move
        undo_mgr = getattr(self.mw, 'undo_manager', None)
        before = undo_mgr.get_project_snapshot() if undo_mgr else None
        
        block_map: Dict[int, int] = getattr(self.mw, 'block_to_project_file_map', {})
        moved_count = 0
        
        for item in selected_items:
            b_idx = item.data(0, Qt.UserRole)
            f_id = item.data(0, Qt.UserRole + 1)
            
            if b_idx is not None:
                proj_idx = block_map.get(b_idx, b_idx)
                if proj_idx < len(pm.project.blocks):
                    pm.move_block_to_folder(pm.project.blocks[proj_idx].id, target_folder_id)
                    moved_count += 1
            elif f_id:
                if pm.move_folder_to_folder(f_id, target_folder_id):
                    moved_count += 1

        if moved_count > 0:
            pm.save()
            if undo_mgr and before is not None:
                undo_mgr.record_structural_action(before, 'MOVE_BATCH', f"Move {moved_count} items to folder")
            
            # Keep focus at the source parent so the view doesn't jump
            source_parent_item = selected_items[0].parent() if selected_items else None
            if source_parent_item:
                self.mw.block_list_widget.setCurrentItem(source_parent_item)
                
            self.ui_updater.populate_blocks(override_folder_id=target_folder_id)
            log_info(f"Batch move completed: {moved_count} items moved.")


    def _populate_blocks_from_project(self) -> None:
        """Populate block list from current project and load data."""
        if not self.mw.project_manager or not self.mw.project_manager.project:
            return

        # Clear current data
        self.mw.block_list_widget.clear()
        self.mw.data = []
        self.mw.edited_data = {}
        self.mw.block_names = {}
        self.mw.block_to_project_file_map = {} # Mapping data_block_idx -> project_block_idx
        
        # Reset plugin state if it tracks keys (like pokemon_fr)
        if hasattr(self.mw.current_game_rules, 'original_keys'):
            self.mw.current_game_rules.original_keys = []

        # Load each block's data
        self.mw.block_to_project_file_map = {}
        source_parsed_counts: List[int] = []
        
        for project_block_idx, block in enumerate(self.mw.project_manager.project.blocks):
            source_path = self.mw.project_manager.get_absolute_path(block.source_file)
            
            if Path(source_path).exists():
                file_extension = Path(source_path).suffix.lower()
                if file_extension == '.json':
                    file_content, error = load_json_file(source_path)
                else:
                    # Try loading as text for any other extension
                    file_content, error = load_text_file(source_path)

                if not error and self.mw.current_game_rules:
                    parsed_data, names = self.mw.current_game_rules.load_data_from_json_obj(file_content)
                    
                    if block.internal_key:
                        # Find the specific sub-block
                        sub_idx = -1
                        for i, name in names.items():
                            if name == block.internal_key:
                                sub_idx = int(i)
                                break
                        
                        if sub_idx != -1 and sub_idx < len(parsed_data):
                            data_block_idx = len(self.mw.data)
                            self.mw.data.append(parsed_data[sub_idx])
                            self.mw.block_to_project_file_map[data_block_idx] = project_block_idx
                            self.mw.block_names[str(data_block_idx)] = block.name
                            source_parsed_counts.append(1)
                        else:
                            # Not found or error loading sub-block
                            source_parsed_counts.append(1)
                            data_block_idx = len(self.mw.data)
                            self.mw.data.append([])
                            self.mw.block_to_project_file_map[data_block_idx] = project_block_idx
                            self.mw.block_names[str(data_block_idx)] = f"{block.name} (Missing)"
                    else:
                        # Fallback for old projects or non-exploded files: load everything
                        count = len(parsed_data) if parsed_data else 1
                        source_parsed_counts.append(count)
                        
                        for sub_block_idx, block_content in enumerate(parsed_data):
                            data_block_idx = len(self.mw.data)
                            self.mw.data.append(block_content)
                            self.mw.block_to_project_file_map[data_block_idx] = project_block_idx
                            
                            # Handle block names
                            if count > 1:
                                p_name = names.get(str(sub_block_idx), f"{block.name} (Part {sub_block_idx+1})")
                                self.mw.block_names[str(data_block_idx)] = p_name
                            else:
                                self.mw.block_names[str(data_block_idx)] = block.name
                else:
                    source_parsed_counts.append(1)
                    data_block_idx = len(self.mw.data)
                    self.mw.data.append([])
                    self.mw.block_to_project_file_map[data_block_idx] = project_block_idx
                    self.mw.block_names[str(data_block_idx)] = block.name
            else:
                source_parsed_counts.append(1)
                data_block_idx = len(self.mw.data)
                self.mw.data.append([])
                self.mw.block_to_project_file_map[data_block_idx] = project_block_idx
                self.mw.block_names[str(data_block_idx)] = block.name

        # Backup authoritative original keys from source files
        plugin_keys_backup = None
        if hasattr(self.mw.current_game_rules, 'original_keys'):
            plugin_keys_backup = list(self.mw.current_game_rules.original_keys)

        # Load edited_file_data
        self.mw.edited_file_data = []
        for project_block_idx, block in enumerate(self.mw.project_manager.project.blocks):
            translation_path = self.mw.project_manager.get_absolute_path(block.translation_file, is_translation=True)
            
            # How many blocks did the source file produce?
            expected_count = source_parsed_counts[project_block_idx]

            if Path(translation_path).exists():
                file_extension = Path(translation_path).suffix.lower()
                if file_extension == '.json':
                    file_content, error = load_json_file(translation_path)
                else:
                    file_content, error = load_text_file(translation_path)

                if not error and self.mw.current_game_rules:
                    parsed_edited_data, _ = self.mw.current_game_rules.load_data_from_json_obj(file_content)
                    
                    # Force match the number of blocks to the source structure
                    for i in range(expected_count):
                        if i < len(parsed_edited_data):
                            self.mw.edited_file_data.append(parsed_edited_data[i])
                        else:
                            self.mw.edited_file_data.append([]) # Pad if translation has fewer blocks
                else:
                    for _ in range(expected_count):
                        self.mw.edited_file_data.append([])
            else:
                for _ in range(expected_count):
                    self.mw.edited_file_data.append([])

        # Restore authoritative original keys
        if plugin_keys_backup is not None and hasattr(self.mw.current_game_rules, 'original_keys'):
            self.mw.current_game_rules.original_keys = plugin_keys_backup

        # Update paths for old-style save/load compatibility
        if self.mw.data:
            first_block = self.mw.project_manager.project.blocks[0]
            self.mw.json_path = self.mw.project_manager.get_absolute_path(first_block.source_file)
            self.mw.edited_json_path = self.mw.project_manager.get_absolute_path(first_block.translation_file, is_translation=True)

        # Perform initial scan
        if hasattr(self.mw, 'app_action_handler'):
            self.mw.issue_scan_handler._perform_initial_silent_scan_all_issues()

        # Update UI
        self.ui_updater.populate_blocks()
        self.ui_updater.update_statusbar_paths()

        # Restore UI Session state for project
        if self.mw.project_manager and self.mw.project_manager.project_file_path:
            p_path = str(self.mw.project_manager.project_file_path)
            state = self.mw.settings_manager.session_state.get_state_for_file(p_path)
            if state:
                log_info(f"Restoring project UI state for {p_path}")
                self.ui_updater.apply_tree_state(state)
                
                # Apply cursor and scroll positions
                if self.mw.edited_text_edit:
                    def _apply_scroll() -> None:
                        self.mw.edited_text_edit.verticalScrollBar().setValue(state.get("v_scroll", 0))
                        self.mw.edited_text_edit.horizontalScrollBar().setValue(state.get("h_scroll", 0))
                        if self.mw.preview_text_edit:
                            self.mw.preview_text_edit.verticalScrollBar().setValue(state.get("preview_v_scroll", 0))
                        if self.mw.original_text_edit:
                            self.mw.original_text_edit.verticalScrollBar().setValue(state.get("original_v_scroll", 0))
                        
                        cursor_pos = state.get("cursor_pos", 0)
                        doc_len = self.mw.edited_text_edit.document().characterCount() - 1
                        pos_to_set = min(cursor_pos, max(0, doc_len))
                        cursor = self.mw.edited_text_edit.textCursor()
                        cursor.setPosition(pos_to_set)
                        self.mw.edited_text_edit.setTextCursor(cursor)
                        self.mw.edited_text_edit.ensureCursorVisible()

                    from PyQt5.QtCore import QTimer
                    QTimer.singleShot(200, _apply_scroll)

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
            log_info(f"Recent project '{project.name}' loaded successfully.")

            # Move to top of recent projects
            if hasattr(self.mw, 'settings_manager'):
                self.mw.settings_manager.add_recent_project(project_path)
                self.mw.settings_manager.save_settings()
                self._update_recent_projects_menu()

            # Switch plugin if needed
            if project.plugin_name and project.plugin_name != self.mw.active_game_plugin:
                log_info(f"Switching plugin to '{project.plugin_name}'")
                self.mw.active_game_plugin = project.plugin_name
                self.mw.load_game_plugin()
                self.ui_updater.update_plugin_status_label()

            # Load project-specific settings from metadata
            if self.mw.project_manager:
                self.mw.project_manager.load_settings_from_project(self.mw)

            # Enable project-specific actions
            if hasattr(self.mw, 'close_project_action'):
                self.mw.close_project_action.setEnabled(True)
            if hasattr(self.mw, 'import_block_action'):
                self.mw.import_block_action.setEnabled(True)
            if hasattr(self.mw, 'import_directory_action'):
                self.mw.import_directory_action.setEnabled(True)
            if hasattr(self.mw, 'add_block_button'):
                self.mw.add_block_button.setEnabled(True)
            if hasattr(self.mw, 'add_folder_button'):
                self.mw.add_folder_button.setEnabled(True)

            # Update UI
            self.ui_updater.update_title()
            self._populate_blocks_from_project()

            log_info(f"Recent project '{project.name}' opened with {len(project.blocks)} blocks.")
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
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No
        )

        if reply == QMessageBox.Yes:
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
        """Recursively update the is_expanded state for all virtual folders."""
        if not self.mw.project_manager or not self.mw.project_manager.project:
            return
            
        def update_folder(f: Any) -> None:
            f.is_expanded = expanded
            for child in f.children:
                update_folder(child)
                
        for folder in self.mw.project_manager.project.virtual_folders:
            update_folder(folder)
        self.mw.project_manager.save()
