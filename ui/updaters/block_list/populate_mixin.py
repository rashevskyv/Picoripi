"""Full block-tree population."""
from __future__ import annotations

import re
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QIcon
from PyQt6.QtWidgets import QTreeWidgetItem, QStyle
from pathlib import Path
from core.mempalace.story_timeline import StoryVirtualProjection
from core.manual_story_structures import apply_manual_story_structures

class PopulateMixin:
    """Full block-tree population."""

    def populate_blocks(self, override_folder_id=None, override_block_idx=None):
        """Populate blocks."""
        self._story_context_overrides_cache = None
        self._story_structure_overrides_cache = None
        self._story_override_index_cache = None
        if not hasattr(self.mw, 'block_list_widget') or not self.mw.block_list_widget:
            return  # Sometimes called during initialization before block_list_widget is created
        self._cache_story_overrides = True

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
                    from core.data_store import store_is_virtual_view
                    if store_is_virtual_view(self.mw.data_store):
                        current_selection_block_idx = self.mw.data_store.view_block_token
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
                id_to_idx = {b.id: idx for idx, b in enumerate(project.blocks)}

                # 1. Add virtual folders recursively
                for folder in project.virtual_folders:
                    self._add_virtual_folder_to_tree(
                        root_item, folder, problem_definitions, current_selection_block_idx,
                        pre_aggregated_counts, folder_id_to_select=current_selection_folder_id,
                        id_to_idx=id_to_idx,
                    )

                # 2. Add root blocks
                root_block_ids = project.metadata.get('root_block_ids', [])

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

            # 3. Add the Story hierarchy from MemePalace if game rows are loaded.
            try:
                composer = getattr(self.mw, "translation_handler", None)
                if self._all_game_rows() and composer and hasattr(composer, "prompt_composer"):
                    client = composer.prompt_composer._get_mempalace_client()
                    if client:
                        wing_name = composer.prompt_composer._get_wing_name()

                        if self._chapters_cache_wing_name != wing_name:
                            self._restore_persisted_virtual_cache(wing_name)

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
                            self._story_projection_cache = None
                            self._reference_item_groups_cache = None
                            self._window_kind_groups_cache = None
                            self._chapters_cache_wing_name = wing_name
                            self._chapters_load_error = None
                            self._is_loading_chapters = False

                        is_test = getattr(self.mw, '_is_test_mode', False)
                        if is_test and self._chapters_cache is None:
                            try:
                                projection_getter = getattr(client, "get_story_virtual_projection", None)
                                projection = projection_getter() if callable(projection_getter) else None
                                if isinstance(projection, StoryVirtualProjection) and projection.document_id:
                                    project = getattr(getattr(self.mw, "project_manager", None), "project", None)
                                    projection = apply_manual_story_structures(projection, project)
                                    self._story_projection_cache = projection
                                    self._chapters_cache = list(projection.roots)
                                else:
                                    self._chapter_mappings_cache = client.get_all_chapter_mappings(wing_name)
                                    self._chapters_cache = client.get_all_chapters(wing_name)
                                self._is_loading_chapters = False
                            except Exception as e_test:
                                self._chapters_load_error = str(e_test)

                        if self._chapters_load_error:
                            # Show load error placeholder
                            chapters_root = QTreeWidgetItem(["Story (Load Error)"])
                            self._set_item_style_icon(chapters_root, 0, QStyle.StandardPixmap.SP_DirIcon)
                            chapters_root.setFlags(chapters_root.flags() & ~Qt.ItemFlag.ItemIsEditable)

                            err_item = QTreeWidgetItem([f"Error: {self._chapters_load_error}"])
                            err_item.setFlags(err_item.flags() & ~Qt.ItemFlag.ItemIsEditable)
                            self._set_item_style_icon(err_item, 0, QStyle.StandardPixmap.SP_MessageBoxCritical)
                            chapters_root.addChild(err_item)

                            self.mw.block_list_widget.invisibleRootItem().addChild(chapters_root)

                        elif self._is_loading_chapters:
                            # Show loading placeholder
                            chapters_root = QTreeWidgetItem(["Story"])
                            self._set_item_style_icon(chapters_root, 0, QStyle.StandardPixmap.SP_DirIcon)
                            chapters_root.setFlags(chapters_root.flags() & ~Qt.ItemFlag.ItemIsEditable)

                            loading_item = QTreeWidgetItem(["Loading..."])
                            loading_item.setFlags(loading_item.flags() & ~Qt.ItemFlag.ItemIsEditable)
                            self._set_item_style_icon(loading_item, 0, QStyle.StandardPixmap.SP_BrowserReload)
                            chapters_root.addChild(loading_item)

                            self.mw.block_list_widget.invisibleRootItem().addChild(chapters_root)

                        elif isinstance(self._story_projection_cache, StoryVirtualProjection):
                            tree_root = self.mw.block_list_widget.invisibleRootItem()
                            selected_id = (
                                getattr(self.mw.data_store, "current_chapter_id", None)
                                if current_selection_block_idx == -2
                                else None
                            )
                            self._add_story_projection_root(
                                tree_root, self._story_projection_cache,
                                selected_id=selected_id,
                            )

                        elif self._chapters_cache is not None:
                            # We have cached chapters, build the hierarchy
                            chapters_root = QTreeWidgetItem(["Story"])
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
                                ch_problem_counts = self._get_aggregated_problems_for_block(-2, chapter_id=ch_id, chapter_mappings=ch_mappings_list)
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
                            self._start_chapters_worker_when_ready()

                            # Show loading placeholder
                            chapters_root = QTreeWidgetItem(["Story"])
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
                prompt_composer = getattr(composer, "prompt_composer", None) if composer else None
                if prompt_composer is not None:
                    client = prompt_composer._get_mempalace_client()

                normalized_story_active = isinstance(
                    self._story_projection_cache, StoryVirtualProjection
                )
                projection = (
                    self._story_projection_cache if normalized_story_active else None
                )

                # Single source of truth: every row's speaker is resolved by the
                # same priority ladder the editor Speaker field uses, so the
                # virtual folders below can never disagree with the field. The
                # cheap sources (override/projection/legacy/stored-script mapping)
                # run every rebuild; the expensive per-row fuzzy scan runs only on
                # the ⟳ "rebuild virtual folders" button and is cached here.
                from core.speaker_resolution import build_speaker_pool
                speaker_pool = build_speaker_pool(
                    self.mw,
                    prompt_composer,
                    projection=projection,
                    script_raw_rows=self._script_speaker_raw_cache,
                )
                # Publish the pool so the editor Speaker field resolves a row to
                # the identical speaker (and folder) it lands in here.
                self._speaker_pool_cache = speaker_pool

                combined_speakers = {}  # {speaker_name: [(b_idx, s_idx), ...]}
                assigned_strings = set()  # {(b_idx, s_idx), ...}
                for row in sorted(speaker_pool):
                    if self._is_blank_row(*row):
                        continue
                    speaker_name = speaker_pool[row]
                    combined_speakers.setdefault(speaker_name, []).append(row)
                    assigned_strings.add(row)

                # None is a real virtual speaker block in every context model. It is
                # the complete complement of assigned rows, not a legacy-only fallback.
                none_strings = []
                data = getattr(getattr(self.mw, "data_store", None), "data", None) or []
                for b_idx in range(len(data)):
                    block_data = data[b_idx]
                    if not isinstance(block_data, (list, tuple)):
                        continue
                    for s_idx in range(len(block_data)):
                        if (b_idx, s_idx) not in assigned_strings and not self._is_blank_row(b_idx, s_idx):
                            none_strings.append((b_idx, s_idx))
                if none_strings:
                    combined_speakers["None"] = none_strings

                pending_retention = None
                if hasattr(self.mw, 'list_selection_handler'):
                    pending_retention = getattr(self.mw.list_selection_handler, '_pending_speaker_retention', None)
                if (
                    not normalized_story_active
                    and isinstance(pending_retention, tuple)
                    and len(pending_retention) == 3
                ):
                    retained_speaker, retained_tuple, retained_index = pending_retention
                    speaker_mappings = list(combined_speakers.get(retained_speaker, []))
                    if retained_tuple not in speaker_mappings:
                        insert_at = min(max(retained_index, 0), len(speaker_mappings))
                        speaker_mappings.insert(insert_at, retained_tuple)
                        combined_speakers[retained_speaker] = speaker_mappings

                # Do not flash the legacy partial Speakers tree while the normalized
                # Story projection is still loading. The complete facet tree is added
                # together when the worker finishes.
                if self._is_loading_chapters:
                    combined_speakers.clear()

                unique_speakers = sorted([c for c in combined_speakers.keys() if c != "None"])
                if "None" in combined_speakers:
                    unique_speakers.insert(0, "None")

                if any(name != "None" for name in combined_speakers):
                    speakers_root = QTreeWidgetItem(["Speakers"])
                    self._set_item_style_icon(speakers_root, 0, QStyle.StandardPixmap.SP_DirIcon)
                    speakers_root.setFlags(speakers_root.flags() & ~Qt.ItemFlag.ItemIsEditable)
                    selected_speaker_item = None

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
                        speaker_item.setData(0, Qt.ItemDataRole.UserRole + 20, dict(speaker_problem_counts or {}))
                        self._apply_issues_and_tooltip(speaker_item, speaker_name, speaker_problem_counts, problem_definitions)

                        speakers_root.addChild(speaker_item)

                        if current_selection_block_idx == -3 and getattr(self.mw.data_store, 'current_speaker_name', None) == speaker_name:
                            selected_speaker_item = speaker_item

                    if speakers_root.childCount() > 0:
                        self.mw.block_list_widget.invisibleRootItem().addChild(speakers_root)
                        if selected_speaker_item:
                            speakers_root.setExpanded(True)
                            self.mw.block_list_widget.setCurrentItem(selected_speaker_item)
                            selected_speaker_item.setSelected(True)

                item_mappings = {}
                if normalized_story_active and client is not None:
                    if self._reference_item_groups_cache is None:
                        item_mappings, reverse_items = self._reference_item_mappings(
                            client, self._story_projection_cache.document_id
                        )
                        self._reference_item_groups_cache = item_mappings
                    else:
                        item_mappings = {
                            name: list(rows)
                            for name, rows in self._reference_item_groups_cache.items()
                        }
                        reverse_items = {
                            row: name
                            for name, rows in item_mappings.items()
                            for row in rows
                        }
                    item_mappings = self._apply_manual_item_overrides(item_mappings)
                    reverse_items = {
                        row: name
                        for name, rows in item_mappings.items()
                        for row in rows
                    }
                    self._story_item_mappings_cache = reverse_items
                    tree_root = self.mw.block_list_widget.invisibleRootItem()
                    self._add_item_projection_root(tree_root, item_mappings)
                    self._add_notated_projection_root(tree_root)
                    story_rows = self._story_linked_rows(self._story_projection_cache)
                    speaker_rows = {
                        row
                        for name, rows in combined_speakers.items()
                        if name != "None"
                        for row in rows
                    }
                    item_rows = {row for rows in item_mappings.values() for row in rows}
                    window_rows = self._window_bound_rows()
                    globally_unbound = {
                        row
                        for row in (
                            self._all_game_rows()
                            - story_rows
                            - speaker_rows
                            - item_rows
                            - window_rows
                        )
                        if not self._is_blank_row(*row)
                    }
                    global_none_item = self._add_virtual_role_leaf(
                        tree_root,
                        "None",
                        -3,
                        Qt.ItemDataRole.UserRole + 15,
                        "None",
                        sorted(globally_unbound),
                    )
                    if global_none_item is not None:
                        global_none_item.setData(
                            0, Qt.ItemDataRole.UserRole + 17, "unbound"
                        )
                    self._add_windows_projection_root(
                        tree_root,
                        self._story_projection_cache,
                        combined_speakers,
                        item_mappings,
                    )
                    self._persist_virtual_cache(
                        getattr(self, "_chapters_cache_wing_name", ""),
                        self._reference_item_groups_cache or {},
                    )
                    self._update_string_statistics(globally_unbound)
            except Exception as e:
                from utils.logging_utils import log_error
                log_error(f"Error populating Speakers folder: {e}", exc_info=True)
        finally:
            self._cache_story_overrides = False
            self._story_context_overrides_cache = None
            self._story_structure_overrides_cache = None
            self._story_override_index_cache = None
            self.mw.block_list_widget._is_programmatic_expansion = False
            self.mw.block_list_widget.blockSignals(False)
            self.mw.block_list_widget.setUpdatesEnabled(True)
            self.mw.block_list_widget.verticalScrollBar().setValue(v_scroll)

        self.mw.block_list_widget.viewport().update()
        if not isinstance(self._story_projection_cache, StoryVirtualProjection):
            self._update_string_statistics(self._all_game_rows() - self._window_bound_rows())
