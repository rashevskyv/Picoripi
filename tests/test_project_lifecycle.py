import os
import sys
import unittest
from unittest.mock import MagicMock, patch
from pathlib import Path
from PyQt5.QtWidgets import QApplication

# Initialize QApplication (needed once for the session)
if not QApplication.instance():
    app = QApplication(sys.argv)

# Add project root to sys.path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from core.project_manager import ProjectManager
from handlers.project_action_handler import ProjectActionHandler
from core.data_state_processor import DataStateProcessor
from ui.ui_updater import UIUpdater
from ui.main_window.main_window_plugin_handler import MainWindowPluginHandler

class MockMainWindow(MagicMock):

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.data_store = self
        from PyQt5.QtWidgets import QTreeWidget, QTextEdit, QLabel, QLineEdit
        self.is_loading_data = False
        self.data = []
        self.edited_file_data = []
        self.block_names = {}
        self.block_to_project_file_map = {}
        self.is_programmatically_changing_text = False
        def is_programmatically_changing(): return self.is_programmatically_changing_text
        self.is_programmatically_changing = is_programmatically_changing
        from PyQt5.QtWidgets import QTreeWidget, QTextEdit, QLabel, QLineEdit, QTreeWidgetItem
        
        def mock_create_item(text, data=None, role=None):
            from PyQt5.QtWidgets import QTreeWidgetItem
            from PyQt5.QtCore import Qt
            item = QTreeWidgetItem([str(text)])
            if data is not None and role is not None:
                item.setData(0, role, data)
            return item

        self.block_list_widget = QTreeWidget()
        self.block_list_widget.create_item = mock_create_item
        self.string_list_widget = QTreeWidget()
        self.string_list_widget.create_item = mock_create_item
        self.search_results_list = QTreeWidget()
        self.search_results_list.create_item = mock_create_item
        
        self.code_input = QTextEdit()

        self.translation_input = QTextEdit()
        self.original_text_display = QTextEdit()
        self.edited_text_edit = QTextEdit()
        self.preview_text_edit = QTextEdit()
        self.original_text_edit = QTextEdit()
        
        self.code_analysis_label = QLabel()
        self.translation_analysis_label = QLabel()
        self.warning_label = QLabel()
        self.search_input = QLineEdit()
        self.last_browse_dir = ""
        self.restore_unsaved_on_startup = False
        self.active_game_plugin = "zelda_mc"
        self._current_game_rules = None
        self.json_path = ""
        self.edited_json_path = ""
        self.unsaved_changes = False
        self.problems_per_subline = {}
        self.plugin_actions = {}
        self.edited_sublines = set()
        self.current_string_idx = -1
        self.tag_color_rgba = "#FF8C00"
        self.newline_color_rgba = "#A020F0"
        self.tag_bold = True
        self.tag_italic = False
        self.tag_underline = False
        self.newline_bold = True
        self.newline_italic = False
        self.newline_underline = False
        
        # Managers

        from core.settings_manager import SettingsManager
        self.settings_manager = SettingsManager(self)
        
        self.ui_provider = self
        self.ui_updater = None 
        self.data_processor = DataStateProcessor(self)
        self.project_manager = None
        self.plugin_handler = MainWindowPluginHandler(self)

    @property
    def current_game_rules(self): return self._current_game_rules
    @current_game_rules.setter
    def current_game_rules(self, v): self._current_game_rules = v

    def menuBar(self):
        from PyQt5.QtWidgets import QMenuBar
        return QMenuBar()

    def show_message(self, t, m, type="info"): pass
    def update_recent_projects_menu(self): pass
    def update_title(self): pass
    def update_plugin_status_label(self): pass
    def update_statusbar_paths(self): pass
    def load_game_plugin(self): pass
    def _perform_initial_silent_scan_all_issues(self): pass


class TestProjectLifecycle(unittest.TestCase):
    def setUp(self):
        self.patcher_msg = patch('PyQt5.QtWidgets.QMessageBox')
        self.patcher_msg.start()
        
        self.mw = MockMainWindow()
        
        # Configure settings_manager to avoid TypeError in QColor when plugins load
        self.mw.settings_manager = MagicMock()
        def mock_get_plugin_setting(key, default_val=None):
            if "color" in key: return "#FFFFFF"
            if key == "project.ui_state": return {}
            return default_val
            
        self.mw.settings_manager.get_plugin_setting.side_effect = mock_get_plugin_setting
        self.mw.settings_manager.get_global_setting.return_value = False
        self.mw.settings_manager.session_state.get_state_for_file.return_value = {}

        
        # Ensure style().standardIcon() returns a real QIcon to prevent TypeError in real QTreeWidgetItems
        from PyQt5.QtGui import QIcon
        mock_style = MagicMock()
        mock_style.standardIcon.return_value = QIcon()
        self.mw.style.return_value = mock_style
        
        self.pm = ProjectManager(self.mw)
        self.mw.project_manager = self.pm
        
        self.ui_updater = UIUpdater(self.mw, self.mw.data_processor)
        self.mw.ui_updater = self.ui_updater
        
        self.handler = ProjectActionHandler(self.mw, self.mw.data_processor, self.ui_updater)

    def tearDown(self):
        self.patcher_msg.stop()

    def test_complete_project_load_and_population(self):
        # Use known project from the environment
        project_path = os.path.abspath(os.path.join(os.path.dirname(__file__), '../PokemonRS/Pokemon/project.uiproj'))
        
        if not os.path.exists(project_path):
            self.skipTest(f"Project path {project_path} not found in this environment")

        # 1. Load project structure
        success = self.pm.load(project_path)
        self.assertTrue(success, "ProjectManager failed to load project")
        self.assertGreater(len(self.pm.project.blocks), 0, "No blocks in project")

        # 2. Load plugin
        self.mw.active_game_plugin = self.pm.project.plugin_name
        self.mw.plugin_handler.load_game_plugin()
        self.assertIsNotNone(self.mw.current_game_rules, f"Failed to load plugin {self.mw.active_game_plugin}")

        # 3. Populate data models
        self.handler._populate_blocks_from_project()
        
        # 4. Verify results
        self.assertGreater(len(self.mw.data_store.data), 0, "mw.data_store.data should not be empty after population")
        self.assertEqual(len(self.mw.data_store.data), len(self.mw.block_to_project_file_map), "Data size mismatch")
        
        # Check first block
        if len(self.mw.data_store.data) > 0:
             self.assertTrue(isinstance(self.mw.data_store.data[0], (str, list)), "Data entries should be strings or lists")

if __name__ == "__main__":
    unittest.main()
