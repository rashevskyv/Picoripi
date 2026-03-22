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

def test_PluginSettings_substitute_env_vars(dummy_mw):
    ps = PluginSettings(dummy_mw)
    os.environ["TEST_ENV_VAR"] = "replaced_value"
    
    data = {
        "key1": "${TEST_ENV_VAR}/path",
        "key2": ["$TEST_ENV_VAR"],
        "key3": "no_change"
    }
    
    Substituted = ps._substitute_env_vars(data)
    assert Substituted["key1"] == "replaced_value/path"
    assert Substituted["key2"] == ["replaced_value"]
    assert Substituted["key3"] == "no_change"
    
    os.environ.pop("TEST_ENV_VAR")

def test_PluginSettings_load_no_file(dummy_mw):
    ps = PluginSettings(dummy_mw)
    ps._get_plugin_config_path = MagicMock(return_value=None)
    
    d = {}
    ps.load(d)
    assert "display_name" in d
    assert d["display_name"] == "Unknown Plugin"
    
    # Check that MW fields get populated
    assert dummy_mw.tag_color_rgba == "#FF8C00"
    assert dummy_mw.tag_bold is True

def test_PluginSettings_load_with_file(dummy_mw, tmp_path):
    f = tmp_path / "config.json"
    f.write_text(json.dumps({
        "display_name": "Test Loaded",
        "block_names": {"1": "Block1"},
        "tag_color_rgba": "#112233",
        "string_metadata": {"(0, 1)": {"state": "done"}}
    }))
    
    ps = PluginSettings(dummy_mw)
    ps._get_plugin_config_path = MagicMock(return_value=f)
    
    d = {}
    ps.load(d)
    
    assert d["display_name"] == "Test Loaded"
    assert dummy_mw.block_names["1"] == "Block1"
    # Legacy migration 
    assert dummy_mw.tag_color_rgba == "#112233"
    assert dummy_mw.string_metadata[(0, 1)]["state"] == "done"

def test_PluginSettings_save(dummy_mw, tmp_path):
    f = tmp_path / "config.json"
    ps = PluginSettings(dummy_mw)
    ps._get_plugin_config_path = MagicMock(return_value=f)
    
    dummy_mw.block_names = {"2": "Block2"}
    ps.save()
    
    assert f.exists()
    saved = json.loads(f.read_text())
    assert saved["block_names"]["2"] == "Block2"
    assert "default_tag_mappings" in saved

def test_PluginSettings_save_block_names(dummy_mw, tmp_path):
    f = tmp_path / "config.json"
    f.write_text(json.dumps({"some_key": "val"}))
    ps = PluginSettings(dummy_mw)
    ps._get_plugin_config_path = MagicMock(return_value=f)
    
    dummy_mw.block_names = {"3": "Block3"}
    ps.save_block_names()
    
    saved = json.loads(f.read_text())
    assert saved["some_key"] == "val"
    assert saved["block_names"]["3"] == "Block3"
