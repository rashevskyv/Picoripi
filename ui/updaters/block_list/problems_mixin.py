"""Problem aggregation, tooltips, and physical/virtual folder items."""
from __future__ import annotations

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import QTreeWidgetItem, QStyle
from core.i18n import tr

class ProblemsMixin:
    """Problem aggregation, tooltips, and physical/virtual folder items."""

    def _get_aggregated_problems_for_block(self, block_idx: int, pre_aggregated_counts: dict = None, category_name: str = None, chapter_id: int = None, speaker_name: str = None, speaker_mappings: list = None, chapter_mappings: list = None, row_mappings: list = None) -> dict:
        """Internal helper to get the aggregated problems for block using central FilterQueryAPI."""
        detection_config = getattr(self.mw, 'detection_enabled', {})
        return self.mw.filter_query_api.get_aggregated_problems_for_block(
            block_idx=block_idx,
            pre_aggregated_counts=pre_aggregated_counts,
            category_name=category_name,
            chapter_id=chapter_id,
            speaker_name=speaker_name,
            speaker_mappings=speaker_mappings,
            detection_config=detection_config,
            chapter_mappings=chapter_mappings,
            row_mappings=row_mappings,
        )

    def _apply_issues_and_tooltip(self, item: QTreeWidgetItem, base_display_name: str, problem_counts: dict, problem_definitions: dict):
        """Internal helper to apply issues and tooltip."""
        display_name_with_issues = base_display_name
        tooltip_lines = []
        total_issues = sum(problem_counts.values())

        sorted_problem_ids_for_display = sorted(
            problem_counts.keys(),
            key=lambda pid: problem_definitions.get(pid, {}).get("priority", 99)
        )

        for problem_id in sorted_problem_ids_for_display:
            count_sublines = problem_counts[problem_id]
            if count_sublines > 0:
                prob_def = problem_definitions.get(problem_id, {})
                full_name = prob_def.get("name", problem_id)
                desc = prob_def.get("description", "")
                tooltip_lines.append(f"<b>{full_name}</b>: {count_sublines} sublines<br><i>{desc}</i>")

        if total_issues > 0:
            display_name_with_issues = f"{base_display_name} ({total_issues})"

        item.setText(0, display_name_with_issues)

        item.setData(0, Qt.ItemDataRole.UserRole + 20, dict(problem_counts or {}))
        self._stamp_item_paint_stats(item)

        if tooltip_lines:
            item.setToolTip(0, "<br><br>".join(tooltip_lines))
        else:
            item.setToolTip(0, tr(''))

    def _stamp_item_paint_stats(self, item: QTreeWidgetItem) -> None:
        """Store unsaved/progress flags so the delegate does not recompute on paint."""
        mw = self.mw
        ds = getattr(mw, "data_store", None)
        dsp = getattr(mw, "data_processor", None)
        pm = getattr(mw, "project_manager", None)
        project = pm.project if pm else None
        block_idx = item.data(0, Qt.ItemDataRole.UserRole)
        category_name = item.data(0, Qt.ItemDataRole.UserRole + 10)
        merged_folder_ids = item.data(0, Qt.ItemDataRole.UserRole + 2)
        mappings = item.data(0, Qt.ItemDataRole.UserRole + 13)
        unsaved_blocks = getattr(ds, "unsaved_block_indices", set()) if ds else set()
        edited_keys = getattr(ds, "edited_data", {}) if ds else {}
        block_map = getattr(mw, "block_to_project_file_map", {}) or {}

        unsaved = False
        if category_name and project and block_idx is not None:
            data_indices = [d_idx for d_idx, p_idx in block_map.items() if p_idx == block_idx] or [block_idx]
            if 0 <= block_idx < len(project.blocks):
                category = next(
                    (c for c in project.blocks[block_idx].categories if c.name == category_name),
                    None,
                )
                if category:
                    unsaved = any(
                        (d_idx, l_idx) in edited_keys
                        for d_idx in data_indices
                        for l_idx in category.line_indices
                    )
        elif merged_folder_ids and pm:
            all_p = set()
            for folder_id in merged_folder_ids:
                all_p.update(pm.get_all_block_indices_under_folder(folder_id))
            if block_map:
                unsaved = any(block_map.get(data_idx) in all_p for data_idx in unsaved_blocks)
            else:
                unsaved = any(data_idx in all_p for data_idx in unsaved_blocks)
        elif isinstance(block_idx, int) and block_idx >= 0:
            if block_map:
                unsaved = any(block_map.get(data_idx) == block_idx for data_idx in unsaved_blocks)
            else:
                unsaved = block_idx in unsaved_blocks
        elif isinstance(mappings, (list, tuple)) and edited_keys:
            unsaved = any(
                (int(row[0]), int(row[1])) in edited_keys
                for row in mappings
                if isinstance(row, (list, tuple)) and len(row) == 2
            )

        percentage = 0.0
        try:
            if dsp is None:
                pass
            elif category_name and project and isinstance(block_idx, int):
                if 0 <= block_idx < len(project.blocks):
                    category = next(
                        (c for c in project.blocks[block_idx].categories if c.name == category_name),
                        None,
                    )
                    if category and category.line_indices:
                        lines = set(category.line_indices)
                        needs = dsp.get_needs_translation_set(block_idx)
                        translated = dsp.get_translated_set(block_idx)
                        total_needs = len(lines & needs)
                        if total_needs > 0:
                            percentage = len(lines & translated) / total_needs
            elif isinstance(mappings, (list, tuple)) and mappings:
                status_sets = {}
                total_needs = 0
                translated_n = 0
                for row in mappings:
                    if not (isinstance(row, (list, tuple)) and len(row) == 2):
                        continue
                    b_idx, s_idx = int(row[0]), int(row[1])
                    if b_idx not in status_sets:
                        status_sets[b_idx] = (
                            dsp.get_needs_translation_set(b_idx),
                            dsp.get_translated_set(b_idx),
                        )
                    if s_idx in status_sets[b_idx][0]:
                        total_needs += 1
                        if s_idx in status_sets[b_idx][1]:
                            translated_n += 1
                if total_needs > 0:
                    percentage = translated_n / total_needs
            elif isinstance(block_idx, int) and block_idx >= 0 and ds and ds.data and block_idx < len(ds.data):
                block_data = ds.data[block_idx]
                if isinstance(block_data, list) and block_data:
                    needs = dsp.get_needs_translation_set(block_idx)
                    if needs:
                        percentage = len(dsp.get_translated_set(block_idx)) / len(needs)
        except Exception:
            percentage = 0.0

        item.setData(0, Qt.ItemDataRole.UserRole + 21, bool(unsaved))
        item.setData(0, Qt.ItemDataRole.UserRole + 22, float(percentage))

    def refresh_block_tree_indicators(self, block_idx: int | None = None) -> None:
        """Refresh stars/progress/warnings on existing items without rebuilding the tree."""
        if not hasattr(self.mw, "block_list_widget") or not self.mw.block_list_widget:
            return
        if block_idx is not None:
            self.update_block_item_text_with_problem_count(block_idx)
            return
        from PyQt6.QtWidgets import QTreeWidgetItemIterator
        iterator = QTreeWidgetItemIterator(self.mw.block_list_widget)
        while iterator.value():
            item = iterator.value()
            kind = item.data(0, Qt.ItemDataRole.UserRole)
            mappings = item.data(0, Qt.ItemDataRole.UserRole + 13)
            if isinstance(kind, int) and kind < 0 and isinstance(mappings, (list, tuple)):
                self._apply_virtual_issue_indicators(item)
            else:
                self._stamp_item_paint_stats(item)
            iterator += 1
        self.mw.block_list_widget.viewport().update()

    def _create_block_tree_item(self, block_idx: int, problem_definitions: dict, pre_aggregated_counts: dict = None) -> QTreeWidgetItem:
        """Helper to create a single block tree item with issue counts and tooltips."""
        base_display_name = self.mw.data_store.block_names.get(str(block_idx), f"Block {block_idx}")
        display_name_with_ext = self._get_block_display_name_with_ext(block_idx, base_display_name)
        block_problem_counts = self._get_aggregated_problems_for_block(block_idx, pre_aggregated_counts)

        item = self.mw.block_list_widget.create_item(display_name_with_ext, block_idx, Qt.ItemDataRole.UserRole)
        self._register_item_in_cache(item)
        self._apply_issues_and_tooltip(item, display_name_with_ext, block_problem_counts, problem_definitions)

        item.setData(0, Qt.ItemDataRole.UserRole + 4, display_name_with_ext)
        item.setData(0, Qt.EditRole, base_display_name)

        # Add categories as children
        if hasattr(self.mw, 'project_manager') and self.mw.project_manager and self.mw.project_manager.project:
            pm = self.mw.project_manager
            block_map = getattr(self.mw, 'block_to_project_file_map', {})
            proj_b_idx = block_map.get(block_idx, block_idx)
            if proj_b_idx < len(pm.project.blocks):
                block = pm.project.blocks[proj_b_idx]
                for cat in block.categories:
                    cat_item = QTreeWidgetItem([cat.name])
                    cat_item.setFlags(cat_item.flags() | Qt.ItemFlag.ItemIsEditable)
                    cat_item.setData(0, Qt.ItemDataRole.UserRole, block_idx)
                    self._register_item_in_cache(cat_item)
                    cat_item.setData(0, Qt.ItemDataRole.UserRole + 10, cat.name)
                    cat_item.setData(0, Qt.ItemDataRole.UserRole + 4, cat.name)
                    cat_item.setData(0, Qt.EditRole, cat.name)
                    self._set_item_style_icon(cat_item, 0, QStyle.StandardPixmap.SP_FileDialogDetailedView)

                    cat_problem_counts = self._get_aggregated_problems_for_block(block_idx, pre_aggregated_counts=None, category_name=cat.name)
                    self._apply_issues_and_tooltip(cat_item, cat.name, cat_problem_counts, problem_definitions)

                    item.addChild(cat_item)

        return item

    def _is_project_block_unsaved(self, project_block_idx: int) -> bool:
        """Check if project block index is unsaved using central FilterQueryAPI."""
        return self.mw.filter_query_api.is_project_block_unsaved(project_block_idx)

    def _folder_has_unsaved_blocks(self, folder, project, id_to_idx: dict) -> bool:
        """Helper to recursively check if folder or its children have unsaved blocks using central FilterQueryAPI."""
        return self.mw.filter_query_api.folder_has_unsaved_blocks(folder, project, id_to_idx)

    def _add_virtual_folder_to_tree(self, parent_item, folder, problem_definitions, current_selection_block_idx, pre_aggregated_counts: dict = None, folder_id_to_select=None, id_to_idx=None):
        """Recursively add virtual folders and their blocks to the tree with folder compaction (GitHub style)."""
        project = self.mw.project_manager.project
        if not project: return

        if id_to_idx is None:
            id_to_idx = {b.id: idx for idx, b in enumerate(project.blocks)}
        if getattr(self.mw.data_store, 'show_unsaved_blocks_only', False) is True:
            if not self._folder_has_unsaved_blocks(folder, project, id_to_idx):
                return

        is_expanded = folder.is_expanded
        display_name = folder.name or "Unnamed Folder"
        merged_folder_ids = [folder.id]
        compaction_type = 0 # 0: None, 1: Folder/Folder, 2: Folder/Block
        block_idx_for_icon = None

        curr_for_children = folder

        # Whether the folder itself is an archive (never compact archives so children stay visible)
        _fname_lower = folder.name.lower()
        is_archive_root = (
            _fname_lower.endswith('.arc') or
            _fname_lower.endswith('.rarc') or
            _fname_lower.endswith('.ark')
        )

        # 1. Compact consecutive single-child folders (Type 1)
        temp_curr = folder
        while len(temp_curr.children) == 1 and len(temp_curr.block_ids) == 0:
            temp_curr = temp_curr.children[0]
            display_name += f" / {temp_curr.name}"
            merged_folder_ids.append(temp_curr.id)
            compaction_type = 1
            curr_for_children = temp_curr

        # 2. Compact with a single block (Type 2)
        if len(curr_for_children.children) == 0 and len(curr_for_children.block_ids) == 1:
            b_id = curr_for_children.block_ids[0]
            idx = id_to_idx.get(b_id)
            if idx is not None:
                block_name = self.mw.data_store.block_names.get(str(idx), f"Block {idx}")
                block_name_with_ext = self._get_block_display_name_with_ext(idx, block_name)
                display_name += f" / {block_name_with_ext}"
                compaction_type = 2
                block_idx_for_icon = idx

        # 3. Add [f / b] counter only for non-compacted folders
        # Rule: Hide counter if the folder contains exactly ONE single child (folder or block)
        child_count = len(curr_for_children.children) + len(curr_for_children.block_ids)

        # Save name BEFORE adding counters for editing
        clean_display_name = display_name

        if compaction_type == 0 and child_count > 1:
            display_name += f" [{len(curr_for_children.children)} | {len(curr_for_children.block_ids)}]"

        # Create folder item
        folder_item = QTreeWidgetItem([display_name])
        folder_item.setFlags(folder_item.flags() | Qt.ItemFlag.ItemIsEditable)

        is_archive_folder = (
            is_archive_root or
            clean_display_name.lower().endswith('.arc') or
            clean_display_name.lower().endswith('.rarc') or
            clean_display_name.lower().endswith('.ark') or
            ('/ ' in clean_display_name and (
                '.arc /' in clean_display_name.lower() or
                '.rarc /' in clean_display_name.lower() or
                '.ark /' in clean_display_name.lower()
            ))
        )
        if is_archive_folder:
            self._set_item_style_icon(folder_item, 0, QStyle.StandardPixmap.SP_DirLinkIcon)
        else:
            self._set_item_style_icon(folder_item, 0, QStyle.StandardPixmap.SP_DirIcon)

        folder_item.setData(0, Qt.ItemDataRole.UserRole + 1, curr_for_children.id)
        folder_item.setData(0, Qt.ItemDataRole.UserRole + 2, merged_folder_ids)
        folder_item.setData(0, Qt.ItemDataRole.UserRole + 3, compaction_type)
        folder_item.setData(0, Qt.ItemDataRole.UserRole + 4, display_name)
        folder_item.setData(0, Qt.EditRole, display_name)

        # Store RAW folder names for robust synchronization (avoids parsing display_name with counters)
        raw_names = []
        temp_f = folder
        raw_names.append(temp_f.name)
        if compaction_type == 1:
             while len(temp_f.children) == 1 and len(temp_f.block_ids) == 0:
                 temp_f = temp_f.children[0]
                 raw_names.append(temp_f.name)
        folder_item.setData(0, Qt.ItemDataRole.UserRole + 5, raw_names)

        if block_idx_for_icon is not None:
            folder_item.setData(0, Qt.ItemDataRole.UserRole, block_idx_for_icon) # For indicator strips
            self._register_item_in_cache(folder_item)
            if compaction_type == 2:
                block_problem_counts = self._get_aggregated_problems_for_block(block_idx_for_icon, pre_aggregated_counts)
                self._apply_issues_and_tooltip(folder_item, clean_display_name, block_problem_counts, problem_definitions)

        self._stamp_item_paint_stats(folder_item)
        parent_item.addChild(folder_item)

        if compaction_type != 2:
            # Standard recursive children population (only if NOT compacted with block)
            for child in curr_for_children.children:
                self._add_virtual_folder_to_tree(
                    folder_item, child, problem_definitions, current_selection_block_idx,
                    pre_aggregated_counts, folder_id_to_select=folder_id_to_select, id_to_idx=id_to_idx,
                )

            for b_id in curr_for_children.block_ids:
                idx = id_to_idx.get(b_id)
                if idx is not None:
                    if (getattr(self.mw.data_store, 'show_unsaved_blocks_only', False) is not True or
                            self._is_project_block_unsaved(idx)):
                        block_item = self._create_block_tree_item(idx, problem_definitions, pre_aggregated_counts)
                        folder_item.addChild(block_item)
                        if idx == current_selection_block_idx:
                            self.mw.block_list_widget.setCurrentItem(block_item)
                            block_item.setSelected(True)
                            if block_item.childCount() > 0:
                                block_item.setExpanded(True)
        else:
            # For compaction Type 2 (Folder/Block), the folder_item itself represents the block.
            if block_idx_for_icon is not None and block_idx_for_icon == current_selection_block_idx:
                self.mw.block_list_widget.setCurrentItem(folder_item)
                folder_item.setSelected(True)

        # Apply expansion state AFTER children are added so Qt knows it's NOT a leaf
        folder_item.setExpanded(is_expanded)

        # Restore folder selection
        if folder_id_to_select:
            if folder_id_to_select in merged_folder_ids:
                self.mw.block_list_widget.setCurrentItem(folder_item)
                folder_item.setSelected(True)
