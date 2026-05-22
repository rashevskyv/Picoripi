import pytest
import os
import json
from pathlib import Path
from unittest.mock import MagicMock, patch

from core.settings.plugin_settings import PluginSettings

@pytest.fixture
def dummy_mw():
    class Dummy:
        def __init__(self):
            self.data_store = self
    mw = Dummy()
    mw.active_game_plugin = "test_plugin"
    mw.block_names = {}
    mw.block_color_markers = {}
    mw.default_tag_mappings = {}
    mw.string_metadata = {}
    mw.default_font_file = ""
    mw.fonts_dir_path = ""
    mw.orig_fonts_dir_path = ""
    mw.newline_display_symbol = "N"
    mw.preview_wrap_lines = True
    mw.editors_wrap_lines = False
    mw.game_dialog_max_width_pixels = 100
    mw.line_width_warning_threshold_pixels = 90
    mw.lines_per_page = 4
    mw.json_path = ""
    mw.edited_json_path = ""
    mw.last_selected_block_index = -1
    mw.last_selected_string_index = -1
    mw.last_cursor_position_in_edited = 0
    mw.last_edited_text_edit_scroll_value_v = 0
    mw.last_edited_text_edit_scroll_value_h = 0
    mw.last_preview_text_edit_scroll_value_v = 0
    mw.last_original_text_edit_scroll_value_v = 0
    mw.last_original_text_edit_scroll_value_h = 0
    mw.search_history_to_save = []
    mw.autofix_enabled = {}
    mw.detection_enabled = {}
    mw.translation_config = {}
    mw.context_menu_tags = {"single_tags": [], "wrap_tags": []}
    return mw

def test_PluginSettings_init(dummy_mw):
    ps = PluginSettings(dummy_mw)
    assert ps.mw == dummy_mw

def test_PluginSettings_get_plugin_config_path(dummy_mw):
    ps = PluginSettings(dummy_mw)
    p = ps._get_plugin_config_path()
    assert str(p) == str(Path("plugins/test_plugin/config.json"))
    
    ps.mw.active_game_plugin = ""
    assert ps._get_plugin_config_path() is None

def test_PluginSettings_get_project_settings_path(dummy_mw):
    ps = PluginSettings(dummy_mw)
    
    # Without project_manager
    assert ps._get_project_settings_path() is None
    
    # With project_manager but no project_dir
    dummy_mw.project_manager = MagicMock()
    dummy_mw.project_manager.project_dir = None
    assert ps._get_project_settings_path() is None
    
    # With project_manager and project_dir
    dummy_mw.project_manager.project_dir = "C:/projects/my_project"
    p = ps._get_project_settings_path()
    assert str(p) == str(Path("C:/projects/my_project/project_settings.json"))

def test_PluginSettings_substitute_env_vars(dummy_mw):
    ps = PluginSettings(dummy_mw)
    os.environ["TEST_ENV_VAR"] = "replaced_value"
    
    data = {
        "key1": "${TEST_ENV_VAR}/path",
        "key2": ["$TEST_ENV_VAR"],
        "key3": "no_change"
    }
    
    substituted = ps._substitute_env_vars(data)
    assert substituted["key1"] == "replaced_value/path"
    assert substituted["key2"] == ["replaced_value"]
    assert substituted["key3"] == "no_change"
    
    os.environ.pop("TEST_ENV_VAR")

def test_PluginSettings_load_no_file(dummy_mw):
    ps = PluginSettings(dummy_mw)
    ps._get_plugin_config_path = MagicMock(return_value=None)
    ps._get_project_settings_path = MagicMock(return_value=None)
    
    d = {}
    ps.load(d)
    assert "display_name" in d
    assert d["display_name"] == "Unknown Plugin"
    
    # Check that MW fields get populated
    assert dummy_mw.tag_color_rgba == "#FF8C00"
    assert dummy_mw.tag_bold is True

def test_PluginSettings_load_with_files(dummy_mw, tmp_path):
    plugin_config = tmp_path / "config.json"
    plugin_config.write_text(json.dumps({
        "display_name": "Test Loaded Plugin",
        "block_names": {"1": "Block1"},
        "tag_color_rgba": "#112233",
        "string_metadata": {"(0, 1)": {"state": "done"}}
    }))
    
    project_settings = tmp_path / "project_settings.json"
    project_settings.write_text(json.dumps({
        "block_names": {"1": "ProjectBlock1", "2": "ProjectBlock2"}
    }))
    
    ps = PluginSettings(dummy_mw)
    ps._get_plugin_config_path = MagicMock(return_value=plugin_config)
    ps._get_project_settings_path = MagicMock(return_value=project_settings)
    
    d = {}
    ps.load(d)
    
    assert d["display_name"] == "Test Loaded Plugin"
    # Project settings override plugin defaults
    assert dummy_mw.block_names["1"] == "ProjectBlock1"
    assert dummy_mw.block_names["2"] == "ProjectBlock2"
    assert dummy_mw.tag_color_rgba == "#112233"
    assert dummy_mw.string_metadata[(0, 1)]["state"] == "done"

