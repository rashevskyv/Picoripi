# tests/test_handlers/test_search_handler_logic.py
import pytest
from unittest.mock import MagicMock
from handlers.search_handler import SearchHandler
from core.data_store import AppDataStore

@pytest.fixture
def mock_mw():
    mw = MagicMock()
    mw.data_store = AppDataStore()
    mw.data_store.data = [["Warp to [Red]Southern Fairy Island"]] # block 0, string 0
    mw.data_store.edited_data = {}
    mw.data_store.current_block_idx = 0
    mw.data_store.current_string_idx = 0
    mw.search_match_block_indices = set()
    mw.show_multiple_spaces_as_dots = False
    mw.newline_display_symbol = "¶"
    return mw

@pytest.fixture
def mock_dsp(mock_mw):
    dsp = MagicMock()
    # Mock get_current_string_text to return original if edited is empty
    def get_text(b, s):
        if (b, s) in mock_mw.data_store.edited_data:
            return mock_mw.data_store.edited_data[(b, s)], "edited"
        return mock_mw.data_store.data[b][s], "original"
    dsp.get_current_string_text.side_effect = get_text
    return dsp

@pytest.fixture
def search_handler(mock_mw, mock_dsp):
    ui_updater = MagicMock()
    handler = SearchHandler(mock_mw, mock_dsp, ui_updater)
    return handler

def test_search_exact_match_no_tags(search_handler, mock_mw):
    # Search for "Southern" in "Warp to [Red]Southern Fairy Island"
    # ignore_tags=True
    result = search_handler.find_next("Southern", case_sensitive=False, search_in_original=True, ignore_tags=True)
    assert result is True
    assert search_handler.last_found_block == 0
    assert search_handler.last_found_string == 0

def test_search_with_zelda_plus_exact(search_handler, mock_mw):
    # Mock text with Zelda-style + separator
    mock_mw.data_store.data = [["[Red]Острова+Тінгла"]]
    
    # Search for "Острова"
    result = search_handler.find_next("Острова", case_sensitive=False, search_in_original=True, ignore_tags=True)
    assert result is True
    
    # Search for "Острова Тінгла" (with space)
    # This now PASSES because prepare_text_for_tagless_search handles +
    result = search_handler.find_next("Острова Тінгла", case_sensitive=False, search_in_original=True, ignore_tags=True)
    assert result is True

def test_search_fuzzy_with_zelda_plus(search_handler, mock_mw):
    mock_mw.data_store.data = [["[Red]Острова+Тінгла"]]
    
    # Fuzzy search for "Острова"
    result = search_handler.find_next("Острова", case_sensitive=False, search_in_original=True, ignore_tags=True, is_fuzzy=True)
    assert result is True
