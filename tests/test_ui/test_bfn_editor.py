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
            "first_char": 65,
            "last_char": 66,
            "mapping_entry_count": 2,
            "entries": [0, 1]  # 'A', 'B' map to glyphs 0, 1
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
    
    # Setup translated characters in MAP1 (Ukrainian 'А' and 'Б', codes >= 128)
    editor.metadata["MAP1"] = [{
        "mapping_type": 2,
        "first_char": 1040,
        "last_char": 1041,
        "mapping_entry_count": 2,
        "entries": [0, 1]  # 'А', 'Б'
    }]
    
    # Setup original characters in MAP1 (Umlauts 'ä' and 'å' in CP1252, codes >= 128)
    editor.original_font_metadata = {
        "MAP1": [{
            "mapping_type": 2,
            "first_char": 228,
            "last_char": 229,
            "mapping_entry_count": 2,
            "entries": [0, 1]  # 'ä', 'å'
        }]
    }
    
    # Generate translation map
    translation_map = editor.generate_translation_map()
    
    # We should have mapping: 'А' -> 'ä' and 'Б' -> 'å'
    assert translation_map == {"А": "ä", "Б": "å"}
    
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
        "first_char": 1040,
        "last_char": 1041,
        "mapping_entry_count": 2,
        "entries": [0, 1]  # 'А', 'Б'
    }]
    
    editor.original_font_metadata = {
        "MAP1": [{
            "mapping_type": 2,
            "first_char": 228,
            "last_char": 229,
            "mapping_entry_count": 2,
            "entries": [0, 1]  # 'ä', 'å'
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
        
    assert saved_map == {"А": "ä", "Б": "å"}
    
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
        "first_char": 1040,
        "last_char": 1041,
        "mapping_entry_count": 2,
        "entries": [0, 1]  # 'А', 'Б'
    }]
    
    editor.original_font_metadata = {
        "MAP1": [{
            "mapping_type": 2,
            "first_char": 228,
            "last_char": 229,
            "mapping_entry_count": 2,
            "entries": [0, 1]  # 'ä', 'å'
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
        
    assert saved_map == {"А": "ä", "Б": "å"}
    
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
        'Glyph Render', 'Character', 'Font Char',
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


def test_bfn_editor_window_dynamic_temp_dir_recreation(qapp, dummy_bfn_bytes):
    """Test that BFN Editor successfully recreates temp_dir on-the-fly if it was deleted or cleared before save."""
    from PyQt5 import QtWidgets
    editor = BfnEditorWindow()
    editor.open_from_bytes(dummy_bfn_bytes, bfn_name="test_font.bfn")
    
    # Verify initial setup
    assert editor.temp_dir != ""
    assert os.path.exists(editor.temp_dir)
    
    # Force delete the temp dir manually (mimicking unexpected OS deletion or premature clear)
    import shutil
    shutil.rmtree(editor.temp_dir, ignore_errors=True)
    assert not os.path.exists(editor.temp_dir)
    
    # Setup mock messagebox to verify no failure modal popped up
    msg_boxes = []
    def mock_critical(parent, title, text):
        msg_boxes.append((title, text))
    
    import PyQt5.QtWidgets as qw
    original_critical = qw.QMessageBox.critical
    qw.QMessageBox.critical = mock_critical
    
    try:
        # Trigger save
        editor.save_changes(silent=True)
        
        # Verify it saved successfully without showing target directory critical errors
        assert len(msg_boxes) == 0, f"Expected no error dialogs, got: {msg_boxes}"
        assert editor.temp_dir != ""
        assert os.path.exists(editor.temp_dir), "Temp directory should have been dynamically recreated"
        assert os.path.exists(editor.bfn_path), "Temp BFN file should have been compiled successfully inside reconstructed temp dir"
    finally:
        qw.QMessageBox.critical = original_critical
        editor.clear_temp()
        editor.close()


def test_bfn_editor_window_unmapped_glyph_addition(qapp, dummy_bfn_bytes):
    """Test that BFN editor successfully maps characters to previously unmapped glyphs by padding MAP1/WID1."""
    editor = BfnEditorWindow()
    editor.open_from_bytes(dummy_bfn_bytes, bfn_name="test_font.bfn")
    
    # We choose a high glyph index that is out of bounds of current entries in MAP1 and packets in WID1
    out_of_bounds_glyph_idx = 150
    
    # Let's edit mapping for this out-of-bounds glyph index
    editor.update_char_mapping(out_of_bounds_glyph_idx, ord('Z'))
    
    # Verify that MAP1 is correctly padded and updated
    maps = editor.metadata.get("MAP1", [])
    assert len(maps) > 0
    m = maps[0]
    entries = m.get("entries", [])
    assert len(entries) >= ord('Z') - m["first_char"] + 1
    assert entries[ord('Z') - m["first_char"]] == out_of_bounds_glyph_idx
    assert m["mapping_entry_count"] == len(entries)
    
    # Now let's test EditMetricsCommand for this out-of-bounds glyph
    from tools.bfn_editor.bfn_commands import EditMetricsCommand
    cmd = EditMetricsCommand(editor, out_of_bounds_glyph_idx, 0, 5, editor.cell_w, 10)
    cmd.redo()
    
    # Verify WID1 is correctly padded
    wid = editor.metadata.get("WID1", [{}])[0]
    packets = wid.get("packets", [])
    wid_idx = out_of_bounds_glyph_idx - editor.first_code
    assert len(packets) > wid_idx
    assert packets[wid_idx]["kerning"] == 5
    assert packets[wid_idx]["width"] == 10
    
    editor.clear_temp()
    editor.close()


def test_bfn_editor_window_copy_paste_chain(qapp, dummy_bfn_bytes):
    """Test that copy and paste chain features in BFN Editor window work correctly with undo/redo."""
    editor = BfnEditorWindow()
    editor.open_from_bytes(dummy_bfn_bytes, bfn_name="test_font.bfn")
    
    # Setup some test glyph mappings (glyph 0 -> 'A', glyph 1 -> 'B')
    editor.update_char_mapping(0, ord('A'))
    editor.update_char_mapping(1, ord('B'))
    editor.populate_glyph_table()
    
    # 1. Test Copy (select row 0 column 3 and row 1 column 3)
    editor.table_glyphs.clearSelection()
    
    # Mock selection
    from PyQt5.QtCore import QItemSelectionModel
    sel_model = editor.table_glyphs.selectionModel()
    sel_model.select(editor.table_glyphs.model().index(0, 3), QItemSelectionModel.Select)
    sel_model.select(editor.table_glyphs.model().index(1, 3), QItemSelectionModel.Select)
    
    editor.copy_glyph_values()
    
    # Check that clipboard has "A\nB"
    clipboard_text = QApplication.clipboard().text()
    assert clipboard_text == "A\nB"
    
    # 2. Test Paste Chain (paste "X\nY" starting at row 0)
    QApplication.clipboard().setText("X\nY")
    
    # Set current index to row 0 column 3
    editor.table_glyphs.setCurrentCell(0, 3)
    
    # Trigger paste
    editor.paste_glyph_values()
    
    # Verify values changed in virtual translation map
    assert editor.translation_map.get("X") == "A"
    assert editor.translation_map.get("Y") == "B"
    
    # Verify undo
    editor.undo_stack.undo()
    assert "X" not in editor.translation_map
    assert "Y" not in editor.translation_map
    
    # Verify redo
    editor.undo_stack.redo()
    assert editor.translation_map.get("X") == "A"
    assert editor.translation_map.get("Y") == "B"
    
    # 3. Test Smart Paste with non-newline string (paste "PQ" starting at row 0)
    QApplication.clipboard().setText("PQ")
    editor.table_glyphs.setCurrentCell(0, 3)
    editor.paste_glyph_values()
    
    assert editor.translation_map.get("P") == "A"
    assert editor.translation_map.get("Q") == "B"
    
    editor.clear_temp()
    editor.close()


def test_bfn_editor_window_generate_translation_map_ignores_ascii(qapp, dummy_bfn_bytes):
    """Test that generate_translation_map ignores ASCII characters with codes < 128."""
    editor = BfnEditorWindow()
    editor.open_from_bytes(
        dummy_bfn_bytes,
        bfn_name="test_font.bfn"
    )
    
    # Setup mixed characters in MAP1: ASCII ('A', 'B') and Ukrainian ('А', 'Б' >= 128)
    editor.metadata["MAP1"] = [{
        "mapping_type": 2,
        "first_char": 65,  # 'A', 'B', 'А' (1040), 'Б' (1041)
        "last_char": 1041,
        "mapping_entry_count": 4,
        "entries": [0, 1, 2, 3]
    }]
    # Force entries to map specifically:
    # Glyph 0 -> 'A' (65)
    # Glyph 1 -> 'B' (66)
    # Glyph 2 -> 'А' (1040)
    # Glyph 3 -> 'Б' (1041)
    
    # Setup original characters in MAP1: ASCII ('!', '"') and German ('ä', 'å' >= 128)
    editor.original_font_metadata = {
        "MAP1": [{
            "mapping_type": 2,
            "first_char": 33,  # '!', '"', 'ä' (228), 'å' (229)
            "last_char": 229,
            "mapping_entry_count": 4,
            "entries": [0, 1, 2, 3]
        }]
    }
    
    # We mock get_char_for_glyph internally by patching get_char_for_glyph in generate_translation_map logic
    # Or simply let our get_char_for_glyph parse the mapped structures:
    # For Glyph 0: trans='A' (65), orig='!' (33) -> Both are ASCII < 128. Should be ignored!
    # For Glyph 1: trans='B' (66), orig='"' (34) -> Both are ASCII < 128. Should be ignored!
    # For Glyph 2: trans='А' (1040), orig='ä' (228) -> Both >= 128. Should be mapped!
    # For Glyph 3: trans='Б' (1041), orig='å' (229) -> Both >= 128. Should be mapped!
    
    # Let's adjust entries to actually return these characters
    # Since get_char_for_glyph searches for m_first + c_idx where entries[c_idx] == glyph_idx:
    # For trans:
    # Glyph 0: code 65. entries has 0 at index 0. first_char = 65. code = 65 + 0 = 65 ('A'). Correct!
    # Glyph 1: code 66. entries has 1 at index 1. first_char = 65. code = 65 + 1 = 66 ('B'). Correct!
    # Glyph 2: code 1040. To get 1040: we need c_idx = 1040 - 65 = 975. So entries must have Glyph 2 at index 975.
    # To keep it extremely simple, let's just mock the nested function get_char_for_glyph, or set map_blocks to have multiple MAP1 blocks!
    # Yes, we can have multiple MAP1 blocks, or we can just mock get_char_for_glyph by monkeypatching!
    # But wait, generate_translation_map defines get_char_for_glyph locally.
    # We can easily create a simple metadata with two blocks!
    
    editor.metadata["MAP1"] = [
        {
            "mapping_type": 2,
            "first_char": 65,  # ASCII
            "last_char": 66,
            "mapping_entry_count": 2,
            "entries": [0, 1]
        },
        {
            "mapping_type": 2,
            "first_char": 1040,  # Cyrillic
            "last_char": 1041,
            "mapping_entry_count": 2,
            "entries": [2, 3]
        }
    ]
    
    editor.original_font_metadata = {
        "MAP1": [
            {
                "mapping_type": 2,
                "first_char": 33,  # ASCII
                "last_char": 34,
                "mapping_entry_count": 2,
                "entries": [0, 1]
            },
            {
                "mapping_type": 2,
                "first_char": 228,  # Cyrillic override
                "last_char": 229,
                "mapping_entry_count": 2,
                "entries": [2, 3]
            }
        ]
    }
    
    translation_map = editor.generate_translation_map()
    
    # ASCII mappings ("A"->"!" and "B"->'"') must be ignored.
    # Only Cyrillic ("А"->"ä" and "Б"->"å") must be present!
    assert "A" not in translation_map
    assert "B" not in translation_map
    assert translation_map == {"А": "ä", "Б": "å"}
    
    editor.clear_temp()
    editor.close()


def test_bfn_editor_empty_glyph_automatic_physical_registration(qapp, dummy_bfn_bytes):
    """Test that empty glyphs are automatically registered in MAP1 metadata with physical codes."""
    editor = BfnEditorWindow()
    editor.open_from_bytes(dummy_bfn_bytes, bfn_name="test_font.bfn")
    
    # Verify glyph 5 has no mapping in original/comparison font MAP1 (empty glyph)
    orig_char = editor.get_original_char_for_glyph(5)
    assert not orig_char
    
    # 1. Trigger manual change of glyph 5 Character (column 3) to "Я"
    from PyQt5.QtWidgets import QTableWidgetItem
    item = QTableWidgetItem("Я")
    
    # Setup table structure and mock item changed event
    editor.table_glyphs.setItem(5, 3, item)
    # Mock row header widget
    row_header = QTableWidgetItem("5")
    editor.table_glyphs.setVerticalHeaderItem(5, row_header)
    
    # Trigger cell edit manually
    editor.on_table_item_changed(item)
    
    # Verify that:
    # A) Glyph 5 is physically registered in MAP1 metadata
    new_orig_char = editor.get_original_char_for_glyph(5)
    assert new_orig_char == chr(5)
    
    # B) Virtual translation map contains clean mapping "Я" -> chr(5) without any synthetic "#g" keys!
    assert editor.translation_map.get("Я") == chr(5)
    assert editor.reverse_translation_map.get(chr(5)) == "Я"
    assert "#g5" not in editor.translation_map
    
    editor.clear_temp()
    editor.close()