def test_PluginSettings_save_no_project(dummy_mw):
    ps = PluginSettings(dummy_mw)
    ps._get_project_settings_path = MagicMock(return_value=None)
    
    # Should log warning and not crash
    ps.save()

def test_PluginSettings_save(dummy_mw, tmp_path):
    project_settings = tmp_path / "project_settings.json"
    ps = PluginSettings(dummy_mw)
    ps._get_plugin_config_path = MagicMock(return_value=None)
    ps._get_project_settings_path = MagicMock(return_value=project_settings)
    
    dummy_mw.block_names = {"2": "Block2"}
    ps.save()
    
    assert project_settings.exists()
    saved = json.loads(project_settings.read_text())
    assert saved["block_names"]["2"] == "Block2"
    assert "default_tag_mappings" in saved

def test_PluginSettings_save_block_names(dummy_mw, tmp_path):
    project_settings = tmp_path / "project_settings.json"
    project_settings.write_text(json.dumps({"some_key": "val"}))
    ps = PluginSettings(dummy_mw)
    ps._get_plugin_config_path = MagicMock(return_value=None)
    ps._get_project_settings_path = MagicMock(return_value=project_settings)
    
    dummy_mw.block_names = {"3": "Block3"}
    ps.save_block_names()
    
    saved = json.loads(project_settings.read_text())
    assert saved["some_key"] == "val"
    assert saved["block_names"]["3"] == "Block3"

def test_PluginSettings_load_save_fonts_dir_path(dummy_mw, tmp_path):
    project_settings = tmp_path / "project_settings.json"
    project_settings.write_text(json.dumps({
        "fonts_dir_path": "C:/custom/fonts/dir"
    }))
    
    ps = PluginSettings(dummy_mw)
    ps._get_plugin_config_path = MagicMock(return_value=None)
    ps._get_project_settings_path = MagicMock(return_value=project_settings)
    
    d = {}
    ps.load(d)
    
    assert dummy_mw.fonts_dir_path == "C:/custom/fonts/dir"
    
    dummy_mw.fonts_dir_path = "D:/another/fonts/dir"
    ps.save()
    
    saved = json.loads(project_settings.read_text())
    assert saved["fonts_dir_path"] == "D:/another/fonts/dir"

def test_PluginSettings_load_save_orig_fonts_dir_path(dummy_mw, tmp_path):
    project_settings = tmp_path / "project_settings.json"
    project_settings.write_text(json.dumps({
        "orig_fonts_dir_path": "C:/custom/orig_fonts/dir"
    }))
    
    ps = PluginSettings(dummy_mw)
    ps._get_plugin_config_path = MagicMock(return_value=None)
    ps._get_project_settings_path = MagicMock(return_value=project_settings)
    
    d = {}
    ps.load(d)
    
    assert dummy_mw.orig_fonts_dir_path == "C:/custom/orig_fonts/dir"
    
    dummy_mw.orig_fonts_dir_path = "D:/another/orig_fonts/dir"
    ps.save()
    
    saved = json.loads(project_settings.read_text())
    assert saved["orig_fonts_dir_path"] == "D:/another/orig_fonts/dir"

def test_PluginSettings_translation_config_loading(dummy_mw, tmp_path):
    # Setup dummy_mw with translation_config
    dummy_mw.translation_config = {"provider": "OpenAI", "providers": {"OpenAI": {"api_key": "global_key", "model": "gpt-4o"}}}
    
    # 1. No project loaded (project_settings.json does not exist)
    ps = PluginSettings(dummy_mw)
    ps._get_plugin_config_path = MagicMock(return_value=None)
    ps._get_project_settings_path = MagicMock(return_value=None)
    
    d = {}
    ps.load(d)
    
    # Should NOT overwrite the globally loaded translation_config with defaults
    assert dummy_mw.translation_config == {"provider": "OpenAI", "providers": {"OpenAI": {"api_key": "global_key", "model": "gpt-4o"}}}
    
    # 2. Project loaded with project-specific translation_config
    project_settings = tmp_path / "project_settings.json"
    project_settings.write_text(json.dumps({
        "translation_config": {"provider": "Gemini", "providers": {"Gemini": {"api_key": "proj_key", "model": "gemini-1.5-pro"}}}
    }))
    
    ps._get_project_settings_path = MagicMock(return_value=project_settings)
    ps.load(d)
    
    # Should overwrite since it's explicitly present in project settings
    assert dummy_mw.translation_config["provider"] == "Gemini"
    assert dummy_mw.translation_config["providers"]["Gemini"]["api_key"] == "proj_key"
