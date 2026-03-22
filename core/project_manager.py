# --- START OF FILE core/project_manager.py ---
# core/project_manager.py
"""
Project management system for the translation workbench.

This module provides data models and management for the project-oriented paradigm:
- Project: Top-level container holding all project data
- Block: Physical file pair (source/translation)
- Category: Virtual grouping of strings within a block
"""

import json
from typing import List, Dict, Optional, Set, Any, Union
from pathlib import Path
from utils.logging_utils import log_info, log_warning, log_error, log_debug

from .project_models import Category, Block, Project, VirtualFolder


class ProjectManager:
    """
    Manager class for loading, saving, and manipulating projects.

    The project structure on disk:
    project_folder/
        project.uiproj          # Project metadata file
        sources/                # Source files (read-only originals)
            file1.txt
            file2.txt
        translation/            # Translation files (working copies)
            file1.txt
            file2.txt
    """

    PROJECT_FILE_NAME = "project.uiproj"
    SOURCES_DIR = "sources"
    TRANSLATION_DIR = "translation"

    # Project-specific settings that are saved to project.metadata
    PROJECT_SETTINGS = [
        'font_size',
        'show_multiple_spaces_as_dots',
        'space_dot_color_hex',
        'preview_wrap_lines',
        'editors_wrap_lines',
        'game_dialog_max_width_pixels',
        'line_width_warning_threshold_pixels',
        'default_font_file',
        'newline_display_symbol',
        'newline_css',
        'tag_css',
        'tag_color_rgba',
        'tag_bold',
        'tag_italic',
        'tag_underline',
        'newline_color_rgba',
        'newline_bold',
        'newline_italic',
        'newline_underline',
        'spellchecker_language',
        'default_tag_mappings',
        'autofix_enabled',
        'detection_enabled',
    ]

    def __init__(self, project_path: Optional[Union[str, Path]] = None):
        """
        Initialize ProjectManager.

        Args:
            project_path: Path to the project directory or .uiproj file
        """
        self.project: Optional[Project] = None
        self.project_dir: Optional[str] = None
        self.project_file_path: Optional[str] = None

        if project_path:
            self.load(str(project_path))

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
            
            # Migration: if no virtual folders exist (or version < 1.1), create them from file structure
            if self.project.version < "1.1" and self.project.blocks:
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

    def add_block(self, name: str, source_file_path: Union[str, Path], translation_file_path: Optional[Union[str, Path]] = None, 
                  internal_key: Optional[str] = None, description: str = "", target_relative_path: str = "") -> Optional[Block]:
        """
        Register a new block (file pair) in the project. Does NOT copy files.

        Args:
            name: Display name for the block
            source_file_path: Relative path to the source file
            translation_file_path: Optional relative path to existing translation file
            description: Optional block description
            target_relative_path: Optional relative directory path (deprecated/ignored)

        Returns:
            The created Block object, or None on failure
        """
        if not self.project or not self.project_dir:
            log_error("No project loaded")
            return None

        try:
            source_path = Path(source_file_path)

            source_rel_path = source_file_path.replace('\\', '/')
            trans_rel_path = translation_file_path.replace('\\', '/') if translation_file_path else source_rel_path

            # Create block
            block = Block(
                name=name or source_path.stem,
                source_file=source_rel_path,
                translation_file=trans_rel_path,
                internal_key=internal_key,
                description=description
            )

            self.project.add_block(block)
            
            # Ensure it's tracked in virtual structure
            if 'root_block_ids' not in self.project.metadata:
                self.project.metadata['root_block_ids'] = []
            
            if block.id not in self.project.metadata['root_block_ids']:
                # Only add to root if it's not already in some virtual folder
                # For simplicity in add_block, we assume it goes to root unless moved later
                self.project.metadata['root_block_ids'].append(block.id)

            self.save()
            log_info(f"Registered block '{block.name}' loosely linked at {source_rel_path}")
            return block

        except Exception as e:
            log_error(f"Failed to register block: {e}", exc_info=True)
            return None

    def sync_project_files(self, plugin: Any = None) -> None:
        """
        Synchronize files from external directories with project blocks.
        """
        if not self.project:
            return

        source_path = self.project.metadata.get('source_path', '')
        translation_path = self.project.metadata.get('translation_path')
        is_directory_mode = self.project.metadata.get('is_directory_mode', True)
        # auto_create = self.project.metadata.get('auto_create_translations', False) # Reserved for later
        
        if not source_path or not Path(source_path).exists():
            log_warning("Source path is invalid or missing during sync.")
            return

        supported_extensions = {'.json', '.txt'}
        existing_blocks = {b.source_file: b for b in self.project.blocks}
        found_sources = set()

        if is_directory_mode:
            root_path = Path(source_path)
            for filepath in root_path.rglob('*'):
                if filepath.is_file() and filepath.suffix.lower() in supported_extensions:
                    rel_path = filepath.relative_to(root_path).as_posix()
                    found_sources.add(rel_path)
                    
                    if rel_path not in existing_blocks:
                        added_sub_blocks = False
                        if plugin and filepath.suffix.lower() == '.json':
                            try:
                                with filepath.open('r', encoding='utf-8') as f:
                                    content = json.load(f)
                                parsed, names = plugin.load_data_from_json_obj(content)
                                if parsed and len(parsed) > 1:
                                    for i in range(len(parsed)):
                                        full_sub_name = names.get(str(i), f"Block {i}")
                                        # Use only the last part of the path as the display name
                                        display_name = full_sub_name.replace('\\', '/').split('/')[-1]
                                        self.add_block(
                                            name=display_name,
                                            source_file_path=rel_path,
                                            translation_file_path=rel_path,
                                            internal_key=full_sub_name # The full key name from JSON
                                        )
                                    added_sub_blocks = True
                            except Exception as e:
                                log_debug(f"Sync: Failed to explode {rel_path}: {e}")

                        if not added_sub_blocks:
                            self.add_block(
                                name=filepath.stem,
                                source_file_path=rel_path,
                                translation_file_path=rel_path
                            )
        else:
            # File mode
            filepath = Path(source_path)
            if filepath.is_file() and filepath.suffix.lower() in supported_extensions:
                rel_path = filepath.name
                found_sources.add(rel_path)
                if rel_path not in existing_blocks:
                    trans_rel_path: str = Path(translation_path).name if translation_path else rel_path
                    
                    added_sub_blocks = False
                    if plugin and filepath.suffix.lower() == '.json':
                         try:
                            with filepath.open('r', encoding='utf-8') as f:
                                content = json.load(f)
                            parsed, names = plugin.load_data_from_json_obj(content)
                            if parsed and len(parsed) > 1:
                                for i in range(len(parsed)):
                                    full_sub_name = names.get(str(i), f"Block {i}")
                                    display_name = full_sub_name.replace('\\', '/').split('/')[-1]
                                    self.add_block(
                                        name=display_name,
                                        source_file_path=rel_path,
                                        translation_file_path=trans_rel_path,
                                        internal_key=full_sub_name
                                    )
                                added_sub_blocks = True
                         except Exception as e:
                            log_debug(f"Sync: Failed to explode {rel_path}: {e}")

                    if not added_sub_blocks:
                        self.add_block(
                            name=filepath.stem,
                            source_file_path=rel_path,
                            translation_file_path=trans_rel_path
                        )
                    
        # Remove blocks that no longer exist
        blocks_to_remove = [b.id for b in self.project.blocks if b.source_file not in found_sources]
        for bid in blocks_to_remove:
            self.project.remove_block(bid)
            
        if blocks_to_remove or len(found_sources) > len(existing_blocks):
            if self.project.version < "1.1":
                self._migrate_file_structure_to_virtual_folders()
            else:
                self.save()

    def import_directory(self, root_dir_path: Union[str, Path]) -> List[Block]:
        """
        Legacy functionality for loose imports. Not used in normal external directory modes.
        """
        # Kept for compatibility, redirects to normal behavior essentially
        return []

    def get_uncategorized_lines(self, block_id: str, total_lines: int) -> List[int]:
        """
        Get list of line indices that are not assigned to any category.

        Args:
            block_id: ID of the block
            total_lines: Total number of lines in the block

        Returns:
            List of uncategorized line indices
        """
        block = self.project.find_block(block_id) if self.project else None
        if not block:
            return list(range(total_lines))

        categorized = block.get_categorized_line_indices()
        return [i for i in range(total_lines) if i not in categorized]

    def get_absolute_path(self, relative_path: Union[str, Path], is_translation: bool = False) -> str:
        """
        Convert a block-relative path to an absolute path.

        Args:
            relative_path: Relative path within external source/translation directory
            is_translation: Determine whether to use source_path or translation_path

        Returns:
            Absolute file path
        """
        if not self.project:
            return relative_path
            
        is_directory_mode = self.project.metadata.get('is_directory_mode', True)
        base_path = self.project.metadata.get('translation_path') if is_translation else self.project.metadata.get('source_path')
        
        if not base_path:
            # Fallback auto create translation path or default directory
            if is_translation and self.project.metadata.get('auto_create_translations', False):
                source_p = Path(self.project.metadata.get('source_path', ''))
                base_path = source_p.parent / 'translation' if source_p.is_dir() else source_p.parent / 'translation'
            else:
                return relative_path

        if is_directory_mode:
            return str(Path(base_path) / relative_path)
        else:
            return str(base_path)

    def get_relative_path(self, absolute_path: Union[str, Path], is_translation: bool = False) -> str:
        """
        Convert an absolute path to a relative path against external directories.

        Args:
            absolute_path: Absolute file path
            is_translation: True if checking against translation_path

        Returns:
            Relative path within project
        """
        if not self.project:
            return absolute_path
            
        base_path = self.project.metadata.get('translation_path') if is_translation else self.project.metadata.get('source_path')
        if not base_path:
            return absolute_path
            
        try:
            return str(Path(absolute_path).relative_to(base_path))
        except ValueError:
            return absolute_path

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
                return False

            # Apply each project-specific setting to MainWindow
            settings_loaded = 0
            for setting_name, value in settings.items():
                if hasattr(main_window, setting_name):
                    setattr(main_window, setting_name, value)
                    settings_loaded += 1

            log_info(f"Loaded {settings_loaded} project settings from metadata")
            return True

        except Exception as e:
            log_error(f"Failed to load settings from project: {e}", exc_info=True)
            return False

    @property
    def current_project(self) -> Optional[Project]:
        """Get the currently loaded project."""
        return self.project

    def _migrate_file_structure_to_virtual_folders(self) -> None:
        """Build virtual folder structure from physical file paths of blocks."""
        if not self.project: return

        folder_map = {} # path -> VirtualFolder
        root_folders = []

        # Sort blocks by name for consistent initial order
        sorted_blocks = sorted(self.project.blocks, key=lambda b: b.source_file)

        for block in sorted_blocks:
            rel_path = block.source_file
            if rel_path.startswith(self.SOURCES_DIR + '/'):
                rel_path = rel_path[len(self.SOURCES_DIR) + 1:]
                
            path_parts = Path(rel_path).parent.as_posix().split('/')
            if path_parts == ['.'] or path_parts == ['']:
                path_parts = []
            
            # If it's a sub-block within a file, add the filename as a folder part
            if block.internal_key:
                path_parts.append(Path(rel_path).name)
                # If the internal key itself looks like a path, split it into folders
                internal_parts = block.internal_key.replace('\\', '/').split('/')
                if len(internal_parts) > 1:
                    # Everything except the last part is a folder
                    path_parts.extend(internal_parts[:-1])

            current_parent_id: Optional[str] = None
            current_path = ""
            
            last_folder: Optional[VirtualFolder] = None
            for part in path_parts:
                if not part: continue
                parent_path = current_path
                current_path = (current_path + "/" + part) if current_path else part
                
                if current_path not in folder_map:
                    new_folder = VirtualFolder(name=part, parent_id=current_parent_id)
                    folder_map[current_path] = new_folder
                    
                    if current_parent_id is None:
                        root_folders.append(new_folder)
                    else:
                        parent_folder = folder_map[parent_path]
                        parent_folder.children.append(new_folder)
                
                last_folder = folder_map[current_path]
                current_parent_id = last_folder.id
            
            if last_folder:
                last_folder.block_ids.append(block.id)

        # Handle blocks at the root level (no folders)
        root_block_ids = []
        for b in sorted_blocks:
            rel_p = b.source_file
            if rel_p.startswith(self.SOURCES_DIR + '/'):
                rel_p = rel_p[len(self.SOURCES_DIR) + 1:]
            parent_p = Path(rel_p).parent.as_posix()
            if parent_p == '.' or not parent_p:
                root_block_ids.append(b.id)
        
        self.project.virtual_folders = root_folders
        self.project.metadata['root_block_ids'] = root_block_ids # Blocks not in any folder
        self.project.version = "1.1"
        self.save()
        log_info(f"Migrated {len(self.project.blocks)} blocks to virtual folder structure.")

    def create_virtual_folder(self, name: str, parent_id: Optional[str] = None) -> VirtualFolder:
        """Create a new virtual folder or return existing if name collision at same level."""
        if not name.strip():
            name = "New Folder"
            
        # Check for existing folder with same name at this level
        siblings = self.project.virtual_folders if parent_id is None else []
        if parent_id:
            parent = self.find_virtual_folder(parent_id)
            if parent: siblings = parent.children
            
        for folder in siblings:
            if folder.name == name:
                log_debug(f"Folder '{name}' already exists at this level. Using existing folder {folder.id}")
                return folder
        
        new_folder = VirtualFolder(name=name, parent_id=parent_id)
        if parent_id is None:
            self.project.virtual_folders.append(new_folder)
        else:
            parent = self.find_virtual_folder(parent_id)
            if parent:
                parent.children.append(new_folder)
        return new_folder

    def move_strings_to_category(self, block_idx: int, string_indices: List[int], category_name: str) -> None:
        """Group specific strings within a block into a named virtual category."""
        if not self.project or block_idx < 0 or block_idx >= len(self.project.blocks):
            return
            
        from .project_models import Category
        block = self.project.blocks[block_idx]
        
        # Find or create target category
        target_category = next((c for c in block.categories if c.name == category_name), None)
        if not target_category:
            target_category = Category(name=category_name)
            block.categories.append(target_category)
            
        # Update indices
        indices_to_add = set(string_indices)
        target_category.line_indices = sorted(list(set(target_category.line_indices) | indices_to_add))
        
        # Remove from other categories
        for cat in block.categories:
            if cat is not target_category:
                cat.line_indices = [i for i in cat.line_indices if i not in indices_to_add]
        
        # Cleanup empty categories
        block.categories = [c for c in block.categories if c.line_indices]
        self.save()

    def merge_folders(self, source_id: str, target_id: str) -> None:
        """Move all contents from source folder to target folder and delete source."""
        if source_id == target_id: return
        
        source = self.find_virtual_folder(source_id)
        target = self.find_virtual_folder(target_id)
        
        if not source or not target: return
        
        log_info(f"Merging folder {source_id} ('{source.name}') into {target_id} ('{target.name}')")
        
        # Move subfolders
        for child in list(source.children):
            child.parent_id = target_id
            target.children.append(child)
        source.children = []
        
        # Move blocks
        for b_id in source.block_ids:
            target.block_ids.append(b_id)
        source.block_ids = []
        
        # Delete source
        self._remove_folder_from_anywhere(source_id)
        self.save()

    def find_virtual_folder(self, folder_id: str, search_list: Optional[List[VirtualFolder]] = None) -> Optional[VirtualFolder]:
        """Recursively find a virtual folder by ID."""
        if not self.project: return None
        if search_list is None:
            search_list = self.project.virtual_folders
            
        for folder in search_list:
            if folder.id == folder_id:
                return folder
            found = self.find_virtual_folder(folder_id, folder.children)
            if found:
                return found
        return None

    def is_descendant_of(self, potential_child_id: str, potential_parent_id: str) -> bool:
        """Check if folder A is a descendant of folder B."""
        if potential_child_id == potential_parent_id:
            return True
        
        parent = self.find_virtual_folder(potential_parent_id)
        if not parent:
            return False
            
        def search_recursive(folders: List[VirtualFolder]) -> bool:
            for f in folders:
                if f.id == potential_child_id:
                    return True
                if search_recursive(f.children):
                    return True
            return False
            
        return search_recursive(parent.children)

    def move_folder_to_folder(self, folder_id: str, target_folder_id: Optional[str]) -> bool:
        """
        Move a virtual folder to a new location with safety checks.
        Returns True if moved, False if skipped (e.g. circular reference).
        """
        if target_folder_id and self.is_descendant_of(target_folder_id, folder_id):
            log_warning(f"Circular reference detected: Cannot move folder '{folder_id}' into its descendant '{target_folder_id}'. Action ignored.")
            return False

        folder = self.find_virtual_folder(folder_id)
        if not folder:
            return False
            
        # 1. Remove from current parent
        self._remove_folder_from_anywhere(folder_id)
        
        # 2. Assign new parent
        folder.parent_id = target_folder_id
        if target_folder_id:
            dest = self.find_virtual_folder(target_folder_id)
            if dest:
                dest.children.append(folder)
        else:
            self.project.virtual_folders.append(folder)
            
        return True

    def move_block_to_folder(self, block_id: str, target_folder_id: Optional[str]) -> None:
        """Move a block from its current location to a new virtual folder."""
        # 1. Remove from current location
        self._remove_block_id_from_any_folder(block_id)
        
        # 2. Add to target
        if target_folder_id:
            target = self.find_virtual_folder(target_folder_id)
            if target:
                target.block_ids.append(block_id)
        else:
            root_blocks = self.project.metadata.get('root_block_ids', [])
            if block_id not in root_blocks:
                root_blocks.append(block_id)
                self.project.metadata['root_block_ids'] = root_blocks
        self.save()

    def _remove_block_id_from_any_folder(self, block_id: str, search_list: Optional[List[VirtualFolder]] = None) -> None:
        if search_list is None:
            if not self.project: return
            search_list = self.project.virtual_folders
            root_blocks = self.project.metadata.get('root_block_ids', [])
            if block_id in root_blocks:
                root_blocks.remove(block_id)
                self.project.metadata['root_block_ids'] = root_blocks

        for folder in search_list:
            if block_id in folder.block_ids:
                folder.block_ids.remove(block_id)
            self._remove_block_id_from_any_folder(block_id, folder.children)

    def get_all_block_indices_under_folder(self, folder_id: str) -> List[int]:
        """Collect indices of all project.blocks within a specific folder subtree."""
        folder = self.find_virtual_folder(folder_id)
        if not folder or not self.project:
            return []
            
        all_ids = []
        
        def collect_recursive(f):
            all_ids.extend(f.block_ids)
            for child in f.children:
                collect_recursive(child)
                
        collect_recursive(folder)
        
        # Convert UUID to index in project.blocks
        id_to_idx = {b.id: idx for idx, b in enumerate(self.project.blocks)}
        return [id_to_idx[bid] for bid in all_ids if bid in id_to_idx]

    def _remove_folder_from_anywhere(self, folder_id: str) -> bool:
        """Remove a folder from its current parent or root."""
        if not self.project: return False
        
        # Check root
        for i, f in enumerate(self.project.virtual_folders):
            if f.id == folder_id:
                self.project.virtual_folders.pop(i)
                return True
                
        # Check nested
        def remove_from_list(folders: List[VirtualFolder]) -> bool:
            for i, f in enumerate(folders):
                if f.id == folder_id:
                    folders.pop(i)
                    return True
                if remove_from_list(f.children):
                    return True
            return False
            
        return remove_from_list(self.project.virtual_folders)
