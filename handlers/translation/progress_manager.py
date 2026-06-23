# handlers/translation/progress_manager.py

from .base_translation_handler import BaseTranslationHandler
from utils.logging_utils import log_debug


class TranslationProgressManager(BaseTranslationHandler):
    """Manager class for translation progress and metadata serialization."""

    def __init__(self, main_handler):
        """Initialize a new instance."""
        super().__init__(main_handler)

    def save_progress_to_metadata(self, block_idx: int) -> None:
        """Saves translation progress for a single block into the block's project metadata."""
        if not self.mw.project_manager or not self.mw.project_manager.project:
            return

        block_map = self.mw.block_to_project_file_map
        proj_block_idx = block_map.get(block_idx, block_idx)

        if proj_block_idx < 0 or proj_block_idx >= len(self.mw.project_manager.project.blocks):
            return

        block = self.mw.project_manager.project.blocks[proj_block_idx]

        if block_idx in self.main_handler.translation_progress:
            prog = self.main_handler.translation_progress[block_idx]
            # Convert set to list for JSON serialization
            serialized_prog = {
                'completed_chunks': list(prog.get('completed_chunks', [])),
                'total_chunks': prog.get('total_chunks', 0),
                'source_items': prog.get('source_items', []),
                'temp_id_map': prog.get('temp_id_map', {}),
                'custom_user_header': prog.get('custom_user_header'),
                'custom_user_label': prog.get('custom_user_label'),
                'system_prompt_override': prog.get('system_prompt_override'),
                'session_reset_attempted': prog.get('session_reset_attempted', False)
            }
            block.metadata['translation_progress'] = serialized_prog
        else:
            if 'translation_progress' in block.metadata:
                del block.metadata['translation_progress']

        # Persist project changes
        self.mw.project_manager.save()

    def load_progress_from_metadata(self) -> None:
        """Loads translation progress for all blocks from their project metadata."""
        self.main_handler.translation_progress.clear()
        if not self.mw.project_manager or not self.mw.project_manager.project:
            return

        block_map = self.mw.block_to_project_file_map
        # Create a reverse map to go from project block index back to data block index
        rev_block_map = {proj_idx: data_idx for data_idx, proj_idx in block_map.items()}

        for proj_idx, block in enumerate(self.mw.project_manager.project.blocks):
            serialized_prog = block.metadata.get('translation_progress')
            if serialized_prog and isinstance(serialized_prog, dict):
                # Resolve the correct data block index
                data_block_idx = rev_block_map.get(proj_idx, proj_idx)

                # Reconstruct completed_chunks as a set
                completed_chunks = set(serialized_prog.get('completed_chunks', []))

                # Reconstruct temp_id_map, converting keys back to integers where possible
                raw_temp_map = serialized_prog.get('temp_id_map', {})
                temp_id_map = {}
                for k, v in raw_temp_map.items():
                    # Handle tuple conversion (in JSON, list was saved)
                    if isinstance(v, list) and len(v) == 2:
                        val = (v[0], v[1])
                    else:
                        val = v

                    try:
                        temp_id_map[int(k)] = val
                    except (ValueError, TypeError):
                        temp_id_map[k] = val

                self.main_handler.translation_progress[data_block_idx] = {
                    'completed_chunks': completed_chunks,
                    'total_chunks': serialized_prog.get('total_chunks', 0),
                    'source_items': serialized_prog.get('source_items', []),
                    'temp_id_map': temp_id_map,
                    'custom_user_header': serialized_prog.get('custom_user_header'),
                    'custom_user_label': serialized_prog.get('custom_user_label'),
                    'system_prompt_override': serialized_prog.get('system_prompt_override'),
                    'session_reset_attempted': serialized_prog.get('session_reset_attempted', False)
                }
        log_debug(f"Loaded translation progress for {len(self.main_handler.translation_progress)} blocks from project metadata.")
