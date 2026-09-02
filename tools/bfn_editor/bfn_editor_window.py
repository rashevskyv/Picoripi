#!/usr/bin/env python3
import os

from PyQt6 import QtCore, QtGui, QtWidgets

from tools.bfn_editor.bfn_io import BfnIoMixin
from tools.bfn_editor.bfn_simulation import BfnSimMixin
from tools.bfn_editor.bfn_navigation import BfnNavigationMixin
from tools.bfn_editor.bfn_view import BfnViewMixin
from tools.bfn_editor.window_ui_mixin import WindowUiMixin
from tools.bfn_editor.window_tree_mixin import (
    ROLE_ARCHIVE_NAME,
    ROLE_DISK_PATH,
    ROLE_FONT_NAME,
    ROLE_SHEET_IDX,
    ROLE_SOURCE_TYPE,
    WindowTreeMixin,
)
from tools.bfn_editor.window_sync_mixin import WindowSyncMixin
from core.i18n import tr

VERSION = "1.0.21"

__all__ = [
    "BfnEditorWindow",
    "VERSION",
    "ROLE_SHEET_IDX",
    "ROLE_FONT_NAME",
    "ROLE_ARCHIVE_NAME",
    "ROLE_SOURCE_TYPE",
    "ROLE_DISK_PATH",
]


class BfnEditorWindow(
    WindowUiMixin,
    WindowTreeMixin,
    WindowSyncMixin,
    BfnIoMixin,
    BfnSimMixin,
    BfnNavigationMixin,
    BfnViewMixin,
    QtWidgets.QMainWindow,
):
    """
    BFN Font Editor Window — embedded into Picoripi as a standalone tool window.

    Integration points:
      - open_from_bytes(bfn_bytes, bfn_name, save_callback, font_sync_callback):
            Opens a BFN file from RAM (e.g., loaded from an ARC archive).
            save_callback(bytes) is called after successful save to update the archive in RAM.
            font_sync_callback() is called to trigger Picoripi font map reload.
      - open_from_path(path):
            Opens a BFN file directly from disk.
    """

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle(tr('BFN Font Editor v{0}', VERSION))
        self.resize(1300, 850)

        # State
        self.bfn_path = ''
        self.folder_path = ''
        self.temp_dir = ''
        self.metadata = {}
        self.sheet_images = []
        self.original_font_metadata = None
        self.original_sheet_images = []
        self._table_headers_resized = False
        self.current_sheet_index = -1
        self.selected_cell = None  # (gx, gy)
        self.selected_sim_item = None
        self.selected_char_index = -1
        self._dragging_in_sim = False
        self._dirty = False
        self.changes_saved_during_session = False

        # Integration callbacks (set by Picoripi when opening from archive)
        self.archive_save_callback = None  # callable(filename, bytes) — write updated BFN back to archive
        self.font_sync_callback = None     # callable() — trigger font map reload in Picoripi
        
        self.archive_name = ""
        self.archive_files = {}
        self.current_bfn_name = ""
        self.font_sources = {}

        self.undo_stack = QtGui.QUndoStack(self)
        self.undo_stack.cleanChanged.connect(lambda clean: self._set_dirty(not clean))
        
        self.auto_sync_timer = QtCore.QTimer(self)
        self.auto_sync_timer.setSingleShot(True)
        self.auto_sync_timer.timeout.connect(self.auto_sync_and_recalculate)

        self.cell_w = 24
        self.cell_h = 24
        self.rows = 5
        self.cols = 5
        self.real_w = 24
        self.real_h = 24
        self.start_glyph = 0
        self.end_glyph = 0
        self.first_code = 0
        self.last_code = 0
        self.is_dark_theme = True

        self.setup_ui()
        self.apply_theme()


    # ------------------------------------------------------------------
    # Public API for Picoripi integration
    # ------------------------------------------------------------------

    def open_from_bytes(self, bfn_bytes: bytes, bfn_name: str = "font.bfn",
                        save_callback=None, font_sync_callback=None,
                        archive_name="", archive_files=None):
        """Open a BFN from in-memory bytes (e.g., extracted from an ARC archive)."""
        self.archive_save_callback = save_callback
        self.font_sync_callback = font_sync_callback
        self.archive_name = archive_name
        self.archive_files = archive_files or {}
        self.current_bfn_name = bfn_name
        
        # Populate in_memory font sources first
        if self.archive_name:
            self.font_sources[self.archive_name] = {
                "type": "in_memory",
                "path": "",
                "files": self.archive_files
            }
        else:
            self.font_sources[bfn_name] = {
                "type": "in_memory",
                "path": "",
                "files": {bfn_name: bfn_bytes}
            }
            
        self.scan_fonts_directories()
        self.load_bfn_bytes(bfn_bytes, bfn_name)

    def open_from_path(self, path: str, font_sync_callback=None):
        """Open a BFN file directly from disk."""
        self.archive_save_callback = None
        self.font_sync_callback = font_sync_callback
        self.archive_name = ""
        self.archive_files = {}
        self.current_bfn_name = os.path.basename(path)
        
        self.font_sources = {}
        self.scan_fonts_directories()
        self.load_bfn(path)


    # ------------------------------------------------------------------
    # Override save_changes to also call Picoripi sync callbacks
    # ------------------------------------------------------------------

    def save_changes(self, silent=False):
        # Call the mixin implementation (defined in BfnIoMixin)
        super_save = None
        for cls in type(self).__mro__:
            if cls is BfnEditorWindow:
                continue
            if 'save_changes' in cls.__dict__:
                super_save = cls.__dict__['save_changes']
                break
        if super_save:
            super_save(self, silent=silent)

        # After successful save, trigger Picoripi font sync
        if not self._dirty and self.font_sync_callback:
            try:
                self.font_sync_callback()
            except Exception:
                pass
