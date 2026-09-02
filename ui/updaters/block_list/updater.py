"""BlockListUpdater composition."""
from __future__ import annotations

from ui.updaters.base_ui_updater import BaseUIUpdater
from ui.updaters.block_list.ready_mixin import ReadyMixin
from ui.updaters.block_list.virtual_cache_mixin import VirtualCacheMixin
from ui.updaters.block_list.virtual_tree_mixin import VirtualTreeMixin
from ui.updaters.block_list.tree_state_mixin import TreeStateMixin
from ui.updaters.block_list.problems_mixin import ProblemsMixin
from ui.updaters.block_list.populate_mixin import PopulateMixin
from ui.updaters.block_list.highlight_mixin import HighlightMixin


class BlockListUpdater(
    ReadyMixin,
    VirtualCacheMixin,
    VirtualTreeMixin,
    TreeStateMixin,
    ProblemsMixin,
    PopulateMixin,
    HighlightMixin,
    BaseUIUpdater,
):
    """Block list updater implementation."""

    def __init__(self, main_window, data_processor):
        """Initialize a new instance."""
        super().__init__(main_window, data_processor)
        self._block_items_cache = {}  # {block_idx: [QTreeWidgetItem, ...]}
        self._chapters_load_worker = None
        self._chapters_cache = None
        self._chapter_mappings_cache = None
        self._story_projection_cache = None
        self._story_item_mappings_cache = {}
        self._reference_item_groups_cache = None
        self._window_kind_groups_cache = None
        # Cached raw per-row marked-script speakers (the expensive script scan);
        # rebuilt only when the script/mappings change (invalidate_mempalace_story_cache).
        self._script_speaker_raw_cache = None
        # The last {(block,string): display_speaker} pool built for the folders;
        # the editor Speaker field reads it so field and folders never disagree.
        self._speaker_pool_cache = None
        self._story_context_overrides_cache = None
        self._story_structure_overrides_cache = None
        self._story_override_index_cache = None
        self._cache_story_overrides = False
        self._chapters_cache_wing_name = None
        self._chapters_load_error = None
        self._is_loading_chapters = False
        self._virtual_ready_callbacks = []
        self._tree_state_restore_pending = False
        self._tree_state_ready_callbacks = []
        if hasattr(self.mw, 'filter_query_api') and self.mw.filter_query_api is not None:
            if getattr(self.mw.filter_query_api, '_data_processor', None) is None:
                self.mw.filter_query_api._data_processor = data_processor
