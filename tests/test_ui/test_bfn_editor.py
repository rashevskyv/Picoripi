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
    
    # Verify Interactive header resize mode and signal connections
    header = editor.table_glyphs.horizontalHeader()
    from PyQt5 import QtWidgets
    assert header.sectionResizeMode(0) == QtWidgets.QHeaderView.Interactive
    
    # Verify that emitting these signals works without errors (signaling correct connection)
    header.sectionHandleDoubleClicked.emit(0)
    header.sectionResized.emit(0, 50, 60)
    
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


def test_bfn_editor_window_original_fonts(qapp, dummy_bfn_bytes):
    """Test that BFN editor window correctly populates table with original comparison font data."""
    editor = BfnEditorWindow()
    editor.open_from_bytes(
        dummy_bfn_bytes,
        bfn_name="test_font.bfn"
    )
    
    # Verify default state without original font loaded
    editor.populate_glyph_table()
    assert editor.table_glyphs.columnCount() == 9
    # Original Char column (index 1) should be empty
    item_orig = editor.table_glyphs.item(0, 1)
    assert item_orig is not None
    assert item_orig.text() == ""
    
    # Load mock original font metadata and sheets
    editor.original_font_metadata = {
        "MAP1": [{
            "mapping_type": 2,
            "first_char": 32,
            "last_char": 34,
            "mapping_entry_count": 2,
            "entries": [65, 66]  # 'A', 'B'
        }]
    }
    editor.original_sheet_images = editor.sheet_images
    
    # Repopulate
    editor.populate_glyph_table()
    
    # Now Original Char column (index 1) for the first glyph should contain 'A'
    item_orig = editor.table_glyphs.item(0, 1)
    assert item_orig is not None
    assert item_orig.text() == "A"
    
    # Clean up
    editor.clear_temp()
    editor.close()


def test_bfn_editor_window_generate_translation_map(qapp, dummy_bfn_bytes):
    """Test that BFN editor window correctly generates a translation map based on difference between trans and orig char."""
    editor = BfnEditorWindow()
    editor.open_from_bytes(
        dummy_bfn_bytes,
        bfn_name="test_font.bfn"
    )
    
    # Setup translated characters in MAP1
    editor.metadata["MAP1"] = [{
        "mapping_type": 2,
        "first_char": 0,
        "last_char": 1,
        "mapping_entry_count": 2,
        "entries": [105, 106]  # 'i', 'j'
    }]
    
    # Setup original characters in MAP1
    editor.original_font_metadata = {
        "MAP1": [{
            "mapping_type": 2,
            "first_char": 0,
            "last_char": 1,
            "mapping_entry_count": 2,
            "entries": [97, 98]  # 'a', 'b'
        }]
    }
    
    # Generate translation map
    translation_map = editor.generate_translation_map()
    
    # We should have mapping: 'i' -> 'a' and 'j' -> 'b'
    assert translation_map == {"i": "a", "j": "b"}
    
    editor.clear_temp()
    editor.close()


def test_bfn_editor_window_save_changes_translation_map(qapp, tmp_path, dummy_bfn_bytes, monkeypatch):
    """Test that save_changes correctly saves translation_map.json when BFN is saved inside Picoripi context."""
    editor = BfnEditorWindow()
    
    from PyQt5 import QtWidgets
    # Mock parent window with active_game_plugin
    class MockParent(QtWidgets.QWidget):
        def __init__(self):
            super().__init__()
            self.active_game_plugin = "mock_plugin"
            
    parent = MockParent()
    editor.setParent(parent)
    
    # Setup directory structure for mock plugin
    plugins_dir = tmp_path / "plugins"
    plugin_dir = plugins_dir / "mock_plugin"
    plugin_dir.mkdir(parents=True, exist_ok=True)
    
    # Mock os.path.exists and path writing
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(QtWidgets.QMessageBox, "information", lambda *args, **kwargs: None)
    
    editor.open_from_bytes(
        dummy_bfn_bytes,
        bfn_name="test_font.bfn"
    )
    
    editor.metadata["MAP1"] = [{
        "mapping_type": 2,
        "first_char": 0,
        "last_char": 1,
        "mapping_entry_count": 2,
        "entries": [105, 106]  # 'i', 'j'
    }]
    
    editor.original_font_metadata = {
        "MAP1": [{
            "mapping_type": 2,
            "first_char": 0,
            "last_char": 1,
            "mapping_entry_count": 2,
            "entries": [97, 98]  # 'a', 'b'
        }]
    }
    
    # Call save_changes
    editor.save_changes()
    
    # Verify that translation_map.json is created in mock plugin folder
    map_file = plugin_dir / "translation_map.json"
    assert map_file.exists()
    
    with open(map_file, "r", encoding="utf-8") as f:
        import json
        saved_map = json.load(f)
        
    assert saved_map == {"i": "a", "j": "b"}
    
    editor.clear_temp()
    editor.close()


