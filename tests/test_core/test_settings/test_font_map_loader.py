import pytest
import json
from pathlib import Path
from unittest.mock import MagicMock

from core.settings.font_map_loader import FontMapLoader

@pytest.fixture
def mock_mw():
    mw = MagicMock()
    mw.active_game_plugin = "test_plugin"
    mw.default_font_file = "default.json"
    mw.all_font_maps = {}
    mw.font_map = {}
    mw.font_map_overrides = {}
    mw.icon_sequences = []
    
    # Mock text edits for highlight refresh
    mock_editor = MagicMock()
    mock_highlighter = MagicMock()
    mock_editor.highlighter = mock_highlighter
    mw.original_text_edit = mock_editor
    mw.edited_text_edit = mock_editor
    mw.preview_text_edit = mock_editor
    
    return mw

def test_FontMapLoader_load_no_plugin(mock_mw):
    mock_mw.active_game_plugin = None
    loader = FontMapLoader(mock_mw)
    loader.load_all_font_maps()
    assert mock_mw.font_map == {}

def test_FontMapLoader_load_fonts(mock_mw, tmp_path):
    # Setup dummy plugin dir
    plugin_dir = tmp_path / "plugins" / "test_plugin"
    fonts_dir = plugin_dir / "fonts"
    fonts_dir.mkdir(parents=True)
    
    # Write a normal font
    f1 = fonts_dir / "default.json"
    f1.write_text(json.dumps({"A": {"width": 10}, "longSeq": {"width": 20}}))
    
    # Write an FFNT new style font
    f2 = fonts_dir / "new_style.json"
    f2.write_text(json.dumps({
        "signature": "FFNT",
        "glyphs": [
            {"char": "B", "width": {"char": 15}}
        ]
    }))
    
    # Write an override
    override_f = plugin_dir / "font_map.json"
    override_f.write_text(json.dumps({"A": {"width": 12}}))
    
    loader = FontMapLoader(mock_mw)
    
    # We must patch Path so it looks in tmp_path
    import core.settings.font_map_loader
    original_path = core.settings.font_map_loader.Path
    
    def mock_path(*args, **kwargs):
        if args and args[0] == "plugins":
            return tmp_path / "plugins"
        return original_path(*args, **kwargs)
        
    core.settings.font_map_loader.Path = mock_path
    
    try:
        loader.load_all_font_maps()
    finally:
        core.settings.font_map_loader.Path = original_path
        
    assert "default.json" in mock_mw.all_font_maps
    assert "new_style.json" in mock_mw.all_font_maps
    
    assert mock_mw.font_map["A"]["width"] == 12 # Override applied
    assert mock_mw.all_font_maps["new_style.json"]["B"]["width"] == 15
    
    assert "longSeq" in mock_mw.icon_sequences
    
    assert mock_mw.original_text_edit.highlighter.rehighlight.called

def test_FontMapLoader_update_icon_sequences(mock_mw):
    mock_mw.all_font_maps = {"f1": {"[Tag]": {"width": 10}, "A": {"width": 5}}}
    mock_mw.font_map = {"{Icon}": {"width": 15}, "x": {}}
    loader = FontMapLoader(mock_mw)
    loader.update_icon_sequences_cache()
    
    assert "[Tag]" in mock_mw.icon_sequences
    assert "{Icon}" in mock_mw.icon_sequences
    assert "A" not in mock_mw.icon_sequences
