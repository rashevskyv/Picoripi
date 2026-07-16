import pytest
from unittest.mock import MagicMock, patch
from PyQt6.QtWidgets import QApplication, QMenu, QFileDialog, QInputDialog
from PyQt6.QtCore import QPoint, QPointF, Qt, QRect, QEvent
from PyQt6.QtGui import QMouseEvent, QImage
from ui.components.bfn_preview_widget import BfnPreviewWidget
from core.bfn_core import BfnCore

@pytest.fixture(scope="module")
def qapp():
    """Ensure a QApplication exists for widget testing."""
    app = QApplication.instance()
    if not app:
        app = QApplication([])
    return app

def test_bfn_preview_widget_init(qapp):
    mw_mock = MagicMock()
    widget = BfnPreviewWidget(mw_mock)
    
    assert widget.mw == mw_mock
    assert widget.text == ""
    assert widget.translation_map is None
    assert "BfnPreviewWidget {" in widget.styleSheet()

def test_bfn_preview_widget_update_text(qapp):
    mw_mock = MagicMock()
    widget = BfnPreviewWidget(mw_mock)
    
    widget.update_preview_text("Привіт")
    assert widget.text == "Привіт"

def test_bfn_preview_widget_get_active_font(qapp):
    mw_mock = MagicMock()
    mw_mock.data_store.current_block_idx = 0
    mw_mock.data_store.current_string_idx = 1
    
    # 1. Custom string meta override font
    mw_mock.string_metadata = {
        (0, 1): {"font_file": "custom_font.bfn"}
    }
    
    bfn_mock = MagicMock(spec=BfnCore)
    mw_mock.all_bfn_fonts = {"custom_font.bfn": bfn_mock}
    
    widget = BfnPreviewWidget(mw_mock)
    active_font = widget.get_active_bfn_font()
    assert active_font == bfn_mock
    
    # 2. Fallback to default_font_file
    mw_mock.string_metadata = {}
    mw_mock.default_font_file = "default_font.bfn"
    default_bfn_mock = MagicMock(spec=BfnCore)
    mw_mock.all_bfn_fonts = {"default_font.bfn": default_bfn_mock}
    
    active_font_fallback = widget.get_active_bfn_font()
    assert active_font_fallback == default_bfn_mock


def test_bfn_preview_widget_uses_window_layout_font(qapp):
    mw_mock = MagicMock()
    mw_mock.data_store.current_block_idx = 0
    mw_mock.data_store.current_string_idx = 1
    mw_mock.string_metadata = {}
    mw_mock.default_font_file = "default.bfn"
    mw_mock.current_game_rules.get_string_layout.return_value = {
        "font_file": "reishotai_24_22.bfn"
    }
    expected = MagicMock(spec=BfnCore)
    mw_mock.all_bfn_fonts = {
        "default.bfn": MagicMock(spec=BfnCore),
        "rubyres.arc/reishotai_24_22.bfn": expected,
    }

    widget = BfnPreviewWidget(mw_mock)

    assert widget.get_active_bfn_font() is expected

def test_bfn_preview_widget_get_active_font_archive_fallback(qapp):
    mw_mock = MagicMock()
    mw_mock.data_store.current_block_idx = 0
    mw_mock.data_store.current_string_idx = 1
    
    # 1. Custom string meta has basic font name
    mw_mock.string_metadata = {
        (0, 1): {"font_file": "reishotai_24_22.bfn"}
    }
    
    bfn_mock = MagicMock(spec=BfnCore)
    # The cache contains archive prefix in its key
    mw_mock.all_bfn_fonts = {"rubyres.arc/reishotai_24_22.bfn": bfn_mock}
    
    widget = BfnPreviewWidget(mw_mock)
    active_font = widget.get_active_bfn_font()
    assert active_font == bfn_mock