def test_bfn_editor_window_save_changes_translation_map_project_dir(qapp, tmp_path, dummy_bfn_bytes, monkeypatch):
    """Test that save_changes correctly saves translation_map.json into active project directory when available."""
    editor = BfnEditorWindow()
    
    from PyQt5 import QtWidgets
    # Mock parent window with active_game_plugin and project_manager
    class MockProjectManager:
        def __init__(self, project_dir):
            self.project_dir = str(project_dir)

    class MockParent(QtWidgets.QWidget):
        def __init__(self, project_dir):
            super().__init__()
            self.active_game_plugin = "mock_plugin"
            self.project_manager = MockProjectManager(project_dir)
            
    project_dir = tmp_path / "my_project"
    project_dir.mkdir(parents=True, exist_ok=True)
    
    parent = MockParent(project_dir)
    editor.setParent(parent)
    
    # Mock os.path.exists and path writing
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(QtWidgets.QMessageBox, "information", lambda *args, **kwargs: None)
    
    editor.open_from_bytes(
        dummy_bfn_bytes,
        bfn_name="test_font.bfn"
    )
    
    editor.metadata["MAP1"] = [{
        "mapping_type": 2,
        "first_char": 0,
        "last_char": 1,
        "mapping_entry_count": 2,
        "entries": [105, 106]  # 'i', 'j'
    }]
    
    editor.original_font_metadata = {
        "MAP1": [{
            "mapping_type": 2,
            "first_char": 0,
            "last_char": 1,
            "mapping_entry_count": 2,
            "entries": [97, 98]  # 'a', 'b'
        }]
    }
    
    # Call save_changes
    editor.save_changes()
    
    # Verify that translation_map.json is created in project directory, not plugin folder
    map_file = project_dir / "translation_map.json"
    assert map_file.exists()
    
    # Verify that plugins/mock_plugin/translation_map.json is NOT created (since it went to project)
    plugins_dir = tmp_path / "plugins"
    plugin_map_file = plugins_dir / "mock_plugin" / "translation_map.json"
    assert not plugin_map_file.exists()
    
    with open(map_file, "r", encoding="utf-8") as f:
        import json
        saved_map = json.load(f)
        
    assert saved_map == {"i": "a", "j": "b"}
    
    editor.clear_temp()
    editor.close()


def test_bfn_editor_window_parent_node_selection(qapp, dummy_bfn_bytes):
    """Test that selecting a parent BFN file node in the tree view automatically redirects to Sheet 0."""
    from PyQt5 import QtWidgets
    editor = BfnEditorWindow()
    editor.open_from_bytes(
        dummy_bfn_bytes,
        bfn_name="test_font.bfn"
    )
    
    # Locate the parent item (file node) in the tree
    from tools.bfn_editor.bfn_editor_window import ROLE_FONT_NAME, ROLE_SHEET_IDX
    parent_item = None
    iterator = QtWidgets.QTreeWidgetItemIterator(editor.list_sheets)
    while iterator.value():
        item = iterator.value()
        if item.data(0, ROLE_FONT_NAME) == "test_font.bfn" and item.data(0, ROLE_SHEET_IDX) is None:
            parent_item = item
            break
        iterator += 1
        
    assert parent_item is not None, "Parent font file item should be present in the tree view"
    
    # Trigger selection on the parent node
    editor.list_sheets.setCurrentItem(parent_item)
    
    # The current item should be automatically redirected to Sheet 0
    current_item = editor.list_sheets.currentItem()
    assert current_item is not None
    assert current_item.data(0, ROLE_SHEET_IDX) == 0, "Selection should redirect to Sheet 0"
    
    # Glyph table must contain rows and be populated
    assert editor.table_glyphs.rowCount() > 0
    
    editor.clear_temp()
    editor.close()


