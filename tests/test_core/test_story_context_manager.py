import os
import pytest
from unittest.mock import MagicMock, patch
from core.translation.story_context_manager import StoryContextManager

@pytest.fixture
def mock_mw():
    mw = MagicMock()
    mw.project_manager = MagicMock()
    mw.project_manager.project_dir = "/path/to/project"
    
    mw.data_store = MagicMock()
    mw.data_store.project_file = "/path/to/project/file.uiproj"
    mw.data_store.block_names = {"0": "bmg_file.bmg"}
    
    mw.active_game_rules = MagicMock()
    mw.active_game_rules.get_display_name.return_value = "Zelda_TP"
    
    return mw

def test_story_context_manager_init(mock_mw):
    manager = StoryContextManager(mock_mw)
    assert manager.mw == mock_mw

def test_story_context_manager_get_wing_name(mock_mw):
    manager = StoryContextManager(mock_mw)
    wing = manager.get_wing_name()
    assert wing == "Zelda_TP"

def test_story_context_manager_get_block_label_project(mock_mw):
    mock_block = MagicMock()
    mock_block.name = "CustomBlockName"
    mock_mw.project_manager.project.blocks = [mock_block]
    
    manager = StoryContextManager(mock_mw)
    assert manager.get_block_label(0) == "CustomBlockName"

def test_story_context_manager_get_block_label_fallback(mock_mw):
    mock_mw.project_manager = None
    manager = StoryContextManager(mock_mw)
    assert manager.get_block_label(0) == "bmg_file"

def test_story_context_manager_fetch_story_context_cached(mock_mw):
    manager = StoryContextManager(mock_mw)
    
    mock_client = MagicMock()
    mock_client.get_cached_context.return_value = {
        "room": "Ordon_Village",
        "speaker": "Link",
        "timestamp": "01:23"
    }
    mock_client.get_room_visual_context.return_value = "Beautiful village near forest."
    mock_client.get_relations.return_value = [
        {"source": "Link", "relation": "friend", "target": "Ilia"}
    ]
    
    manager.get_mempalace_client = MagicMock(return_value=mock_client)
    
    script_speaker_finder = MagicMock()
    data_processor = MagicMock()
    
    res = manager.fetch_story_context(0, 5, "Hello there", script_speaker_finder, data_processor)
    assert "Scene: Ordon Village" in res
    assert "Speaker in this line: Link" in res
    assert "Visual Action Context:\nBeautiful village near forest." in res
    assert "Link -[friend]-> Ilia" in res

def test_story_context_manager_fetch_story_context_database_search(mock_mw):
    manager = StoryContextManager(mock_mw)
    
    mock_client = MagicMock()
    mock_client.get_cached_context.return_value = None
    mock_client.search_context.return_value = [{
        "room": "Faron_Woods",
        "content": "ID:Faron_Woods_Str_5 | Text: Hello there",
        "metadata": {
            "timestamp": "02:45",
            "speaker_map": {"Faron_Woods_Str_5": "Midna"}
        }
    }]
    mock_client.get_room_visual_context.return_value = "Dark forest scene."
    mock_client.get_relations.return_value = []
    
    manager.get_mempalace_client = MagicMock(return_value=mock_client)
    
    script_speaker_finder = MagicMock()
    data_processor = MagicMock()
    
    res = manager.fetch_story_context(0, 5, "Hello there", script_speaker_finder, data_processor)
    assert "Scene: Faron Woods" in res
    assert "Speaker in this line: Midna" in res
    assert "Visual Action Context:\nDark forest" in res