def test_bfn_preview_widget_paint_event_fallback(qapp):
    from PyQt6.QtGui import QImage
    
    # 1. Setup mocks
    mw_mock = MagicMock()
    mw_mock.active_game_plugin = "zelda_bmg"
    mw_mock.data_store.current_block_idx = 0
    mw_mock.data_store.current_string_idx = 1
    mw_mock.string_metadata = {}
    mw_mock.default_font_file = "default.bfn"
    
    bfn_mock = MagicMock()
    bfn_mock.gly1 = [{
        "cell_width": 24,
        "cell_height": 24,
        "glyph_horizontal_count": 5,
        "glyph_vertical_count": 5,
        "start_glyph": 0,
        "end_glyph": 224
    }]
    
    # Entries: let's map CP1252 'â' (code 226) to glyph index 226, 
    # and also map Cyrillic 'в' (code 1074) to glyph index 100 in MAP1 entries
    bfn_mock.map1 = [{
        "mapping_type": 3,
        "first_char": 0,
        "last_char": 2000,
        "entries": [
            226, 1074,  # Codes
            226, 100    # Glyph Indices (half-sized layout for type 3)
        ]
    }]
    
    bfn_mock.wid1 = [{
        "first_code_included": 0,
        "packets": [{"kerning": 0, "width": 20} for _ in range(2000)]
    }]
    
    img = QImage(128, 128, QImage.Format.Format_ARGB32)
    bfn_mock.get_sheets_qimages.return_value = [img]
    
    mw_mock.all_bfn_fonts = {"default.bfn": bfn_mock}
    
    # 2. Setup widget with translation map
    widget = BfnPreviewWidget(mw_mock)
    widget.translation_map = {
        "в": "â",  # 'в' translates to CP1252 'â'
        "о": "î"   # 'о' translates to CP1252 'î' (which won't be directly in MAP1)
    }
    
    # Text contains:
    # - 'в': directly mapped in MAP1 to glyph 100.
    # - 'о': not directly in MAP1, but in translation_map. Translates to 'î' (which also isn't in MAP1). Should trigger fallback and finally draw fallback box.
    # - 'â': directly in MAP1 to glyph 226.
    widget.update_preview_text("вâо")
    
    # Trigger paintEvent manually by rendering into a paint device
    render_img = QImage(300, 130, QImage.Format.Format_ARGB32)
    render_img.fill(Qt.GlobalColor.black if hasattr(Qt, "GlobalColor") else Qt.black)
    
    # Ensure no exception is raised
    widget.render(render_img)


def test_bfn_preview_widget_drag_and_drop(qapp):
    mw_mock = MagicMock()
    widget = BfnPreviewWidget(mw_mock)
    widget.setGeometry(0, 0, 500, 300)
    widget.text_rect = QRect(10, 10, 100, 100)
    
    # Mouse press inside
    press_event = QMouseEvent(QEvent.Type.MouseButtonPress, QPointF(20, 20), Qt.MouseButton.LeftButton, Qt.MouseButton.LeftButton, Qt.KeyboardModifier.NoModifier)
    widget.mousePressEvent(press_event)
    assert widget.drag_active is True
    assert widget.drag_start_pos == QPoint(20, 20)
    
    # Mouse move to drag
    widget.mouseMoveEvent(QMouseEvent(QEvent.Type.MouseMove, QPointF(40, 50), Qt.MouseButton.NoButton, Qt.MouseButton.NoButton, Qt.KeyboardModifier.NoModifier))
    
    # self.text_rect should move by dx=20, dy=30
    assert widget.text_rect == QRect(30, 40, 100, 100)
    
    # Mouse release
    release_event = QMouseEvent(QEvent.Type.MouseButtonRelease, QPointF(40, 50), Qt.MouseButton.LeftButton, Qt.MouseButton.LeftButton, Qt.KeyboardModifier.NoModifier)
    widget.mouseReleaseEvent(release_event)
    assert widget.drag_active is False
    # Check that settings_manager.save_settings was called
    mw_mock.settings_manager.save_settings.assert_called_once()
    assert mw_mock.preview_text_rect == [30, 40, 100, 100]


