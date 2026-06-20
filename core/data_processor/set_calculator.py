from typing import Any, List, Set

class SetCalculator:
    """Calculates and caches various string status sets (empty, translated, unsaved, overrides, etc.)."""
    def __init__(self, data_processor: Any):
        """Initialize a new instance."""
        self.dsp = data_processor
        self.mw = data_processor.mw

    def get_empty_set(self, block_idx: int) -> Set[int]:
        """Get or build the set of empty string indices for the given block."""
        store = self.mw.data_store
        if block_idx < 0 or not store.data or block_idx >= len(store.data):
            return set()

        if block_idx not in store._index_empty:
            empty_set = set()
            block_data = store.data[block_idx]
            if isinstance(block_data, list):
                for s_idx in range(len(block_data)):
                    orig_text = self.dsp._get_string_from_source(block_idx, s_idx, store.data, "readonly")
                    edited_text, _ = self.dsp.get_current_string_text(block_idx, s_idx)
                    is_empty = (not orig_text or not orig_text.strip()) and (not edited_text or not str(edited_text).strip())
                    if is_empty:
                        empty_set.add(s_idx)
            store._index_empty[block_idx] = empty_set

        return store._index_empty[block_idx]

    def get_translated_set(self, block_idx: int) -> Set[int]:
        """Get or build the set of translated string indices for the given block."""
        store = self.mw.data_store
        if block_idx < 0 or not store.data or block_idx >= len(store.data):
            return set()

        if block_idx not in store._index_translated:
            trans_set = set()
            block_data = store.data[block_idx]
            if isinstance(block_data, list):
                for s_idx in range(len(block_data)):
                    if self.dsp.is_string_translated(block_idx, s_idx):
                        trans_set.add(s_idx)
            store._index_translated[block_idx] = trans_set

        return store._index_translated[block_idx]

    def get_unsaved_set(self, block_idx: int) -> Set[int]:
        """Get or build the set of unsaved string indices for the given block."""
        store = self.mw.data_store
        if block_idx not in store._index_unsaved:
            unsaved_set = set()
            for b_idx, s_idx in store.edited_data.keys():
                if b_idx == block_idx:
                    unsaved_set.add(s_idx)
            store._index_unsaved[block_idx] = unsaved_set

        return store._index_unsaved[block_idx]

    def get_overrides_set(self, block_idx: int) -> Set[int]:
        """Get or build the set of override string indices for the given block."""
        store = self.mw.data_store
        if block_idx < 0 or not store.data or block_idx >= len(store.data):
            return set()

        if block_idx not in store._index_overrides:
            overrides_set = set()
            default_font = getattr(self.mw, 'default_font_file', None)
            max_width = getattr(self.mw, 'game_dialog_max_width_pixels', None)
            metadata = getattr(self.mw, 'string_metadata', {})

            for (b_idx, s_idx), meta in metadata.items():
                if b_idx == block_idx:
                    has_font = "font_file" in meta and meta["font_file"] != default_font and meta["font_file"] != "default"
                    has_width = "width" in meta and meta["width"] != max_width and meta["width"] != 0
                    if has_font or has_width:
                        overrides_set.add(s_idx)
            store._index_overrides[block_idx] = overrides_set

        return store._index_overrides[block_idx]

    def get_categorized_set(self, block_idx: int) -> Set[int]:
        """Get or build the set of categorized string indices for the given block."""
        store = self.mw.data_store
        if block_idx < 0:
            return set()

        if block_idx not in store._index_categorized:
            categorized_set = set()
            pm = getattr(self.mw, 'project_manager', None)
            if pm and pm.project:
                block_map = getattr(self.mw, 'block_to_project_file_map', {})
                proj_b_idx = block_map.get(block_idx, block_idx)
                if isinstance(proj_b_idx, int) and proj_b_idx < len(pm.project.blocks):
                    block = pm.project.blocks[proj_b_idx]
                    categorized_set.update(block.get_categorized_line_indices())
            store._index_categorized[block_idx] = categorized_set

        return store._index_categorized[block_idx]

    def ensure_index_warnings(self, block_idx: int):
        """Helper to build warnings index if it is missing."""
        store = self.mw.data_store
        if block_idx not in store._index_warnings:
            warn_dict = {}
            for (b_idx, s_idx, subline_idx), problems in store.problems_per_subline.items():
                if b_idx == block_idx:
                    for p_id in problems:
                        if p_id not in warn_dict:
                            warn_dict[p_id] = set()
                        warn_dict[p_id].add((s_idx, subline_idx))
            store._index_warnings[block_idx] = warn_dict

    def get_warnings_matching_set(self, block_idx: int, active_filters: List[str], detection_config: dict) -> Set[int]:
        """Get the set of string indices matching active or enabled warnings."""
        store = self.mw.data_store
        if block_idx < 0:
            return set()

        self.ensure_index_warnings(block_idx)
        warn_dict = store._index_warnings[block_idx]

        matching_strings = set()
        if active_filters:
            for p_id in active_filters:
                if p_id in warn_dict:
                    matching_strings.update(s_idx for s_idx, _ in warn_dict[p_id])
        else:
            for p_id, occurrences in warn_dict.items():
                if detection_config.get(p_id, True):
                    matching_strings.update(s_idx for s_idx, _ in occurrences)
        return matching_strings
