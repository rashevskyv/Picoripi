from PyQt5.QtCore import Qt, QTimer
from PyQt5.QtGui import QIcon
from PyQt5.QtWidgets import QTreeWidgetItem, QTreeWidgetItemIterator, QStyle
from utils.logging_utils import log_info, log_warning
from pathlib import Path
from .base_ui_updater import BaseUIUpdater

class BlockListUpdater(BaseUIUpdater):
    def get_tree_state(self) -> dict:
        """Returns the current expansion and selection state of the block tree."""
        if not self.mw.block_list_widget:
            return {}
        
        expanded_ids = []
        selected_id = None
        selected_type = None # 'block', 'folder', 'category'
        
        current_item = self.mw.block_list_widget.currentItem()
        
        iterator = QTreeWidgetItemIterator(self.mw.block_list_widget)
        while iterator.value():
            item = iterator.value()
            
            # Identify the item
            item_id = None
            item_type = None
            
            # Check if it's a block
            block_idx = item.data(0, Qt.UserRole)
            category_name = item.data(0, Qt.UserRole + 10)
            folder_id = item.data(0, Qt.UserRole + 1)
            
            if folder_id is not None:
                item_id = f"folder_{folder_id}"
                item_type = 'folder'
            elif category_name is not None:
                parent = item.parent()
                if parent:
                    p_block_idx = parent.data(0, Qt.UserRole)
                    item_id = f"cat_{p_block_idx}_{category_name}"
                item_type = 'category'
            elif block_idx is not None:
                item_id = f"block_{block_idx}"
                item_type = 'block'
                
            if item_id:
                if item.isExpanded():
                    expanded_ids.append(item_id)
                if item == current_item:
                    selected_id = item_id
                    selected_type = item_type
                    
            iterator += 1
            
        result = {
            "expanded_ids": expanded_ids,
            "selected_id": selected_id,
            "selected_type": selected_type,
            "selected_string_idx": self.mw.data_store.current_string_idx if hasattr(self.mw, 'current_string_idx') else -1
        }
        from utils.logging_utils import log_info
        log_info(f"UIUpdater: Captured tree state: selected={selected_id}, string_idx={result['selected_string_idx']}")
        return result

    def apply_tree_state(self, state: dict):
        """Restores the tree expansion and selection from state."""
        if not state or not self.mw.block_list_widget:
            return
            
        expanded_ids = set(state.get("expanded_ids", []))
        selected_id = state.get("selected_id")
        selected_string_idx = state.get("selected_string_idx", -1)
        
        # 1. Restore Expansion (Signals blocked to avoid redundant updates)
        old_blocked = self.mw.block_list_widget.blockSignals(True)
        try:
            iterator = QTreeWidgetItemIterator(self.mw.block_list_widget)
            while iterator.value():
                item = iterator.value()
                item_id = self._get_item_id(item)
                if item_id in expanded_ids:
                    item.setExpanded(True)
                iterator += 1
        finally:
            self.mw.block_list_widget.blockSignals(old_blocked)
            
        # 2. Restore Selection (Delayed to ensure tree is stable)
        if selected_id:
            from utils.logging_utils import log_info, log_warning
            
            def _delayed_select():
                # Re-find the item to avoid "deleted object" errors
                target_item = None
                iterator = QTreeWidgetItemIterator(self.mw.block_list_widget)
                while iterator.value():
                    if self._get_item_id(iterator.value()) == selected_id:
                        target_item = iterator.value()
                        break
                    iterator += 1
                
                if target_item:
                    log_info(f"UIUpdater: Restoring selection to {selected_id}")
                    self.mw.block_list_widget.setFocus()
                    self.mw.block_list_widget.setCurrentItem(target_item)
                    # Manually trigger block load
                    self.mw.list_selection_handler.block_selected(target_item, None)
                    
                    if selected_string_idx != -1:
                        log_info(f"UIUpdater: Restoring string selection to absolute index {selected_string_idx}")
                        # Further delay for strings to ensure they are populated and mapped
                        from PyQt5.QtCore import QTimer
                        QTimer.singleShot(200, lambda: self.mw.list_selection_handler.select_string_by_absolute_index(selected_string_idx))
                else:
                    log_warning(f"UIUpdater: Failed to find item {selected_id} for restoration.")

            from PyQt5.QtCore import QTimer
            QTimer.singleShot(50, _delayed_select)

    def _get_item_id(self, item) -> str:
        """Helper to generate consistent IDs for tree items."""
        if not item: return None
        
        block_idx = item.data(0, Qt.UserRole)
        category_name = item.data(0, Qt.UserRole + 10)
        folder_id = item.data(0, Qt.UserRole + 1)
        
        if folder_id is not None:
            return f"folder_{folder_id}"
        elif category_name is not None:
            parent = item.parent()
            if parent:
                p_block_idx = parent.data(0, Qt.UserRole)
                return f"cat_{p_block_idx}_{category_name}"
        elif block_idx is not None:
            return f"block_{block_idx}"
        return None

    def _get_aggregated_problems_for_block(self, block_idx: int, pre_aggregated_counts: dict = None, category_name: str = None) -> dict:
        problem_counts = {}
        if not self.mw.current_game_rules or not (0 <= block_idx < len(self.mw.data_store.data)):
            return problem_counts
        
        problem_definitions = self.mw.current_game_rules.get_problem_definitions()
        
        if pre_aggregated_counts is not None and category_name is None:
            # Fast path: use the pre-calculated problem counts for this block (only for full blocks)
            block_counts = pre_aggregated_counts.get(block_idx, {})
            return {pid: block_counts.get(pid, 0) for pid in problem_definitions.keys()}
        
        # Slow path/Category path
        problem_counts = {pid: 0 for pid in problem_definitions.keys()}
        detection_config = getattr(self.mw, 'detection_enabled', {})
        
        # Determine which strings to check
        target_indices = None
        if category_name:
            if hasattr(self.mw, 'project_manager') and self.mw.project_manager and self.mw.project_manager.project:
                pm = self.mw.project_manager
                block_map = getattr(self.mw, 'block_to_project_file_map', {})
                proj_b_idx = block_map.get(block_idx, block_idx)
                if proj_b_idx < len(pm.project.blocks):
                    block = pm.project.blocks[proj_b_idx]
                    category = next((c for c in block.categories if c.name == category_name), None)
                    if category:
                        target_indices = set(category.line_indices)

        for (b_idx, s_idx, subline_idx), problems in self.mw.data_store.problems_per_subline.items():
            if b_idx == block_idx:
                if target_indices is not None and s_idx not in target_indices:
                    continue
                    
                filtered_problems = {p_id for p_id in problems if detection_config.get(p_id, True)}
                for p_id in filtered_problems:
                    if p_id in problem_counts:
                        problem_counts[p_id] += 1
                        
        return problem_counts

    def _apply_issues_and_tooltip(self, item: QTreeWidgetItem, base_display_name: str, problem_counts: dict, problem_definitions: dict):
        display_name_with_issues = base_display_name
        issue_texts = []
        tooltip_lines = []
        
        sorted_problem_ids_for_display = sorted(
            problem_counts.keys(),
            key=lambda pid: problem_definitions.get(pid, {}).get("priority", 99)
        )

        for problem_id in sorted_problem_ids_for_display:
            count_sublines = problem_counts[problem_id]
            if count_sublines > 0:
                short_name = self.mw.current_game_rules.get_short_problem_name(problem_id)
                issue_texts.append(f"{count_sublines} {short_name}")
                
                prob_def = problem_definitions.get(problem_id, {})
                full_name = prob_def.get("name", problem_id)
                desc = prob_def.get("description", "")
                tooltip_lines.append(f"<b>{full_name}</b>: {count_sublines} sublines<br><i>{desc}</i>")
        
        if issue_texts:
            display_name_with_issues = f"{base_display_name} ({', '.join(issue_texts)})"
            
        item.setText(0, display_name_with_issues)
        
        if tooltip_lines:
            item.setToolTip(0, "<br><br>".join(tooltip_lines))
        else:
            item.setToolTip(0, "")

    def _create_block_tree_item(self, block_idx: int, problem_definitions: dict, pre_aggregated_counts: dict = None) -> QTreeWidgetItem:
        """Helper to create a single block tree item with issue counts and tooltips."""
        base_display_name = self.mw.data_store.block_names.get(str(block_idx), f"Block {block_idx}")
        block_problem_counts = self._get_aggregated_problems_for_block(block_idx, pre_aggregated_counts)
        
        item = self.mw.block_list_widget.create_item(base_display_name, block_idx, Qt.UserRole)
        self._apply_issues_and_tooltip(item, base_display_name, block_problem_counts, problem_definitions)
        
        item.setData(0, Qt.UserRole + 4, base_display_name)
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
                    cat_item.setFlags(cat_item.flags() | Qt.ItemIsEditable)
                    cat_item.setData(0, Qt.UserRole, block_idx)
                    cat_item.setData(0, Qt.UserRole + 10, cat.name)
                    cat_item.setData(0, Qt.UserRole + 4, cat.name)
                    cat_item.setData(0, Qt.EditRole, cat.name)
                    cat_item.setIcon(0, self.mw.style().standardIcon(QStyle.SP_FileDialogDetailedView))
                    
                    cat_problem_counts = self._get_aggregated_problems_for_block(block_idx, pre_aggregated_counts=None, category_name=cat.name)
                    self._apply_issues_and_tooltip(cat_item, cat.name, cat_problem_counts, problem_definitions)
                    
                    item.addChild(cat_item)
            
        return item

    def _add_virtual_folder_to_tree(self, parent_item, folder, problem_definitions, current_selection_block_idx, pre_aggregated_counts: dict = None, folder_id_to_select=None):
        """Recursively add virtual folders and their blocks to the tree with folder compaction (GitHub style)."""
        project = self.mw.project_manager.project
        if not project: return

        is_expanded = folder.is_expanded
        display_name = folder.name or "Unnamed Folder"
        merged_folder_ids = [folder.id]
        compaction_type = 0 # 0: None, 1: Folder/Folder, 2: Folder/Block
        block_idx_for_icon = None
        
        curr_for_children = folder
        
        # 1. Compact consecutive single-child folders (Type 1)
        if not is_expanded:
            temp_curr = folder
            while len(temp_curr.children) == 1 and len(temp_curr.block_ids) == 0:
                temp_curr = temp_curr.children[0]
                display_name += f" / {temp_curr.name}"
                merged_folder_ids.append(temp_curr.id)
                compaction_type = 1
                curr_for_children = temp_curr
            
            # 2. Compact with a single block (Type 2)
            if len(curr_for_children.children) == 0 and len(curr_for_children.block_ids) == 1:
                id_to_idx = {b.id: idx for idx, b in enumerate(project.blocks)}
                b_id = curr_for_children.block_ids[0]
                idx = id_to_idx.get(b_id)
                if idx is not None:
                    block_name = self.mw.data_store.block_names.get(str(idx), f"Block {idx}")
                    display_name += f" / {block_name}"
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
        folder_item.setFlags(folder_item.flags() | Qt.ItemIsEditable)
        folder_item.setIcon(0, self.mw.style().standardIcon(QStyle.SP_DirIcon))
        
        folder_item.setData(0, Qt.UserRole + 1, curr_for_children.id)
        folder_item.setData(0, Qt.UserRole + 2, merged_folder_ids)
        folder_item.setData(0, Qt.UserRole + 3, compaction_type)
        folder_item.setData(0, Qt.UserRole + 4, display_name)
        folder_item.setData(0, Qt.EditRole, display_name)
        
        # Store RAW folder names for robust synchronization (avoids parsing display_name with counters)
        raw_names = []
        temp_f = folder
        raw_names.append(temp_f.name)
        if compaction_type == 1:
             while len(temp_f.children) == 1 and len(temp_f.block_ids) == 0:
                 temp_f = temp_f.children[0]
                 raw_names.append(temp_f.name)
        folder_item.setData(0, Qt.UserRole + 5, raw_names)
        
        if block_idx_for_icon is not None:
            folder_item.setData(0, Qt.UserRole, block_idx_for_icon) # For indicator strips
            
        parent_item.addChild(folder_item)
        
        # Standard recursive children population
        for child in curr_for_children.children:
            self._add_virtual_folder_to_tree(folder_item, child, problem_definitions, current_selection_block_idx, pre_aggregated_counts, folder_id_to_select=folder_id_to_select)
            
        id_to_idx = {b.id: idx for idx, b in enumerate(project.blocks)}
        for b_id in curr_for_children.block_ids:
            idx = id_to_idx.get(b_id)
            if idx is not None:
                block_item = self._create_block_tree_item(idx, problem_definitions, pre_aggregated_counts)
                folder_item.addChild(block_item)
                if idx == current_selection_block_idx:
                    self.mw.block_list_widget.setCurrentItem(block_item)
                    block_item.setSelected(True)
                    if block_item.childCount() > 0:
                        block_item.setExpanded(True)

        # Apply expansion state AFTER children are added so Qt knows it's NOT a leaf
        folder_item.setExpanded(is_expanded)

        # Restore folder selection
        if folder_id_to_select:
            if folder_id_to_select in merged_folder_ids:
                self.mw.block_list_widget.setCurrentItem(folder_item)
                folder_item.setSelected(True)

    def populate_blocks(self, override_folder_id=None, override_block_idx=None):
        if not hasattr(self.mw, 'block_list_widget') or not self.mw.block_list_widget:
            return  # Sometimes called during initialization before block_list_widget is created

        current_selection_block_idx = override_block_idx
        current_selection_folder_id = override_folder_id
        
        if current_selection_block_idx is None and current_selection_folder_id is None:
            current_item = self.mw.block_list_widget.currentItem()
            if current_item:
                current_selection_block_idx = current_item.data(0, Qt.UserRole)
                current_selection_folder_id = current_item.data(0, Qt.UserRole + 1)
        
        # Save scroll position
        v_scroll = self.mw.block_list_widget.verticalScrollBar().value()
        
        # Don't let signals trigger more refreshes while we are rebuilding
        self.mw.block_list_widget.blockSignals(True)
        self.mw.block_list_widget._is_programmatic_expansion = True
        self.mw.block_list_widget.setUpdatesEnabled(False)
        
        try:
            self.mw.block_list_widget.clear()
            if not self.mw.data_store.data: 
                return
            
            problem_definitions = {}
            if self.mw.current_game_rules:
                problem_definitions = self.mw.current_game_rules.get_problem_definitions()

            # Use virtual folders if project is active and folders exist (or root_block_ids explicitly set)
            has_virtual_structure = False
            if hasattr(self.mw, 'project_manager') and self.mw.project_manager and self.mw.project_manager.project:
                project = self.mw.project_manager.project
                if project.virtual_folders or 'root_block_ids' in project.metadata:
                    has_virtual_structure = True
            
            # Hide categorization toggles during tree rebuild; they will be
            # shown by populate_strings_for_block only when the selected block
            # actually has categories.
            if hasattr(self.mw, 'highlight_categorized_checkbox'):
                self.mw.highlight_categorized_checkbox.setVisible(False)
            if hasattr(self.mw, 'hide_categorized_checkbox'):
                self.mw.hide_categorized_checkbox.setVisible(False)

            # Compute aggregated problems for ALL blocks once (O(M) complexity instead of O(N*M))
            pre_aggregated_counts = {}
            detection_config = getattr(self.mw, 'detection_enabled', {})
            for (b_idx, _, _), problems in self.mw.data_store.problems_per_subline.items():
                if b_idx not in pre_aggregated_counts:
                    pre_aggregated_counts[b_idx] = {}
                filtered_problems = {p_id for p_id in problems if detection_config.get(p_id, True)}
                for p_id in filtered_problems:
                    pre_aggregated_counts[b_idx][p_id] = pre_aggregated_counts[b_idx].get(p_id, 0) + 1

            if has_virtual_structure:
                project = self.mw.project_manager.project
                root_item = self.mw.block_list_widget.invisibleRootItem()
                
                # 1. Add virtual folders recursively
                for folder in project.virtual_folders:
                    self._add_virtual_folder_to_tree(root_item, folder, problem_definitions, current_selection_block_idx, pre_aggregated_counts, folder_id_to_select=current_selection_folder_id)
                    
                # 2. Add root blocks
                root_block_ids = project.metadata.get('root_block_ids', [])
                id_to_idx = {b.id: idx for idx, b in enumerate(project.blocks)}
                
                for b_id in root_block_ids:
                    idx = id_to_idx.get(b_id)
                    if idx is not None:
                        block_item = self._create_block_tree_item(idx, problem_definitions, pre_aggregated_counts)
                        root_item.addChild(block_item)
                        if idx == current_selection_block_idx:
                            self.mw.block_list_widget.setCurrentItem(block_item)
                            block_item.setSelected(True)
                            if block_item.childCount() > 0:
                                block_item.setExpanded(True)
            else:
                # Legacy / Physical structure fallback
                dir_nodes = {"": self.mw.block_list_widget.invisibleRootItem()}

                for i in range(len(self.mw.data_store.data)):
                    block_item = self._create_block_tree_item(i, problem_definitions, pre_aggregated_counts)
                    
                    if hasattr(self.mw, 'project_manager') and self.mw.project_manager and self.mw.project_manager.project and i < len(self.mw.project_manager.project.blocks):
                        block = self.mw.project_manager.project.blocks[i]
                        rel_path = block.source_file
                        if rel_path.startswith(self.mw.project_manager.SOURCES_DIR + '/'):
                            rel_path = rel_path[len(self.mw.project_manager.SOURCES_DIR) + 1:]
                        dir_path = Path(rel_path).parent.as_posix()
                    else:
                        dir_path = ""

                    parts = dir_path.split('/') if dir_path else []
                    current_path = ""
                    for part in parts:
                        if not part: continue
                        parent_path = current_path
                        current_path = current_path + "/" + part if current_path else part
                        
                        if current_path not in dir_nodes:
                            dir_item = QTreeWidgetItem([part])
                            dir_item.setIcon(0, QIcon.fromTheme('folder'))
                            dir_nodes[parent_path].addChild(dir_item)
                            dir_item.setExpanded(True)
                            dir_nodes[current_path] = dir_item

                    parent_item = dir_nodes.get(dir_path, dir_nodes[""])
                    parent_item.addChild(block_item)

                    if i == current_selection_block_idx:
                        self.mw.block_list_widget.setCurrentItem(block_item)
                        block_item.setSelected(True)
                        if block_item.childCount() > 0:
                            block_item.setExpanded(True)
        finally:
            self.mw.block_list_widget._is_programmatic_expansion = False
            self.mw.block_list_widget.blockSignals(False)
            self.mw.block_list_widget.setUpdatesEnabled(True)
            self.mw.block_list_widget.verticalScrollBar().setValue(v_scroll)

        self.mw.block_list_widget.viewport().update()

    def update_block_item_text_with_problem_count(self, block_idx: int):
        if not hasattr(self.mw, 'block_list_widget'):
            return
        
        # Find ALL tree items representing this block (could be multiple if categories are listed as sub-items)
        items_to_update = []
        iterator = QTreeWidgetItemIterator(self.mw.block_list_widget)
        while iterator.value():
            tree_item = iterator.value()
            if tree_item.data(0, Qt.UserRole) == block_idx:
                items_to_update.append(tree_item)
            iterator += 1

        if not items_to_update: return

        problem_definitions = self.mw.current_game_rules.get_problem_definitions() if self.mw.current_game_rules else {}

        self.mw.block_list_widget.blockSignals(True)
        try:
            for item in items_to_update:
                category_name = item.data(0, Qt.UserRole + 10)
                
                # Try to use stored base name to preserve folder path in compacted view
                base_display_name = item.data(0, Qt.UserRole + 4)
                if base_display_name is None:
                    base_display_name = self.mw.data_store.block_names.get(str(block_idx), f"Block {block_idx}")
                    
                block_problem_counts = self._get_aggregated_problems_for_block(block_idx, category_name=category_name)
                
                display_name_with_issues = base_display_name
                issue_texts = []

                sorted_problem_ids_for_display = sorted(
                    block_problem_counts.keys(),
                    key=lambda pid: problem_definitions.get(pid, {}).get("priority", 99)
                )

                for problem_id in sorted_problem_ids_for_display:
                    count_sublines = block_problem_counts[problem_id]
                    if count_sublines > 0:
                        short_name = self.mw.current_game_rules.get_short_problem_name(problem_id)
                        issue_texts.append(f"{count_sublines} {short_name}")

                if issue_texts:
                    display_name_with_issues = f"{base_display_name} ({', '.join(issue_texts)})"
                
                if item.text(0) != display_name_with_issues:
                    item.setText(0, display_name_with_issues)
        finally:
            self.mw.block_list_widget.blockSignals(False)
            
        # Global update to ensure all delegates are re-run for visible ancestors
        self.mw.block_list_widget.viewport().update()

    def highlight_problem_block(self, block_idx: int, highlight: bool, is_critical: bool = True):
        pass 

    def clear_all_problem_block_highlights_and_text(self): 
        if not hasattr(self.mw, 'block_list_widget'): return
        
        iterator = QTreeWidgetItemIterator(self.mw.block_list_widget)
        while iterator.value():
            item = iterator.value()
            block_idx = item.data(0, Qt.UserRole)
            if block_idx is not None:
                base_display_name = item.data(0, Qt.UserRole + 4)
                if base_display_name is None:
                    base_display_name = self.mw.data_store.block_names.get(str(block_idx), f"Block {block_idx}")
                
                if item.text(0) != base_display_name: 
                    item.setText(0, base_display_name) 
            iterator += 1

        if hasattr(self.mw, 'block_list_widget'):
            self.mw.block_list_widget.viewport().update()