def test_bfn_editor_window_escape_key_closes_window(qapp, dummy_bfn_bytes):
    """Test that pressing Escape key calls close() on the BFN editor window, and bypasses when editing."""
    from PyQt5 import QtCore, QtGui, QtWidgets
    editor = BfnEditorWindow()
    editor.open_from_bytes(dummy_bfn_bytes, bfn_name="test_font.bfn")
    
    # 1. Test closing when not editing
    close_called = False
    def mock_close():
        nonlocal close_called
        close_called = True
        
    editor.close = mock_close
    
    # Trigger the shortcut directly
    editor.sc_close.activated.emit()
    assert close_called, "Escape shortcut should close the window when not editing"
    
    # 2. Test bypass when editing in table
    close_called = False
    # Mock EditingState
    editor.table_glyphs.state = lambda: QtWidgets.QAbstractItemView.EditingState
    
    # Setup focus widget
    mock_focus = QtWidgets.QLineEdit(editor)
    editor.focusWidget = lambda: mock_focus
    
    # We expect event to be sent to mock_focus
    event_sent = False
    def mock_send_event(receiver, event):
        nonlocal event_sent
        if receiver == mock_focus and event.key() == QtCore.Qt.Key_Escape:
            event_sent = True
        return True
        
    original_send_event = QtWidgets.QApplication.sendEvent
    QtWidgets.QApplication.sendEvent = mock_send_event
    try:
        editor.sc_close.activated.emit()
    finally:
        QtWidgets.QApplication.sendEvent = original_send_event
        
    assert not close_called, "Escape shortcut should not close the window when editing"
    assert event_sent, "Escape key event should be sent to focus widget to cancel edit"
    
    editor.clear_temp()


def test_bfn_editor_window_event_filter_double_click(qapp, dummy_bfn_bytes):
    """Test that BfnEditorWindow event filter correctly intercepts double click on header boundaries."""
    from PyQt5 import QtCore, QtGui
    editor = BfnEditorWindow()
    editor.open_from_bytes(
        dummy_bfn_bytes,
        bfn_name="test_font.bfn"
    )
    
    header = editor.table_glyphs.horizontalHeader()
    header.resizeSection(0, 100)
    
    # 1. Double click exactly on the boundary of column 0 (at x=100)
    event_on_boundary = QtGui.QMouseEvent(
        QtCore.QEvent.MouseButtonDblClick,
        QtCore.QPoint(100, 5),
        QtCore.Qt.LeftButton,
        QtCore.Qt.LeftButton,
        QtCore.Qt.NoModifier
    )
    
    called_col = None
    def mock_on_double_clicked(logical_index):
        nonlocal called_col
        called_col = logical_index
        
    editor.on_header_handle_double_clicked = mock_on_double_clicked
    
    res = editor.eventFilter(header, event_on_boundary)
    assert res is True, "Event filter should intercept double click on section handle boundary"
    assert called_col == 0, "Correct section index should be passed to handler"
    
    # 2. Double click far from boundary (e.g. at x=50, middle of column 0)
    called_col = None
    event_not_on_boundary = QtGui.QMouseEvent(
        QtCore.QEvent.MouseButtonDblClick,
        QtCore.QPoint(50, 5),
        QtCore.Qt.LeftButton,
        QtCore.Qt.LeftButton,
        QtCore.Qt.NoModifier
    )
    res = editor.eventFilter(header, event_not_on_boundary)
    assert res is not True, "Event filter should not intercept double click far from boundary"
    assert called_col is None, "Handler should not be called for non-boundary click"
    
    editor.clear_temp()
    editor.close()


def test_bfn_editor_window_header_tooltips_and_no_header_resize(qapp, dummy_bfn_bytes):
    """Test that column headers have tooltips and header text is excluded from auto-resize calculation."""
    editor = BfnEditorWindow()
    editor.open_from_bytes(
        dummy_bfn_bytes,
        bfn_name="test_font.bfn"
    )
    
    # 1. Verify all 9 headers have tooltips
    expected_headers = [
        'Original Render', 'Original Char',
        'Glyph Render', 'Character', 'Unicode',
        'Texture Sheet', 'Tile Position', 'Kerning', 'Width'
    ]
    for col_idx, expected_text in enumerate(expected_headers):
        item = editor.table_glyphs.horizontalHeaderItem(col_idx)
        assert item is not None
        assert item.toolTip() == expected_text, f"Header {col_idx} should have tooltip '{expected_text}'"
        
    # 2. Verify on_header_handle_double_clicked calculates based on content only (ignoring long header text)
    # The header for column 0 is "Original Render" (very long).
    # But the content in column 0 is a glyph cellWidget with small pixmap (~12px width).
    # With header text excluded, the width should be reduced to minimum limit (35px).
    editor.on_header_handle_double_clicked(0)
    col_w = editor.table_glyphs.columnWidth(0)
    assert 35 <= col_w <= 55, f"Column 0 width should be compressed to content size, got {col_w}"
    
    editor.clear_temp()
    editor.close()


