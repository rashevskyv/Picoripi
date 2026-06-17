import pytest
from unittest.mock import MagicMock, patch
from plugins.common.problem_analyzer import GenericProblemAnalyzer
from handlers.list_selection_handler import ListSelectionHandler
from handlers.text_operation_handler import TextOperationHandler
from core.data_state_processor import DataStateProcessor
from core.glossary_manager import GlossaryManager, GlossaryEntry

class MockMainWindow:
    def __init__(self):
        self.data_store = self
        self.data = [["Original text with [Link] and [Epona]", "Another [Tag] text"]]
        self.edited_file_data = [["Original text with [Link] and [Epona]", "Another [Tag] text"]]
        self.edited_data = {}
        self.edited_sublines = set()
        self.current_block_idx = 0
        self.current_string_idx = 0
        self.block_names = {"0": "Test Block"}
        self.problems_per_subline = {}
        self.string_metadata = {}
        self.line_width_warning_threshold_pixels = 280
        self.game_dialog_max_width_pixels = 300
        self.project_manager = MagicMock()
        self.project_manager.project = MagicMock()
        self.project_manager.project.blocks = [MagicMock()]
        self.block_to_project_file_map = {0: 0}
        self.ui_updater = MagicMock()
        self.undo_manager = MagicMock()
        self.is_programmatically_changing_text = False
        self.current_game_rules = MagicMock()
        self.helper = MagicMock()
        
        self.current_game_rules.convert_editor_text_to_data = lambda x: x
        self.current_game_rules.get_text_representation_for_editor = lambda x: x
        self.current_game_rules.get_problem_definitions = lambda: {}
        
        self.edited_text_edit = MagicMock()
        self.original_text_edit = MagicMock()
        self.preview_text_edit = MagicMock()
        self.spellchecker_manager = MagicMock()
        self.warnings_enabled = True
        self.glossary_enabled = True

@pytest.fixture
def main_window():
    return MockMainWindow()

def test_check_tags_mismatch_basic(main_window):
    analyzer = GenericProblemAnalyzer(main_window, MagicMock(), {}, MagicMock())
    
    # 1. No tags in both - no mismatch
    assert analyzer.check_tags_mismatch("Hello", "Hello") is False
    assert analyzer.check_tags_mismatch("Hello", "Hi") is False
    
    # 2. Match tag count and names exactly
    assert analyzer.check_tags_mismatch("Hello {Color:Red} world [A]", "Hi {Color:Red} test [A]") is False
    
    # 3. Mismatch tag count
    assert analyzer.check_tags_mismatch("Hello {Color:Red} world [A]", "Hi {Color:Red} test") is True
    
    # 4. Mismatch tag content (different tags)
    assert analyzer.check_tags_mismatch("Hello {Color:Red}", "Hi {Color:Blue}") is True

def test_check_tags_mismatch_with_exceptions(main_window):
    analyzer = GenericProblemAnalyzer(main_window, MagicMock(), {}, MagicMock())
    
    # "Link" and "Epona" should be ignored (case insensitive)
    # Original has [Link] and [A], translation only has [A]
    # Since Link is exception, it shouldn't cause tag mismatch.
    assert analyzer.check_tags_mismatch("Hello [Link] and [A]", "Hi [A]") is False
    assert analyzer.check_tags_mismatch("Hello [link] and [A]", "Hi [A]") is False
    assert analyzer.check_tags_mismatch("Hello [EPONA] and {Color:Red}", "Hi {Color:Red}") is False
    
    # If other tags differ, it should still fail
    assert analyzer.check_tags_mismatch("Hello [Link] and [A]", "Hi [B]") is True
    
    # Exception inside curly brackets
    assert analyzer.check_tags_mismatch("Hello {Link} and [A]", "Hi [A]") is False

@patch('handlers.text_operation_handler.AsyncIssueScanner')
def test_immediate_async_scan_on_string_select(mock_async_scanner, main_window):
    dsp = DataStateProcessor(main_window)
    toh = TextOperationHandler(main_window, dsp, main_window.ui_updater)
    main_window.editor_operation_handler = toh
    lsh = ListSelectionHandler(main_window, dsp, main_window.ui_updater)
    
    main_window.current_game_rules.problem_analyzer = MagicMock()
    
    # Select a string
    lsh.string_selected_from_preview(0)
    
    # The scan should be launched immediately without debounce
    mock_async_scanner.assert_called_once()
    
    # Verify arguments of AsyncIssueScanner
    called_kwargs = mock_async_scanner.call_args[1]
    assert called_kwargs['block_idx'] == 0
    assert called_kwargs['string_idx'] == 0

def test_multiline_glossary_match_in_find_matches():
    # Setup GlossaryManager with an entry "Озеро Гілія"
    manager = GlossaryManager()
    
    # Load glossary with markdown
    raw_text = "| Original | Translation | Notes |\n|---|---|---|\n| Озеро Гілія | Hylia Lake | Test |\n"
    manager.load_from_text(plugin_name="test", glossary_path=None, raw_text=raw_text)
    
    # 1. Matches single-line
    matches_single = manager.find_matches("Тут є Озеро Гілія.")
    assert len(matches_single) == 1
    assert matches_single[0].entry.original == "Озеро Гілія"
    
    # 2. Matches multiline (separated by newline)
    matches_multi = manager.find_matches("Тут є Озеро\nГілія.")
    assert len(matches_multi) == 1, "Failed to match glossary term broken by a newline"
    assert matches_multi[0].entry.original == "Озеро Гілія"
