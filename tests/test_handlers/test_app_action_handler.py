import pytest
from unittest.mock import MagicMock, patch
from pathlib import Path
from handlers.app_action_handler import AppActionHandler

@pytest.fixture
def mock_mw():
    mw = MagicMock()
    mw.state.enter.return_value.__enter__.return_value = MagicMock()
    mw.current_game_rules = MagicMock()
    mw.data = []
    mw.block_names = {}
    return mw

@pytest.fixture
def mock_ui():
    return MagicMock()

def test_AppActionHandler_load_all_data_success(mock_mw, mock_ui):
    handler = AppActionHandler(mock_mw, MagicMock(), mock_ui, mock_mw.current_game_rules)
    
    with patch("handlers.app_action_handler.load_json_file") as mock_load, \
         patch("handlers.app_action_handler.QMessageBox") as mock_msg:
        mock_load.return_value = ({"key": "value"}, None)
        mock_mw.current_game_rules.load_data_from_json_obj.return_value = ([["string1"]], {"0": "Block1"})
        
        with patch("handlers.app_action_handler.Path.exists") as mock_exists:
            mock_exists.return_value = False
            
            handler.load_all_data_for_path("dummy.json")
            
            assert mock_mw.json_path == "dummy.json"
            assert len(mock_mw.data) == 1
            mock_ui.populate_blocks.assert_called()

def test_AppActionHandler_load_all_data_error(mock_mw, mock_ui):
    handler = AppActionHandler(mock_mw, MagicMock(), mock_ui, mock_mw.current_game_rules)
    
    with patch("handlers.app_action_handler.load_json_file") as mock_load, \
         patch("handlers.app_action_handler.QMessageBox") as mock_msg:
        mock_load.return_value = (None, "File not found")
        
        handler.load_all_data_for_path("missing.json")
        
        assert mock_mw.json_path is None
        mock_ui.update_title.assert_called()
        mock_msg.critical.assert_called()