def test_bfn_preview_widget_resize(qapp):
    mw_mock = MagicMock()
    widget = BfnPreviewWidget(mw_mock)
    widget.setGeometry(0, 0, 500, 300)
    widget.text_rect = QRect(10, 10, 100, 100)
    
    # Mouse press on 'bottom-right' handle.
    # rx + rw = 10 + 100 = 110. ry + rh = 10 + 100 = 110.
    # bottom-right handle center is at (110, 110)
    press_event = QMouseEvent(QEvent.Type.MouseButtonPress, QPointF(110, 110), Qt.MouseButton.LeftButton, Qt.MouseButton.LeftButton, Qt.KeyboardModifier.NoModifier)
    widget.mousePressEvent(press_event)
    assert widget.resize_active is True
    assert widget.resize_handle == 'bottom-right'
    
    # Drag to (130, 140) -> dx = 20, dy = 30
    widget.mouseMoveEvent(QMouseEvent(QEvent.Type.MouseMove, QPointF(130, 140), Qt.MouseButton.NoButton, Qt.MouseButton.NoButton, Qt.KeyboardModifier.NoModifier))
    # bottom right moves: x2 becomes 110 + 20 = 130, y2 becomes 110 + 30 = 140
    # QRect(QPoint(10, 10), QPoint(130, 140)) -> width = 130 - 10 + 1 = 121, height = 140 - 10 + 1 = 131
    assert widget.text_rect.width() == 120
    assert widget.text_rect.height() == 130
    
    # Release
    widget.mouseReleaseEvent(QMouseEvent(QEvent.Type.MouseButtonRelease, QPointF(130, 140), Qt.MouseButton.LeftButton, Qt.MouseButton.LeftButton, Qt.KeyboardModifier.NoModifier))
    assert widget.resize_active is False


def test_bfn_preview_widget_menu_actions(qapp):
    mw_mock = MagicMock()
    widget = BfnPreviewWidget(mw_mock)
    
    actions_created = {}
    original_add_action = QMenu.addAction
    
    def spy_add_action(menu_obj, text):
        action = original_add_action(menu_obj, text)
        actions_created[text] = action
        return action
        
    with patch.object(QMenu, 'addAction', spy_add_action), \
         patch.object(QMenu, 'exec') as mock_exec, \
         patch.object(QFileDialog, 'getOpenFileName', return_value=("test_image.png", "Images")), \
         patch.object(QInputDialog, 'getInt', return_value=(15, True)):
         
         # 1. Test Set Background Image
         actions_created.clear()
         mock_exec.side_effect = lambda *args: actions_created.get("Set Background Image...")
         widget.show_context_menu(QPoint(0, 0))
         
         assert widget.bg_image_path == "test_image.png"
         assert mw_mock.preview_bg_image_path == "test_image.png"
         mw_mock.settings_manager.save_settings.assert_called()
         
         # 2. Test Clear Background Image
         actions_created.clear()
         mock_exec.side_effect = lambda *args: actions_created.get("Clear Background Image")
         widget.show_context_menu(QPoint(0, 0))
         
         assert widget.bg_image_path == ""
         assert widget.bg_image is None
         assert mw_mock.preview_bg_image_path == ""
         
         # 3. Test Set Line Spacing
         actions_created.clear()
         mock_exec.side_effect = lambda *args: actions_created.get("Set Line Spacing...")
         widget.show_context_menu(QPoint(0, 0))
         
         assert widget.line_spacing == 15
         assert mw_mock.preview_line_spacing == 15
         
         # 4. Test Reset Text Area
         actions_created.clear()
         mock_exec.side_effect = lambda *args: actions_created.get("Reset Text Area")
         widget.show_context_menu(QPoint(0, 0))
         
         assert widget.text_rect == QRect(15, 15, 300, 120)
         assert mw_mock.preview_text_rect == [15, 15, 300, 120]


def test_bfn_preview_widget_paint_event_no_bfn_fallback(qapp):
    from PyQt6.QtGui import QImage
    
    # 1. Setup mocks with no BFN fonts
    mw_mock = MagicMock()
    mw_mock.active_game_plugin = "zelda_mc"
    mw_mock.data_store.current_block_idx = 0
    mw_mock.data_store.current_string_idx = 1
    mw_mock.string_metadata = {}
    mw_mock.default_font_file = None
    mw_mock.all_bfn_fonts = {}
    
    # Setup spellcheck ignore pattern to test regex ignore
    mock_rules = MagicMock()
    mock_rules.get_spellcheck_ignore_pattern.return_value = r'\[\w+\]'
    mw_mock.current_game_rules = mock_rules
    
    widget = BfnPreviewWidget(mw_mock)
    widget.text_rect = QRect(15, 15, 300, 120)
    widget.update_preview_text("Hello {Color:Red} world [PLAYER]!")
    
    # Render into a paint device
    render_img = QImage(300, 130, QImage.Format.Format_ARGB32)
    render_img.fill(Qt.GlobalColor.black if hasattr(Qt, "GlobalColor") else Qt.black)
    
    # Ensure no exception is raised and fallback paint branch is fully executed
    widget.render(render_img)


