"""Virtual folders and category grouping for ProjectManager."""
from __future__ import annotations

from pathlib import Path
from typing import List, Optional

from utils.logging_utils import log_info, log_warning, log_debug

from core.project_models import Category, VirtualFolder


class FoldersMixin:
    """Virtual folders, move block/folder, find, merge."""

    def _migrate_file_structure_to_virtual_folders(self) -> None:
        """Build virtual folder structure from physical file paths of blocks."""
        if not self.project: return

        folder_map = {} # path -> VirtualFolder
        root_folders = []

        # Sort blocks by name for consistent initial order
        sorted_blocks = sorted(self.project.blocks, key=lambda b: b.source_file)

        for block in sorted_blocks:
            rel_path = block.source_file
            if rel_path.startswith('.extracted/sources/'):
                rel_path = rel_path[len('.extracted/sources/'):]
            elif rel_path.startswith(self.SOURCES_DIR + '/'):
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
            if rel_p.startswith('.extracted/sources/'):
                rel_p = rel_p[len('.extracted/sources/'):]
            elif rel_p.startswith(self.SOURCES_DIR + '/'):
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
            """Search recursive."""
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
        """Internal helper to remove block id from any folder."""
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
            """Collect recursive."""
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
            """Remove from list."""
            for i, f in enumerate(folders):
                if f.id == folder_id:
                    folders.pop(i)
                    return True
                if remove_from_list(f.children):
                    return True
            return False
            
        return remove_from_list(self.project.virtual_folders)
