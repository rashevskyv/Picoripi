from typing import List, Dict, Set, Optional, Any, Tuple
from dataclasses import dataclass, field
from utils.logging_utils import log_debug

class IndexingDict(dict):
    """Словник, який автоматично сповіщає про свої зміни (мутації)."""
    def __init__(self, *args, on_change_callback=None, **kwargs):
        super().__init__(*args, **kwargs)
        self._on_change_callback = on_change_callback

    def __setitem__(self, key, value):
        super().__setitem__(key, value)
        callback = getattr(self, '_on_change_callback', None)
        if callback:
            callback(key)

    def __delitem__(self, key):
        super().__delitem__(key)
        callback = getattr(self, '_on_change_callback', None)
        if callback:
            callback(key)

    def clear(self):
        super().clear()
        callback = getattr(self, '_on_change_callback', None)
        if callback:
            callback(None)

    def update(self, *args, **kwargs):
        super().update(*args, **kwargs)
        callback = getattr(self, '_on_change_callback', None)
        if callback:
            callback(None)

    def __getstate__(self):
        return dict(self)

    def __setstate__(self, state):
        self.update(state)
        self._on_change_callback = None

@dataclass
class AppDataStore:
    """
    Centralized store for application data.
    Decouples data state from MainWindow UI.
    """
    # File Paths
    json_path: Optional[str] = None
    edited_json_path: Optional[str] = None

    # Text Data
    # data is a property defined below
    edited_data: Dict[Tuple[int, int], str] = field(default_factory=dict)  # Unsaved changes per (block_idx, string_idx)
    edited_file_data: List[Any] = field(default_factory=list)  # Currently loaded file data

    # Metadata
    block_names: Dict[str, str] = field(default_factory=dict)
    unsaved_changes: bool = False
    unsaved_block_indices: Set[int] = field(default_factory=set)
    block_to_project_file_map: Dict[int, int] = field(default_factory=dict)

    # Selection State
    current_block_idx: int = -1
    _physical_block_idx: int = -1
    current_string_idx: int = -1
    selected_string_indices: List[int] = field(default_factory=list)
    _displayed_string_indices: List[Any] = field(default_factory=list, init=False, repr=False)
    _displayed_string_indices_map: Dict[Any, int] = field(default_factory=dict, init=False, repr=False)
    current_category_name: Optional[str] = None
    current_chapter_id: Optional[int] = None
    chapter_mappings: List[Tuple[int, int]] = field(default_factory=list) # List of (block_idx, string_idx) for selected chapter

    # Virtual Block Display Options
    highlight_categorized: bool = False
    hide_categorized: bool = False
    hide_translated: bool = False
    hide_original_tags: bool = False
    hide_translation_tags: bool = False
    show_overrides_only: bool = False
    hide_empty_strings: bool = False
    show_unsaved_only: bool = False
    show_unsaved_blocks_only: bool = False
    show_warnings_only: bool = False
    active_warning_filters: List[str] = field(default_factory=list)
    current_character_name: Optional[str] = None

    # Analysis & Problems
    problems_per_subline: Dict[Tuple[int, int, int], Set[str]] = field(default_factory=dict)

    # Filtering Indexes
    _index_empty: Dict[int, Set[int]] = field(default_factory=dict, init=False, repr=False)
    _index_translated: Dict[int, Set[int]] = field(default_factory=dict, init=False, repr=False)
    _index_unsaved: Dict[int, Set[int]] = field(default_factory=dict, init=False, repr=False)
    _index_overrides: Dict[int, Set[int]] = field(default_factory=dict, init=False, repr=False)
    _index_warnings: Dict[int, Dict[str, Set[Tuple[int, int]]]] = field(default_factory=dict, init=False, repr=False)
    _index_categorized: Dict[int, Set[int]] = field(default_factory=dict, init=False, repr=False)

    def __post_init__(self):
        # Wrap dictionaries with IndexingDict for automatic cache invalidation
        # For edited_data, we handle incremental updates manually in update_edited_data
        # to avoid discarding cached indexes for the entire block on single edits.
        # We only clear indexes on bulk operations (when key is None).
        self.edited_data = IndexingDict(
            self.edited_data,
            on_change_callback=lambda key: self.clear_indexes(None) if key is None else None
        )
        self.problems_per_subline = IndexingDict(
            self.problems_per_subline,
            on_change_callback=lambda key: self.clear_warnings_index(key[0] if key is not None else None)
        )

    @property
    def data(self) -> List[Any]:
        if not hasattr(self, '_data'):
            self._data = []
        return self._data

    @data.setter
    def data(self, value: List[Any]) -> None:
        self._data = value
        self.clear_indexes()

    def clear_indexes(self, block_idx: Optional[int] = None):
        """Clear filtering indexes for a specific block or all blocks."""
        if block_idx is not None:
            self._index_empty.pop(block_idx, None)
            self._index_translated.pop(block_idx, None)
            self._index_unsaved.pop(block_idx, None)
            self._index_overrides.pop(block_idx, None)
            self._index_warnings.pop(block_idx, None)
            self._index_categorized.pop(block_idx, None)
        else:
            self._index_empty.clear()
            self._index_translated.clear()
            self._index_unsaved.clear()
            self._index_overrides.clear()
            self._index_warnings.clear()
            self._index_categorized.clear()

    def clear_warnings_index(self, block_idx: Optional[int] = None):
        """Clear warnings index for a specific block or all blocks."""
        if block_idx is not None:
            self._index_warnings.pop(block_idx, None)
        else:
            self._index_warnings.clear()

    # Editor subline modification tracking (QTextBlock numbers that were changed)
    edited_sublines: Set[int] = field(default_factory=set)

    # Undo / Redo stacks for session persistence
    undo_stack: List[Any] = field(default_factory=list)
    redo_stack: List[Any] = field(default_factory=list)


    # Selection Persistence
    last_selected_block_index: int = -1
    last_selected_string_index: int = -1

    @property
    def physical_block_idx(self) -> int:
        """
        Returns the actual index of the physical block currently being viewed/edited.
        Fallback to current_block_idx if current_block_idx >= 0.
        """
        if self._physical_block_idx >= 0:
            return self._physical_block_idx
        if self.current_block_idx >= 0:
            return self.current_block_idx
        return -1

    @physical_block_idx.setter
    def physical_block_idx(self, value: int) -> None:
        if value >= 0:
            self._physical_block_idx = value

    @property
    def current_speaker_name(self) -> Optional[str]:
        """Alias for current_character_name for Speaker terminology."""
        return self.current_character_name

    @current_speaker_name.setter
    def current_speaker_name(self, value: Optional[str]) -> None:
        """Alias setter for current_character_name for Speaker terminology."""
        self.current_character_name = value

    @property
    def virtual_mappings(self) -> List[Tuple[int, int]]:
        """Alias for chapter_mappings representing general virtual mappings (chapters or speakers)."""
        return self.chapter_mappings

    @virtual_mappings.setter
    def virtual_mappings(self, value: List[Tuple[int, int]]) -> None:
        """Alias setter for chapter_mappings."""
        self.chapter_mappings = value

    @property
    def displayed_string_indices(self) -> List[Any]:
        if not hasattr(self, '_displayed_string_indices'):
            self._displayed_string_indices = []
        return self._displayed_string_indices

    @displayed_string_indices.setter
    def displayed_string_indices(self, value: List[Any]) -> None:
        self._displayed_string_indices = value
        self._rebuild_displayed_string_indices_map()

    def _rebuild_displayed_string_indices_map(self) -> None:
        self._displayed_string_indices_map = {}
        for idx, val in enumerate(self.displayed_string_indices):
            self._displayed_string_indices_map.setdefault(val, idx)

    def get_displayed_index_pos(self, value: Any) -> int:
        """Get the 0-based relative index position of a physical string index in the preview list.
        O(1) lookup using the cached reverse map.
        """
        if not hasattr(self, '_displayed_string_indices_map'):
            self._rebuild_displayed_string_indices_map()
        return self._displayed_string_indices_map.get(value, -1)

    def get_session_snapshot(self) -> dict:
        """Returns a compact dictionary representing the current session state."""
        return {
            "version": 1,
            "json_path": self.json_path,
            "edited_json_path": self.edited_json_path,
            "data": self.data,
            "edited_file_data": self.edited_file_data,
            "edited_data": dict(self.edited_data),
            "current_block_idx": self.current_block_idx,
            "_physical_block_idx": self._physical_block_idx,
            "current_string_idx": self.current_string_idx,
            "selected_string_indices": self.selected_string_indices,
            "current_category_name": self.current_category_name,
            "current_character_name": self.current_character_name,
            "last_selected_block_index": self.last_selected_block_index,
            "last_selected_string_index": self.last_selected_string_index,
            # UI filters
            "highlight_categorized": self.highlight_categorized,
            "hide_categorized": self.hide_categorized,
            "hide_translated": self.hide_translated,
            "hide_original_tags": self.hide_original_tags,
            "hide_translation_tags": self.hide_translation_tags,
            "show_overrides_only": self.show_overrides_only,
            "hide_empty_strings": self.hide_empty_strings,
            "show_unsaved_only": self.show_unsaved_only,
            "show_unsaved_blocks_only": self.show_unsaved_blocks_only,
            "show_warnings_only": self.show_warnings_only,
            "active_warning_filters": self.active_warning_filters,
            # Undo / Redo
            "undo_stack": self.undo_stack,
            "redo_stack": self.redo_stack,
            # Metadata
            "block_names": self.block_names,
            "unsaved_changes": self.unsaved_changes,
            "unsaved_block_indices": self.unsaved_block_indices,
            "block_to_project_file_map": self.block_to_project_file_map,
            # Problems per subline
            "problems_per_subline": dict(self.problems_per_subline),
        }

    def restore_from_snapshot(self, snapshot: dict) -> bool:
        """Restores store state from a compact session snapshot."""
        if not snapshot or snapshot.get("version") != 1:
            return False

        self.json_path = snapshot.get("json_path")
        self.edited_json_path = snapshot.get("edited_json_path")
        self.data = snapshot.get("data", [])
        self.edited_file_data = snapshot.get("edited_file_data", [])

        # Restore edited_data wrapping in IndexingDict
        self.edited_data = IndexingDict(
            snapshot.get("edited_data", {}),
            on_change_callback=lambda key: self.clear_indexes(None) if key is None else None
        )

        self.current_block_idx = snapshot.get("current_block_idx", -1)
        self._physical_block_idx = snapshot.get("_physical_block_idx", -1)
        self.current_string_idx = snapshot.get("current_string_idx", -1)
        self.selected_string_indices = snapshot.get("selected_string_indices", [])
        self.current_category_name = snapshot.get("current_category_name")
        self.current_character_name = snapshot.get("current_character_name")
        self.last_selected_block_index = snapshot.get("last_selected_block_index", -1)
        self.last_selected_string_index = snapshot.get("last_selected_string_index", -1)

        # UI filters
        self.highlight_categorized = snapshot.get("highlight_categorized", False)
        self.hide_categorized = snapshot.get("hide_categorized", False)
        self.hide_translated = snapshot.get("hide_translated", False)
        self.hide_original_tags = snapshot.get("hide_original_tags", False)
        self.hide_translation_tags = snapshot.get("hide_translation_tags", False)
        self.show_overrides_only = snapshot.get("show_overrides_only", False)
        self.hide_empty_strings = snapshot.get("hide_empty_strings", False)
        self.show_unsaved_only = snapshot.get("show_unsaved_only", False)
        self.show_unsaved_blocks_only = snapshot.get("show_unsaved_blocks_only", False)
        self.show_warnings_only = snapshot.get("show_warnings_only", False)
        self.active_warning_filters = snapshot.get("active_warning_filters", [])

        # Undo / Redo
        self.undo_stack = snapshot.get("undo_stack", [])
        self.redo_stack = snapshot.get("redo_stack", [])

        # Metadata
        self.block_names = snapshot.get("block_names", {})
        self.unsaved_changes = snapshot.get("unsaved_changes", False)
        self.unsaved_block_indices = set(snapshot.get("unsaved_block_indices", []))
        self.block_to_project_file_map = snapshot.get("block_to_project_file_map", {})

        # Problems per subline
        self.problems_per_subline = IndexingDict(
            snapshot.get("problems_per_subline", {}),
            on_change_callback=lambda key: self.clear_warnings_index(key[0] if key is not None else None)
        )

        self.clear_indexes()
        return True

    def clear(self):
        """Reset all data to default state."""
        self.json_path = None
        self.edited_json_path = None
        self.data = []
        self.edited_data = {}
        self.edited_file_data = []
        self.block_names = {}
        self.unsaved_changes = False
        self.unsaved_block_indices = set()
        self.block_to_project_file_map = {}
        self.current_block_idx = -1
        self._physical_block_idx = -1
        self.current_string_idx = -1
        self.current_chapter_id = None
        self.chapter_mappings = []
        self.problems_per_subline = {}
        self.edited_sublines = set()
        self.undo_stack.clear()
        self.redo_stack.clear()
        self.hide_translated = False
        self.hide_original_tags = False
        self.hide_translation_tags = False
        self.show_overrides_only = False
        self.hide_empty_strings = False
        self.show_unsaved_only = False
        self.show_unsaved_blocks_only = False
        self.show_warnings_only = False
        self.active_warning_filters = []
        self.current_character_name = None
        log_debug("AppDataStore: Data cleared")

    def mark_dirty(self, block_idx: int):
        """Mark a block as having unsaved changes."""
        self.unsaved_changes = True
        self.unsaved_block_indices.add(block_idx)

    def mark_clean(self, block_idx: Optional[int] = None):
        """Mark a block or the entire store as clean."""
        if block_idx is not None:
            self.unsaved_block_indices.discard(block_idx)
            if not self.unsaved_block_indices:
                self.unsaved_changes = False
        else:
            self.unsaved_changes = False
            self.unsaved_block_indices.clear()

    def __setstate__(self, state):
        self.__dict__.update(state)
        self.__post_init__()
