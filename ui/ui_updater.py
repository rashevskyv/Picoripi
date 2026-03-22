# --- START OF FILE ui/ui_updater.py ---
from pathlib import Path
from PyQt5.QtCore import Qt
from PyQt5.QtGui import QColor, QBrush, QTextCursor, QIcon
from PyQt5.QtWidgets import QApplication, QTreeWidgetItem, QTreeWidgetItemIterator, QStyle
from utils.logging_utils import log_debug
from utils.constants import APP_VERSION
from utils.utils import convert_spaces_to_dots_for_display, convert_dots_to_spaces_from_editor, remove_curly_tags, calculate_string_width, calculate_strict_string_width, remove_all_tags
from core.glossary_manager import GlossaryOccurrence

class UIUpdater:
    def __init__(self, main_window, data_processor):
        self.mw = main_window
        self.data_processor = data_processor

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

    def highlight_glossary_occurrence(self, occurrence: GlossaryOccurrence):
        """Highlights a glossary occurrence in the original_text_edit."""
        if not hasattr(self.mw, 'original_text_edit'):
            return

        editor = self.mw.original_text_edit
        if not hasattr(editor, 'highlightManager'):
            return

        editor.highlightManager.clear_search_match_highlights()
        
        block_number = occurrence.line_idx
        start_char = occurrence.start
        length = occurrence.end - occurrence.start
        
        editor.highlightManager.add_search_match_highlight(block_number, start_char, length)

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
        
        item.setData(0, Qt.EditRole, base_display_name)
        item.setData(0, Qt.UserRole + 4, base_display_name)
        
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
                    cat_item.setData(0, Qt.EditRole, cat.name)
                    cat_item.setData(0, Qt.UserRole + 4, cat.name)
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
        folder_item.setData(0, Qt.EditRole, clean_display_name)
        folder_item.setFlags(folder_item.flags() | Qt.ItemIsEditable)
        folder_item.setIcon(0, self.mw.style().standardIcon(QStyle.SP_DirIcon))
        
        folder_item.setData(0, Qt.UserRole + 1, curr_for_children.id)
        folder_item.setData(0, Qt.UserRole + 2, merged_folder_ids)
        folder_item.setData(0, Qt.UserRole + 3, compaction_type)
        folder_item.setData(0, Qt.UserRole + 4, display_name)
        
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
                
                # 1. Trigger parent tree update for recursive asterisks
                # We climb up the tree from each item and force its parent to update/repaint
                # This ensures CustomListItemDelegate.paint is called for all ancestors.
                curr = item
                while curr:
                    # In Qt, changing a property or just calling update() on the viewport 
                    # usually suffice if we triggered dataChanged.
                    # tree_item.emitDataChanged() is internal but we can trigger it 
                    # by setting an irrelevant property if needed, or just update the viewport.
                    curr = curr.parent()
        finally:
            self.mw.block_list_widget.blockSignals(False)
            
        # Global update to ensure all delegates are re-run for visible ancestors
        self.mw.block_list_widget.viewport().update()

    def update_status_bar(self):
        if not hasattr(self.mw, 'edited_text_edit') or not self.mw.edited_text_edit or \
           not all(hasattr(self.mw, label_name) for label_name in ['status_label_part1', 'status_label_part2', 'status_label_part3']):
            return
        
        editor = self.mw.edited_text_edit
        cursor = editor.textCursor()
        
        font_map_for_string = self.mw.helper.get_font_map_for_string(self.mw.data_store.current_block_idx, self.mw.data_store.current_string_idx)
        icon_sequences = getattr(self.mw, 'icon_sequences', [])

        if cursor.hasSelection():
            self.update_status_bar_selection() 
        else:
            block = cursor.block()
            pos_in_block = cursor.positionInBlock()
            
            line_text_with_dots = block.text()
            line_text_with_spaces = convert_dots_to_spaces_from_editor(line_text_with_dots)
            
            line_text_no_all_tags = remove_all_tags(line_text_with_spaces)
            line_len_no_tags = len(line_text_no_all_tags)
            line_len_with_tags = len(line_text_with_spaces)

            text_to_cursor_with_dots = line_text_with_dots[:pos_in_block]
            text_to_cursor_with_spaces = convert_dots_to_spaces_from_editor(text_to_cursor_with_dots)
            
            pixel_width = calculate_string_width(text_to_cursor_with_spaces, font_map_for_string, icon_sequences=icon_sequences)
            
            self.mw.status_label_part1.setText(f"Pos: {pos_in_block}")
            self.mw.status_label_part2.setText(f"Line: {line_len_no_tags}/{line_len_with_tags}")
            self.mw.status_label_part3.setText(f"Width: {pixel_width}px")
        
        self.synchronize_original_cursor()

    def update_status_bar_selection(self):
        if not hasattr(self.mw, 'edited_text_edit') or not self.mw.edited_text_edit or \
           not all(hasattr(self.mw, label_name) for label_name in ['status_label_part1', 'status_label_part2', 'status_label_part3']):
            return
        
        editor = self.mw.edited_text_edit
        cursor = editor.textCursor()
        
        font_map_for_string = self.mw.helper.get_font_map_for_string(self.mw.data_store.current_block_idx, self.mw.data_store.current_string_idx)
        icon_sequences = getattr(self.mw, 'icon_sequences', [])

        if not cursor.hasSelection():
            block = cursor.block()
            pos_in_block = cursor.positionInBlock()
            line_text_with_dots = block.text()
            line_text_with_spaces = convert_dots_to_spaces_from_editor(line_text_with_dots)
            line_text_no_all_tags = remove_all_tags(line_text_with_spaces)
            line_len_no_tags = len(line_text_no_all_tags)
            line_len_with_tags = len(line_text_with_spaces)
            text_to_cursor_with_dots = line_text_with_dots[:pos_in_block]
            text_to_cursor_with_spaces = convert_dots_to_spaces_from_editor(text_to_cursor_with_dots)
            pixel_width = calculate_string_width(text_to_cursor_with_spaces, font_map_for_string, icon_sequences=icon_sequences)
            self.mw.status_label_part1.setText(f"Pos: {pos_in_block}")
            self.mw.status_label_part2.setText(f"Line: {line_len_no_tags}/{line_len_with_tags}")
            self.mw.status_label_part3.setText(f"Width: {pixel_width}px")
            return

        selected_text_with_dots = cursor.selectedText()
        selected_text_with_spaces = convert_dots_to_spaces_from_editor(selected_text_with_dots)
        len_with_tags = len(selected_text_with_spaces)
        selected_text_no_all_tags = remove_all_tags(selected_text_with_spaces)
        len_no_tags = len(selected_text_no_all_tags)
        
        pixel_width = calculate_string_width(selected_text_with_spaces, font_map_for_string, icon_sequences=icon_sequences)
        
        sel_start_abs = cursor.selectionStart()
        sel_start_block_obj = editor.document().findBlock(sel_start_abs)
        sel_start_pos_in_block = sel_start_abs - sel_start_block_obj.position()
        
        self.mw.status_label_part1.setText(f"Sel: {len_no_tags}/{len_with_tags}")
        self.mw.status_label_part2.setText(f"At: {sel_start_pos_in_block}")
        self.mw.status_label_part3.setText(f"Width: {pixel_width}px")

    def clear_status_bar(self):
        if hasattr(self.mw, 'status_label_part1'): self.mw.status_label_part1.setText("Pos: 0")
        if hasattr(self.mw, 'status_label_part2'): self.mw.status_label_part2.setText("Line: 0/0")
        if hasattr(self.mw, 'status_label_part3'): self.mw.status_label_part3.setText("Width: 0px")


    def synchronize_original_cursor(self):
        if not hasattr(self.mw, 'edited_text_edit') or not hasattr(self.mw, 'original_text_edit') or \
           not self.mw.edited_text_edit or not self.mw.original_text_edit:
            return
        
        if self.mw.data_store.current_block_idx == -1 or self.mw.data_store.current_string_idx == -1 or \
           not self.mw.edited_text_edit.document().toPlainText(): 
            if hasattr(self.mw.original_text_edit, 'highlightManager'):
                self.mw.original_text_edit.highlightManager.setLinkedCursorPosition(-1, -1) 
            return

        edited_cursor = self.mw.edited_text_edit.textCursor()
        current_line_in_edited = edited_cursor.blockNumber()
        current_col_in_edited = edited_cursor.positionInBlock()

        if hasattr(self.mw.original_text_edit, 'highlightManager'):
            self.mw.original_text_edit.highlightManager.setLinkedCursorPosition(current_line_in_edited, current_col_in_edited)


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

            
    def update_title(self):
        title = f"Picoripi v{APP_VERSION}"
        if hasattr(self.mw, 'project_manager') and self.mw.project_manager and hasattr(self.mw.project_manager, 'project') and self.mw.project_manager.project:
            title += f" - [{self.mw.project_manager.project.name}]"
        elif self.mw.data_store.json_path: 
            title += f" - [{Path(self.mw.data_store.json_path).name}]"
        else: 
            title += " - [No File Open]"
        if self.mw.data_store.unsaved_changes: 
            title += " *"
        self.mw.setWindowTitle(title)

    def update_plugin_status_label(self):
        if self.mw.plugin_status_label:
            if self.mw.current_game_rules:
                display_name = self.mw.current_game_rules.get_display_name()
                self.mw.plugin_status_label.setText(f"Plugin: {display_name}")
            else:
                self.mw.plugin_status_label.setText("Plugin: [None]")

    def update_statusbar_paths(self):
        if hasattr(self.mw, 'original_path_label') and self.mw.original_path_label:
            orig_filename = Path(self.mw.data_store.json_path).name if self.mw.data_store.json_path else "[not specified]"
            self.mw.original_path_label.setText(f"Original: {orig_filename}")
            self.mw.original_path_label.setToolTip(self.mw.data_store.json_path if self.mw.data_store.json_path else "Path to original file")
        if hasattr(self.mw, 'edited_path_label') and self.mw.edited_path_label:
            edited_filename = Path(self.mw.data_store.edited_json_path).name if self.mw.data_store.edited_json_path else "[not specified]"
            self.mw.edited_path_label.setText(f"Changes: {edited_filename}")
            self.mw.edited_path_label.setToolTip(self.mw.data_store.edited_json_path if self.mw.data_store.edited_json_path else "Path to changes file")

    def _apply_highlights_for_block(self, block_idx: int):
        preview_edit = getattr(self.mw, 'preview_text_edit', None)
        if not preview_edit or not hasattr(preview_edit, 'highlightManager') or not self.mw.current_game_rules:
            return

        preview_edit.highlightManager.clearAllProblemHighlights()
        
        if not (0 <= block_idx < len(self.mw.data_store.data)):
            return

        displayed_indices = getattr(self.mw, 'displayed_string_indices', [])
        if not displayed_indices:
             # If no filtering is active, use all
             displayed_indices = list(range(len(self.mw.data_store.data[block_idx])))

        for preview_idx, real_idx in enumerate(displayed_indices):
            if self.mw.list_selection_handler._data_string_has_any_problem(block_idx, real_idx):
                preview_edit.addProblemLineHighlight(preview_idx)
        
        # Highlight categorized strings if enabled
        if getattr(self.mw, 'highlight_categorized', False) and not self.mw.data_store.current_category_name:
            categorized_indices = self._get_all_categorized_indices_for_block(block_idx)
            if categorized_indices:
                preview_indices = []
                for p_idx, r_idx in enumerate(displayed_indices):
                    if r_idx in categorized_indices:
                        preview_indices.append(p_idx)
                if preview_indices:
                    highlight_color = QColor(200, 230, 255, 60) # Light subtle blue
                    preview_edit.highlightManager.setCategorizedLineHighlights(preview_indices, highlight_color)
        else:
            preview_edit.highlightManager.clearCategorizedLineHighlights()

    def _apply_highlights_to_editor(self, editor, block_idx: int, string_idx: int):
        if not editor or not hasattr(editor, 'highlightManager'):
            return
        
        editor.highlightManager.clearAllProblemHighlights()
        
        if block_idx < 0 or string_idx < 0:
            return

        doc = editor.document()
        for i in range(doc.blockCount()):
            problem_key = (block_idx, string_idx, i)
            if problem_key in self.mw.data_store.problems_per_subline:
                problems = self.mw.data_store.problems_per_subline[problem_key]
                if problems:
                    # Determine if critical or warning
                    is_critical = False; warning_color = None
                    for p_id in problems:
                        def_ = self.mw.current_game_rules.get_problem_definitions().get(p_id, {})
                        if def_.get("severity") == "error":
                            is_critical = True
                            break
                        elif "color" in def_:
                             warning_color = def_["color"]
                    
                    if is_critical:
                        editor.highlightManager.addCriticalProblemHighlight(i)
                    else:
                        editor.highlightManager.addWarningLineHighlight(i, warning_color)
                        
            # Also check for specific highlights that have their own methods in HighlightManager
            if problem_key in self.mw.data_store.problems_per_subline:
                 problems = self.mw.data_store.problems_per_subline[problem_key]
                 if hasattr(self.mw.current_game_rules, 'problem_ids') and hasattr(self.mw.current_game_rules.problem_ids, 'PROBLEM_EMPTY_ODD_SUBLINE_DISPLAY'):
                     if self.mw.current_game_rules.problem_ids.PROBLEM_EMPTY_ODD_SUBLINE_DISPLAY in problems:
                         editor.highlightManager.addEmptyOddSublineHighlight(i)

    def _get_all_categorized_indices_for_block(self, block_idx: int) -> set:
        """Get set of all string indices that are assigned to any virtual block (category)."""
        if block_idx < 0: return set()
        pm = getattr(self.mw, 'project_manager', None)
        if not pm or not pm.project: return set()
        
        block_map = getattr(self.mw, 'block_to_project_file_map', {})
        proj_b_idx = block_map.get(block_idx, block_idx)
        if proj_b_idx >= len(pm.project.blocks): return set()
        
        block = pm.project.blocks[proj_b_idx]
        categorized_indices = set()
        for cat in block.categories:
            categorized_indices.update(cat.line_indices)
        return categorized_indices

    def populate_strings_for_block(self, block_idx, category_name=None, force=False):
        if not hasattr(self.mw, 'preview_text_edit') or not getattr(self.mw, 'current_game_rules', None):
            return

        preview_edit = getattr(self.mw, 'preview_text_edit', None)
        original_edit = getattr(self.mw, 'original_text_edit', None)
        edited_edit = getattr(self.mw, 'edited_text_edit', None)

        old_preview_scrollbar_value = preview_edit.verticalScrollBar().value() if preview_edit else 0
        
        self.mw.is_programmatically_changing_text = True
        self.mw.data_store.current_category_name = category_name

        # Show "Highlight moved" / "Hide moved" only when this block has categories
        block_has_categories = False
        if hasattr(self.mw, 'project_manager') and self.mw.project_manager and self.mw.project_manager.project:
            pm = self.mw.project_manager
            block_map = getattr(self.mw, 'block_to_project_file_map', {})
            proj_b_idx = block_map.get(block_idx, block_idx)
            if proj_b_idx < len(pm.project.blocks):
                block_has_categories = bool(pm.project.blocks[proj_b_idx].categories)
        show_cat_toggles = block_has_categories and not category_name
        if hasattr(self.mw, 'highlight_categorized_checkbox'):
            self.mw.highlight_categorized_checkbox.setVisible(show_cat_toggles)
        if hasattr(self.mw, 'hide_categorized_checkbox'):
            self.mw.hide_categorized_checkbox.setVisible(show_cat_toggles)

        # Use a local cache of the last populated block to avoid redundant full resets
        last_block_idx = getattr(self, '_last_populated_block_idx', -999)
        last_category_name = getattr(self, '_last_populated_category_name', None)
        
        block_changed = (block_idx != last_block_idx) or (category_name != last_category_name)
        
        if block_changed:
            if preview_edit: preview_edit.reset_selection_state()
            if original_edit: original_edit.reset_selection_state()
            if edited_edit: edited_edit.reset_selection_state()
            self._last_populated_block_idx = block_idx
            self._last_populated_category_name = category_name

        if block_idx < 0 or not self.mw.data_store.data or block_idx >= len(self.mw.data_store.data) or not isinstance(self.mw.data_store.data[block_idx], list):
            self.mw.data_store.displayed_string_indices = []
            if preview_edit: preview_edit.setPlainText("")
            if original_edit: original_edit.setPlainText("")
            if edited_edit: edited_edit.setPlainText("")
            self.update_text_views(); self.synchronize_original_cursor() 
            if preview_edit: preview_edit.verticalScrollBar().setValue(old_preview_scrollbar_value)
            self.mw.is_programmatically_changing_text = False 
            return
        
        if preview_edit and self.mw.current_game_rules:
            # Determine which indices to show
            target_indices = []
            if category_name and hasattr(self.mw, 'project_manager') and self.mw.project_manager and self.mw.project_manager.project:
                pm = self.mw.project_manager
                block_map = getattr(self.mw, 'block_to_project_file_map', {})
                proj_b_idx = block_map.get(block_idx, block_idx)
                if proj_b_idx < len(pm.project.blocks):
                    block = pm.project.blocks[proj_b_idx]
                    category = next((c for c in block.categories if c.name == category_name), None)
                    if category:
                        target_indices = category.line_indices

            if not target_indices and not category_name:
                target_indices = list(range(len(self.mw.data_store.data[block_idx])))
                # Filter out categorized if "Hide moved" is enabled
                if getattr(self.mw, 'hide_categorized', False):
                    categorized_indices = self._get_all_categorized_indices_for_block(block_idx)
                    target_indices = [idx for idx in target_indices if idx not in categorized_indices]
            
            # Re-verify indices are within bounds
            target_indices = [i for i in target_indices if 0 <= i < len(self.mw.data_store.data[block_idx])]
            
            # Check if displayed indices actually changed (for "Hide moved" toggle)
            old_indices = getattr(self.mw, 'displayed_string_indices', [])
            displayed_indices_changed = (target_indices != old_indices)
            
            self.mw.data_store.displayed_string_indices = target_indices

            # Generate full text if block changed OR if the subset of strings changed (e.g. Hide moved toggled) OR force refresh
            if block_changed or displayed_indices_changed or force:
                preview_lines = []
                for real_idx in target_indices:
                    text_for_preview_raw, _ = self.data_processor.get_current_string_text(block_idx, real_idx)
                    preview_line_text = self.mw.current_game_rules.get_text_representation_for_preview(str(text_for_preview_raw))
                    preview_lines.append(preview_line_text)

                preview_full_text = "\n".join(preview_lines)
                if preview_edit.toPlainText() != preview_full_text:
                    preview_edit.setPlainText(preview_full_text)

            # Apply highlights based on NEW displayed_string_indices (MUST be after setPlainText)
            self._apply_highlights_for_block(block_idx)

            # Map current_string_idx to preview index if possible
            preview_idx_to_select = -1
            if self.mw.data_store.current_string_idx in target_indices:
                preview_idx_to_select = target_indices.index(self.mw.data_store.current_string_idx)

            if preview_idx_to_select != -1 and \
               hasattr(preview_edit, 'set_selected_lines') and \
               0 <= preview_idx_to_select < preview_edit.document().blockCount(): 
                preview_edit.set_selected_lines([preview_idx_to_select])

            # Only restore scroll value if block changed AND we are NOT intentionally selecting a string
            # (If we are selecting a string, ensureCursorVisible will be called later in string_selected_from_preview)
            if block_changed and self.mw.data_store.current_string_idx == -1:
                preview_edit.verticalScrollBar().setValue(old_preview_scrollbar_value)
        
        self.update_text_views() 
        self.synchronize_original_cursor() 
        self.mw.is_programmatically_changing_text = False

            
    def update_text_views(self): 
        is_programmatic_call_flag_original = self.mw.is_programmatically_changing_text
        
        self.mw.is_programmatically_changing_text = True

        original_text_raw = ""
        edited_text_raw = ""
        if self.mw.data_store.current_block_idx != -1 and self.mw.data_store.current_string_idx != -1:
            original_text_raw = self.data_processor._get_string_from_source(
                self.mw.data_store.current_block_idx, self.mw.data_store.current_string_idx, self.mw.data_store.data, 
                "original_data_for_readonly_view"
            )
            if original_text_raw is None: original_text_raw = ""
            edited_text_raw, _ = self.data_processor.get_current_string_text(self.mw.data_store.current_block_idx, self.mw.data_store.current_string_idx)
            if edited_text_raw is None: edited_text_raw = ""
        
        if self.mw.current_game_rules and hasattr(self.mw.current_game_rules, 'get_text_representation_for_editor'):
            original_text_for_display_processed = self.mw.current_game_rules.get_text_representation_for_editor(str(original_text_raw))
            edited_text_for_display_processed = self.mw.current_game_rules.get_text_representation_for_editor(str(edited_text_raw))
        else: 
            original_text_for_display_processed = str(original_text_raw)
            edited_text_for_display_processed = str(edited_text_raw)

        original_text_for_display = convert_spaces_to_dots_for_display(original_text_for_display_processed, self.mw.show_multiple_spaces_as_dots)
        edited_text_for_display_converted = convert_spaces_to_dots_for_display(edited_text_for_display_processed, self.mw.show_multiple_spaces_as_dots)
        
        orig_edit = self.mw.original_text_edit
        if orig_edit:
            if orig_edit.toPlainText() != original_text_for_display:
                orig_text_edit_cursor_pos = orig_edit.textCursor().position()
                orig_anchor_pos = orig_edit.textCursor().anchor()
                orig_has_selection = orig_edit.textCursor().hasSelection()
                orig_edit.setPlainText(original_text_for_display)
                new_orig_cursor = orig_edit.textCursor()
                new_orig_cursor.setPosition(min(orig_anchor_pos, len(original_text_for_display)))
                if orig_has_selection: new_orig_cursor.setPosition(min(orig_text_edit_cursor_pos, len(original_text_for_display)), QTextCursor.KeepAnchor)
                else: new_orig_cursor.setPosition(min(orig_text_edit_cursor_pos, len(original_text_for_display)))
                orig_edit.setTextCursor(new_orig_cursor)

        edited_widget = self.mw.edited_text_edit
        if edited_widget:
            if edited_widget.toPlainText() != edited_text_for_display_converted:
                saved_edited_cursor_pos = edited_widget.textCursor().position()
                saved_edited_anchor_pos = edited_widget.textCursor().anchor()
                saved_edited_has_selection = edited_widget.textCursor().hasSelection()
                
                edited_widget.setPlainText(edited_text_for_display_converted)

                restored_cursor = edited_widget.textCursor()
                new_edited_anchor_pos = min(saved_edited_anchor_pos, len(edited_text_for_display_converted))
                new_edited_cursor_pos = min(saved_edited_cursor_pos, len(edited_text_for_display_converted))
                restored_cursor.setPosition(new_edited_anchor_pos)
                if saved_edited_has_selection: restored_cursor.setPosition(new_edited_cursor_pos, QTextCursor.KeepAnchor)
                else: restored_cursor.setPosition(new_edited_cursor_pos)
                edited_widget.setTextCursor(restored_cursor)
            
        # Optional: Calculate original strictly (without fallback char width) width
        if hasattr(self.mw, 'original_width_label'):
            if self.mw.data_store.current_block_idx != -1 and self.mw.data_store.current_string_idx != -1:
                font_map_for_string = self.mw.helper.get_font_map_for_string(self.mw.data_store.current_block_idx, self.mw.data_store.current_string_idx)
                icon_sequences = getattr(self.mw, 'icon_sequences', [])
                strict_width = calculate_strict_string_width(str(original_text_raw), font_map_for_string, icon_sequences=icon_sequences)
                if strict_width is not None:
                    self.mw.original_width_label.setText(f"Width: {strict_width}px")
                    self.mw.original_width_label.show()
                else:
                    self.mw.original_width_label.setText("")
                    self.mw.original_width_label.hide()
            else:
                self.mw.original_width_label.setText("")
                self.mw.original_width_label.hide()

        self.mw.is_programmatically_changing_text = is_programmatic_call_flag_original

        # Apply highlights to editors
        if self.mw.data_store.current_block_idx != -1 and self.mw.data_store.current_string_idx != -1:
             self._apply_highlights_to_editor(self.mw.edited_text_edit, self.mw.data_store.current_block_idx, self.mw.data_store.current_string_idx)
             self._apply_highlights_to_editor(self.mw.original_text_edit, self.mw.data_store.current_block_idx, self.mw.data_store.current_string_idx)
        else: 
            self.clear_status_bar()