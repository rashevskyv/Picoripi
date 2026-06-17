import re
from PyQt6.QtCore import Qt, QTimer
from PyQt6.QtGui import QIcon
from PyQt6.QtWidgets import QTreeWidgetItem, QTreeWidgetItemIterator, QStyle
from utils.logging_utils import log_info, log_warning
from pathlib import Path
from .base_ui_updater import BaseUIUpdater

class BlockListUpdater(BaseUIUpdater):
    """Block list updater implementation."""
    def __init__(self, main_window, data_processor):
        """Initialize a new instance."""
        super().__init__(main_window, data_processor)
        self._block_items_cache = {}  # {block_idx: [QTreeWidgetItem, ...]}
        self._chapters_load_worker = None
        self._chapters_cache = None
        self._chapters_cache_wing_name = None
        self._chapters_load_error = None
        self._is_loading_chapters = False


    def _set_item_style_icon(self, item: QTreeWidgetItem, column: int, standard_icon_enum) -> None:
        """Internal helper to set the item style icon."""
        try:
            if hasattr(self.mw, 'style') and self.mw.style():
                icon = self.mw.style().standardIcon(standard_icon_enum)
                from PyQt6.QtGui import QIcon
                if isinstance(icon, QIcon) and not icon.isNull():
                    item.setIcon(column, icon)
        except Exception:
            pass

    def _register_item_in_cache(self, item: QTreeWidgetItem):
        """Internal helper to register item in cache."""
        block_idx = item.data(0, Qt.ItemDataRole.UserRole)
        if block_idx is not None:
            self._block_items_cache.setdefault(block_idx, []).append(item)

    def _get_block_display_name_with_ext(self, block_idx: int, base_display_name: str) -> str:
        """Internal helper to get the block display name with ext."""
        if hasattr(self.mw, 'project_manager') and self.mw.project_manager and self.mw.project_manager.project:
            pm = self.mw.project_manager
            block_map = getattr(self.mw, 'block_to_project_file_map', {})
            proj_b_idx = block_map.get(block_idx, block_idx)
            try:
                if (isinstance(proj_b_idx, int) and
                    isinstance(pm.project.blocks, list) and
                    proj_b_idx < len(pm.project.blocks)):

                    block = pm.project.blocks[proj_b_idx]
                    if block is not None and isinstance(getattr(block, 'metadata', None), dict):
                        is_archive = block.metadata.get('is_archive_member', False)
                        if is_archive:
                            orig_filename = block.metadata.get('archive_file_name') or Path(block.source_file).name
                            ext = Path(orig_filename).suffix
                            if ext and not base_display_name.lower().endswith(ext.lower()):
                                return f"{base_display_name}{ext}"
            except Exception:
                pass
        return base_display_name

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
            block_idx = item.data(0, Qt.ItemDataRole.UserRole)
            category_name = item.data(0, Qt.ItemDataRole.UserRole + 10)
            folder_id = item.data(0, Qt.ItemDataRole.UserRole + 1)
            chapter_id = item.data(0, Qt.ItemDataRole.UserRole + 11)
            
            if chapter_id is not None:
                item_id = f"chapter_{chapter_id}"
                item_type = 'chapter'
            elif folder_id is not None:
                item_id = f"folder_{folder_id}"
                item_type = 'folder'
            elif category_name is not None:
                parent = item.parent()
                if parent:
                    p_block_idx = parent.data(0, Qt.ItemDataRole.UserRole)
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
            "selected_string_idx": self.mw.data_store.current_string_idx if (hasattr(self.mw, 'data_store') and hasattr(self.mw.data_store, 'current_string_idx')) else (self.mw.current_string_idx if hasattr(self.mw, 'current_string_idx') else -1)
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
        
        # Set a flag indicating that session state is being restored to prevent double loads
        self.mw._restoring_session_state = True
        
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
                try:
                    from PyQt6 import sip
                except ImportError:
                    import sip

                def safe_isdeleted(obj):
                    try:
                        return sip.isdeleted(obj)
                    except (TypeError, RuntimeError):
                        return False

                try:
                    if not self.mw.block_list_widget or safe_isdeleted(self.mw.block_list_widget):
                        self.mw._restoring_session_state = False
                        return

                    # Re-find the item to avoid "deleted object" errors
                    target_item = None
                    iterator = QTreeWidgetItemIterator(self.mw.block_list_widget)
                    while iterator.value():
                        item = iterator.value()
                        if not safe_isdeleted(item):
                            try:
                                if self._get_item_id(item) == selected_id:
                                    target_item = item
                                    break
                            except RuntimeError:
                                pass
                        iterator += 1
                    
                    if target_item and not safe_isdeleted(target_item):
                        log_info(f"UIUpdater: Restoring selection to {selected_id}")
                        self.mw.block_list_widget.setFocus()
                        self.mw.block_list_widget.setCurrentItem(target_item)
                        # Manually trigger block load
                        self.mw.list_selection_handler.block_selected(target_item, None)
                        
                        if selected_string_idx != -1:
                            log_info(f"UIUpdater: Restoring string selection to absolute index {selected_string_idx}")
                            # Further delay for strings to ensure they are populated and mapped
                            from PyQt6.QtCore import QTimer
                            
                            def _select_string_and_restore_scroll():
                                try:
                                    if safe_isdeleted(self.mw.block_list_widget):
                                        return
                                    self.mw.list_selection_handler.select_string_by_absolute_index(selected_string_idx)
                                    
                                    # Restore scroll & cursor after string is loaded and text edits are populated!
                                    if self.mw.edited_text_edit and not safe_isdeleted(self.mw.edited_text_edit):
                                        self.mw.edited_text_edit.verticalScrollBar().setValue(state.get("v_scroll", 0))
                                        self.mw.edited_text_edit.horizontalScrollBar().setValue(state.get("h_scroll", 0))
                                        if self.mw.preview_text_edit and not safe_isdeleted(self.mw.preview_text_edit):
                                            self.mw.preview_text_edit.verticalScrollBar().setValue(state.get("preview_v_scroll", 0))
                                        if self.mw.original_text_edit and not safe_isdeleted(self.mw.original_text_edit):
                                            self.mw.original_text_edit.verticalScrollBar().setValue(state.get("original_v_scroll", 0))
                                            self.mw.original_text_edit.horizontalScrollBar().setValue(state.get("original_h_scroll", 0))
                                        
                                        cursor_pos = state.get("cursor_pos", 0)
                                        try:
                                            doc_len = self.mw.edited_text_edit.document().characterCount() - 1
                                        except Exception:
                                            doc_len = 0
                                        
                                        try:
                                            c_pos = int(cursor_pos) if not hasattr(cursor_pos, '_mock_name') else 0
                                            d_len = int(doc_len) if not hasattr(doc_len, '_mock_name') else 0
                                            pos_to_set = min(c_pos, max(0, d_len))
                                            log_info(f"UIUpdater: Restoring cursor position to {pos_to_set}")
                                        except Exception:
                                            pos_to_set = 0
                                            
                                        cursor = self.mw.edited_text_edit.textCursor()
                                        cursor.setPosition(pos_to_set)
                                        self.mw.edited_text_edit.setTextCursor(cursor)
                                        self.mw.edited_text_edit.ensureCursorVisible()
                                except Exception as e:
                                    log_warning(f"UIUpdater: Error in _select_string_and_restore_scroll: {e}")
                                finally:
                                    # Ensure we clean up the restoration flag
                                    self.mw._restoring_session_state = False
                            
                            QTimer.singleShot(200, _select_string_and_restore_scroll)
                        else:
                            self.mw._restoring_session_state = False
                    else:
                        log_warning(f"UIUpdater: Failed to find item {selected_id} for restoration.")
                        self.mw._restoring_session_state = False
                except Exception as e:
                    log_warning(f"UIUpdater: Error in _delayed_select: {e}")
                    self.mw._restoring_session_state = False
 
            from PyQt6.QtCore import QTimer
            QTimer.singleShot(50, _delayed_select)
        else:
            self.mw._restoring_session_state = False

    def _get_item_id(self, item) -> str:
        """Helper to generate consistent IDs for tree items."""
        if not item: return None
        
        block_idx = item.data(0, Qt.ItemDataRole.UserRole)
        category_name = item.data(0, Qt.ItemDataRole.UserRole + 10)
        folder_id = item.data(0, Qt.ItemDataRole.UserRole + 1)
        chapter_id = item.data(0, Qt.ItemDataRole.UserRole + 11)
        
        if chapter_id is not None:
            return f"chapter_{chapter_id}"
        elif folder_id is not None:
            return f"folder_{folder_id}"
        elif category_name is not None:
            parent = item.parent()
            if parent:
                p_block_idx = parent.data(0, Qt.ItemDataRole.UserRole)
                return f"cat_{p_block_idx}_{category_name}"
        elif block_idx is not None:
            return f"block_{block_idx}"
        return None

    def _get_aggregated_problems_for_block(self, block_idx: int, pre_aggregated_counts: dict = None, category_name: str = None, chapter_id: int = None, speaker_name: str = None, speaker_mappings: list = None) -> dict:
        """Internal helper to get the aggregated problems for block."""
        problem_counts = {}
        if not self.mw.current_game_rules:
            return problem_counts
        
        is_chapter = (block_idx == -2)
        is_speaker = (block_idx == -3)
        if not is_chapter and not is_speaker and not (0 <= block_idx < len(self.mw.data_store.data)):
            return problem_counts
        
        problem_definitions = self.mw.current_game_rules.get_problem_definitions()
        problem_counts = {pid: 0 for pid in problem_definitions.keys()}
        detection_config = getattr(self.mw, 'detection_enabled', {})

        if is_speaker:
            spk_mappings = set(speaker_mappings or [])
            if not spk_mappings and speaker_name and hasattr(self.mw, 'project_manager') and self.mw.project_manager.project:
                for b_idx, block in enumerate(self.mw.project_manager.project.blocks):
                    assignments = block.metadata.get("character_assignments", {})
                    for s_idx_str, c_name in assignments.items():
                        if c_name == speaker_name:
                            spk_mappings.add((b_idx, int(s_idx_str)))
            
            for (b_idx, s_idx, subline_idx), problems in self.mw.data_store.problems_per_subline.items():
                if (b_idx, s_idx) in spk_mappings:
                    filtered_problems = {p_id for p_id in problems if detection_config.get(p_id, True)}
                    for p_id in filtered_problems:
                        if p_id in problem_counts:
                            problem_counts[p_id] += 1
            return problem_counts

        if is_chapter:
            mappings = []
            if chapter_id is not None:
                if hasattr(self, '_chapter_mappings_cache') and self._chapter_mappings_cache is not None and chapter_id in self._chapter_mappings_cache:
                    mappings = self._chapter_mappings_cache[chapter_id]
                else:
                    composer = getattr(self.mw, "translation_handler", None)
                    if composer and hasattr(composer, "prompt_composer"):
                        client = composer.prompt_composer._get_mempalace_client()
                        if client:
                            wing_name = composer.prompt_composer._get_wing_name()
                            mappings = client.get_chapter_mappings(wing_name, chapter_id)
            ch_mappings = set()
            for m in mappings:
                bmg_id = m.get("bmg_id")
                indices = self.mw.list_selection_handler.resolve_bmg_id_to_indices(bmg_id)
                if indices:
                    ch_mappings.add(indices)
            
            for (b_idx, s_idx, subline_idx), problems in self.mw.data_store.problems_per_subline.items():
                if (b_idx, s_idx) in ch_mappings:
                    filtered_problems = {p_id for p_id in problems if detection_config.get(p_id, True)}
                    for p_id in filtered_problems:
                        if p_id in problem_counts:
                            problem_counts[p_id] += 1
            return problem_counts
        
        if pre_aggregated_counts is not None and category_name is None:
            # Fast path: use the pre-calculated problem counts for this block (only for full blocks)
            block_counts = pre_aggregated_counts.get(block_idx, {})
            return {pid: block_counts.get(pid, 0) for pid in problem_definitions.keys()}
        
        # Slow path/Category path
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
        
        if tooltip_lines:
            item.setToolTip(0, "<br><br>".join(tooltip_lines))
        else:
            item.setToolTip(0, "")

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
        """Check if project block index is unsaved."""
        block_map = getattr(self.mw, 'block_to_project_file_map', {})
        if isinstance(block_map, dict) and block_map:
            return any(
                block_map.get(data_idx) == project_block_idx 
                for data_idx in self.mw.data_store.unsaved_block_indices
            )
        return project_block_idx in self.mw.data_store.unsaved_block_indices

    def _folder_has_unsaved_blocks(self, folder, project, id_to_idx: dict) -> bool:
        """Helper to recursively check if folder or its children have unsaved blocks."""
        for b_id in folder.block_ids:
            idx = id_to_idx.get(b_id)
            if idx is not None and self._is_project_block_unsaved(idx):
                return True
        for child in folder.children:
            if self._folder_has_unsaved_blocks(child, project, id_to_idx):
                return True
        return False

    def _add_virtual_folder_to_tree(self, parent_item, folder, problem_definitions, current_selection_block_idx, pre_aggregated_counts: dict = None, folder_id_to_select=None):
        """Recursively add virtual folders and their blocks to the tree with folder compaction (GitHub style)."""
        project = self.mw.project_manager.project
        if not project: return

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
            id_to_idx = {b.id: idx for idx, b in enumerate(project.blocks)}
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
            
        parent_item.addChild(folder_item)
        
        if compaction_type != 2:
            # Standard recursive children population (only if NOT compacted with block)
            for child in curr_for_children.children:
                self._add_virtual_folder_to_tree(folder_item, child, problem_definitions, current_selection_block_idx, pre_aggregated_counts, folder_id_to_select=folder_id_to_select)
                
            id_to_idx = {b.id: idx for idx, b in enumerate(project.blocks)}
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

    def populate_blocks(self, override_folder_id=None, override_block_idx=None):
        """Populate blocks."""
        if not hasattr(self.mw, 'block_list_widget') or not self.mw.block_list_widget:
            return  # Sometimes called during initialization before block_list_widget is created

        current_selection_block_idx = override_block_idx
        current_selection_folder_id = override_folder_id
        
        if current_selection_block_idx is None and current_selection_folder_id is None:
            current_item = self.mw.block_list_widget.currentItem()
            if current_item:
                current_selection_block_idx = current_item.data(0, Qt.ItemDataRole.UserRole)
                current_selection_folder_id = current_item.data(0, Qt.ItemDataRole.UserRole + 1)
            else:
                # Robust fallback using data_store selection state
                if hasattr(self.mw, 'data_store'):
                    if getattr(self.mw.data_store, 'current_chapter_id', None) is not None:
                        current_selection_block_idx = -2
                    elif getattr(self.mw.data_store, 'current_block_idx', -1) != -1:
                        current_selection_block_idx = self.mw.data_store.current_block_idx
        
        # Save scroll position
        v_scroll = self.mw.block_list_widget.verticalScrollBar().value()
        
        # Don't let signals trigger more refreshes while we are rebuilding
        self.mw.block_list_widget.blockSignals(True)
        self.mw.block_list_widget._is_programmatic_expansion = True
        self.mw.block_list_widget.setUpdatesEnabled(False)
        
        try:
            self.mw.block_list_widget.clear()
            self._block_items_cache.clear()
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
                        if (getattr(self.mw.data_store, 'show_unsaved_blocks_only', False) is not True or 
                                self._is_project_block_unsaved(idx)):
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
                    if (getattr(self.mw.data_store, 'show_unsaved_blocks_only', False) is True and 
                            i not in self.mw.data_store.unsaved_block_indices):
                        continue
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

            # 3. Add virtual Chapters folder hierarchy from MemePalace if available
            try:
                composer = getattr(self.mw, "translation_handler", None)
                if composer and hasattr(composer, "prompt_composer"):
                    client = composer.prompt_composer._get_mempalace_client()
                    if client:
                        wing_name = composer.prompt_composer._get_wing_name()
                        
                        # Check if wing changed
                        if getattr(self, '_chapters_cache_wing_name', None) != wing_name:
                            # Clean up old worker and caches
                            if self._chapters_load_worker:
                                try:
                                    self._chapters_load_worker.finished_signal.disconnect(self._on_chapters_loaded)
                                    self._chapters_load_worker.error_signal.disconnect(self._on_chapters_load_failed)
                                except TypeError:
                                    pass
                                self._chapters_load_worker = None
                            self._chapters_cache = None
                            self._chapter_mappings_cache = None
                            self._chapters_cache_wing_name = wing_name
                            self._chapters_load_error = None
                            self._is_loading_chapters = False

                        # Check if running in tests or with MagicMocks to load synchronously
                        from unittest.mock import MagicMock
                        is_test = (isinstance(client, MagicMock) or 
                                   'Mock' in type(client).__name__ or 
                                   getattr(self.mw, '_is_test_mode', False))
                        if is_test and self._chapters_cache is None:
                            try:
                                self._chapter_mappings_cache = client.get_all_chapter_mappings(wing_name)
                                self._chapters_cache = client.get_all_chapters(wing_name)
                                self._is_loading_chapters = False
                            except Exception as e_test:
                                self._chapters_load_error = str(e_test)
                        
                        if self._chapters_load_error:
                            # Show load error placeholder
                            chapters_root = QTreeWidgetItem(["Chapters (Load Error)"])
                            self._set_item_style_icon(chapters_root, 0, QStyle.StandardPixmap.SP_DirIcon)
                            chapters_root.setFlags(chapters_root.flags() & ~Qt.ItemFlag.ItemIsEditable)
                            
                            err_item = QTreeWidgetItem([f"Error: {self._chapters_load_error}"])
                            err_item.setFlags(err_item.flags() & ~Qt.ItemFlag.ItemIsEditable)
                            self._set_item_style_icon(err_item, 0, QStyle.StandardPixmap.SP_MessageBoxCritical)
                            chapters_root.addChild(err_item)
                            
                            self.mw.block_list_widget.invisibleRootItem().addChild(chapters_root)
                            
                        elif self._is_loading_chapters:
                            # Show loading placeholder
                            chapters_root = QTreeWidgetItem(["Chapters"])
                            self._set_item_style_icon(chapters_root, 0, QStyle.StandardPixmap.SP_DirIcon)
                            chapters_root.setFlags(chapters_root.flags() & ~Qt.ItemFlag.ItemIsEditable)
                            
                            loading_item = QTreeWidgetItem(["Loading..."])
                            loading_item.setFlags(loading_item.flags() & ~Qt.ItemFlag.ItemIsEditable)
                            self._set_item_style_icon(loading_item, 0, QStyle.StandardPixmap.SP_BrowserReload)
                            chapters_root.addChild(loading_item)
                            
                            self.mw.block_list_widget.invisibleRootItem().addChild(chapters_root)
                            
                        elif self._chapters_cache is not None:
                            # We have cached chapters, build the hierarchy
                            chapters_root = QTreeWidgetItem(["Chapters"])
                            self._set_item_style_icon(chapters_root, 0, QStyle.StandardPixmap.SP_DirIcon)
                            chapters_root.setFlags(chapters_root.flags() & ~Qt.ItemFlag.ItemIsEditable)
                            
                            act_nodes = {}
                            for ch in self._chapters_cache:
                                ch_id = ch.get("id")
                                
                                # Pre-calculate ch_mappings and store it on the item to avoid DB query in paint delegate
                                ch_mappings_list = []
                                if self._chapter_mappings_cache and ch_id in self._chapter_mappings_cache:
                                    for m in self._chapter_mappings_cache[ch_id]:
                                        bmg_id = m.get("bmg_id")
                                        if hasattr(self.mw, 'list_selection_handler'):
                                            indices = self.mw.list_selection_handler.resolve_bmg_id_to_indices(bmg_id)
                                            if indices:
                                                ch_mappings_list.append(indices)
                                                
                                # Filter chapters by unsaved strings if requested
                                if getattr(self.mw.data_store, 'show_unsaved_blocks_only', False) is True:
                                    has_unsaved_in_chapter = any(mapping in self.mw.data_store.edited_data for mapping in ch_mappings_list)
                                    if not has_unsaved_in_chapter:
                                        continue
                                        
                                num = ch.get("num", "")
                                title = ch.get("title", "")
                                
                                # Parse Act and Chapter
                                m = re.search(r'Act\s+([^,]+),\s*Ch\s+(.+)', num, re.IGNORECASE)
                                if m:
                                    act_part = m.group(1).strip()
                                    ch_part = m.group(2).strip()
                                    act_name = f"Act {act_part}"
                                    ch_name = f"Chapter {ch_part}: {title}"
                                else:
                                    m2 = re.search(r'Act\s+([^,]+)', num, re.IGNORECASE)
                                    if m2:
                                        act_part = m2.group(1).strip()
                                        act_name = f"Act {act_part}"
                                        ch_name = f"Chapter {num}: {title}"
                                    else:
                                        act_name = "Act 1"
                                        ch_name = f"Chapter {num}: {title}"
                                
                                if act_name not in act_nodes:
                                    act_item = QTreeWidgetItem([act_name])
                                    self._set_item_style_icon(act_item, 0, QStyle.StandardPixmap.SP_DirIcon)
                                    act_item.setFlags(act_item.flags() & ~Qt.ItemFlag.ItemIsEditable)
                                    chapters_root.addChild(act_item)
                                    act_nodes[act_name] = act_item
                                
                                ch_item = QTreeWidgetItem([ch_name])
                                self._set_item_style_icon(ch_item, 0, QStyle.StandardPixmap.SP_FileDialogDetailedView)
                                ch_item.setFlags(ch_item.flags() & ~Qt.ItemFlag.ItemIsEditable)
                                ch_item.setData(0, Qt.ItemDataRole.UserRole, -2) # Special block index for chapters
                                ch_item.setData(0, Qt.ItemDataRole.UserRole + 11, ch_id) # Store chapter ID
                                ch_item.setData(0, Qt.ItemDataRole.UserRole + 4, ch_name)
                                ch_item.setData(0, Qt.EditRole, ch_name)
                                ch_item.setData(0, Qt.ItemDataRole.UserRole + 13, ch_mappings_list)
                                
                                self._register_item_in_cache(ch_item)
                                problem_definitions = self.mw.current_game_rules.get_problem_definitions() if self.mw.current_game_rules else {}
                                ch_problem_counts = self._get_aggregated_problems_for_block(-2, chapter_id=ch_id)
                                self._apply_issues_and_tooltip(ch_item, ch_name, ch_problem_counts, problem_definitions)
                                
                                act_nodes[act_name].addChild(ch_item)
                                
                                # Restore chapter selection
                                if current_selection_block_idx == -2 and getattr(self.mw.data_store, 'current_chapter_id', None) == ch_id:
                                    self.mw.block_list_widget.setCurrentItem(ch_item)
                                    ch_item.setSelected(True)
                                    act_nodes[act_name].setExpanded(True)
                                    chapters_root.setExpanded(True)
                                    
                            # Remove empty Acts if any
                            for act_name, act_item in list(act_nodes.items()):
                                if act_item.childCount() == 0:
                                    chapters_root.removeChild(act_item)
                                    
                            if chapters_root.childCount() > 0:
                                self.mw.block_list_widget.invisibleRootItem().addChild(chapters_root)
                        else:
                            # Cache is empty, and we are not currently loading. Start async load.
                            self._is_loading_chapters = True
                            self._chapters_load_error = None
                            
                            from core.mempalace_worker import MemePalaceChaptersLoadWorker
                            self._chapters_load_worker = MemePalaceChaptersLoadWorker(client, wing_name)
                            self._chapters_load_worker.finished_signal.connect(self._on_chapters_loaded)
                            self._chapters_load_worker.error_signal.connect(self._on_chapters_load_failed)
                            self._chapters_load_worker.start()
                            
                            # Show loading placeholder
                            chapters_root = QTreeWidgetItem(["Chapters"])
                            self._set_item_style_icon(chapters_root, 0, QStyle.StandardPixmap.SP_DirIcon)
                            chapters_root.setFlags(chapters_root.flags() & ~Qt.ItemFlag.ItemIsEditable)
                            
                            loading_item = QTreeWidgetItem(["Loading..."])
                            loading_item.setFlags(loading_item.flags() & ~Qt.ItemFlag.ItemIsEditable)
                            self._set_item_style_icon(loading_item, 0, QStyle.StandardPixmap.SP_BrowserReload)
                            chapters_root.addChild(loading_item)
                            
                            self.mw.block_list_widget.invisibleRootItem().addChild(chapters_root)
            except Exception as e:
                from utils.logging_utils import log_error
                log_error(f"Error populating Chapters folder: {e}", exc_info=True)

            # 4. Add virtual Speakers folder hierarchy
            try:
                # Query MemePalace for speakers as well
                client = None
                composer = getattr(self.mw, "translation_handler", None)
                if composer and hasattr(composer, "prompt_composer"):
                    client = composer.prompt_composer._get_mempalace_client()

                mempalace_speakers = {}  # {speaker_name: [(b_idx, s_idx), ...]}
                if client:
                    wing_name = composer.prompt_composer._get_wing_name() if hasattr(composer, "prompt_composer") else "Zelda_TP"
                    # Try using _bmg_to_context cache first
                    if hasattr(client, "_bmg_to_context") and client._bmg_to_context:
                        for bmg_id_key, ctx_info in client._bmg_to_context.items():
                            if bmg_id_key.startswith("[") and bmg_id_key.endswith("]"):
                                continue
                            speaker = ctx_info.get("speaker")
                            if speaker and str(speaker).strip() and str(speaker).lower() not in ("unknown", "none"):
                                speaker_name = str(speaker).strip()
                                if hasattr(self.mw, 'list_selection_handler'):
                                    indices = self.mw.list_selection_handler.resolve_bmg_id_to_indices(bmg_id_key)
                                    if indices:
                                        mempalace_speakers.setdefault(speaker_name, []).append(indices)
                    
                    # Fallback to loading script mappings + script file if cache is empty
                    if not mempalace_speakers and hasattr(composer, "prompt_composer"):
                        import os
                        script_path = composer.prompt_composer._find_script_path()
                        if script_path and os.path.exists(script_path):
                            line_to_speaker = getattr(composer.prompt_composer, "_line_to_speaker_cache", None)
                            cached_path = getattr(composer.prompt_composer, "_line_to_speaker_path", None)
                            if not line_to_speaker or cached_path != script_path:
                                try:
                                    lines = getattr(composer.prompt_composer, "_script_lines_cache", None)
                                    if not lines:
                                        try:
                                            with open(script_path, "r", encoding="cp1252", errors="replace") as f:
                                                lines = f.readlines()
                                        except Exception:
                                            with open(script_path, "r", encoding="utf-8", errors="replace") as f:
                                                lines = f.readlines()
                                        composer.prompt_composer._script_lines_cache = lines
                                    
                                    def line_strip_is_speaker(s: str) -> bool:
                                        return s.isupper() and len(s) >= 2 and re.match(r'^[A-Z0-9\s#]+$', s) is not None

                                    line_to_speaker = {}
                                    current_speaker = None
                                    for idx, line in enumerate(lines):
                                        line_strip = line.strip()
                                        if not line_strip:
                                            continue
                                        if line_strip.startswith("[") and line_strip.endswith("]"):
                                            continue
                                        if line_strip_is_speaker(line_strip):
                                            current_speaker = line_strip
                                        if current_speaker:
                                            line_to_speaker[idx + 1] = current_speaker
                                    
                                    composer.prompt_composer._line_to_speaker_cache = line_to_speaker
                                    composer.prompt_composer._line_to_speaker_path = script_path
                                except Exception as e_parse:
                                    from utils.logging_utils import log_error
                                    log_error(f"Error building line_to_speaker map in block_list_updater: {e_parse}")
                                    line_to_speaker = None
                            
                            if line_to_speaker:
                                all_mappings = client.get_all_chapter_mappings(wing_name)
                                for ch_id, ch_maps in all_mappings.items():
                                    for mapping in ch_maps:
                                        bmg_id_key = mapping.get("bmg_id")
                                        script_line = mapping.get("script_line")
                                        if bmg_id_key and script_line:
                                            speaker = line_to_speaker.get(script_line)
                                            if speaker and str(speaker).strip() and str(speaker).lower() not in ("unknown", "none"):
                                                speaker_name = str(speaker).strip()
                                                if hasattr(self.mw, 'list_selection_handler'):
                                                    indices = self.mw.list_selection_handler.resolve_bmg_id_to_indices(bmg_id_key)
                                                    if indices:
                                                        mempalace_speakers.setdefault(speaker_name, []).append(indices)

                combined_speakers = {}  # {speaker_name: [(b_idx, s_idx), ...]}
                assigned_strings = set()  # {(b_idx, s_idx), ...}

                # 1. Project assignments (highest priority)
                project = getattr(self.mw, 'project_manager', None) and self.mw.project_manager.project
                if project:
                    block_map = getattr(self.mw, 'block_to_project_file_map', {})
                    project_to_block_map = {}
                    if block_map:
                        project_to_block_map = {proj_idx: data_idx for data_idx, proj_idx in block_map.items()}
                        
                    for proj_b_idx, block in enumerate(project.blocks):
                        assignments = block.metadata.get("character_assignments", {})
                        for s_idx_str, c_name in assignments.items():
                            if c_name and str(c_name).strip() and str(c_name).lower() not in ("unknown", "none"):
                                speaker_name = str(c_name).strip()
                                s_idx = int(s_idx_str)
                                data_idx = project_to_block_map.get(proj_b_idx, proj_b_idx)
                                combined_speakers.setdefault(speaker_name, []).append((data_idx, s_idx))
                                assigned_strings.add((data_idx, s_idx))

                # 2. Add MemePalace speakers (only if not already assigned in project metadata)
                for speaker_name, strings in mempalace_speakers.items():
                    for string_tuple in strings:
                        if string_tuple in assigned_strings:
                            continue
                        combined_speakers.setdefault(speaker_name, []).append(string_tuple)
                        assigned_strings.add(string_tuple)

                # 3. Collect all other strings into "None"
                none_strings = []
                for b_idx in range(len(self.mw.data_store.data)):
                    block_data = self.mw.data_store.data[b_idx]
                    for s_idx in range(len(block_data)):
                        if (b_idx, s_idx) not in assigned_strings:
                            none_strings.append((b_idx, s_idx))

                if none_strings:
                    combined_speakers["None"] = none_strings

                unique_speakers = sorted([c for c in combined_speakers.keys() if c != "None"])
                if "None" in combined_speakers:
                    unique_speakers.insert(0, "None")

                has_named_speakers = any(c != "None" for c in combined_speakers.keys())
                if combined_speakers and has_named_speakers:
                    speakers_root = QTreeWidgetItem(["Speakers"])
                    self._set_item_style_icon(speakers_root, 0, QStyle.StandardPixmap.SP_DirIcon)
                    speakers_root.setFlags(speakers_root.flags() & ~Qt.ItemFlag.ItemIsEditable)

                    for speaker_name in unique_speakers:
                        speaker_mappings_list = combined_speakers[speaker_name]

                        if getattr(self.mw.data_store, 'show_unsaved_blocks_only', False) is True:
                            has_unsaved_in_speaker = any(mapping in self.mw.data_store.edited_data for mapping in speaker_mappings_list)
                            if not has_unsaved_in_speaker:
                                continue

                        speaker_item = QTreeWidgetItem([speaker_name])
                        self._set_item_style_icon(speaker_item, 0, QStyle.StandardPixmap.SP_FileDialogDetailedView)
                        speaker_item.setFlags(speaker_item.flags() & ~Qt.ItemFlag.ItemIsEditable)
                        speaker_item.setData(0, Qt.ItemDataRole.UserRole, -3)
                        speaker_item.setData(0, Qt.ItemDataRole.UserRole + 15, speaker_name)
                        speaker_item.setData(0, Qt.ItemDataRole.UserRole + 4, speaker_name)
                        speaker_item.setData(0, Qt.EditRole, speaker_name)
                        speaker_item.setData(0, Qt.ItemDataRole.UserRole + 13, speaker_mappings_list)

                        self._register_item_in_cache(speaker_item)
                        
                        problem_definitions = self.mw.current_game_rules.get_problem_definitions() if self.mw.current_game_rules else {}
                        speaker_problem_counts = self._get_aggregated_problems_for_block(-3, speaker_name=speaker_name, speaker_mappings=speaker_mappings_list)
                        self._apply_issues_and_tooltip(speaker_item, speaker_name, speaker_problem_counts, problem_definitions)

                        speakers_root.addChild(speaker_item)

                        if current_selection_block_idx == -3 and getattr(self.mw.data_store, 'current_speaker_name', None) == speaker_name:
                            self.mw.block_list_widget.setCurrentItem(speaker_item)
                            speaker_item.setSelected(True)
                            speakers_root.setExpanded(True)

                    if speakers_root.childCount() > 0:
                        self.mw.block_list_widget.invisibleRootItem().addChild(speakers_root)
            except Exception as e:
                from utils.logging_utils import log_error
                log_error(f"Error populating Speakers folder: {e}", exc_info=True)
        finally:
            self.mw.block_list_widget._is_programmatic_expansion = False
            self.mw.block_list_widget.blockSignals(False)
            self.mw.block_list_widget.setUpdatesEnabled(True)
            self.mw.block_list_widget.verticalScrollBar().setValue(v_scroll)

        self.mw.block_list_widget.viewport().update()


    def update_block_item_text_with_problem_count(self, block_idx: int):
        """Update the block item text with problem count."""
        if not hasattr(self.mw, 'block_list_widget'):
            return
        
        items_to_update = self._block_items_cache.get(block_idx, [])
        if not items_to_update:
            # Fallback for unit tests where items are added manually without populate_blocks
            iterator = QTreeWidgetItemIterator(self.mw.block_list_widget)
            while iterator.value():
                tree_item = iterator.value()
                if tree_item.data(0, Qt.ItemDataRole.UserRole) == block_idx:
                    items_to_update.append(tree_item)
                iterator += 1

        if not items_to_update: return

        problem_definitions = self.mw.current_game_rules.get_problem_definitions() if self.mw.current_game_rules else {}

        self.mw.block_list_widget.blockSignals(True)
        try:
            for item in items_to_update:
                is_virtual_row = item.data(0, Qt.ItemDataRole.UserRole + 12)
                if is_virtual_row:
                    continue
                category_name = item.data(0, Qt.ItemDataRole.UserRole + 10)
                ch_id = item.data(0, Qt.ItemDataRole.UserRole + 11)
                
                # Try to use stored base name to preserve folder path in compacted view
                base_display_name = item.data(0, Qt.ItemDataRole.UserRole + 4)
                if base_display_name is None:
                    base_display_name = self.mw.data_store.block_names.get(str(block_idx), f"Block {block_idx}")
                    base_display_name = self._get_block_display_name_with_ext(block_idx, base_display_name)
                    
                block_problem_counts = self._get_aggregated_problems_for_block(block_idx, category_name=category_name, chapter_id=ch_id)
                self._apply_issues_and_tooltip(item, base_display_name, block_problem_counts, problem_definitions)
        finally:
            self.mw.block_list_widget.blockSignals(False)
            
        # Global update to ensure all delegates are re-run for visible ancestors
        self.mw.block_list_widget.viewport().update()

    def highlight_problem_block(self, block_idx: int, highlight: bool, is_critical: bool = True):
        """Highlight problem block."""
        pass 

    def clear_all_problem_block_highlights_and_text(self): 
        """Remove all problem block highlights and text."""
        if not hasattr(self.mw, 'block_list_widget'): return
        
        iterator = QTreeWidgetItemIterator(self.mw.block_list_widget)
        while iterator.value():
            item = iterator.value()
            block_idx = item.data(0, Qt.ItemDataRole.UserRole)
            if block_idx is not None:
                base_display_name = item.data(0, Qt.ItemDataRole.UserRole + 4)
                if base_display_name is None:
                    base_display_name = self.mw.data_store.block_names.get(str(block_idx), f"Block {block_idx}")
                    base_display_name = self._get_block_display_name_with_ext(block_idx, base_display_name)
                
                if item.text(0) != base_display_name: 
                    item.setText(0, base_display_name) 
                item.setToolTip(0, "") 
            iterator += 1

        if hasattr(self.mw, 'block_list_widget'):
            self.mw.block_list_widget.viewport().update()

    def _on_chapters_loaded(self, chapters, mappings):
        """Slot for successful async loading of MemePalace chapters."""
        self._chapters_cache = chapters
        self._chapter_mappings_cache = mappings
        self._is_loading_chapters = False
        self._chapters_load_worker = None
        self.populate_blocks()

    def _on_chapters_load_failed(self, error_msg):
        """Slot for failed async loading of MemePalace chapters."""
        self._chapters_load_error = error_msg
        self._is_loading_chapters = False
        self._chapters_load_worker = None
        self.populate_blocks()


