"""Block registration, sync, paths, and archive cache for ProjectManager."""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any, List, Optional, Union

from utils.logging_utils import log_info, log_warning, log_error, log_debug

from core.containers import ContainerManager
from core.project_models import Block


class BlocksMixin:
    """add_block, sync_project_files, import_directory, paths, archive cache."""

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
            
            # Determine virtual path parts
            rel_path = source_rel_path
            if rel_path.startswith('.extracted/sources/'):
                rel_path = rel_path[len('.extracted/sources/'):]
            elif rel_path.startswith(self.SOURCES_DIR + '/'):
                rel_path = rel_path[len(self.SOURCES_DIR) + 1:]
            
            path_parts = Path(rel_path).parent.as_posix().split('/')
            if path_parts == ['.'] or path_parts == ['']:
                path_parts = []
            
            if block.internal_key:
                path_parts.append(Path(rel_path).name)
                internal_parts = block.internal_key.replace('\\', '/').split('/')
                if len(internal_parts) > 1:
                    path_parts.extend(internal_parts[:-1])

            # Ensure it's tracked in virtual structure
            if path_parts:
                current_parent_id = None
                for part in path_parts:
                    if not part: continue
                    folder = self.create_virtual_folder(part, current_parent_id)
                    current_parent_id = folder.id
                
                if current_parent_id:
                    last_folder = self.find_virtual_folder(current_parent_id)
                    if last_folder and block.id not in last_folder.block_ids:
                        last_folder.block_ids.append(block.id)
            else:
                if 'root_block_ids' not in self.project.metadata:
                    self.project.metadata['root_block_ids'] = []
                if block.id not in self.project.metadata['root_block_ids']:
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
        
        if not source_path or not Path(source_path).exists():
            log_warning("Source path is invalid or missing during sync.")
            return

        supported_extensions = {'.json', '.txt', '.bmg', '.arc', '.rarc', '.ark', '.bfn'}
        existing_blocks = {b.source_file: b for b in self.project.blocks}
        found_sources = set()
        

        def process_source_file(filepath: Path, rel_path: str):
            """Process source file."""
            if filepath.suffix.lower() in {'.arc', '.rarc', '.ark'}:
                archive_rel_path = rel_path
                try:
                    raw = filepath.read_bytes()
                    container = ContainerManager.open(raw)
                    if container is None:
                        log_warning(f"Unsupported archive format during sync: {filepath}")
                        return

                    inner_extensions = {'.json', '.txt', '.bmg', '.bfn'}
                    for inner_path in container.list_files():
                        if Path(inner_path).suffix.lower() in inner_extensions:
                            block_src_rel = f".extracted/sources/{archive_rel_path}/{inner_path}"
                            block_trans_rel = f".extracted/translation/{archive_rel_path}/{inner_path}"
                            found_sources.add(block_src_rel)

                            if block_src_rel not in existing_blocks:
                                block = self.add_block(
                                    name=Path(inner_path).stem,
                                    source_file_path=block_src_rel,
                                    translation_file_path=block_trans_rel
                                )
                                if block:
                                    block.metadata['is_archive_member'] = True
                                    block.metadata['archive_rel_path'] = archive_rel_path
                                    block.metadata['archive_file_name'] = inner_path
                            else:
                                block = existing_blocks[block_src_rel]
                                block.metadata['is_archive_member'] = True
                                block.metadata['archive_rel_path'] = archive_rel_path
                                block.metadata['archive_file_name'] = inner_path
                except Exception as e:
                    log_error(f"Failed to process archive {filepath}: {e}", exc_info=True)
            else:
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
                                    display_name = full_sub_name.replace('\\', '/').split('/')[-1]
                                    self.add_block(
                                        name=display_name,
                                        source_file_path=rel_path,
                                        translation_file_path=rel_path,
                                        internal_key=full_sub_name
                                    )
                                added_sub_blocks = True
                        except Exception as e:
                            log_debug(f"Sync: Failed to explode {rel_path}: {e}")

                    if not added_sub_blocks:
                        trans_rel_path = rel_path
                        if not is_directory_mode and translation_path:
                            trans_rel_path = Path(translation_path).name
                        self.add_block(
                            name=filepath.stem,
                            source_file_path=rel_path,
                            translation_file_path=trans_rel_path
                        )

        if is_directory_mode:
            root_path = Path(source_path)
            for filepath in root_path.rglob('*'):
                if filepath.is_file() and filepath.suffix.lower() in supported_extensions:
                    rel_path = filepath.relative_to(root_path).as_posix()
                    process_source_file(filepath, rel_path)
        else:
            filepath = Path(source_path)
            if filepath.is_file() and filepath.suffix.lower() in supported_extensions:
                rel_path = filepath.name
                process_source_file(filepath, rel_path)
                    
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
            return str(relative_path)

        # SPECIAL CASE: if path starts with '.extracted/', it is located inside the temporary directory!
        rel_str = str(relative_path).replace('\\', '/')
        if rel_str.startswith('.extracted/'):
            if self.project:
                import tempfile
                temp_dir = Path(tempfile.gettempdir()) / "picoripi" / self.project.id
                return str(temp_dir / relative_path)
            else:
                return str(Path(self.project_dir) / relative_path) if self.project_dir else str(relative_path)
            
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

    def cleanup_temp_dir(self) -> None:
        """Clean up temporary resources (no-op since we use in-memory containers)."""
        self.clear_archive_cache()

    def get_archive_container(self, archive_rel_path: str, is_translation: bool = False) -> ContainerManager:
        """
        Get or open an archive container from cache or file.
        """
        archive_abs_path = self.get_absolute_path(archive_rel_path, is_translation=is_translation)
        
        # Fallback to source if translation doesn't exist yet
        if is_translation and not Path(archive_abs_path).exists():
            archive_abs_path = self.get_absolute_path(archive_rel_path, is_translation=False)
            
        if not Path(archive_abs_path).exists():
            raise FileNotFoundError(f"Archive not found: {archive_abs_path}")
            
        cache_key = (archive_rel_path, is_translation)
        if cache_key in self._archive_cache:
            self._archive_cache.move_to_end(cache_key)
            return self._archive_cache[cache_key]
            
        raw_archive = Path(archive_abs_path).read_bytes()
        container = ContainerManager.open(raw_archive)
        if not container:
            raise ValueError(f"Failed to open archive: {archive_abs_path}")
            
        self._archive_cache[cache_key] = container
        if len(self._archive_cache) > 10:
            self._archive_cache.popitem(last=False)
        return container

    def clear_archive_cache(self) -> None:
        """Remove archive cache."""
        self._archive_cache.clear()

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
