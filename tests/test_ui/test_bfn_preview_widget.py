import pytest
from unittest.mock import MagicMock
from PyQt5.QtWidgets import QApplication
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