def test_bfn_preview_widget_paint_event_missing_glyph_fallback(qapp):
    from PyQt6.QtGui import QImage
    
    # Setup mocks for a valid BFN font but missing glyph for specific character
    mw_mock = MagicMock()
    mw_mock.active_game_plugin = "zelda_mc"
    mw_mock.data_store.current_block_idx = 0
    mw_mock.data_store.current_string_idx = 1
    mw_mock.string_metadata = {}
    mw_mock.default_font_file = "test.bfn"
    
    bfn_mock = MagicMock()
    bfn_mock.gly1 = [{
        "cell_width": 16,
        "cell_height": 16,
        "glyph_horizontal_count": 8,
        "glyph_vertical_count": 8,
        "start_glyph": 0,
        "end_glyph": 64
    }]
    
    # Standard ASCII map
    bfn_mock.map1 = [{
        "mapping_type": 0,
        "first_char": 0,
        "last_char": 127,
        "entries": []
    }]
    
    bfn_mock.wid1 = [{
        "first_code_included": 0,
        "packets": [{"kerning": 0, "width": 12} for _ in range(128)]
    }]
    
    sheet = QImage(128, 128, QImage.Format.Format_ARGB32)
    bfn_mock.get_sheets_qimages.return_value = [sheet]
    mw_mock.all_bfn_fonts = {"test.bfn": bfn_mock}
    
    widget = BfnPreviewWidget(mw_mock)
    widget.text_rect = QRect(10, 10, 200, 100)
    
    # "Hello" -> found in ASCII. "Ф" -> not in ASCII map, triggers fallback
    widget.update_preview_text("HelloФ")
    
    render_img = QImage(200, 100, QImage.Format.Format_ARGB32)
    render_img.fill(Qt.GlobalColor.black if hasattr(Qt, "GlobalColor") else Qt.black)
    
    # Should execute successfully without throwing exceptions
    widget.render(render_img)


def test_bfn_preview_widget_with_active_editor_adapter(qapp):
    from PyQt6.QtGui import QImage
    from ui.components.bfn_preview_widget import BfnEditorAdapter

    class DummyBfnEditor:
        def __init__(self):
            self.metadata = {
                "GLY1": [{
                    "cell_width": 24,
                    "cell_height": 24,
                    "glyph_horizontal_count": 5,
                    "glyph_vertical_count": 5,
                    "start_glyph": 0,
                    "end_glyph": 224,
                    "texture_width": 128,
                    "texture_height": 128
                }],
                "MAP1": [{
                    "mapping_type": 2,
                    "first_char": 0,
                    "last_char": 127,
                    "entries": [i for i in range(128)]
                }],
                "WID1": [{
                    "first_code_included": 0,
                    "packets": [{"kerning": 0, "width": 12} for _ in range(128)]
                }],
                "INF1": []
            }
            self.sheet_images = [QImage(128, 128, QImage.Format.Format_ARGB32)]
            
        def isHidden(self):
            return False

    mw_mock = MagicMock()
    editor_dummy = DummyBfnEditor()
    
    mw_mock._bfn_editor_window = editor_dummy
    
    widget = BfnPreviewWidget(mw_mock)
    active_font = widget.get_active_bfn_font()
    
    assert isinstance(active_font, BfnEditorAdapter)
    assert active_font.gly1 == editor_dummy.metadata["GLY1"]
    assert active_font.map1 == editor_dummy.metadata["MAP1"]
    assert active_font.wid1 == editor_dummy.metadata["WID1"]
    assert active_font.get_sheets_qimages() == editor_dummy.sheet_images
    
    # Verify that paintEvent renders successfully with adapter
    widget.text_rect = QRect(10, 10, 200, 100)
    widget.update_preview_text("Test text")
    
    render_img = QImage(200, 100, QImage.Format.Format_ARGB32)
    render_img.fill(Qt.GlobalColor.black if hasattr(Qt, "GlobalColor") else Qt.black)
    widget.render(render_img)


