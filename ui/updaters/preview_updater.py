from typing import Optional, Any, OrderedDict, List, Tuple
from collections import OrderedDict
from PyQt6.QtCore import Qt, QTimer
from PyQt6.QtGui import QTextCursor, QColor

from utils.utils import (
    convert_spaces_to_dots_for_display, convert_dots_to_spaces_from_editor,
    calculate_string_width, remove_all_tags, calculate_strict_string_width
)
from core.glossary_manager import GlossaryOccurrence
from ui.components.bfn_preview_widget import _looks_like_bfn_editor
from .base_ui_updater import BaseUIUpdater
from utils.logging_utils import log_debug
from .preview_cache import PreviewCache
from .preview_renderer import PreviewRenderer
from core.data_store import ViewKind, get_view_kind, store_is_virtual_view

class PreviewUpdater(BaseUIUpdater):
    """Preview updater implementation coordinating caching, filtering, and rendering."""
    def __init__(self, main_window: Any, data_processor: Any):
        """Initialize a new instance."""
        super().__init__(main_window, data_processor)
        self.preview_cache = PreviewCache(main_window, data_processor)
        self.preview_renderer = PreviewRenderer(main_window, data_processor, self.preview_cache)
        self.preview_renderer.preview_updater = self

        if hasattr(self.mw, 'filter_query_api') and self.mw.filter_query_api is not None:
            if getattr(self.mw.filter_query_api, '_data_processor', None) is None:
                self.mw.filter_query_api._data_processor = data_processor

        self._in_populate = False
        self._in_update_text_views = False
        self._last_populated_block_idx = -999
        self._last_populated_category_name = None

        # Setup lazy load timer
        from PyQt6.QtCore import QObject
        timer_parent = self.mw if isinstance(self.mw, QObject) else None
        self._lazy_load_timer = QTimer(timer_parent)
        self._lazy_load_timer.timeout.connect(self._load_next_preview_chunk)

    @property
    def _preview_cache(self) -> OrderedDict:
        """Get the underlying preview cache (for backwards compatibility)."""
        return self.preview_cache.cache

    @_preview_cache.setter
    def _preview_cache(self, value):
        self.preview_cache.cache = value

    @property
    def _placeholder_texts(self) -> dict:
        """Get the collapsed empty lines placeholder texts."""
        return self.preview_renderer._placeholder_texts

    @_placeholder_texts.setter
    def _placeholder_texts(self, value: dict):
        self.preview_renderer._placeholder_texts = value

    @property
    def _lazy_load_block_idx(self) -> int:
        return self.preview_renderer._lazy_load_block_idx

    @_lazy_load_block_idx.setter
    def _lazy_load_block_idx(self, value: int):
        self.preview_renderer._lazy_load_block_idx = value

    @property
    def _lazy_load_target_indices(self) -> list:
        return self.preview_renderer._lazy_load_target_indices

    @_lazy_load_target_indices.setter
    def _lazy_load_target_indices(self, value: list):
        self.preview_renderer._lazy_load_target_indices = value

    @property
    def _lazy_load_next_index(self) -> int:
        return self.preview_renderer._lazy_load_next_index

    @_lazy_load_next_index.setter
    def _lazy_load_next_index(self, value: int):
        self.preview_renderer._lazy_load_next_index = value

    # Proxy methods for PreviewCache compatibility
    def get_cache_key(self, block_idx: int, category_name: Optional[str]) -> tuple:
        return self.preview_cache.get_cache_key(block_idx, category_name)

    def update_cached_string(self, block_idx: int, string_idx: int, preview_line_text: str, physical_block_idx: Optional[int] = None) -> None:
        self.preview_cache.update_cached_string(block_idx, string_idx, preview_line_text, physical_block_idx)

    def schedule_pre_cache(self):
        if not getattr(self.mw, 'preview_enabled', True):
            self.preview_cache.cancel_idle_caching()
            return
        self.preview_cache.schedule_pre_cache()

    def pre_cache_all_blocks(self):
        if not getattr(self.mw, 'preview_enabled', True):
            self.preview_cache.cancel_idle_caching()
            return
        self.preview_cache.pre_cache_all_blocks()

    def cancel_idle_caching(self):
        self.preview_cache.cancel_idle_caching()

    @property
    def _idle_cache_queue(self) -> list:
        return self.preview_cache._idle_cache_queue

    @_idle_cache_queue.setter
    def _idle_cache_queue(self, value: list):
        self.preview_cache._idle_cache_queue = value

    def _start_idle_caching(self):
        self.preview_cache._start_idle_caching()

    @property
    def _idle_timer(self):
        return self.preview_cache._idle_timer

    @_idle_timer.setter
    def _idle_timer(self, value):
        self.preview_cache._idle_timer = value

    def _cache_next_idle_block(self):
        self.preview_cache._cache_next_idle_block()

    def _get_all_categorized_indices_for_block(self, block_idx: int) -> set:
        return self.preview_renderer._get_all_categorized_indices_for_block(block_idx)

    # Proxy methods for PreviewRenderer compatibility
    def highlight_glossary_occurrence(self, occurrence: GlossaryOccurrence):
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

    def _apply_highlights_for_block(self, block_idx: int):
        self.preview_renderer._apply_highlights_for_block(block_idx)

    def _apply_highlights_to_editor(self, editor, block_idx: int, string_idx: int):
        self.preview_renderer._apply_highlights_to_editor(editor, block_idx, string_idx)

    def _load_next_preview_chunk(self):
        self.preview_renderer._load_next_preview_chunk()

    def _block_has_overrides(self, block_idx: int) -> bool:
        """Internal helper to check if a block has overrides."""
        if block_idx == -1:
            return False
        default_font = getattr(self.mw, 'default_font_file', None)
        max_width = getattr(self.mw, 'game_dialog_max_width_pixels', None)

        is_chapter = (block_idx == -2)
        if is_chapter:
            target_indices = getattr(self.mw.data_store, 'chapter_mappings', [])
        else:
            for (b_idx, s_idx), meta in self.mw.string_metadata.items():
                if b_idx == block_idx:
                    has_font = "font_file" in meta and meta["font_file"] != default_font and meta["font_file"] != "default"
                    has_width = "width" in meta and meta["width"] != max_width and meta["width"] != 0
                    if has_font or has_width:
                        return True
            return False

        for b_idx, s_idx in target_indices:
            meta = self.mw.string_metadata.get((b_idx, s_idx), {})
            has_font = "font_file" in meta and meta["font_file"] != default_font and meta["font_file"] != "default"
            has_width = "width" in meta and meta["width"] != max_width and meta["width"] != 0
            if has_font or has_width:
                return True
        return False

    def populate_strings_for_block(self, block_idx, category_name=None, force=False):
        """Populate strings for block with reentrancy prevention."""
        if getattr(self, '_in_populate', False):
            log_debug("populate_strings_for_block: reentrancy blocked.")
            return
        self._in_populate = True
        try:
            self._do_populate_strings_for_block(block_idx, category_name, force)
        finally:
            self._in_populate = False

    def populate_current_view(self, force=False):
        """Refresh the active grouping while retaining the physical address."""
        self.populate_strings_for_block(
            self.mw.data_store.current_block_idx,
            self.mw.data_store.current_category_name,
            force,
        )

    def _do_populate_strings_for_block(self, block_idx, category_name=None, force=False):
        """Actual populate strings for block logic using central FilterQueryAPI."""
        current_view_kind = get_view_kind(self.mw.data_store)
        if current_view_kind == ViewKind.CHAPTER:
            block_idx = -2
            category_name = None
        elif current_view_kind == ViewKind.SPEAKER:
            block_idx = -3
            category_name = None
        elif current_view_kind == ViewKind.ITEM:
            block_idx = -4
            category_name = None
        elif current_view_kind == ViewKind.NOTATED:
            block_idx = -5
            category_name = None
        elif block_idx != -1 and category_name is None:
            category_name = getattr(self.mw.data_store, 'current_category_name', None)

        if not hasattr(self.mw, 'preview_text_edit'):
            return

        preview_edit = getattr(self.mw, 'preview_text_edit', None)
        original_edit = getattr(self.mw, 'original_text_edit', None)
        edited_edit = getattr(self.mw, 'edited_text_edit', None)

        old_preview_scrollbar_value = preview_edit.verticalScrollBar().value() if preview_edit else 0

        _saved_programmatic_flag = self.mw.is_programmatically_changing_text
        self.mw.is_programmatically_changing_text = True
        self.mw.data_store.current_category_name = category_name
        detection_config = getattr(self.mw, 'detection_enabled', {})

        # Show "Highlight moved" / "Hide moved" only when this block has categories
        block_has_categories = False
        if hasattr(self.mw, 'project_manager') and self.mw.project_manager and self.mw.project_manager.project:
            pm = self.mw.project_manager
            block_map = getattr(self.mw, 'block_to_project_file_map', {})
            proj_b_idx = block_map.get(block_idx, block_idx)
            if isinstance(proj_b_idx, int) and 0 <= proj_b_idx < len(pm.project.blocks):
                block_has_categories = bool(pm.project.blocks[proj_b_idx].categories)
        show_cat_toggles = block_has_categories and not category_name
        if hasattr(self.mw, 'highlight_categorized_checkbox'):
            self.mw.highlight_categorized_checkbox.setVisible(show_cat_toggles)
        if hasattr(self.mw, 'hide_categorized_checkbox'):
            self.mw.hide_categorized_checkbox.setVisible(show_cat_toggles)

        # Show "Show Overrides Only" checkbox only if the block has overrides, or if the filter is currently active
        show_overrides_toggle = False
        if hasattr(self.mw, 'data_store') and self.mw.data_store:
            show_overrides_only = getattr(self.mw.data_store, 'show_overrides_only', False)
            show_overrides_toggle = show_overrides_only or self._block_has_overrides(block_idx)
        if hasattr(self.mw, 'show_overrides_only_checkbox'):
            self.mw.show_overrides_only_checkbox.setVisible(show_overrides_toggle)

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

        data_source = getattr(self.mw.data_store, 'data', None)
        if not isinstance(data_source, list):
            if hasattr(self.mw, 'data') and isinstance(self.mw.data, list):
                data_source = self.mw.data
            else:
                data_source = []

        is_chapter = (block_idx == -2)
        is_speaker = (block_idx in (-3, -4, -5))
        is_virtual = is_chapter or is_speaker
        if not is_virtual and (block_idx < 0 or not data_source or block_idx >= len(data_source) or not isinstance(data_source[block_idx], list)):
            self.preview_cache.cache.clear()
            self.mw.data_store.displayed_string_indices = []
            if preview_edit:
                preview_edit.override_total_lines = None
                preview_edit.updateLineNumberAreaWidth(0)
                if preview_edit.toPlainText() != "": preview_edit.setPlainText("")
            if original_edit and original_edit.toPlainText() != "": original_edit.setPlainText("")
            if edited_edit and edited_edit.toPlainText() != "": edited_edit.setPlainText("")
            self.update_text_views(); self.synchronize_original_cursor()
            if preview_edit: preview_edit.verticalScrollBar().setValue(old_preview_scrollbar_value)
            self.mw.is_programmatically_changing_text = False
            return

        if preview_edit and self.mw.current_game_rules:
            old_indices = getattr(self.mw.data_store, 'displayed_string_indices', [])
            if not old_indices and hasattr(self.mw, 'displayed_string_indices'):
                old_indices = self.mw.displayed_string_indices

            # Query FilterQueryAPI for target string indices
            active_filters = getattr(self.mw.data_store, 'active_warning_filters', [])
            target_indices, placeholder_texts = self.mw.filter_query_api.get_filtered_string_indices(
                block_idx=block_idx,
                category_name=category_name,
                hide_categorized=getattr(self.mw.data_store, 'hide_categorized', False),
                hide_translated=getattr(self.mw.data_store, 'hide_translated', False),
                show_overrides_only=getattr(self.mw.data_store, 'show_overrides_only', False),
                show_unsaved_only=getattr(self.mw.data_store, 'show_unsaved_only', False),
                show_warnings_only=getattr(self.mw.data_store, 'show_warnings_only', False),
                active_warning_filters=active_filters,
                detection_config=detection_config,
                hide_empty_strings=getattr(self.mw.data_store, 'hide_empty_strings', False),
                data_source=data_source,
                virtual_mappings=getattr(self.mw.data_store, 'virtual_mappings', getattr(self.mw.data_store, 'chapter_mappings', []))
            )

            # Sync indices with renderer
            self.preview_renderer._placeholder_texts = placeholder_texts
            self.mw.data_store.displayed_string_indices = target_indices

            # Generate custom line numbers to preserve original indices in gutter
            custom_line_numbers = []
            for idx in target_indices:
                if idx == -1:
                    custom_line_numbers.append(None)
                elif isinstance(idx, tuple):
                    custom_line_numbers.append(idx[1] + 1)
                else:
                    custom_line_numbers.append(idx + 1)
            preview_edit.custom_line_numbers = custom_line_numbers

            should_regenerate = block_changed or force
            # Check if actual elements changed
            if not should_regenerate and target_indices != old_indices:
                should_regenerate = True

            if should_regenerate and self._lazy_load_timer.isActive():
                self._lazy_load_timer.stop()

            # Map current_string_idx to preview index if possible
            preview_idx_to_select = -1
            if is_virtual:
                target_tuple = (self.mw.data_store.physical_block_idx, self.mw.data_store.current_string_idx)
                if hasattr(self.mw.data_store, 'get_displayed_index_pos'):
                    res = self.mw.data_store.get_displayed_index_pos(target_tuple)
                    if isinstance(res, int) and not isinstance(res, bool):
                        preview_idx_to_select = res
                if preview_idx_to_select == -1 and target_tuple in target_indices:
                    preview_idx_to_select = target_indices.index(target_tuple)
            else:
                if hasattr(self.mw.data_store, 'get_displayed_index_pos'):
                    res = self.mw.data_store.get_displayed_index_pos(self.mw.data_store.current_string_idx)
                    if isinstance(res, int) and not isinstance(res, bool):
                        preview_idx_to_select = res
                if preview_idx_to_select == -1 and self.mw.data_store.current_string_idx in target_indices:
                    preview_idx_to_select = target_indices.index(self.mw.data_store.current_string_idx)

            # Set override_total_lines to prevent dynamic width change
            if len(target_indices) > 0:
                preview_edit.override_total_lines = len(target_indices)
            else:
                preview_edit.override_total_lines = None
            preview_edit.updateLineNumberAreaWidth(0)

            # Generate full text if block changed OR if the subset of strings changed OR force refresh
            if should_regenerate:
                cache_key = self.get_cache_key(block_idx, category_name)

                if force and not block_changed and cache_key in self.preview_cache.cache:
                    self.preview_cache.cache.move_to_end(cache_key)
                    cache = self.preview_cache.cache[cache_key]
                    if cache.get('target_indices') == target_indices:
                        for idx_offset in range(cache['next_index']):
                            if idx_offset < len(target_indices) and idx_offset < len(cache['lines']):
                                real_idx = target_indices[idx_offset]
                                if real_idx == -1:
                                    preview_line_text = placeholder_texts.get(idx_offset, "[Empty Lines]")
                                else:
                                    b_idx = block_idx
                                    s_idx = real_idx
                                    if isinstance(real_idx, tuple):
                                        b_idx, s_idx = real_idx
                                    text_for_preview_raw, _ = self.data_processor.get_current_string_text(b_idx, s_idx)
                                    preview_line_text = self.mw.current_game_rules.get_text_representation_for_preview(str(text_for_preview_raw))
                                cache['lines'][idx_offset] = preview_line_text
                elif force and cache_key in self.preview_cache.cache:
                    del self.preview_cache.cache[cache_key]

                approx_visible_lines = 0
                if hasattr(self.mw, 'list_selection_handler'):
                    val = getattr(self.mw.list_selection_handler, '_saved_approx_visible_lines', 0)
                    if isinstance(val, (int, float)) and not isinstance(val, bool):
                        approx_visible_lines = val

                if getattr(self, '_load_fully_synchronously', False):
                    initial_chunk_size = len(target_indices)
                else:
                    initial_chunk_size = max(200, preview_idx_to_select + 50, approx_visible_lines)
                    initial_chunk_size = min(initial_chunk_size, len(target_indices))

                use_cache = False
                if cache_key in self.preview_cache.cache:
                    self.preview_cache.cache.move_to_end(cache_key)
                    cache = self.preview_cache.cache[cache_key]
                    if cache.get('target_indices') == target_indices:
                        use_cache = True

                self.preview_renderer._lazy_load_block_idx = block_idx
                self.preview_renderer._lazy_load_target_indices = target_indices

                if len(target_indices) >= initial_chunk_size or getattr(self, '_load_fully_synchronously', False):
                    self.preview_renderer._lazy_load_next_index = initial_chunk_size

                    # Initialize cache structure if not exists
                    if not use_cache:
                        cache = {
                            'lines': [""] * len(target_indices),
                            'next_index': 0,
                            'target_indices': target_indices
                        }
                        self.preview_cache.cache[cache_key] = cache
                        self.preview_cache.cache.move_to_end(cache_key)
                        if len(self.preview_cache.cache) > self.preview_cache.MAX_CACHE_SIZE:
                            self.preview_cache.cache.popitem(last=False)
                    else:
                        self.preview_cache.cache.move_to_end(cache_key)
                        cache = self.preview_cache.cache[cache_key]

                    # Quick path (directly sets populated text to avoid QTextCursor and QProgressDialog/processEvents)
                    preview_lines = []
                    for line_idx in range(len(target_indices)):
                        if line_idx < initial_chunk_size:
                            preview_line_text = None
                            if use_cache and line_idx < len(cache['lines']) and line_idx < cache.get('next_index', 0):
                                preview_line_text = cache['lines'][line_idx]

                            if preview_line_text is None or preview_line_text == "":
                                real_idx = target_indices[line_idx]
                                if real_idx == -1:
                                    preview_line_text = placeholder_texts.get(line_idx, "[Empty Lines]")
                                else:
                                    b_idx = block_idx
                                    s_idx = real_idx
                                    if isinstance(real_idx, tuple):
                                        b_idx, s_idx = real_idx
                                    text_for_preview_raw, _ = self.data_processor.get_current_string_text(b_idx, s_idx)
                                    preview_line_text = self.mw.current_game_rules.get_text_representation_for_preview(str(text_for_preview_raw))

                                if line_idx < len(cache['lines']):
                                    cache['lines'][line_idx] = preview_line_text
                            preview_lines.append(preview_line_text)
                        else:
                            preview_lines.append("")

                    preview_full_text = "\n".join(preview_lines)
                    if preview_edit.toPlainText() != preview_full_text:
                        preview_edit.setPlainText(preview_full_text)

                    cache['next_index'] = max(cache.get('next_index', 0), initial_chunk_size)

                    if initial_chunk_size < len(target_indices):
                        self._lazy_load_timer.start(15)
                else:
                    # Small block, load everything at once
                    if use_cache:
                        self.preview_cache.cache.move_to_end(cache_key)
                        cache = self.preview_cache.cache[cache_key]
                        preview_full_text = "\n".join(cache['lines'])
                        if preview_edit.toPlainText() != preview_full_text:
                            preview_edit.setPlainText(preview_full_text)
                    else:
                        preview_lines = []
                        for line_idx, real_idx in enumerate(target_indices):
                            if real_idx == -1:
                                preview_line_text = placeholder_texts.get(line_idx, "[Empty Lines]")
                            else:
                                b_idx = block_idx
                                s_idx = real_idx
                                if isinstance(real_idx, tuple):
                                    b_idx, s_idx = real_idx
                                text_for_preview_raw, _ = self.data_processor.get_current_string_text(b_idx, s_idx)
                                preview_line_text = self.mw.current_game_rules.get_text_representation_for_preview(str(text_for_preview_raw))
                            preview_lines.append(preview_line_text)

                        self.preview_cache.cache[cache_key] = {
                            'lines': preview_lines,
                            'next_index': len(target_indices),
                            'target_indices': target_indices
                        }
                        self.preview_cache.cache.move_to_end(cache_key)
                        if len(self.preview_cache.cache) > self.preview_cache.MAX_CACHE_SIZE:
                            self.preview_cache.cache.popitem(last=False)
                        preview_full_text = "\n".join(preview_lines)
                        if preview_edit.toPlainText() != preview_full_text:
                            preview_edit.setPlainText(preview_full_text)

                    self.preview_renderer._lazy_load_next_index = len(target_indices)
                    if self._lazy_load_timer.isActive():
                        self._lazy_load_timer.stop()

            # Apply highlights based on NEW displayed_string_indices
            self._apply_highlights_for_block(block_idx)

            if preview_idx_to_select != -1 and \
               hasattr(preview_edit, 'set_selected_lines') and \
               0 <= preview_idx_to_select < preview_edit.document().blockCount():
                preview_edit.set_selected_lines([preview_idx_to_select])

            # Restore scroll value if block did NOT change
            displayed_indices_changed = (target_indices != old_indices)
            if (not block_changed and not displayed_indices_changed) or self.mw.data_store.current_string_idx == -1:
                preview_edit.verticalScrollBar().setValue(old_preview_scrollbar_value)

        self.update_text_views()
        self.synchronize_original_cursor()
        self.mw.is_programmatically_changing_text = _saved_programmatic_flag

    def update_text_views(self):
        """Update the text views."""
        if getattr(self, '_in_update_text_views', False):
            return
        self._in_update_text_views = True
        is_programmatic_call_flag_original = self.mw.is_programmatically_changing_text

        self.mw.is_programmatically_changing_text = True
        try:
            self._do_update_text_views(is_programmatic_call_flag_original)
        finally:
            self.mw.is_programmatically_changing_text = is_programmatic_call_flag_original
            self._in_update_text_views = False

    def _do_update_text_views(self, is_programmatic_call_flag_original):
        """Internal helper to do update text views."""
        original_text_raw = ""
        edited_text_raw = ""
        if self.mw.data_store.physical_block_idx != -1 and self.mw.data_store.current_string_idx != -1:
            original_text_raw = self.data_processor._get_string_from_source(
                self.mw.data_store.physical_block_idx, self.mw.data_store.current_string_idx, self.mw.data_store.data,
                "original_data_for_readonly_view"
            )
            if original_text_raw is None: original_text_raw = ""
            edited_text_raw, _ = self.data_processor.get_current_string_text(self.mw.data_store.physical_block_idx, self.mw.data_store.current_string_idx)
            if edited_text_raw is None: edited_text_raw = ""

        # Update the corresponding line in preview_text_edit and in the cache dynamically
        if self.mw.data_store.physical_block_idx != -1 and self.mw.data_store.current_string_idx != -1:
            preview_edit = getattr(self.mw, 'preview_text_edit', None)
            if preview_edit:
                is_virtual = store_is_virtual_view(self.mw.data_store)
                displayed_indices = getattr(self.mw.data_store, 'displayed_string_indices', [])

                preview_idx = -1
                if is_virtual:
                    target_tuple = (self.mw.data_store.physical_block_idx, self.mw.data_store.current_string_idx)
                    if hasattr(self.mw.data_store, 'get_displayed_index_pos'):
                        res = self.mw.data_store.get_displayed_index_pos(target_tuple)
                        if isinstance(res, int) and not isinstance(res, bool):
                            preview_idx = res
                    if preview_idx == -1 and target_tuple in displayed_indices:
                        preview_idx = displayed_indices.index(target_tuple)
                else:
                    if hasattr(self.mw.data_store, 'get_displayed_index_pos'):
                        res = self.mw.data_store.get_displayed_index_pos(self.mw.data_store.current_string_idx)
                        if isinstance(res, int) and not isinstance(res, bool):
                            preview_idx = res
                    if preview_idx == -1 and self.mw.data_store.current_string_idx in displayed_indices:
                        preview_idx = displayed_indices.index(self.mw.data_store.current_string_idx)

                if preview_idx != -1:
                    if self.mw.current_game_rules:
                        preview_line_text = self.mw.current_game_rules.get_text_representation_for_preview(str(edited_text_raw))
                    else:
                        preview_line_text = str(edited_text_raw)

                    self.update_cached_string(
                        self.mw.data_store.current_block_idx,
                        self.mw.data_store.current_string_idx,
                        preview_line_text,
                        physical_block_idx=self.mw.data_store.physical_block_idx
                    )

                    doc = preview_edit.document()
                    block = doc.findBlockByNumber(preview_idx)
                    if block.isValid() and block.text() != preview_line_text:
                        _saved_prog = self.mw.is_programmatically_changing_text
                        self.mw.is_programmatically_changing_text = True
                        try:
                            cursor = QTextCursor(doc)
                            cursor.setPosition(block.position())
                            cursor.setPosition(block.position() + len(block.text()), QTextCursor.MoveMode.KeepAnchor)
                            cursor.insertText(preview_line_text)
                        finally:
                            self.mw.is_programmatically_changing_text = _saved_prog

                    if hasattr(preview_edit, 'lineNumberArea') and preview_edit.lineNumberArea:
                        preview_edit.lineNumberArea.update()
                    preview_edit.viewport().update()

        if self.mw.current_game_rules and hasattr(self.mw.current_game_rules, 'get_text_representation_for_editor'):
            original_text_for_display_processed = str(self.mw.current_game_rules.get_text_representation_for_editor(str(original_text_raw)))
            edited_text_for_display_processed = str(self.mw.current_game_rules.get_text_representation_for_editor(str(edited_text_raw)))
        else:
            original_text_for_display_processed = str(original_text_raw)
            edited_text_for_display_processed = str(edited_text_raw)

        original_text_for_display = convert_spaces_to_dots_for_display(original_text_for_display_processed, self.mw.show_multiple_spaces_as_dots)
        edited_text_for_display_converted = convert_spaces_to_dots_for_display(edited_text_for_display_processed, self.mw.show_multiple_spaces_as_dots)

        orig_edit = self.mw.original_text_edit
        if orig_edit:
            if orig_edit.toPlainText() != original_text_for_display:
                orig_text_edit_cursor_pos = int(orig_edit.textCursor().position())
                orig_anchor_pos = int(orig_edit.textCursor().anchor())
                orig_has_selection = bool(orig_edit.textCursor().hasSelection())
                orig_edit.setPlainText(original_text_for_display)
                new_orig_cursor = orig_edit.textCursor()
                new_orig_cursor.setPosition(min(orig_anchor_pos, len(original_text_for_display)))
                if orig_has_selection: new_orig_cursor.setPosition(min(orig_text_edit_cursor_pos, len(original_text_for_display)), QTextCursor.MoveMode.KeepAnchor)
                else: new_orig_cursor.setPosition(min(orig_text_edit_cursor_pos, len(original_text_for_display)))
                orig_edit.setTextCursor(new_orig_cursor)

        edited_widget = self.mw.edited_text_edit
        if edited_widget:
            if edited_widget.toPlainText() != edited_text_for_display_converted:
                saved_edited_cursor_pos = int(edited_widget.textCursor().position())
                saved_edited_anchor_pos = int(edited_widget.textCursor().anchor())
                saved_edited_has_selection = bool(edited_widget.textCursor().hasSelection())

                edited_widget.setPlainText(edited_text_for_display_converted)

                # Sync subline asterisks immediately after programmatic text update
                if self.mw.data_store.physical_block_idx != -1 and self.mw.data_store.current_string_idx != -1:
                    if hasattr(self.mw, 'text_operation_handler'):
                        self.mw.text_operation_handler.sync_subline_asterisks(
                            self.mw.data_store.physical_block_idx,
                            self.mw.data_store.current_string_idx,
                            edited_text_raw
                        )

                restored_cursor = edited_widget.textCursor()
                new_edited_anchor_pos = min(saved_edited_anchor_pos, len(edited_text_for_display_converted))
                new_edited_cursor_pos = min(saved_edited_cursor_pos, len(edited_text_for_display_converted))
                restored_cursor.setPosition(new_edited_anchor_pos)
                if saved_edited_has_selection: restored_cursor.setPosition(new_edited_cursor_pos, QTextCursor.MoveMode.KeepAnchor)
                else: restored_cursor.setPosition(new_edited_cursor_pos)
                edited_widget.setTextCursor(restored_cursor)

        # Optional: Calculate original strictly (without fallback char width) width
        if hasattr(self.mw, 'original_width_label'):
            if self.mw.data_store.physical_block_idx != -1 and self.mw.data_store.current_string_idx != -1:
                font_map_for_string = self.mw.helper.get_font_map_for_string(self.mw.data_store.physical_block_idx, self.mw.data_store.current_string_idx)
                icon_sequences = getattr(self.mw, 'icon_sequences', [])

                original_lines = str(original_text_raw).split('\n')
                widths = []
                for line in original_lines:
                    w = calculate_strict_string_width(line, font_map_for_string, icon_sequences=icon_sequences)
                    if w is None:
                        widths = None
                        break
                    widths.append(w)

                strict_width = max(widths) if widths is not None and widths else None

                if strict_width is not None:
                    self.mw.original_width_label.setText(f"{strict_width} px")
                    self.mw.original_width_label.show()
                else:
                    self.mw.original_width_label.setText("")
                    self.mw.original_width_label.hide()
            else:
                self.mw.original_width_label.setText("")
                self.mw.original_width_label.hide()

        # Apply highlights to editors
        if self.mw.data_store.physical_block_idx != -1 and self.mw.data_store.current_string_idx != -1:
             self._apply_highlights_to_editor(self.mw.edited_text_edit, self.mw.data_store.physical_block_idx, self.mw.data_store.current_string_idx)
             self._apply_highlights_to_editor(self.mw.original_text_edit, self.mw.data_store.physical_block_idx, self.mw.data_store.current_string_idx)

             # Apply font based on exact logic
             if self.mw.current_game_rules:
                  font_info = self.mw.current_game_rules.get_font_for_block(self.mw.data_store.physical_block_idx)
                  if font_info:
                      custom_font_original = self.mw.helper.get_font_for_name(font_info['original_font_name'])
                      if custom_font_original:
                          self.mw.original_text_edit.setDocumentFont(custom_font_original)

                      custom_font_edited = self.mw.helper.get_font_for_name(font_info['font_name'])
                      if custom_font_edited:
                          self.mw.edited_text_edit.setDocumentFont(custom_font_edited)

                      if getattr(self.mw, 'string_settings_handler', None) and font_info.get('font_name'):
                           setattr(self.mw.data_store, 'current_font_name', font_info['font_name'])

             self.mw.ui_updater.update_status_bar()
        else:
             self.mw.ui_updater.clear_status_bar()

        # Update BFN visual preview
        preview_enabled = getattr(self.mw, 'preview_enabled', True)
        toggle_action = getattr(self.mw, 'toggle_preview_action', None)
        show_preview = preview_enabled and (toggle_action.isChecked() if toggle_action else True)

        if hasattr(self.mw, 'bfn_preview_widget') and self.mw.bfn_preview_widget:
            if show_preview:
                if self.mw.bfn_preview_widget.isHidden():
                    self.mw.bfn_preview_widget.show()
                self.mw.bfn_preview_widget.update_preview_text(edited_text_raw)
            else:
                if not self.mw.bfn_preview_widget.isHidden():
                    self.mw.bfn_preview_widget.hide()

        # Sync text with active BFN Font Editor simulation if it is open
        editor = getattr(self.mw, '_bfn_editor_window', None)
        if _looks_like_bfn_editor(editor):
            try:
                if not editor.isHidden():
                    sync_enabled = True
                    if hasattr(editor, 'chk_sync_sim_text'):
                        sync_enabled = editor.chk_sync_sim_text.isChecked()
                    if sync_enabled:
                        editor.sim_input.blockSignals(True)
                        editor.sim_input.setPlainText(edited_text_raw)
                        editor.sim_input.blockSignals(False)
                        editor.update_simulation()
            except RuntimeError:
                self.mw._bfn_editor_window = None
            except Exception:
                pass

        if hasattr(self.mw, 'dictionary_tooltip') and self.mw.dictionary_tooltip:
             self.mw.dictionary_tooltip.hide()

    def update_preview_visibility(self, checked=None, *, persist=True):
        """Update visibility of the visual preview widget based on loaded fonts and menu toggle state."""
        preview_widget = getattr(self.mw, 'bfn_preview_widget', None)
        if not preview_widget:
            return

        toggle_action = getattr(self.mw, 'toggle_preview_action', None)
        explicit_change = checked is not None
        if checked is None:
            checked = getattr(self.mw, 'preview_enabled', True)
        enabled = bool(checked)
        self.mw.preview_enabled = enabled
        if persist and explicit_change and hasattr(self.mw, 'settings_manager'):
            self.mw.settings_manager.save_settings()

        if not enabled:
            if toggle_action:
                toggle_action.setChecked(False)
            self.preview_cache.cancel_idle_caching()
            preview_widget.hide()
            return

        all_bfn_fonts = getattr(self.mw, 'all_bfn_fonts', {})
        fonts_loaded = bool(all_bfn_fonts)

        if not fonts_loaded:
            preview_widget.hide()
            if toggle_action:
                toggle_action.setEnabled(False)
                toggle_action.setChecked(False)
        else:
            if toggle_action:
                toggle_action.setEnabled(True)
                toggle_action.setChecked(True)
            activate_preview = getattr(preview_widget, 'activate_preview', None)
            if callable(activate_preview):
                activate_preview()
            preview_widget.show()
            # Immediately update preview text when showing
            edited_text_raw = ""
            if self.mw.data_store.physical_block_idx != -1 and self.mw.data_store.current_string_idx != -1:
                edited_text_raw, _ = self.data_processor.get_current_string_text(self.mw.data_store.physical_block_idx, self.mw.data_store.current_string_idx)
                if edited_text_raw is None:
                    edited_text_raw = ""
            preview_widget.update_preview_text(edited_text_raw)

        if enabled:
            self.schedule_pre_cache()
