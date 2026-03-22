# --- START OF FILE ui/updaters/block_list_updater.py ---
from PyQt5.QtCore import Qt
from PyQt5.QtGui import QColor
from utils.utils import log_debug

from .base_ui_updater import BaseUIUpdater

class BlockListUpdater(BaseUIUpdater):
    def __init__(self, main_window, data_processor):
        super().__init__(main_window, data_processor)

    def populate_blocks(self):
        log_debug("[BlockListUpdater] populate_blocks called.")
        current_selection_block_idx = None
        current_item = self.mw.block_list_widget.currentItem()
        if current_item and current_item.data(0, Qt.UserRole) is not None:
            current_selection_block_idx = current_item.data(0, Qt.UserRole)

        self.mw.block_list_widget.clear()
        if not self.mw.data_store.data: 
            log_debug("[BlockListUpdater] populate_blocks: No original data.")
            return
        
        problem_definitions = {}
        if self.mw.current_game_rules:
            problem_definitions = self.mw.current_game_rules.get_problem_definitions()

        dir_nodes = {"": self.mw.block_list_widget.invisibleRootItem()}

        # Compute aggregated problems for ALL blocks once (O(M) complexity)
        pre_aggregated_counts = {}
        for (b_idx, _, _), problems in self.mw.data_store.problems_per_subline.items():
            if b_idx not in pre_aggregated_counts:
                pre_aggregated_counts[b_idx] = {}
            for p_id in problems:
                pre_aggregated_counts[b_idx][p_id] = pre_aggregated_counts[b_idx].get(p_id, 0) + 1

        for i in range(len(self.mw.data_store.data)):
            base_display_name = self.mw.data_store.block_names.get(str(i), f"Block {i}")
            
            block_problem_counts = {pid: 0 for pid in problem_definitions.keys()}
            
            string_count = 0
            if isinstance(self.mw.data_store.data[i], list):
                string_count = len(self.mw.data_store.data[i])
                block_counts = pre_aggregated_counts.get(i, {})
                for pid in problem_definitions.keys():
                    block_problem_counts[pid] = block_counts.get(pid, 0)
            
            base_display_name_with_count = f"{base_display_name} [{string_count}]"
            display_name_with_issues = base_display_name_with_count
            issue_texts = []
            
            sorted_problem_ids_for_display = sorted(
                block_problem_counts.keys(),
                key=lambda pid: problem_definitions.get(pid, {}).get("priority", 99)
            )

            for problem_id in sorted_problem_ids_for_display:
                count = block_problem_counts[problem_id]
                if count > 0:
                    problem_name_from_def = problem_definitions.get(problem_id, {}).get("name", problem_id)
                    problem_name_short = problem_name_from_def.split(" ")[0].lower()
                    if "empty" in problem_name_short and "odd" in problem_name_short:
                        problem_name_short = "emptyOdd"
                    elif "width" in problem_name_short or "ширин" in problem_name_short : 
                        problem_name_short = "width"
                    elif "short" in problem_name_short or "корот" in problem_name_short: 
                        problem_name_short = "short"
                    else: 
                        problem_name_short = problem_name_short[:5]

                    issue_texts.append(f"{count} {problem_name_short}")
            
            if issue_texts:
                display_name_with_issues = f"{base_display_name_with_count} ({', '.join(issue_texts)})"
                
            from pathlib import Path
            from PyQt5.QtWidgets import QTreeWidgetItem
            from PyQt5.QtGui import QIcon

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

            item = self.mw.block_list_widget.create_item(display_name_with_issues, i, Qt.UserRole)
            parent_item = dir_nodes.get(dir_path, dir_nodes[""])
            parent_item.addChild(item)

            if i == current_selection_block_idx:
                self.mw.block_list_widget.setCurrentItem(item)

        self.mw.block_list_widget.viewport().update()
        log_debug(f"[BlockListUpdater] populate_blocks: Done updating.")

    def update_block_item_text_with_problem_count(self, block_idx: int):
        if not hasattr(self.mw, 'block_list_widget'):
            return
        
        from PyQt5.QtWidgets import QTreeWidgetItemIterator
        
        item = None
        iterator = QTreeWidgetItemIterator(self.mw.block_list_widget)
        while iterator.value():
            tree_item = iterator.value()
            if tree_item.data(0, Qt.UserRole) == block_idx:
                item = tree_item
                break
            iterator += 1
            
        if not item: return

        base_display_name = self.mw.data_store.block_names.get(str(block_idx), f"Block {block_idx}")
        
        problem_definitions = {}
        if self.mw.current_game_rules:
            problem_definitions = self.mw.current_game_rules.get_problem_definitions()
        
        block_problem_counts = {pid: 0 for pid in problem_definitions.keys()}

        if block_idx < len(self.mw.data_store.data) and isinstance(self.mw.data_store.data[block_idx], list):
            string_count = len(self.mw.data_store.data[block_idx])
            for data_string_idx in range(len(self.mw.data_store.data[block_idx])):
                data_string_text, _ = self.data_processor.get_current_string_text(block_idx, data_string_idx)
                if data_string_text is not None:
                    logical_sublines = str(data_string_text).split('\n')
                    for subline_local_idx in range(len(logical_sublines)):
                        problem_key = (block_idx, data_string_idx, subline_local_idx)
                        subline_problems = self.mw.data_store.problems_per_subline.get(problem_key, set())
                        for problem_id in subline_problems:
                            if problem_id in block_problem_counts:
                                block_problem_counts[problem_id] += 1
        
        base_display_name_with_count = f"{base_display_name} [{string_count}]"
        display_name_with_issues = base_display_name_with_count
        issue_texts = []

        sorted_problem_ids_for_display = sorted(
            block_problem_counts.keys(),
            key=lambda pid: problem_definitions.get(pid, {}).get("priority", 99)
        )

        for problem_id in sorted_problem_ids_for_display:
            count = block_problem_counts[problem_id]
            if count > 0:
                problem_name_from_def = problem_definitions.get(problem_id, {}).get("name", problem_id)
                problem_name_short = problem_name_from_def.split(" ")[0].lower()
                if "empty" in problem_name_short and "odd" in problem_name_short:
                    problem_name_short = "emptyOdd"
                elif "width" in problem_name_short or "ширин" in problem_name_short:
                    problem_name_short = "width"
                elif "short" in problem_name_short or "корот" in problem_name_short:
                    problem_name_short = "short"
                else:
                    problem_name_short = problem_name_short[:5]
                issue_texts.append(f"{count} {problem_name_short}")
        
        if issue_texts:
            display_name_with_issues = f"{base_display_name_with_count} ({', '.join(issue_texts)})"
        
        if item.text(0) != display_name_with_issues:
            item.setText(0, display_name_with_issues)
        
        self.mw.block_list_widget.viewport().update()

    def clear_all_problem_block_highlights_and_text(self): 
        if not hasattr(self.mw, 'block_list_widget'): return
        
        from PyQt5.QtWidgets import QTreeWidgetItemIterator
        
        iterator = QTreeWidgetItemIterator(self.mw.block_list_widget)
        while iterator.value():
            item = iterator.value()
            block_idx = item.data(0, Qt.UserRole)
            if block_idx is not None:
                base_display_name = self.mw.data_store.block_names.get(str(block_idx), f"Block {block_idx}")
                if item.text(0) != base_display_name: 
                    item.setText(0, base_display_name)
            iterator += 1
            
        if hasattr(self.mw, 'block_list_widget'):
            self.mw.block_list_widget.viewport().update()
        log_debug("[BlockListUpdater] Cleared all problem/warning/width/short block highlights and count texts.")