def test_bfn_preview_widget_stem_matching_and_fallback(qapp):
    # 1. Stem matching test
    mw_mock = MagicMock()
    mw_mock.data_store.current_block_idx = 0
    mw_mock.data_store.current_string_idx = 1
    mw_mock.string_metadata = {
        (0, 1): {"font_file": "CKingMsg.json"}
    }
    
    bfn_mock = MagicMock(spec=BfnCore)
    mw_mock.all_bfn_fonts = {"CKingMsg.bfn": bfn_mock}
    
    widget = BfnPreviewWidget(mw_mock)
    active_font = widget.get_active_bfn_font()
    assert active_font == bfn_mock
    
    # 2. Fallback to first available BFN font when name does not match
    mw_mock.string_metadata = {
        (0, 1): {"font_file": "unknown_font.bfn"}
    }
    active_font_fallback = widget.get_active_bfn_font()
    assert active_font_fallback == bfn_mock


def test_bfn_editor_to_global_preview_cache_sync(qapp):
    from tools.bfn_editor.bfn_io import BfnIoMixin
    from PyQt6.QtGui import QImage
    
    # Create a mock window class that mixes in BfnIoMixin
    class DummyEditor(BfnIoMixin):
        def __init__(self, parent_mw):
            self._parent_mw = parent_mw
            self.metadata = {
                "GLY1": [{"cell_width": 24, "cell_height": 24}],
                "MAP1": [],
                "WID1": [],
                "INF1": []
            }
            self.sheet_images = [QImage(32, 32, QImage.Format.Format_ARGB32)]
            self.current_bfn_name = "test_sync_font.bfn"
            self.archive_name = "test_sync_archive.arc"
            
        def parent(self):
            return self._parent_mw
            
        def _set_dirty(self, state):
            pass

    mw_mock = MagicMock()
    mw_mock.all_bfn_fonts = {}
    preview_widget_mock = MagicMock()
    mw_mock.bfn_preview_widget = preview_widget_mock
    
    editor = DummyEditor(mw_mock)
    editor._sync_with_global_preview_cache()
    
    # Check that cache was populated with multiple fallback names
    assert "test_sync_font.bfn" in mw_mock.all_bfn_fonts
    assert "default.bfn" in mw_mock.all_bfn_fonts
    assert "default" in mw_mock.all_bfn_fonts
    assert "test_sync_archive.arc/test_sync_font.bfn" in mw_mock.all_bfn_fonts
    
    # Verify the cached object is a BfnCore instance with correct properties
    cached_bfn = mw_mock.all_bfn_fonts["test_sync_font.bfn"]
    assert isinstance(cached_bfn, BfnCore)
    assert cached_bfn.gly1 == editor.metadata["GLY1"]
    assert len(cached_bfn._qimages_cache) == 1
    
    # Verify widget refresh was triggered
    preview_widget_mock.update.assert_called_once()


def test_bfn_preview_widget_get_active_font_no_project_fallback(qapp):
    # Setup mock main window with a populated BFN cache but no project/string metadata
    mw_mock = MagicMock()
    mw_mock.data_store.current_block_idx = -1
    mw_mock.data_store.current_string_idx = -1
    mw_mock.default_font_file = None
    
    bfn_mock = MagicMock(spec=BfnCore)
    mw_mock.all_bfn_fonts = {"fallback_test.bfn": bfn_mock}
    
    widget = BfnPreviewWidget(mw_mock)
    active_font = widget.get_active_bfn_font()
    
    # Even without a project (font_file is None), it should fallback to the first available BFN font in cache
    assert active_font == bfn_mock


