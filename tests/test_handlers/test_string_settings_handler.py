import pytest
from unittest.mock import MagicMock, patch
from handlers.string_settings_handler import StringSettingsHandler

@pytest.fixture
def handler(mock_mw):
    mock_mw.current_block_idx = 0
    mock_mw.current_string_idx = 0
    mock_mw.string_metadata = {}
    mock_mw.line_width_warning_threshold_pixels = 200
    mock_mw.font_combobox = MagicMock()
    mock_mw.width_spinbox = MagicMock()
    mock_mw.apply_width_button = MagicMock()
    mock_mw.ui_updater = MagicMock()
    p = mock_mw.project_manager.project
    p.blocks = [MagicMock()]
    return StringSettingsHandler(mock_mw, MagicMock(), mock_mw.ui_updater)

def test_StringSettingsHandler_init(handler, mock_mw):
    assert handler.mw == mock_mw

def test_StringSettingsHandler_on_font_changed(handler):
    handler.mw.font_combobox.itemData.return_value = "CustomFont"
    handler.on_font_changed(1)
    handler.mw.apply_width_button.setEnabled.assert_called_with(True)

def test_StringSettingsHandler_on_width_changed(handler):
    handler.mw.string_metadata[(0, 0)] = {"width": 100}
    handler.on_width_changed(150)
    handler.mw.apply_width_button.setEnabled.assert_called_with(True)

def test_StringSettingsHandler_apply_settings_change(handler):
    handler.mw.font_combobox.currentData.return_value = "NewFont"
    handler.mw.width_spinbox.value.return_value = 120
    with patch.object(handler, '_apply_and_rescan'):
        handler.apply_settings_change()
    assert handler.mw.string_metadata[(0, 0)]["font_file"] == "NewFont"

def test_StringSettingsHandler_apply_font_to_range(handler):
    handler.mw.string_metadata = {}
    with patch.object(handler, '_apply_and_rescan'):
        handler.apply_font_to_range(0, 1, "RangeFont")
        assert handler.mw.string_metadata[(0, 0)]["font_file"] == "RangeFont"
        assert handler.mw.string_metadata[(0, 1)]["font_file"] == "RangeFont"

def test_StringSettingsHandler_apply_font_to_lines(handler):
    handler.mw.string_metadata = {}
    with patch.object(handler, '_apply_and_rescan'):
        handler.apply_font_to_lines([0, 2], "LineFont")
        assert handler.mw.string_metadata[(0, 0)]["font_file"] == "LineFont"
        assert handler.mw.string_metadata[(0, 2)]["font_file"] == "LineFont"

def test_StringSettingsHandler_apply_width_to_range(handler):
    handler.mw.string_metadata = {}
    with patch.object(handler, '_apply_and_rescan'):
        handler.apply_width_to_range(0, 1, 150)
        assert handler.mw.string_metadata[(0, 0)]["width"] == 150
        assert handler.mw.string_metadata[(0, 1)]["width"] == 150

def test_StringSettingsHandler_apply_width_to_lines(handler):
    handler.mw.string_metadata = {}
    with patch.object(handler, '_apply_and_rescan'):
        handler.apply_width_to_lines([0, 3], 180) # Use 180 instead of 200 (default)
        assert handler.mw.string_metadata[(0, 0)]["width"] == 180
        assert handler.mw.string_metadata[(0, 3)]["width"] == 180

def test_StringSettingsHandler_apply_and_rescan(handler):
    handler.mw.issue_scan_handler = MagicMock()
    handler._apply_and_rescan()
    handler.mw.ui_updater.populate_blocks.assert_called()

def test_StringSettingsHandler_delete_font_if_default(handler):
    handler.mw.string_metadata[(0, 0)] = {"font_file": "old"}
    with patch.object(handler, '_apply_and_rescan'):
        handler.apply_font_to_lines([0], "default")
    assert "font_file" not in handler.mw.string_metadata.get((0,0), {})

def test_StringSettingsHandler_delete_width_if_default(handler):
    handler.mw.string_metadata[(0, 0)] = {"width": 123}
    with patch.object(handler, '_apply_and_rescan'):
        handler.apply_width_to_lines([0], 200) # 200 is threshold (default)
    assert "width" not in handler.mw.string_metadata.get((0,0), {})
