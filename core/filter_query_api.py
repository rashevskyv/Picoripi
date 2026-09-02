from typing import List, Dict, Tuple, Optional, Any, Union

class FilterQueryAPI:
    """Centralized filter and index query API for data filtering and aggregation."""
    def __init__(self, main_window: Any, data_processor: Any = None):
        """Initialize the query API."""
        self.mw = main_window
        self._data_processor = data_processor

    @property
    def data_store(self):
        return self.mw.data_store

    @property
    def data_processor(self):
        if self._data_processor is not None:
            return self._data_processor
        return getattr(self.mw, 'data_processor', None)

    @property
    def project_manager(self):
        return getattr(self.mw, 'project_manager', None)

    @property
    def current_game_rules(self):
        return getattr(self.mw, 'current_game_rules', None)

    def get_filtered_string_indices(
        self,
        block_idx: int,
        category_name: Optional[str] = None,
        hide_categorized: bool = False,
        hide_translated: bool = False,
        show_overrides_only: bool = False,
        show_unsaved_only: bool = False,
        show_warnings_only: bool = False,
        active_warning_filters: Optional[List[str]] = None,
        detection_config: Optional[Dict[str, bool]] = None,
        hide_empty_strings: bool = False,
        data_source: Optional[List[Any]] = None,
        virtual_mappings: Optional[List[Tuple[int, int]]] = None
    ) -> Tuple[List[Union[int, Tuple[int, int]]], Dict[int, str]]:
        """
        Get the list of filtered string indices and placeholder texts for collapsed empty lines.
        
        Returns:
            Tuple[target_indices, placeholder_texts]
        """
        if active_warning_filters is None:
            active_warning_filters = []
        if detection_config is None:
            detection_config = {}
        if data_source is None:
            data_source = getattr(self.data_store, 'data', []) or []

        is_virtual = block_idx in (-2, -3, -4, -5)

        # 1. Determine base target indices
        target_indices = []
        if is_virtual:
            if virtual_mappings is not None:
                target_indices = list(virtual_mappings)
            else:
                target_indices = list(getattr(self.data_store, 'virtual_mappings', []))
        elif category_name and self.project_manager and self.project_manager.project:
            pm = self.project_manager
            block_map = getattr(self.data_store, 'block_to_project_file_map', {})
            # Fallback to direct attribute on mw if not in store
            if not block_map:
                block_map = getattr(self.mw, 'block_to_project_file_map', {})
            proj_b_idx = block_map.get(block_idx, block_idx)
            if isinstance(proj_b_idx, int) and proj_b_idx < len(pm.project.blocks):
                block = pm.project.blocks[proj_b_idx]
                category = next((c for c in block.categories if c.name == category_name), None)
                if category:
                    target_indices = list(category.line_indices)

        if not is_virtual and not target_indices and not category_name:
            if 0 <= block_idx < len(data_source) and isinstance(data_source[block_idx], list):
                target_indices = list(range(len(data_source[block_idx])))
                # Filter out categorized if "Hide moved" (hide_categorized) is enabled
                if hide_categorized:
                    categorized_indices = self.data_processor.get_categorized_set(block_idx)
                    target_indices = [idx for idx in target_indices if idx not in categorized_indices]

        # 2. Re-verify indices are within bounds
        if is_virtual:
            target_indices = [
                i for i in target_indices
                if isinstance(i, tuple) and len(i) == 2 and
                   0 <= i[0] < len(data_source) and
                   0 <= i[1] < len(data_source[i[0]])
            ]
        else:
            if 0 <= block_idx < len(data_source) and isinstance(data_source[block_idx], list):
                target_indices = [i for i in target_indices if 0 <= i < len(data_source[block_idx])]
            else:
                target_indices = []

        # 3. Apply filters
        if hide_translated:
            if is_virtual:
                target_indices = [
                    idx for idx in target_indices
                    if idx[1] not in self.data_processor.get_translated_set(idx[0])
                ]
            else:
                trans_set = self.data_processor.get_translated_set(block_idx)
                target_indices = [idx for idx in target_indices if idx not in trans_set]

        if show_overrides_only:
            if is_virtual:
                target_indices = [
                    idx for idx in target_indices
                    if idx[1] in self.data_processor.get_overrides_set(idx[0])
                ]
            else:
                overrides_set = self.data_processor.get_overrides_set(block_idx)
                target_indices = [idx for idx in target_indices if idx in overrides_set]

        if show_unsaved_only:
            if is_virtual:
                target_indices = [
                    idx for idx in target_indices
                    if idx[1] in self.data_processor.get_unsaved_set(idx[0])
                ]
            else:
                unsaved_set = self.data_processor.get_unsaved_set(block_idx)
                target_indices = [idx for idx in target_indices if idx in unsaved_set]

        if show_warnings_only:
            if is_virtual:
                target_indices = [
                    idx for idx in target_indices
                    if idx[1] in self.data_processor.get_warnings_matching_set(idx[0], active_warning_filters, detection_config)
                ]
            else:
                matching_set = self.data_processor.get_warnings_matching_set(block_idx, active_warning_filters, detection_config)
                target_indices = [idx for idx in target_indices if idx in matching_set]

        # 4. Collapse empty strings if enabled
        placeholder_texts = {}
        if hide_empty_strings:
            collapsed_indices = []
            streak_indices = []

            def append_empty_streak(streak):
                if len(streak) <= 3:
                    collapsed_indices.extend(streak)
                    return
                collapsed_indices.append(streak[0])
                collapsed_indices.append(-1)
                hidden = streak[1:-1]
                start_idx = hidden[0][1] if isinstance(hidden[0], tuple) else hidden[0]
                end_idx = hidden[-1][1] if isinstance(hidden[-1], tuple) else hidden[-1]
                placeholder_texts[len(collapsed_indices) - 1] = (
                    f"[{start_idx}-{end_idx}] {len(hidden)} empty line(s)"
                )
                collapsed_indices.append(streak[-1])

            for idx in target_indices:
                b_idx = block_idx
                s_idx = idx
                if isinstance(idx, tuple):
                    b_idx, s_idx = idx

                empty_set = self.data_processor.get_empty_set(b_idx)
                is_empty = s_idx in empty_set

                if is_empty:
                    streak_indices.append(idx)
                else:
                    if streak_indices:
                        append_empty_streak(streak_indices)
                        streak_indices = []
                    collapsed_indices.append(idx)
            if streak_indices:
                append_empty_streak(streak_indices)
            target_indices = collapsed_indices

        return target_indices, placeholder_texts

    def _problem_counts_for_rows(
        self,
        mappings: Optional[List[Any]],
        detection_config: Dict[str, bool],
        problem_definitions: Dict[str, Any],
    ) -> Dict[str, int]:
        """Count enabled problems on an explicit set of (block, string) rows."""
        problem_counts = {pid: 0 for pid in problem_definitions.keys()}
        mapping_set = set()
        list_sel = getattr(self.mw, "list_selection_handler", None)
        for mapping in mappings or ():
            if isinstance(mapping, (tuple, list)) and len(mapping) == 2:
                try:
                    mapping_set.add((int(mapping[0]), int(mapping[1])))
                except (TypeError, ValueError):
                    continue
            elif hasattr(mapping, "get"):
                bmg_id = mapping.get("bmg_id")
                if list_sel and bmg_id:
                    indices = list_sel.resolve_bmg_id_to_indices(bmg_id)
                    if indices:
                        mapping_set.add(indices)
        if not mapping_set:
            return problem_counts
        for (b_idx, s_idx, _subline_idx), problems in self.data_store.problems_per_subline.items():
            if (b_idx, s_idx) not in mapping_set:
                continue
            for p_id in problems:
                if detection_config.get(p_id, True) and p_id in problem_counts:
                    problem_counts[p_id] += 1
        return problem_counts

    def get_aggregated_problems_for_block(
        self,
        block_idx: int,
        pre_aggregated_counts: Optional[Dict[int, Dict[str, int]]] = None,
        category_name: Optional[str] = None,
        chapter_id: Optional[int] = None,
        speaker_name: Optional[str] = None,
        speaker_mappings: Optional[List[Tuple[int, int]]] = None,
        detection_config: Optional[Dict[str, bool]] = None,
        chapter_mappings: Optional[List[Any]] = None,
        row_mappings: Optional[List[Any]] = None,
    ) -> Dict[str, int]:
        """Get aggregated problems counts for tree nodes."""
        if detection_config is None:
            detection_config = {}

        problem_counts = {}
        if not self.current_game_rules:
            return problem_counts

        problem_definitions = self.current_game_rules.get_problem_definitions() or {}
        is_chapter = (block_idx == -2)
        is_speaker = (block_idx == -3)

        if row_mappings is not None:
            return self._problem_counts_for_rows(
                row_mappings, detection_config, problem_definitions
            )

        if not is_chapter and not is_speaker and not (0 <= block_idx < len(self.data_store.data)):
            return problem_counts

        problem_counts = {pid: 0 for pid in problem_definitions.keys()}

        if is_speaker:
            spk_mappings = list(speaker_mappings or [])
            if not spk_mappings and speaker_name and self.project_manager and self.project_manager.project:
                for b_idx, block in enumerate(self.project_manager.project.blocks):
                    assignments = block.metadata.get("character_assignments", {})
                    for s_idx_str, c_name in assignments.items():
                        if c_name == speaker_name:
                            spk_mappings.append((b_idx, int(s_idx_str)))
            return self._problem_counts_for_rows(
                spk_mappings, detection_config, problem_definitions
            )

        if is_chapter:
            mappings = chapter_mappings
            if mappings is None:
                mappings = []
                if chapter_id is not None:
                    # Resolve using prompt_composer if available
                    bl_updater = getattr(self.mw.ui_updater, 'block_list_updater', None) if hasattr(self.mw, 'ui_updater') else None
                    if bl_updater and isinstance(getattr(bl_updater, '_chapter_mappings_cache', None), dict) and chapter_id in bl_updater._chapter_mappings_cache:
                        mappings = bl_updater._chapter_mappings_cache[chapter_id]
                    else:
                        composer = getattr(self.mw, "translation_handler", None)
                        if composer and hasattr(composer, "prompt_composer"):
                            client = composer.prompt_composer._get_mempalace_client()
                            if client and hasattr(client, 'get_chapter_mappings'):
                                wing_name = composer.prompt_composer._get_wing_name()
                                mappings = client.get_chapter_mappings(wing_name, chapter_id)
            return self._problem_counts_for_rows(
                mappings, detection_config, problem_definitions
            )
 
        if pre_aggregated_counts is not None and category_name is None:
            block_counts = pre_aggregated_counts.get(block_idx, {})
            return {pid: block_counts.get(pid, 0) for pid in problem_definitions.keys()}
 
        self.data_processor.ensure_index_warnings(block_idx)
        warn_dict = self.data_store._index_warnings.get(block_idx, {})
 
        target_indices = None
        if category_name:
            if self.project_manager and self.project_manager.project:
                pm = self.project_manager
                block_map = getattr(self.data_store, 'block_to_project_file_map', {})
                if not block_map:
                    block_map = getattr(self.mw, 'block_to_project_file_map', {})
                proj_b_idx = block_map.get(block_idx, block_idx)
                if proj_b_idx < len(pm.project.blocks):
                    block = pm.project.blocks[proj_b_idx]
                    category = next((c for c in block.categories if c.name == category_name), None)
                    if category:
                        target_indices = set(category.line_indices)
 
        for p_id in problem_counts.keys():
            if not detection_config.get(p_id, True):
                continue
            if p_id in warn_dict:
                if target_indices is not None:
                    count = sum(1 for s_idx, _ in warn_dict[p_id] if s_idx in target_indices)
                    problem_counts[p_id] = count
                else:
                    problem_counts[p_id] = len(warn_dict[p_id])
 
        return problem_counts
 
    def is_project_block_unsaved(self, project_block_idx: int) -> bool:
        """Check if project block index is unsaved."""
        block_map = getattr(self.data_store, 'block_to_project_file_map', {})
        if not isinstance(block_map, dict):
            block_map = getattr(self.mw, 'block_to_project_file_map', {})

        if isinstance(block_map, dict) and block_map:
            return any(
                block_map.get(data_idx) == project_block_idx
                for data_idx in self.data_store.unsaved_block_indices
            )
        return project_block_idx in self.data_store.unsaved_block_indices

    def folder_has_unsaved_blocks(self, folder: Any, project: Any, id_to_idx: Dict[str, int]) -> bool:
        """Helper to recursively check if folder or its children have unsaved blocks."""
        for b_id in folder.block_ids:
            idx = id_to_idx.get(b_id)
            if idx is not None and self.is_project_block_unsaved(idx):
                return True
        for child in folder.children:
            if self.folder_has_unsaved_blocks(child, project, id_to_idx):
                return True
        return False