def test_bfn_core_linear_mapping_type_0_conversion():
    # Construct a raw binary BFN payload with a MAP1 chunk of type 0
    # Header: 8 bytes signature, 4 bytes file size, 4 bytes chunk count, 16 bytes padding = 32 bytes
    # INF1 chunk: 'INF1' (4 bytes), size 32 (4 bytes), body 24 bytes (encoding=1, ascent=24, descent=0, width=24, leading=0, fallback_code=0, unk1=0, 8 bytes padding)
    # GLY1 chunk: 'GLY1' (4 bytes), size 32 (4 bytes), start_glyph=0, end_glyph=10, cell_width=24, cell_height=24, page_data_size=0, texture_format=0, h_count=5, v_count=5, texture_width=120, texture_height=120, 2 bytes padding
    # MAP1 chunk: 'MAP1' (4 bytes), size 32 (4 bytes), mapping_type=0, first_char=32, last_char=42, entry_count=0, padded to 32 bytes
    # WID1 chunk: 'WID1' (4 bytes), size 32 (4 bytes), first_code=32, last_code=42, 10 packets (kerning=0, width=20)
    
    import struct
    header = struct.pack('>8sII', b'FFNT1bnd', 160, 4) + b'\x00' * 16 # 32 bytes
    
    inf1 = struct.pack('>4sI', b'INF1', 32) + struct.pack('>HHHHHH', 1, 24, 0, 24, 0, 0) + struct.pack('>I', 0) + b'\x00' * 8 # 32 bytes
    
    gly1 = struct.pack('>4sI', b'GLY1', 32) + struct.pack('>HHHHIHHHHH', 0, 10, 24, 24, 0, 0, 5, 5, 120, 120) + b'\x00' * 2 # 32 bytes
    
    map1 = struct.pack('>4sI', b'MAP1', 32) + struct.pack('>HHHH', 0, 32, 42, 0) + b'\x00' * 16 # 32 bytes
    
    wid1 = struct.pack('>4sI', b'WID1', 32) + struct.pack('>HH', 32, 42) + b'\x00' * 20 # 32 bytes
    
    bfn_data = header + inf1 + gly1 + map1 + wid1
    
    bfn = BfnCore()
    bfn.load(bfn_data)
    
    # 1. Verify automatic type 0 to type 2 conversion in BfnCore.load()
    assert bfn.map1[0]["mapping_type"] == 2
    assert bfn.map1[0]["mapping_entry_count"] == 11
    # entries should be [0, 1, 2, ..., 10]
    assert bfn.map1[0]["entries"] == list(range(11))
    
    # 2. Verify that layout_text successfully maps character with absolute code to relative index
    # Char space ' ' has code 32, '!' has code 33
    # With conversion, char '!' (code 33) maps to entries index 1 (relative glyph index 1)
    glyphs, w, h = bfn.layout_text("!")
    assert len(glyphs) == 1
    assert glyphs[0]["char"] == "!"
    assert glyphs[0]["glyph_idx"] == 1 # 33 - 32 = 1
    assert glyphs[0]["is_fallback"] is False


def test_bfn_preview_widget_visibility_management(qapp):
    from ui.updaters.preview_updater import PreviewUpdater

    # Setup mock MainWindow
    mw_mock = MagicMock()
    mw_mock.all_bfn_fonts = {} # Initially no fonts loaded
    mw_mock.data_store.current_block_idx = -1
    mw_mock.data_store.current_string_idx = -1
    
    # Mock bfn_preview_widget
    preview_widget_mock = MagicMock()
    mw_mock.bfn_preview_widget = preview_widget_mock
    
    # Mock toggle_preview_action
    toggle_action_mock = MagicMock()
    mw_mock.toggle_preview_action = toggle_action_mock
    
    # Initialize PreviewUpdater
    data_proc_mock = MagicMock()
    updater = PreviewUpdater(mw_mock, data_proc_mock)
    
    # Test case 1: Fonts not loaded
    updater.update_preview_visibility()
    
    preview_widget_mock.hide.assert_called_once()
    toggle_action_mock.setEnabled.assert_called_once_with(False)
    toggle_action_mock.setChecked.assert_called_once_with(False)
    mw_mock.settings_manager.save_settings.assert_not_called()
    
    # Reset mocks
    preview_widget_mock.reset_mock()
    toggle_action_mock.reset_mock()
    
    # Test case 2: Fonts loaded, toggle action is checked
    mw_mock.all_bfn_fonts = {"font.bfn": MagicMock()}
    toggle_action_mock.isChecked.return_value = True
    
    updater.update_preview_visibility()
    
    toggle_action_mock.setEnabled.assert_called_once_with(True)
    preview_widget_mock.show.assert_called_once()
    preview_widget_mock.hide.assert_not_called()
    
    # Reset mocks
    preview_widget_mock.reset_mock()
    toggle_action_mock.reset_mock()
    
    # Test case 3: the user explicitly switches preview off
    updater.update_preview_visibility(False)
    
    preview_widget_mock.hide.assert_called_once()
    preview_widget_mock.show.assert_not_called()
    assert mw_mock.preview_enabled is False
    mw_mock.settings_manager.save_settings.assert_called_once()


def test_disabled_bfn_preview_does_not_prepare_text(qapp):
    mw_mock = MagicMock()
    mw_mock.preview_enabled = False
    widget = BfnPreviewWidget(mw_mock)
    widget.text = "old"

    widget.update_preview_text("new")

    assert widget.text == "old"
    assert widget._preview_resources_loaded is False


