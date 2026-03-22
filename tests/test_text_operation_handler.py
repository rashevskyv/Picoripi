import unittest
from unittest.mock import MagicMock, patch
from handlers.text_operation_handler import TextOperationHandler

class MockUIProvider:
    def __init__(self):
        self._programmatically_changing = False
        self._texts = {"edited_text_edit": "Initial text"}
        self._cursor_pos = 0
        
    def is_programmatically_changing(self): return self._programmatically_changing
    def set_programmatically_changing(self, v): self._programmatically_changing = v
    def get_editor_text(self, etype): return self._texts.get(etype, "")
    def set_editor_text(self, etype, text, preserve_undo=True): self._texts[etype] = text
    def update_editor_linenumber_area(self, etype): pass
    def set_search_status(self, msg): pass
    def show_message(self, t, m, i="info"): pass

class MockContext(MagicMock):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.current_block_idx = 0
        self.current_string_idx = 0
        self.data = [["Original line 1"]]
        self.edited_data = {}
        self.edited_file_data = [["Original line 1"]]
        self.edited_sublines = set()
        self.problems_per_subline = {}
        self.string_metadata = {}
        self.line_width_warning_threshold_pixels = 300
        self.ui_provider = MockUIProvider()
        self.ui_updater = MagicMock()
        self.current_game_rules = MagicMock()
        self.current_game_rules.convert_editor_text_to_data.side_effect = lambda x: x
        self.current_game_rules.get_text_representation_for_preview.side_effect = lambda x: f"PREVIEW: {x}"
        self.newline_display_symbol = "↵"
        self.show_multiple_spaces_as_dots = False
        self.is_programmatically_changing_text = False
        self.edited_text_edit = MagicMock()
        self.helper = MagicMock()

    def update_title(self): pass
    def get_font_map_for_string(self, b, s): return {}

def test_text_edited_basic():
    ctx = MockContext()
    data_processor = MagicMock()
    # Mock data_processor._get_string_from_source to return original
    data_processor._get_string_from_source.return_value = "Original line 1"
    
    ui_updater = MagicMock()
    handler = TextOperationHandler(ctx, data_processor, ui_updater)
    
    # Simulate editing text
    ctx.edited_text_edit.toPlainText.return_value = "Changed line 1"
    
    handler.text_edited()
    
    # Verify edited_sublines contains index 0
    assert 0 in ctx.edited_sublines
    # Verify data_processor.update_edited_data was called
    data_processor.update_edited_data.assert_called()

def test_revert_line():
    ctx = MockContext()
    data_processor = MagicMock()
    data_processor._get_string_from_source.return_value = "Original line 1"
    data_processor.get_current_string_text.return_value = ("Changed line 1", "edited")
    
    ui_updater = MagicMock()
    handler = TextOperationHandler(ctx, data_processor, ui_updater)
    
    handler.revert_single_line(0)
    
    # Verify update_edited_data called with original text
    data_processor.update_edited_data.assert_called_with(0, 0, "Original line 1", action_type="REVERT")

if __name__ == "__main__":
    test_text_edited_basic()
    test_revert_line()
    print("TextOperationHandler tests passed!")