def test_bfn_editor_window_column_widths_persistence(qapp, dummy_bfn_bytes):
    """Test that BFN Glyph Table column widths are saved on close and restored on populate."""
    editor = BfnEditorWindow()
    editor.open_from_bytes(dummy_bfn_bytes, bfn_name="test_font.bfn")
    
    # 1. Mock the settings manager
    mock_settings = {}
    mock_sm = MagicMock()
    mock_sm.get.side_effect = lambda key, default=None: mock_settings.get(key, default)
    mock_sm.set.side_effect = lambda key, val: mock_settings.__setitem__(key, val)
    mock_sm.mw = MagicMock()
    
    editor.get_settings_manager = lambda: mock_sm
    
    # 2. Set some custom column widths
    test_widths = [50, 60, 70, 80, 90, 100, 110, 120, 130]
    for col, w in enumerate(test_widths):
        editor.table_glyphs.setColumnWidth(col, w)
        
    # 3. Trigger save
    editor.save_column_widths()
    
    # Verify that widths are saved in the mocked settings manager
    assert mock_settings.get("bfn_glyph_table_column_widths") == test_widths
    
    # 4. Now reset table column widths
    for col in range(len(test_widths)):
        editor.table_glyphs.setColumnWidth(col, 20)
        
    # Set _table_headers_resized to False to force populate_glyph_table to resize columns
    editor._table_headers_resized = False
    
    # 5. Populate table and verify widths are restored
    editor.populate_glyph_table()
    
    for col, w in enumerate(test_widths):
        assert editor.table_glyphs.columnWidth(col) == w, f"Column {col} width should be restored to {w}"
        
    # 6. Test fallback when no saved widths are present
    mock_settings.clear()
    editor._table_headers_resized = False
    # Verify populate does not crash and applies default column widths
    editor.populate_glyph_table()
    for col in range(9):
        assert editor.table_glyphs.columnWidth(col) > 0
        
    editor.clear_temp()
    editor.close()


def test_bfn_editor_window_autosync_and_force_recalculation(qapp, dummy_bfn_bytes):
    """Test that Auto-sync and Force Recalculation features in BFN Editor window work correctly."""
    from PyQt5 import QtCore
    editor = BfnEditorWindow()
    editor.open_from_bytes(dummy_bfn_bytes, bfn_name="test_font.bfn")
    
    # 1. Setup mock callbacks and settings manager
    mock_settings = {}
    mock_sm = MagicMock()
    mock_sm.get.side_effect = lambda key, default=None: mock_settings.get(key, default)
    mock_sm.set.side_effect = lambda key, val: mock_settings.__setitem__(key, val)
    mock_sm.mw = MagicMock()
    editor.get_settings_manager = lambda: mock_sm
    
    save_called = False
    def save_cb(bfn_name, bfn_bytes):
        nonlocal save_called
        save_called = True
        
    sync_called = False
    def sync_cb():
        nonlocal sync_called
        sync_called = True
        
    editor.archive_save_callback = save_cb
    editor.font_sync_callback = sync_cb
    
    # 2. Test manual force recalculation
    editor._dirty = True
    editor.force_sync_and_recalculate()
    assert save_called, "save_changes should be called on force_sync_and_recalculate"
    assert sync_called, "font_sync_callback should be called on force_sync_and_recalculate"
    
    # 3. Test Auto-sync toggling saves to settings
    editor.chk_auto_sync.setChecked(True)
    editor.on_auto_sync_toggled(QtCore.Qt.Checked)
    assert mock_settings.get("bfn_auto_sync_enabled") is True
    
    editor.chk_auto_sync.setChecked(False)
    editor.on_auto_sync_toggled(QtCore.Qt.Unchecked)
    assert mock_settings.get("bfn_auto_sync_enabled") is False
    
    # 4. Test Auto-sync triggers timer on dirty state
    save_called = False
    sync_called = False
    editor._dirty = False
    editor.chk_auto_sync.setChecked(True)
    
    # Trigger dirty state change via _set_dirty(True)
    editor._set_dirty(True)
    assert editor.auto_sync_timer.isActive(), "auto_sync_timer should be started when Auto-sync is checked and window becomes dirty"
    
    # 5. Verify timer timeout triggers save
    # Let's fire the timeout signal manually
    editor.auto_sync_timer.timeout.emit()
    assert save_called, "save_changes should be triggered when auto_sync_timer fires"
    
    editor.clear_temp()
    editor.close()






