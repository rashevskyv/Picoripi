import pytest
from unittest.mock import MagicMock, patch
from handlers.string_settings_handler import StringSettingsHandler

@pytest.fixture
def handler(mock_mw):
    mock_mw.current_block_idx = 0
    mock_mw.current_string_idx = 0
    mock_mw.string_metadata = {}
    mock_mw.line_width_warning_threshold_pixels = 200
    mock_mw.game_dialog_max_width_pixels = 200
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
        handler.apply_width_to_lines([0, 3], 180) 
        assert handler.mw.string_metadata[(0, 0)]["width"] == 180
        assert handler.mw.string_metadata[(0, 3)]["width"] == 180

def test_StringSettingsHandler_apply_and_rescan(handler):
    handler.mw.issue_scan_handler = MagicMock()
    handler._apply_and_rescan()
    handler.mw.ui_updater.update_block_item_text_with_problem_count.assert_called()
    handler.mw.ui_updater.update_text_views.assert_called()

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

def test_StringSettingsHandler_uses_per_string_plugin_default(handler):
    class KindRules:
        def get_string_layout(self, _block_idx, string_idx):
            return {"warn_width": 260, "max_width": 280} if string_idx == 0 else {
                "warn_width": 230, "max_width": 250
            }

    handler.mw.current_game_rules = KindRules()
    handler.mw.string_metadata[(0, 0)] = {"width": 123}
    handler.mw.string_metadata[(0, 1)] = {"width": 456}

    with patch.object(handler, '_apply_and_rescan'):
        handler.apply_width_to_lines([0], 280)
        handler.apply_width_to_lines([1], 250)

    assert "width" not in handler.mw.string_metadata.get((0, 0), {})
    assert "width" not in handler.mw.string_metadata.get((0, 1), {})

def test_StringSettingsHandler_global_width_is_custom_for_other_window_kind(handler):
    class ItemRules:
        def get_string_layout(self, _block_idx, _string_idx):
            return {"warn_width": 230, "max_width": 250}

    handler.mw.current_game_rules = ItemRules()

    with patch.object(handler, '_apply_and_rescan'):
        handler.apply_width_to_lines([0], 200)

    assert handler.mw.string_metadata[(0, 0)]["width"] == 200

def test_StringSettingsHandler_apply_auto_width_from_original_to_lines(handler):
    handler.mw.string_metadata = {}
    handler.data_processor._get_string_from_source.return_value = "Line1\nLongerLine2"
    handler.mw.helper.get_font_map_for_string.return_value = {}
    handler.mw.icon_sequences = []
    handler.mw.default_tag_mappings = {}
    
    with patch('handlers.string_settings_handler.calculate_string_width', side_effect=lambda text, *args, **kwargs: len(text) * 10), \
         patch.object(handler, '_apply_and_rescan'):
        handler.apply_auto_width_from_original_to_lines([0])
        
        # "Line1" length 5 * 10 = 50
        # "LongerLine2" length 11 * 10 = 110
        assert handler.mw.string_metadata[(0, 0)]["width"] == 110
