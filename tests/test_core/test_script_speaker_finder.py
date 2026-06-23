import os
import pytest
from unittest.mock import MagicMock, patch, mock_open
from core.translation.script_speaker_finder import ScriptSpeakerFinder

@pytest.fixture
def mock_mw():
    mw = MagicMock()
    mw.current_game_rules = MagicMock()
    mw.current_game_rules.get_default_script_name.return_value = "zelda_tp_script.txt"
    mw.current_game_rules.get_display_name.return_value = "Zelda_TP"
    mw.current_game_rules.get_dynamic_name_tags.return_value = {}
    
    mw.data_store = MagicMock()
    mw.data_store.data = [["Line 1", "Line 2"]]
    
    return mw

@pytest.fixture
def mock_story_ctx():
    story_ctx = MagicMock()
    story_ctx.get_mempalace_client.return_value = None
    story_ctx._mempalace_project_dir = "/path/to/project"
    return story_ctx

def test_script_speaker_finder_init(mock_mw, mock_story_ctx):
    finder = ScriptSpeakerFinder(mock_mw, mock_story_ctx)
    assert finder.mw == mock_mw
    assert finder.story_context_manager == mock_story_ctx

def test_script_speaker_finder_find_script_path(mock_mw, mock_story_ctx):
    finder = ScriptSpeakerFinder(mock_mw, mock_story_ctx)
    with patch('os.path.exists', return_value=True):
        path = finder.find_script_path()
        assert "zelda_tp_script.txt" in path

def test_script_speaker_finder_translate_speaker():
    finder = ScriptSpeakerFinder(MagicMock(), MagicMock())
    
    mock_entry = MagicMock()
    mock_entry.original = "Link"
    mock_entry.translation = "Лінк"
    
    glossary_manager = MagicMock()
    glossary_manager.get_entries.return_value = [mock_entry]
    
    res = finder.translate_speaker("Link", glossary_manager)
    assert res == "Лінк"

def test_script_speaker_finder_find_speaker_in_script_direct(mock_mw, mock_story_ctx):
    finder = ScriptSpeakerFinder(mock_mw, mock_story_ctx)
    
    # Mock mempalace client for direct script mapping
    mock_client = MagicMock()
    mock_client.get_script_mapping.return_value = {"script_line": 3}
    mock_story_ctx.get_mempalace_client.return_value = mock_client
    
    # Mock reading script file
    script_content = "LINK\n[some tag]\nHello Link\n"
    
    with patch('os.path.exists', return_value=True):
        with patch('os.stat') as mock_stat:
            mock_stat.return_value.st_mtime = 12345
            mock_stat.return_value.st_size = 100
            
            with patch('builtins.open', mock_open(read_data=script_content)):
                speaker, line_num = finder.find_speaker_in_script(0, 0, "Hello Link", "Zelda_TP", "block_0")
                assert speaker == "LINK"
                assert line_num == "3"
