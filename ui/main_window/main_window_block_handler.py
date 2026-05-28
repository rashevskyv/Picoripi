from __future__ import annotations
from typing import TYPE_CHECKING
from utils.logging_utils import log_debug

if TYPE_CHECKING:
    from main import MainWindow

class MainWindowBlockHandler:
    def __init__(self, main_window: MainWindow):
        self.mw = main_window

    def get_block_color_markers(self, block_idx: int) -> set:
        return self.mw.block_color_markers.get(str(block_idx), set())

    def toggle_block_color_marker(self, block_idx: int, color_name: str):
        block_key = str(block_idx)
        if block_key not in self.mw.block_color_markers:
            self.mw.block_color_markers[block_key] = set()

        if color_name in self.mw.block_color_markers[block_key]:
            self.mw.block_color_markers[block_key].remove(color_name)
            if not self.mw.block_color_markers[block_key]: 
                del self.mw.block_color_markers[block_key]
        else:
            self.mw.block_color_markers[block_key].add(color_name)
        
        log_debug(f"Toggled marker '{color_name}' for block {block_idx}. Current markers: {self.mw.block_color_markers.get(block_key)}")
        
        if hasattr(self.mw, 'block_list_widget'):
            item = self.mw.block_list_widget.item(block_idx)
            if item:
                self.mw.block_list_widget.update(self.mw.block_list_widget.indexFromItem(item))

    def rebuild_unsaved_block_indices(self):
        self.mw.helper.rebuild_unsaved_block_indices()