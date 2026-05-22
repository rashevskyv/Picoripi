import pytest
from unittest.mock import MagicMock, patch
from PyQt5.QtWidgets import QApplication, QMenu, QFileDialog, QInputDialog
from PyQt5.QtCore import QPoint, Qt, QRect
from PyQt5.QtGui import QMouseEvent
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
    from PyQt5.QtGui import QImage
    
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
    
    img = QImage(128, 128, QImage.Format_ARGB32)
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
    render_img = QImage(300, 130, QImage.Format_ARGB32)
    render_img.fill(0)
    
    # Ensure no exception is raised
    widget.render(render_img)


def test_bfn_preview_widget_drag_and_drop(qapp):
    mw_mock = MagicMock()
    widget = BfnPreviewWidget(mw_mock)
    widget.setGeometry(0, 0, 500, 300)
    widget.text_rect = QRect(10, 10, 100, 100)
    
    # Mouse press inside
    press_event = QMouseEvent(QMouseEvent.MouseButtonPress, QPoint(20, 20), Qt.LeftButton, Qt.LeftButton, Qt.NoModifier)
    widget.mousePressEvent(press_event)
    assert widget.drag_active is True
    assert widget.drag_start_pos == QPoint(20, 20)
    
    # Mouse move to drag
    widget.mouseMoveEvent(QMouseEvent(QMouseEvent.MouseMove, QPoint(40, 50), Qt.NoButton, Qt.NoButton, Qt.NoModifier))
    
    # self.text_rect should move by dx=20, dy=30
    assert widget.text_rect == QRect(30, 40, 100, 100)
    
    # Mouse release
    release_event = QMouseEvent(QMouseEvent.MouseButtonRelease, QPoint(40, 50), Qt.LeftButton, Qt.LeftButton, Qt.NoModifier)
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
    press_event = QMouseEvent(QMouseEvent.MouseButtonPress, QPoint(110, 110), Qt.LeftButton, Qt.LeftButton, Qt.NoModifier)
    widget.mousePressEvent(press_event)
    assert widget.resize_active is True
    assert widget.resize_handle == 'bottom-right'
    
    # Drag to (130, 140) -> dx = 20, dy = 30
    widget.mouseMoveEvent(QMouseEvent(QMouseEvent.MouseMove, QPoint(130, 140), Qt.NoButton, Qt.NoButton, Qt.NoModifier))
    # bottom right moves: x2 becomes 110 + 20 = 130, y2 becomes 110 + 30 = 140
    # QRect(QPoint(10, 10), QPoint(130, 140)) -> width = 130 - 10 + 1 = 121, height = 140 - 10 + 1 = 131
    assert widget.text_rect.width() == 121
    assert widget.text_rect.height() == 131
    
    # Release
    widget.mouseReleaseEvent(QMouseEvent(QMouseEvent.MouseButtonRelease, QPoint(130, 140), Qt.LeftButton, Qt.LeftButton, Qt.NoModifier))
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
         patch.object(QMenu, 'exec_') as mock_exec, \
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

