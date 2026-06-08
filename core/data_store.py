from typing import List, Dict, Set, Optional, Any, Tuple
from dataclasses import dataclass, field
from utils.logging_utils import log_debug

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
    data: List[Any] = field(default_factory=list)  # Original data
    edited_data: Dict[int, List[str]] = field(default_factory=dict)  # Unsaved changes per block
    edited_file_data: List[Any] = field(default_factory=list)  # Currently loaded file data
    
    # Metadata
    block_names: Dict[int, str] = field(default_factory=dict)
    unsaved_changes: bool = False
    unsaved_block_indices: Set[int] = field(default_factory=set)
    
    # Selection State
    current_block_idx: int = -1
    current_string_idx: int = -1
    selected_string_indices: List[int] = field(default_factory=list)
    displayed_string_indices: List[Any] = field(default_factory=list) # Absolute indices/tuples of strings shown in preview
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
    
    # Analysis & Problems
    problems_per_subline: Dict[int, Set[str]] = field(default_factory=dict)
    
    # Editor subline modification tracking (QTextBlock numbers that were changed)
    edited_sublines: Set[int] = field(default_factory=set)
    
    # Selection Persistence
    last_selected_block_index: int = -1
    last_selected_string_index: int = -1
    
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
        self.current_block_idx = -1
        self.current_string_idx = -1
        self.current_chapter_id = None
        self.chapter_mappings = []
        self.problems_per_subline = {}
        self.edited_sublines = set()
        self.hide_translated = False
        self.hide_original_tags = False
        self.hide_translation_tags = False
        self.show_overrides_only = False
        self.hide_empty_strings = False
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
