import unittest
from unittest.mock import MagicMock, patch

from handlers.search_handler import SearchHandler

class MockUIProvider:

    def __init__(self):
        self.preview_text_edit = MagicMock()
        self.original_text_edit = MagicMock()
        self.edited_text_edit = MagicMock()
        self.preview_text_edit.objectName.return_value = "preview_text_edit"
        self.original_text_edit.objectName.return_value = "original_text_edit"
        self.edited_text_edit.objectName.return_value = "edited_text_edit"
        
    def set_search_status(self, message, is_error=False): pass
    def clear_search_highlights(self): pass
    def add_search_highlight(self, editor_type, qblock_idx, start, length): pass
    def navigate_to_block(self, block_idx): pass
    def scroll_to_cursor(self, editor_type, qblock_idx, pos_in_block): pass

class MockContext(MagicMock):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.data = [["Hello world", "Test string"], ["Second block"]]
        self.current_block_idx = 0
        self.current_string_idx = 0
        self.search_match_block_indices = set()
        self.ui_provider = MockUIProvider()
        self.preview_text_edit = self.ui_provider.preview_text_edit
        self.original_text_edit = self.ui_provider.original_text_edit
        self.edited_text_edit = self.ui_provider.edited_text_edit
        self.list_selection_handler = MagicMock()
        self.show_multiple_spaces_as_dots = False
        self.newline_display_symbol = ""
        self.helper = MagicMock()

class TestSearchHandler(unittest.TestCase):
    def setUp(self):
        self.patcher_cursor = patch('handlers.search_handler.QTextCursor')
        self.patcher_cursor.start()
        
        self.patcher_tree_iter = patch('PyQt5.QtWidgets.QTreeWidgetItemIterator')
        mock_tree_iter_cls = self.patcher_tree_iter.start()
        mock_tree_iter_cls.return_value.value.return_value = None

        self.ctx = MockContext()
        self.data_processor = MagicMock()
        self.data_processor.get_current_string_text.side_effect = lambda b, s: (self.ctx.data[b][s], None)
        self.ui_updater = MagicMock()
        self.handler = SearchHandler(self.ctx, self.data_processor, self.ui_updater)

    def tearDown(self):
        self.patcher_cursor.stop()
        self.patcher_tree_iter.stop()


    def test_search_basic(self):
        # Test find next
        found = self.handler.find_next("world", False, True, False)
        self.assertTrue(found)
        self.assertEqual(self.handler.last_found_block, 0)
        self.assertEqual(self.handler.last_found_string, 0)
        self.assertEqual(self.handler.last_found_char_pos_raw, 6)
    
        # Test find next again (should be next string)
        found = self.handler.find_next("string", False, True, False)
        self.assertTrue(found)
        self.assertEqual(self.handler.last_found_block, 0)
        self.assertEqual(self.handler.last_found_string, 1)
        self.assertEqual(self.handler.last_found_char_pos_raw, 5)

    def test_search_reset(self):
        self.handler.find_next("world", False, True, False)
        self.assertNotEqual(self.handler.last_found_block, -1)
    
        self.handler.reset_search()
        self.assertEqual(self.handler.last_found_block, -1)
        self.assertEqual(self.handler.current_query, "")

    def test_search_previous(self):
        # Find something at the end first
        self.handler.find_next("block", False, True, False)
        self.assertEqual(self.handler.last_found_block, 1)
        
        # Find previous "world"
        found = self.handler.find_previous("world", False, True, False)
        self.assertTrue(found)
        self.assertEqual(self.handler.last_found_block, 0)
        self.assertEqual(self.handler.last_found_string, 0)

if __name__ == "__main__":
    unittest.main()
