import pytest
from unittest.mock import MagicMock
from handlers.issue_scan_handler import IssueScanHandler

class MockContext:
    def __init__(self):
        self.data_store = self
        self.data = [["Line 1", "Line 2"]]
        self.problems_per_subline = {}
        self.string_metadata = {}
        self.line_width_warning_threshold_pixels = 100
        self.current_game_rules = MagicMock()
        self.current_block_idx = 0
        self.ui_provider = MagicMock()
        self.helper = MagicMock()
        self.helper.get_font_map_for_string = self.get_font_map_for_string
        
    def get_font_map_for_string(self, b, s):
        return {}

def test_issue_scan_basic_isolation():
    ctx = MockContext()
    data_processor = MagicMock()
    # String 0 has text, String 1 has None
    data_processor.get_current_string_text.side_effect = [("Text 1", None), (None, None)]
    ui_updater = MagicMock()
    
    handler = IssueScanHandler(ctx, data_processor, ui_updater)
    
    # Mock analyzer
    analyzer = MagicMock()
    ctx.current_game_rules.problem_analyzer = analyzer
    # Mock analyzer to return a problem for the first string and nothing for the second
    analyzer.analyze_data_string.side_effect = [[{"Width"}], []]
    
    # Pre-fill with some old garbage
    ctx.data_store.problems_per_subline[(0, 0, 0)] = {"OldError"}
    ctx.data_store.problems_per_subline[(0, 1, 0)] = {"OldError"}
    
    handler._perform_issues_scan_for_block(0)
    
    # Check if old problems were cleared and new ones recorded
    assert (0, 0, 0) in ctx.data_store.problems_per_subline
    assert ctx.data_store.problems_per_subline[(0, 0, 0)] == {"Width"} # Replaced OldError
    assert (0, 1, 0) not in ctx.data_store.problems_per_subline # Cleared and not re-added because text was None
