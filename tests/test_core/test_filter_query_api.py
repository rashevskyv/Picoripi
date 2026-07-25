import pytest
from unittest.mock import MagicMock
from core.filter_query_api import FilterQueryAPI

class FakeDataStore:
    def __init__(self):
        self.data = [["line0", "line1", "line2", "", "", "", "line6"]]
        self.unsaved_block_indices = set()
        self.edited_data = {}
        self._index_empty = {}
        self._index_translated = {}
        self._index_unsaved = {}
        self._index_overrides = {}
        self._index_categorized = {}
        self._index_warnings = {}
        self.problems_per_subline = {}
        self.chapter_mappings = []
        self.virtual_mappings = []
        self.show_overrides_only = False
        self.hide_translated = False
        self.hide_categorized = False
        self.hide_empty_strings = False
        self.show_unsaved_only = False
        self.show_warnings_only = False
        self.active_warning_filters = []

class FakeMainWindow:
    def __init__(self):
        self.data_store = FakeDataStore()
        self.data_processor = MagicMock()
        self.project_manager = MagicMock()
        self.current_game_rules = MagicMock()

@pytest.fixture
def mock_mw():
    return FakeMainWindow()

def test_get_filtered_string_indices_basic(mock_mw):
    api = FilterQueryAPI(mock_mw)
    indices, placeholders = api.get_filtered_string_indices(0)
    assert indices == [0, 1, 2, 3, 4, 5, 6]
    assert placeholders == {}

def test_get_filtered_string_indices_hide_translated(mock_mw):
    api = FilterQueryAPI(mock_mw)
    mock_mw.data_processor.get_translated_set.return_value = {0, 2}
    
    indices, placeholders = api.get_filtered_string_indices(0, hide_translated=True)
    assert indices == [1, 3, 4, 5, 6]

def test_get_filtered_string_indices_show_overrides_only(mock_mw):
    api = FilterQueryAPI(mock_mw)
    mock_mw.data_processor.get_overrides_set.return_value = {1, 6}
    
    indices, placeholders = api.get_filtered_string_indices(0, show_overrides_only=True)
    assert indices == [1, 6]

def test_get_filtered_string_indices_show_unsaved_only(mock_mw):
    api = FilterQueryAPI(mock_mw)
    mock_mw.data_processor.get_unsaved_set.return_value = {2}
    
    indices, placeholders = api.get_filtered_string_indices(0, show_unsaved_only=True)
    assert indices == [2]

def test_get_filtered_string_indices_hide_empty_strings(mock_mw):
    api = FilterQueryAPI(mock_mw)
    # Mark indices 3, 4, 5 as empty
    mock_mw.data_processor.get_empty_set.return_value = {3, 4, 5}
    
    indices, placeholders = api.get_filtered_string_indices(0, hide_empty_strings=True)
    # Three or fewer empty rows remain fully visible.
    assert indices == [0, 1, 2, 3, 4, 5, 6]
    assert placeholders == {}


def test_hide_empty_strings_keeps_edges_and_collapses_only_middle(mock_mw):
    api = FilterQueryAPI(mock_mw)
    mock_mw.data_processor.get_empty_set.return_value = {2, 3, 4, 5}

    indices, placeholders = api.get_filtered_string_indices(
        0, hide_empty_strings=True
    )

    assert indices == [0, 1, 2, -1, 5, 6]
    assert placeholders == {3: "[3-4] 2 empty line(s)"}

def test_get_aggregated_problems_for_block(mock_mw):
    api = FilterQueryAPI(mock_mw)
    problem_defs = {"warning_tag": {"severity": "warning"}, "error_width": {"severity": "error"}}
    mock_mw.current_game_rules.get_problem_definitions.return_value = problem_defs
    
    # Mock warnings index
    mock_mw.data_store._index_warnings = {
        0: {
            "warning_tag": {(1, 0)},
            "error_width": {(2, 0), (6, 0)}
        }
    }
    
    counts = api.get_aggregated_problems_for_block(0, detection_config={"warning_tag": True, "error_width": True})
    assert counts == {"warning_tag": 1, "error_width": 2}

def test_is_project_block_unsaved(mock_mw):
    api = FilterQueryAPI(mock_mw)
    mock_mw.data_store.unsaved_block_indices = {0}
    
    assert api.is_project_block_unsaved(0) is True
    assert api.is_project_block_unsaved(1) is False

def test_get_filtered_string_indices_speaker_hide_translated(mock_mw):
    api = FilterQueryAPI(mock_mw)
    mock_mw.data_store.virtual_mappings = [(0, 0), (0, 1), (0, 2)]
    mock_mw.data_processor.get_translated_set.return_value = {0, 2}
    
    indices, placeholders = api.get_filtered_string_indices(-3, hide_translated=True, virtual_mappings=[(0, 0), (0, 1), (0, 2)])
    assert indices == [(0, 1)]

def test_get_filtered_string_indices_speaker_hide_empty(mock_mw):
    api = FilterQueryAPI(mock_mw)
    mappings = [(0, index) for index in range(7)]
    mock_mw.data_store.virtual_mappings = mappings
    mock_mw.data_processor.get_empty_set.side_effect = lambda b: {1, 2, 3, 4, 5}

    indices, placeholders = api.get_filtered_string_indices(
        -3, hide_empty_strings=True, virtual_mappings=mappings
    )
    assert indices == [(0, 0), (0, 1), -1, (0, 5), (0, 6)]
    assert placeholders[2] == "[2-4] 3 empty line(s)"

def test_get_filtered_string_indices_speaker_show_warnings_only(mock_mw):
    api = FilterQueryAPI(mock_mw)
    mock_mw.data_store.virtual_mappings = [(0, 0), (0, 1), (0, 2)]
    mock_mw.data_processor.get_warnings_matching_set.return_value = {1}
    
    indices, placeholders = api.get_filtered_string_indices(-3, show_warnings_only=True, virtual_mappings=[(0, 0), (0, 1), (0, 2)])
    assert indices == [(0, 1)]
