import pytest
from unittest.mock import MagicMock, patch
from pathlib import Path
import json

from core.settings.global_settings import GlobalSettings

@pytest.fixture
def mock_mw():
    mw = MagicMock()
    mw.data_store = mw
    mw.current_font_size = 12
    mw.tree_font_size = 12
    mw.preview_font_size = 12
    mw.editors_font_size = 12
    mw.tooltip_font_size = 11
    mw.active_game_plugin = "test_plugin"
    mw.show_multiple_spaces_as_dots = True
    mw.space_dot_color_hex = "#123456"
    mw.window_was_maximized_on_close = False
    mw.theme = "auto"
    mw.restore_unsaved_on_startup = False
    mw.last_opened_path = ""
    mw.prompt_editor_enabled = True
    mw.recent_projects = []
    mw.translation_ai = {}
    mw.glossary_ai = {}
    mw.spellchecker_enabled = False
    mw.spellchecker_language = "en"
    mw.preview_enabled = True
    mw.warnings_enabled = True
    mw.glossary_enabled = True
    mw.last_browse_dir = "C:/"
    mw.enable_console_logging = True
    mw.enable_file_logging = False
    mw.settings_window_width = 800
    mw.log_file_path = ""
    mw.enabled_log_categories = []
    mw.bfn_glyph_table_column_widths = []
    mw.bfn_auto_sync_enabled = False
    mw.preview_bg_image_path = ""
    mw.preview_bg_scale = 100
    mw.preview_bg_offset_x = 0
    mw.preview_bg_offset_y = 0
    mw.preview_bg_hidden = False
    mw.preview_line_spacing = 10
    mw.preview_text_rect = [15, 15, 300, 120]
    mw.preview_text_color = "#ffffff"
    mw.preview_shadow_enabled = False
    mw.preview_shadow_color = "#000000"
    mw.preview_shadow_alpha = 178
    mw.preview_shadow_angle = 315
    mw.preview_shadow_distance = 3
    mw.preview_glow_enabled = False
    mw.preview_glow_color = "#ffffff"
    mw.preview_glow_alpha = 180
    mw.preview_glow_spread = 4
    mw.preview_fix_font_scale = False
    mw.preview_fixed_font_scale = 1.0
    
    mw.data_store.edited_data = None
    mw.window_normal_geometry_on_close = None
    
    mw.main_splitter = None
    mw.right_splitter = None
    mw.bottom_right_splitter = None
    return mw

def test_GlobalSettings_init(mock_mw):
    s = GlobalSettings(mock_mw, "test.json")
    assert s.settings_file_path == "test.json"
    assert "theme" in s.defaults

def test_GlobalSettings_load_no_file(mock_mw, tmp_path):
    f = tmp_path / "missing.json"
    s = GlobalSettings(mock_mw, f)
    d = {}
    s.load(d)
    assert d["theme"] == "auto"
    assert mock_mw.current_font_size > 0

def test_GlobalSettings_load_with_file(mock_mw, tmp_path):
    f = tmp_path / "settings.json"
    f.write_text(json.dumps({
        "theme": "dark",
        "font_size": 20,
        "editors_font_size": 22,
        "translation_ai": {"provider": "DeepL"}
    }))
    s = GlobalSettings(mock_mw, f)
    d = {}
    s.load(d)
    
    assert d["theme"] == "dark"
    # Merges dicts
    assert d["translation_ai"]["provider"] == "DeepL"
    assert "model" in d["translation_ai"] # Rest of dict is from defaults
    
    assert mock_mw.theme == "dark"
    assert mock_mw.editors_font_size == 22
    assert mock_mw.current_font_size == 20

def test_GlobalSettings_save(mock_mw, tmp_path):
    f = tmp_path / "settings.json"
    s = GlobalSettings(mock_mw, f)
    
    s.save({})
    
    assert f.exists()
    saved = json.loads(f.read_text())
    assert saved["theme"] == "auto"
    assert saved["active_game_plugin"] == "test_plugin"

def test_GlobalSettings_save_unsaved_session(mock_mw, tmp_path):
    f = tmp_path / "settings.json"
    s = GlobalSettings(mock_mw, f)
    
    mock_mw.restore_unsaved_on_startup = True
    mock_mw.edited_data = {(0, 0, 0): "Edited"}
    
    s.save({})
    saved = json.loads(f.read_text())
    assert "unsaved_session_data" in saved
    assert saved["unsaved_session_data"]["(0, 0, 0)"] == "Edited"

    # Save without it deletes it
    mock_mw.restore_unsaved_on_startup = False
    s.save({})
    saved_again = json.loads(f.read_text())
    assert "unsaved_session_data" not in saved_again

def test_GlobalSettings_saves_and_loads_translation_config(mock_mw, tmp_path):
    f = tmp_path / "settings.json"
    s = GlobalSettings(mock_mw, f)
    
    # Setup mock config
    mock_mw.translation_config = {
        "provider": "gemini",
        "providers": {
            "gemini": {
                "api_key": "test-key-123",
                "model": "gemini-test-model"
            }
        }
    }
    
    # Save settings
    s.save({})
    assert f.exists()
    
    saved_data = json.loads(f.read_text())
    assert "translation_config" in saved_data
    assert saved_data["translation_config"]["provider"] == "gemini"
    assert saved_data["translation_config"]["providers"]["gemini"]["api_key"] == "test-key-123"
    
    # Also check legacy translation_ai sync
    assert saved_data["translation_ai"]["provider"] == "gemini"
    assert saved_data["translation_ai"]["api_key"] == "test-key-123"
    assert saved_data["translation_ai"]["model"] == "gemini-test-model"
    
    # Load settings back
    mock_mw.translation_config = None
    settings_dict = {}
    s.load(settings_dict)
    
    assert mock_mw.translation_config is not None
    assert mock_mw.translation_config["provider"] == "gemini"
    assert mock_mw.translation_config["providers"]["gemini"]["api_key"] == "test-key-123"
    assert mock_mw.translation_config["providers"]["gemini"]["model"] == "gemini-test-model"

def test_GlobalSettings_saves_and_loads_tooltip_font_size(mock_mw, tmp_path):
    f = tmp_path / "settings.json"
    s = GlobalSettings(mock_mw, f)
    
    mock_mw.tooltip_font_size = 18
    s.save({})
    
    assert f.exists()
    saved = json.loads(f.read_text())
    assert saved["tooltip_font_size"] == 18
    
    # Reset and load
    mock_mw.tooltip_font_size = 11
    d = {}
    s.load(d)
    assert d["tooltip_font_size"] == 18
    assert mock_mw.tooltip_font_size == 18