def test_page_bar_is_pinned_to_rendered_background(qapp):
    from PyQt6.QtGui import QImage

    mw_mock = MagicMock()
    mw_mock.preview_enabled = True
    widget = BfnPreviewWidget(mw_mock)
    widget.resize(900, 300)
    widget.bg_image = QImage(700, 240, QImage.Format.Format_ARGB32)
    widget.bg_hidden = False
    widget.bg_scale = 100
    widget.bg_offset_x = 20
    widget.bg_offset_y = 15

    widget._position_page_bar()

    assert widget.page_bar.geometry() == QRect(720, 15, 38, 240)


def test_bfn_preview_widget_background_gestures(qapp):
    from PyQt6.QtGui import QImage
    mw_mock = MagicMock()
    widget = BfnPreviewWidget(mw_mock)
    widget.setGeometry(0, 0, 500, 300)
    
    # Mock loaded image
    widget.bg_image = QImage(32, 32, QImage.Format.Format_ARGB32)
    widget.bg_scale = 100
    widget.bg_offset_x = 10
    widget.bg_offset_y = 15
    
    # 1. Ctrl + Drag gesture (Scale)
    press_event_ctrl = QMouseEvent(
        QEvent.Type.MouseButtonPress, QPointF(100, 100), Qt.MouseButton.LeftButton, Qt.MouseButton.LeftButton, Qt.KeyboardModifier.ControlModifier
    )
    widget.mousePressEvent(press_event_ctrl)
    assert widget.scale_drag_active is True
    assert widget.drag_start_pos == QPoint(100, 100)
    assert widget.drag_start_scale == 100
    
    # Move mouse up by 30px (dy = -30) -> Scale should change by 30% (increase)
    widget.mouseMoveEvent(QMouseEvent(QEvent.Type.MouseMove, QPointF(100, 70), Qt.MouseButton.NoButton, Qt.MouseButton.NoButton, Qt.KeyboardModifier.ControlModifier))
    assert widget.bg_scale == 130
    
    # Release Ctrl + Drag
    widget.mouseReleaseEvent(QMouseEvent(QEvent.Type.MouseButtonRelease, QPointF(100, 70), Qt.MouseButton.LeftButton, Qt.MouseButton.LeftButton, Qt.KeyboardModifier.ControlModifier))
    assert widget.scale_drag_active is False
    assert mw_mock.preview_bg_scale == 130
    mw_mock.settings_manager.save_settings.assert_called()
    
    # Reset mock
    mw_mock.settings_manager.save_settings.reset_mock()
    
    # 2. Alt + Drag gesture (Move offset)
    press_event_alt = QMouseEvent(
        QEvent.Type.MouseButtonPress, QPointF(100, 100), Qt.MouseButton.LeftButton, Qt.MouseButton.LeftButton, Qt.KeyboardModifier.AltModifier
    )
    widget.mousePressEvent(press_event_alt)
    assert widget.move_bg_drag_active is True
    assert widget.drag_start_pos == QPoint(100, 100)
    assert widget.drag_start_offset_x == 10
    assert widget.drag_start_offset_y == 15
    
    # Move mouse by dx = 20px, dy = -10px
    widget.mouseMoveEvent(QMouseEvent(QEvent.Type.MouseMove, QPointF(120, 90), Qt.MouseButton.NoButton, Qt.MouseButton.NoButton, Qt.KeyboardModifier.AltModifier))
    assert widget.bg_offset_x == 30
    assert widget.bg_offset_y == 5
    
    # Release Alt + Drag
    widget.mouseReleaseEvent(QMouseEvent(QEvent.Type.MouseButtonRelease, QPointF(120, 90), Qt.MouseButton.LeftButton, Qt.MouseButton.LeftButton, Qt.KeyboardModifier.AltModifier))
    assert widget.move_bg_drag_active is False
    assert mw_mock.preview_bg_offset_x == 30
    assert mw_mock.preview_bg_offset_y == 5
    mw_mock.settings_manager.save_settings.assert_called_once()


