import pytest
import json
from pathlib import Path
from unittest.mock import MagicMock

from core.settings.font_map_loader import FontMapLoader

@pytest.fixture
def mock_mw():
    mw = MagicMock()
    mw.data_store = mw
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

def test_FontMapLoader_load_bfn_font(mock_mw, tmp_path):
    # Setup dummy plugin dir
    plugin_dir = tmp_path / "plugins" / "test_plugin"
    fonts_dir = plugin_dir / "fonts"
    fonts_dir.mkdir(parents=True)
    
    # Create dummy BFN via BfnCore
    from core.bfn_core import BfnCore
    bfn = BfnCore()
    bfn.signature = "FFNT1bnd"
    bfn.inf1 = [{"encoding": 0, "ascent": 20, "descent": 2, "width": 12, "leading": 2, "fallback_code": 63, "unk1": 0}]
    bfn.map1 = [{"mapping_type": 2, "first_char": 32, "last_char": 34, "mapping_entry_count": 2, "entries": [0, 1]}]
    bfn.wid1 = [{"first_code_included": 32, "last_code_included": 34, "packets": [{"kerning": 0, "width": 8}, {"kerning": 1, "width": 10}]}]
    
    bfn_file = fonts_dir / "test_font.bfn"
    with open(bfn_file, 'wb') as f:
        f.write(bfn.save())
        
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
        
    assert "test_font.bfn" in mock_mw.all_font_maps
    # 32 (space) must have width 8
    assert mock_mw.all_font_maps["test_font.bfn"][" "]["width"] == 8
    # 33 (exclamation mark) must have width 10
    assert mock_mw.all_font_maps["test_font.bfn"]["!"]["width"] == 10


def test_FontMapLoader_load_bfn_from_project_blocks(mock_mw, tmp_path):
    from core.bfn_core import BfnCore
    
    # 1. Create dummy BFN
    bfn = BfnCore()
    bfn.signature = "FFNT1bnd"
    bfn.inf1 = [{"encoding": 0, "ascent": 20, "descent": 2, "width": 12, "leading": 2, "fallback_code": 63, "unk1": 0}]
    bfn.map1 = [{"mapping_type": 2, "first_char": 32, "last_char": 34, "mapping_entry_count": 2, "entries": [0, 1]}]
    bfn.wid1 = [{"first_code_included": 32, "last_code_included": 34, "packets": [{"kerning": 0, "width": 8}, {"kerning": 1, "width": 10}]}]
    bfn_bytes = bfn.save()

    # 2. Setup mock project structure
    pm_mock = MagicMock()
    mock_mw.project_manager = pm_mock
    
    # Mock blocks
    block_disk = MagicMock()
    block_disk.source_file = "test_disk_font.bfn"
    block_disk.metadata = {"is_archive_member": False}
    
    block_archive = MagicMock()
    block_archive.metadata = {
        "is_archive_member": True,
        "archive_rel_path": "test_archive.arc",
        "archive_file_name": "test_archive_font.bfn"
    }
    
    pm_mock.project.blocks = [block_disk, block_archive]
    
    # Write disk font
    disk_font_path = tmp_path / "test_disk_font.bfn"
    disk_font_path.write_bytes(bfn_bytes)
    
    pm_mock.get_absolute_path.return_value = str(disk_font_path)
    
    # Mock container for archive block
    container_mock = MagicMock()
    container_mock.read_file.return_value = bfn_bytes
    pm_mock.get_archive_container.return_value = container_mock
    
    mock_mw.all_bfn_fonts = {}
    
    loader = FontMapLoader(mock_mw)
    loader.load_all_font_maps()
    
    # Verify that fonts from blocks were successfully loaded
    assert "test_disk_font.bfn" in mock_mw.all_bfn_fonts
    assert "test_archive_font.bfn" in mock_mw.all_bfn_fonts
    assert "test_archive.arc/test_archive_font.bfn" in mock_mw.all_bfn_fonts


