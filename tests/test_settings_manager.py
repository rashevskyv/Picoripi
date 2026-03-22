import pytest
from pathlib import Path
from unittest.mock import MagicMock
from core.settings_manager import SettingsManager

class MockMainWindow:
    def __init__(self):
        self.data_store = self
        self.active_game_plugin = "zelda_mc"
        self.current_font_size = 10
        self.theme = "auto"
        self.restore_unsaved_on_startup = False
        self.show_multiple_spaces_as_dots = True
        self.space_dot_color_hex = "#BBBBBB"
        self.window_was_maximized_on_close = False
        self.window_normal_geometry_on_close = None
        self.prompt_editor_enabled = True
        self.recent_projects = []
        self.translation_ai = {}
        self.glossary_ai = {}
        self.spellchecker_enabled = False
        self.spellchecker_language = 'uk'
        self.last_browse_dir = ""
        self.enable_console_logging = True
        self.enable_file_logging = True
        self.settings_window_width = 800
        self.log_file_path = ""
        self.enabled_log_categories = []
        self.edited_data = {}
        self.json_path = None
        self.edited_json_path = None
        self.main_splitter = None
        self.right_splitter = None
        self.bottom_right_splitter = None
        self.ui_updater = MagicMock()
        self.statusBar = MagicMock()
        
        # Plugin settings attributes
        self.default_tag_mappings = {}
        self.block_names = {}
        self.block_color_markers = {}
        self.string_metadata = {}
        self.default_font_file = ""
        self.newline_display_symbol = "↵"
        self.preview_wrap_lines = True
        self.editors_wrap_lines = False
        self.game_dialog_max_width_pixels = 208
        self.line_width_warning_threshold_pixels = 208
        self.last_cursor_position_in_edited = 0
        self.last_selected_block_index = -1
        self.last_selected_string_index = -1
        self.last_edited_text_edit_scroll_value_v = 0
        self.last_edited_text_edit_scroll_value_h = 0
        self.last_preview_text_edit_scroll_value_v = 0
        self.last_original_text_edit_scroll_value_v = 0
        self.last_original_text_edit_scroll_value_h = 0
        self.search_history_to_save = []
        self.autofix_enabled = {}
        self.detection_enabled = {}
        self.translation_config = {}
        self.context_menu_tags = {"single_tags": [], "wrap_tags": []}

@pytest.fixture
def mock_mw():
    return MockMainWindow()

@pytest.fixture
def settings_manager(mock_mw, tmp_path):
    # Use a temporary file for settings.json
    settings_file = tmp_path / "settings.json"
    manager = SettingsManager(mock_mw)
    manager.settings_file_path = str(settings_file)
    manager.global_settings.settings_file_path = str(settings_file)
    return manager

def test_initialization(settings_manager):
    assert settings_manager.global_settings is not None
    assert settings_manager.plugin_settings is not None
    assert settings_manager.font_map_loader is not None
    assert settings_manager.recent_projects_manager is not None

def test_set_and_get(settings_manager):
    settings_manager.set("test_key", "test_value")
    assert settings_manager.get("test_key") == "test_value"

def test_save_and_load_global_settings(settings_manager, mock_mw):
    mock_mw.theme = "dark"
    settings_manager.save_settings()
    
    # Create a new manager to load
    new_mw = MockMainWindow()
    new_manager = SettingsManager(new_mw)
    new_manager.settings_file_path = settings_manager.settings_file_path
    new_manager.global_settings.settings_file_path = settings_manager.settings_file_path
    
    new_manager.load_settings()
    assert new_mw.theme == "dark"
    assert new_manager.get("theme") == "dark"

def test_recent_projects(settings_manager, mock_mw):
    project_path = str(Path("/path/to/project").resolve())
    settings_manager.add_recent_project(project_path)
    assert project_path in mock_mw.recent_projects
    
    settings_manager.remove_recent_project(project_path)
    assert project_path not in mock_mw.recent_projects