def test_bfn_preview_widget_hide_background(qapp):
    mw_mock = MagicMock()
    mw_mock.preview_bg_hidden = False
    widget = BfnPreviewWidget(mw_mock)
    
    actions_created = {}
    original_add_action = QMenu.addAction
    
    def spy_add_action(menu_obj, text):
        action = original_add_action(menu_obj, text)
        actions_created[text] = action
        if text == "Hide Background":
            action.isChecked = MagicMock(return_value=True)
        return action
        
    with patch.object(QMenu, 'addAction', spy_add_action), \
         patch.object(QMenu, 'exec') as mock_exec:
         
         widget.bg_image_path = "some_image.png"
         
         # Return the dynamically created QAction when exec is called
         mock_exec.side_effect = lambda *args: actions_created.get("Hide Background")
         
         widget.show_context_menu(QPoint(0, 0))
         
         assert widget.bg_hidden is True
         assert mw_mock.preview_bg_hidden is True
         mw_mock.settings_manager.save_settings.assert_called_once()


def test_bfn_preview_widget_fix_font_scale(qapp):
    mw_mock = MagicMock()
    mw_mock.preview_fix_font_scale = False
    mw_mock.preview_fixed_font_scale = 1.0
    
    widget = BfnPreviewWidget(mw_mock)
    assert widget.fix_font_scale is False
    
    widget._last_computed_scale_factor = 1.85
    
    actions_created = {}
    original_add_action = QMenu.addAction
    
    def spy_add_action(menu_obj, text):
        action = original_add_action(menu_obj, text)
        actions_created[text] = action
        if text == "Fix Font Scale":
            action.isChecked = MagicMock(return_value=True)
        return action
        
    with patch.object(QMenu, 'addAction', spy_add_action), \
         patch.object(QMenu, 'exec') as mock_exec:
         
         # Return the dynamically created QAction when exec is called
         mock_exec.side_effect = lambda *args: actions_created.get("Fix Font Scale")
         
         widget.show_context_menu(QPoint(0, 0))
         
         assert widget.fix_font_scale is True
         assert widget.fixed_font_scale == 1.85
         assert mw_mock.preview_fix_font_scale is True
         assert mw_mock.preview_fixed_font_scale == 1.85
         mw_mock.settings_manager.save_settings.assert_called()


def test_bfn_preview_widget_page_switcher(qapp):
    mw_mock = MagicMock()
    widget = BfnPreviewWidget(mw_mock)
    widget.setGeometry(0, 0, 400, 300)
    
    # Initially hide
    assert widget.page_bar.isHidden()
    
    # Mock text and lines per page to have 3 pages
    widget._lines_per_page = MagicMock(return_value=4)
    widget._prepare_render_text = MagicMock(return_value=("Line 1\nLine 2\nLine 3\nLine 4\nLine 5\nLine 6\nLine 7\nLine 8\nLine 9", None, None, None))
    
    # Trigger refresh
    widget._refresh_page_bar()
    
    assert widget._page_count == 3
    assert not widget.page_bar.isHidden()
    assert len(widget.indicator_buttons) == 3
    
    # Active index is 0, so first button is checked, others not
    assert widget.indicator_buttons[0].isChecked() is True
    assert widget.indicator_buttons[1].isChecked() is False
    assert widget.indicator_buttons[2].isChecked() is False
    
    # Prev button should be disabled, Next button enabled
    assert widget.btn_page_prev.isEnabled() is False
    assert widget.btn_page_next.isEnabled() is True
    
    # Position check: geometry should stretch full height on the right
    widget._position_page_bar()
    assert widget.page_bar.geometry() == QRect(400 - 38, 0, 38, 300)
    
    # Test jump to page 1 via clicking indicator button
    widget.indicator_buttons[1].click()
    assert widget._preview_page == 1
    assert widget.indicator_buttons[0].isChecked() is False
    assert widget.indicator_buttons[1].isChecked() is True
    assert widget.indicator_buttons[2].isChecked() is False
    
    # Now both buttons should be enabled
    assert widget.btn_page_prev.isEnabled() is True
    assert widget.btn_page_next.isEnabled() is True
    
    # Click next button to go to page 2
    widget.btn_page_next.click()
    assert widget._preview_page == 2
    assert widget.indicator_buttons[0].isChecked() is False
    assert widget.indicator_buttons[1].isChecked() is False
    assert widget.indicator_buttons[2].isChecked() is True
    
    # Now next should be disabled, prev enabled
    assert widget.btn_page_prev.isEnabled() is True
    assert widget.btn_page_next.isEnabled() is False
    
    # Test single page hides bar
    widget._prepare_render_text = MagicMock(return_value=("Single line text", None, None, None))
    widget._refresh_page_bar()
    assert widget._page_count == 1
    assert widget.page_bar.isHidden()









