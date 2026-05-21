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
