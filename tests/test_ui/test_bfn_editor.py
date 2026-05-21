import pytest
from unittest.mock import MagicMock
import os
from PyQt5.QtWidgets import QApplication
from tools.bfn_editor.bfn_editor_window import BfnEditorWindow
from core.bfn_core import BfnCore

@pytest.fixture
def dummy_bfn_bytes():
    """Generates valid BFN bytes using BfnCore."""
    bfn = BfnCore()
    bfn.signature = "FFNT1bnd"
    bfn.inf1 = [{
        "encoding": 0,
        "ascent": 20,
        "descent": 2,
        "width": 12,
        "leading": 2,
        "fallback_code": 63,
        "unk1": 0
    }]
    # Add a mock glyph chunk
    bfn.gly1 = [{
        "texture_format": 0,
        "glyph_width": 12,
        "glyph_height": 12,
        "texture_width": 128,
        "texture_height": 128,
        "cell_width": 12,
        "cell_height": 12,
        "page_data_size": 8192,
        "glyph_horizontal_count": 10,
        "glyph_vertical_count": 10,
        "start_glyph": 0,
        "end_glyph": 100,
        "sheets": [b"\x00" * 8192]
    }]
    bfn.map1 = [{
        "mapping_type": 2,
        "first_char": 32,
        "last_char": 34,
        "mapping_entry_count": 2,
        "entries": [0, 1]
    }]
    bfn.wid1 = [{
        "first_code_included": 32,
        "last_code_included": 34,
        "packets": [
            {"kerning": 0, "width": 8},
            {"kerning": 1, "width": 10}
        ]
    }]
    return bfn.save()

def test_bfn_editor_window_init(qapp):
    """Test that BfnEditorWindow initializes properly."""
    editor = BfnEditorWindow()
    assert editor.windowTitle().startswith("BFN Font Editor")
    assert editor.bfn_path == ""
    assert editor.sheet_images == []
    assert editor.selected_cell is None
    editor.close()

def test_bfn_editor_window_open_from_bytes(qapp, dummy_bfn_bytes):
    """Test opening a BFN file from RAM bytes."""
    editor = BfnEditorWindow()
    
    save_called = False
    def save_cb(b):
        nonlocal save_called
        save_called = True
        
    sync_called = False
    def sync_cb():
        nonlocal sync_called
        sync_called = True

    editor.open_from_bytes(
        dummy_bfn_bytes,
        bfn_name="test_font.bfn",
        save_callback=save_cb,
        font_sync_callback=sync_cb
    )
    
    assert editor.archive_save_callback == save_cb
    assert editor.font_sync_callback == sync_cb
    assert len(editor.sheet_images) > 0
    assert editor.cell_w == 12
    assert editor.cell_h == 12
    
    # Clean up
    editor.clear_temp()
    editor.close()
