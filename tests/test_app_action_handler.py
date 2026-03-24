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
        self.data = [["string_default"]]
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
        # Use ctx as the main_window (where test data is stored via data_store=self)
        self.handler = AppActionHandler(
            self.ctx,
            self.ctx.data_processor, 
            self.ctx.ui_updater, 
            self.ctx.current_game_rules
        )

    @patch('handlers.app_action_handler.load_json_file')
    @patch('handlers.app_action_handler.QFileDialog.getOpenFileName')
    @patch('handlers.app_action_handler.QMessageBox.question')
    def test_open_file_dialog_basic(self, mock_question, mock_get_open, mock_load):
        mock_load.return_value = ({}, None)
        mock_get_open.return_value = ("test.json", "Supported Files")
        self.ctx.data_store.unsaved_changes = False
        
        self.handler.open_file_dialog_action()
        
        mock_get_open.assert_called_once()
        self.assertEqual(self.handler.mw.json_path, "test.json")

    @patch('handlers.app_action_handler.QFileDialog.getSaveFileName')
    @patch('handlers.app_action_handler.QMessageBox.information')
    def test_save_as_dialog(self, mock_info, mock_get_save):
        mock_get_save.return_value = ("new_save.json", "Supported Files")
        self.handler.save_data_action = MagicMock(return_value=True)
        
        self.handler.save_as_dialog_action()
        
        mock_get_save.assert_called_once()
        self.assertEqual(self.handler.mw.data_store.edited_json_path, "new_save.json")
        self.handler.save_data_action.assert_called_once()

    @patch('handlers.app_action_handler.QProgressDialog')
    @patch('handlers.app_action_handler.WidthCalculationWorker')
    def test_calculate_widths_progress(self, mock_worker_cls, mock_progress):
        # Data stored on ctx (ctx IS self.handler.mw)
        self.ctx.data_store.data = [["line1", "line2"]]
        self.ctx.data_store.block_names = {"0": "TestBlock"}
        self.ctx.font_map = {"a": {"width": 5}}
        self.ctx.string_metadata = {}
        self.ctx.line_width_warning_threshold_pixels = 200
        self.ctx.game_dialog_max_width_pixels = 240
        self.ctx.helper = MagicMock()
        self.ctx.helper.get_font_map_for_string.return_value = {"a": {"width": 5}}
        self.ctx.current_game_rules.get_problem_definitions.return_value = {}
        
        # Mock progress dialog instance
        mock_pd_inst = mock_progress.return_value
        mock_pd_inst.wasCanceled.return_value = False
        mock_pd_inst.exec_.return_value = None  # Don't block

        # Mock worker: don't actually run the thread
        mock_worker_inst = mock_worker_cls.return_value
        mock_worker_inst.isRunning.return_value = False
        
        self.handler.calculate_widths_for_block_action(0)
        
        # Verify progress dialog was created
        mock_progress.assert_called_once()
        # Verify worker was created and started
        mock_worker_cls.assert_called_once()
        mock_worker_inst.start.assert_called_once()

if __name__ == '__main__':
    unittest.main()
