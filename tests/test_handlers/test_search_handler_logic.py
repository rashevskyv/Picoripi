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
    # Search for "Southern" in "Warp to [Red]Southern Fairy Island" (ignore_tags=True)
    result = search_handler.find_next("Southern", case_sensitive=False, search_in_original=True, ignore_tags=True)
    assert result is True
    assert search_handler.last_found_block == 0
    assert search_handler.last_found_string == 0


def test_search_with_zelda_plus_exact(search_handler, mock_mw):
    # Mock text with Zelda-style + separator
    mock_mw.data_store.data = [["[Red]Острова+Тінгла"]]

    result = search_handler.find_next("Острова", case_sensitive=False, search_in_original=True, ignore_tags=True)
    assert result is True

    # Search for "Острова Тінгла" — now PASSES because prepare_text_for_tagless_search handles +
    result = search_handler.find_next("Острова Тінгла", case_sensitive=False, search_in_original=True, ignore_tags=True)
    assert result is True


def test_search_fuzzy_with_zelda_plus(search_handler, mock_mw):
    mock_mw.data_store.data = [["[Red]Острова+Тінгла"]]

    result = search_handler.find_next("Острова", case_sensitive=False, search_in_original=True, ignore_tags=True, is_fuzzy=True)
    assert result is True


# --- Unit tests for _find_in_text tuple return ---

def test_find_in_text_exact_returns_correct_length(search_handler):
    pos, length = search_handler._find_in_text("Hello World", "World", 0, False)
    assert pos == 6
    assert length == 5  # length of "World"


def test_find_in_text_exact_not_found(search_handler):
    pos, length = search_handler._find_in_text("Hello World", "XYZ", 0, False)
    assert pos == -1
    assert length == 0


def test_find_in_text_fuzzy_returns_matched_word_length(search_handler):
    # Searching "острів" in text containing "монстрів" — fuzzy should match "монстрів"
    pos, length = search_handler._find_in_text("Тут монстрів багато", "острів", 0, False, is_fuzzy=True)
    # монстрів starts at index 4
    assert pos == 4
    assert length == 8  # len("монстрів") — NOT len("острів")==6

def test_find_in_text_fuzzy_returns_actual_word_not_query_length(search_handler):
    # Exact form: "острова" found when searching "острів"
    pos, length = search_handler._find_in_text("Бачу острова вдалині", "острів", 0, False, is_fuzzy=True)
    assert pos == 5  # "Бачу " = 5 chars
    assert length == 7  # len("острова") — NOT len("острів")==6
