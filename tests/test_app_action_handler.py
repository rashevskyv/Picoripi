import unittest
from unittest.mock import MagicMock, patch
from pathlib import Path
from handlers.app_action_handler import AppActionHandler

class MockUIProvider:
    def __init__(self):
        self.data_store = self
        self.block_list_widget = MagicMock()
...
class MockContext(MagicMock):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.data_store = self
        self.state = MagicMock()
        self.state.enter.return_value.__enter__ = lambda x: None
        self.state.enter.return_value.__exit__ = lambda x, y, z, w: None
        self.json_path = "orig.json"
        self.edited_json_path = None
        self.unsaved_changes = False
        self.data = [[]]
        self.block_names = {}
        self.edited_data = {}
        self.edited_file_data = []
        self.string_metadata = {}
        self.line_width_warning_threshold_pixels = 200
        self.game_dialog_max_width_pixels = 240
        self.font_map = {"dummy": "data"}
        self.helper = MagicMock()
        self.current_game_rules = MagicMock()
        self.current_game_rules.get_display_name.return_value = "Test Plugin"
        self.current_game_rules.load_data_from_json_obj.return_value = ([["string"]], {"0": "Block"})
        self.get_font_map_for_string = MagicMock(return_value={})
        self.helper.get_font_map_for_string = self.get_font_map_for_string
        self.undo_manager = MagicMock()
        self.data_processor = MagicMock()
        self.data_processor.get_current_string_text.return_value = ("some text", "source")
        self.data_processor._get_string_from_source.return_value = "orig text"
        self.ui_updater = MagicMock()
        self.block_list_widget = MagicMock()
        self.statusBar = MagicMock()
        self.unsaved_changes = False

class TestAppActionHandler(unittest.TestCase):
    def setUp(self):
        self.ctx = MockContext()
        # We need to mock MainWindow for BaseHandler init if it's still used there, 
        # but our goal was to use ctx.
        self.mw = MagicMock() 
        self.handler = AppActionHandler(
            self.mw, 
            self.ctx.data_processor, 
            self.ctx.ui_updater, 
            self.ctx.current_game_rules
        )
        self.handler.ctx = self.ctx
        self.handler.ui_updater = self.ctx.ui_updater
        self.handler.data_processor = self.ctx.data_processor

    @patch('handlers.app_action_handler.load_json_file')
    @patch('handlers.app_action_handler.QFileDialog.getOpenFileName')
    @patch('handlers.app_action_handler.QMessageBox.question')
    def test_open_file_dialog_basic(self, mock_question, mock_get_open, mock_load):
        mock_load.return_value = ({}, None)
        mock_get_open.return_value = ("test.json", "Supported Files")
        self.ctx.data_store.unsaved_changes = False
        
        self.handler.open_file_dialog_action()
        
        mock_get_open.assert_called_once()
        self.assertEqual(self.ctx.data_store.json_path, "test.json")

    @patch('handlers.app_action_handler.QFileDialog.getSaveFileName')
    @patch('handlers.app_action_handler.QMessageBox.information')
    def test_save_as_dialog(self, mock_info, mock_get_save):
        mock_get_save.return_value = ("new_save.json", "Supported Files")
        self.handler.save_data_action = MagicMock(return_value=True)
        
        self.handler.save_as_dialog_action()
        
        mock_get_save.assert_called_once()
        self.assertEqual(self.ctx.data_store.edited_json_path, "new_save.json")
        self.handler.save_data_action.assert_called_once()

    @patch('handlers.app_action_handler.QMessageBox')
    @patch('handlers.app_action_handler.QProgressDialog')
    @patch('handlers.app_action_handler.calculate_string_width', return_value=10)
    @patch('handlers.app_action_handler.remove_all_tags', side_effect=lambda x: x)
    def test_calculate_widths_progress(self, mock_remove, mock_calc, mock_progress, mock_qmsgbox):
        mock_warning = mock_qmsgbox.warning
        mock_info = mock_qmsgbox.information
        self.ctx.data_store.data = [[ "line1", "line2" ]]
        self.ctx.data_store.block_names = {"0": "TestBlock"}
        self.ctx.current_game_rules.get_problem_definitions.return_value = {}
        
        # Mock progress dialog instance
        mock_pd_inst = mock_progress.return_value
        mock_pd_inst.wasCanceled.return_value = False
        
        self.handler.calculate_widths_for_block_action(0)
        
        mock_progress.assert_called_once()
        # update_progress_value is not used in modern version, it's progress.setValue
        self.assertGreaterEqual(mock_pd_inst.setValue.call_count, 2)

if __name__ == '__main__':
    unittest.main()
