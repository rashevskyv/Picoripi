# tests/test_core/test_mempalace_client.py
import os
import json
import sqlite3
import urllib.request
import urllib.error
import socket
from unittest.mock import patch, MagicMock
import pytest
from core.mempalace_client import MemePalaceClient

@pytest.fixture
def temp_project_dir(tmp_path):
    return str(tmp_path)

@pytest.fixture
def client(temp_project_dir):
    # Initialize with local db inside temporary path
    return MemePalaceClient(project_dir=temp_project_dir, server_url="http://127.0.0.1:8000")

def test_mempalace_client_init(client, temp_project_dir):
    assert client.server_url == "http://127.0.0.1:8000"
    assert client.project_dir == temp_project_dir
    assert client.db_path == os.path.join(temp_project_dir, "mempalace_local.db")
    assert os.path.exists(client.db_path)

def test_mempalace_client_get_connection(client):
    conn = client._get_connection()
    assert isinstance(conn, sqlite3.Connection)
    # Check that foreign keys are enabled
    cursor = conn.cursor()
    cursor.execute("PRAGMA foreign_keys;")
    fk = cursor.fetchone()[0]
    assert fk == 1

@patch("urllib.request.urlopen")
def test_is_server_available_success(mock_urlopen, client):
    mock_response = MagicMock()
    mock_response.status = 200
    mock_urlopen.return_value.__enter__.return_value = mock_response

    # Clear cached availability if any
    if hasattr(client, "_server_available_cached"):
        delattr(client, "_server_available_cached")
    if hasattr(client, "_server_last_checked"):
        delattr(client, "_server_last_checked")

    assert client.is_server_available() is True

@patch("urllib.request.urlopen")
def test_is_server_available_non_200(mock_urlopen, client):
    mock_response = MagicMock()
    mock_response.status = 500
    mock_urlopen.return_value.__enter__.return_value = mock_response

    if hasattr(client, "_server_available_cached"):
        delattr(client, "_server_available_cached")

    assert client.is_server_available() is False

@patch("urllib.request.urlopen")
def test_is_server_available_timeout(mock_urlopen, client):
    mock_urlopen.side_effect = socket.timeout("timeout")

    if hasattr(client, "_server_available_cached"):
        delattr(client, "_server_available_cached")

    assert client.is_server_available() is False

@patch("urllib.request.urlopen")
def test_is_server_available_url_error(mock_urlopen, client):
    mock_urlopen.side_effect = urllib.error.URLError("reason")

    if hasattr(client, "_server_available_cached"):
        delattr(client, "_server_available_cached")

    assert client.is_server_available() is False

def test_local_db_write_read_fallback(client):
    # Ensure server is offline
    with patch.object(client, "is_server_available", return_value=False):
        # 1. Add wing
        assert client.add_wing("ZeldaMC", "Minish Cap project") is True
        wings = client.get_wings()
        assert len(wings) == 1
        assert wings[0]["name"] == "ZeldaMC"
        assert wings[0]["description"] == "Minish Cap project"

        # 2. Add room
        assert client.add_room("ZeldaMC", "HyruleTown", "Town area") is True
        rooms = client.get_rooms("ZeldaMC")
        assert len(rooms) == 1
        assert rooms[0]["name"] == "HyruleTown"
        assert rooms[0]["description"] == "Town area"

        # Check has_room for non-existing visual context
        assert client.has_room("ZeldaMC", "HyruleTown") is False

        # 3. Add drawer
        metadata = {"speaker_map": {"Str_1": "Link", "Str_2": "Zelda"}, "timestamp": "12:00"}
        content = "ID: Str_1 | Text: Hey!\n[Str_2]: Hi Link!"
        assert client.add_drawer("ZeldaMC", "HyruleTown", "visual_scene_context", content, metadata) is True
        assert client.has_room("ZeldaMC", "HyruleTown") is True

        drawers = client.get_room_drawers("ZeldaMC", "HyruleTown")
        assert len(drawers) == 1
        assert drawers[0]["name"] == "visual_scene_context"
        assert drawers[0]["content"] == content
        assert drawers[0]["metadata"] == metadata

        # Test preloaded cache lookup after add_drawer (which sets cache_loaded=False)
        ctx = client.get_cached_context("Str_1", "")
        assert ctx is not None
        assert ctx["room"] == "HyruleTown"
        assert ctx["speaker"] == "Link"

        ctx_text = client.get_cached_context("", "Hi Link!")
        assert ctx_text is not None
        assert ctx_text["speaker"] == "Zelda"

        # Test get_room_visual_context
        vis_ctx = client.get_room_visual_context("ZeldaMC", "HyruleTown")
        assert vis_ctx == content

def test_preload_cache_invalidation_on_mtime_change(client):
    with patch.object(client, "is_server_available", return_value=False):
        client.add_wing("TestWing")
        client.add_room("TestWing", "TestRoom")
        client.add_drawer("TestWing", "TestRoom", "dialogues", "ID: S_1 | Text: Hello", {"speaker_map": {"S_1": "Hero"}})

        # Prime the cache
        ctx1 = client.get_cached_context("S_1", "")
        assert ctx1 is not None
        assert ctx1["speaker"] == "Hero"

        # Manually alter the database outside client, then query again
        conn = sqlite3.connect(client.db_path)
        cursor = conn.cursor()
        # Update drawer content
        metadata = json.dumps({"speaker_map": {"S_1": "Legend"}})
        cursor.execute("UPDATE drawers SET metadata = ? WHERE name = 'dialogues'", (metadata,))
        conn.commit()
        conn.close()

        # Touch the file to update its mtime
        os.utime(client.db_path, None)

        # Retrieve again - it should trigger cache reload and find "Legend"
        ctx2 = client.get_cached_context("S_1", "")
        assert ctx2 is not None
        assert ctx2["speaker"] == "Legend"

def test_add_relation_and_get_relations(client):
    with patch.object(client, "is_server_available", return_value=False):
        assert client.add_relation("ZeldaMC", "Link", "friend", "Zelda", "always") is True
        relations = client.get_relations("ZeldaMC")
        assert len(relations) == 1
        assert relations[0]["source"] == "Link"
        assert relations[0]["relation"] == "friend"
        assert relations[0]["target"] == "Zelda"
        assert relations[0]["valid_from"] == "always"

def test_search_context(client):
    with patch.object(client, "is_server_available", return_value=False):
        client.add_wing("ZeldaMC")
        client.add_room("ZeldaMC", "Forest")
        client.add_drawer("ZeldaMC", "Forest", "scene_info", "The forest is dark and full of Minish.", {})
        client.add_drawer("ZeldaMC", "Forest", "dialogues", "ID: Str_10 | Text: Look at this sword!", {"speaker_map": {"Str_10": "Link"}})

        # Search query matching drawer content
        results = client.search_context("ZeldaMC", "sword forest")
        assert len(results) >= 1
        # The best match should be first (both words score)
        assert results[0]["name"] in ("scene_info", "dialogues")

def test_clear_wing(client):
    with patch.object(client, "is_server_available", return_value=False):
        client.add_wing("ZeldaMC")
        client.add_room("ZeldaMC", "Castle")
        client.add_drawer("ZeldaMC", "Castle", "dialogues", "content", {})
        client.add_relation("ZeldaMC", "A", "rel", "B")

        assert len(client.get_rooms("ZeldaMC")) == 1
        assert len(client.get_relations("ZeldaMC")) == 1

        assert client.clear_wing("ZeldaMC") is True

        assert len(client.get_rooms("ZeldaMC")) == 0
        assert len(client.get_relations("ZeldaMC")) == 0

def test_clear_all_local_data(client):
    with patch.object(client, "is_server_available", return_value=False):
        client.add_wing("W1")
        client.add_wing("W2")
        assert len(client.get_wings()) == 2
        assert client.clear_all_local_data() is True
        assert len(client.get_wings()) == 0

def test_script_chapters_and_mappings(client):
    with patch.object(client, "is_server_available", return_value=False):
        # 1. Save chapters
        chapters = [
            {"num": "1", "title": "Intro", "start_line": 1, "end_line": 10, "ai_summary": "Link starts", "content": "Chapter 1 text"},
            {"num": "2", "title": "Town", "start_line": 11, "end_line": 20, "ai_summary": "Town life", "content": "Chapter 2 text"}
        ]
        client.save_chapters_to_db("ZeldaMC", chapters)

        all_ch = client.get_all_chapters("ZeldaMC")
        assert len(all_ch) == 2
        assert all_ch[0]["title"] == "Intro"
        assert all_ch[1]["title"] == "Town"

        # Test get_chapter_for_line
        ch_info = client.get_chapter_for_line("ZeldaMC", 5)
        assert ch_info is not None
        assert ch_info["title"] == "Intro"
        assert ch_info["ai_summary"] == "Link starts"

        # Update chapter summary
        client.save_chapter_summary(all_ch[0]["id"], "New intro summary")
        ch_info_updated = client.get_chapter_for_line("ZeldaMC", 5)
        assert ch_info_updated["ai_summary"] == "New intro summary"

        # 2. Save mappings
        mappings = [
            {"bmg_id": "Str_100", "script_line": 5, "bmg_text": "Hello world"},
            {"bmg_id": "Str_101", "script_line": 15, "bmg_text": "Welcome to town"}
        ]
        client.save_mappings_to_db("ZeldaMC", mappings)

        # Test get_script_mapping
        map_info = client.get_script_mapping("ZeldaMC", "Str_100")
        assert map_info is not None
        assert map_info["script_line"] == 5
        assert map_info["bmg_text"] == "Hello world"
        assert map_info["chapter_title"] == "Intro"

        # Test bracketed lookup
        map_info_bracket = client.get_script_mapping("ZeldaMC", "[Str_100]")
        assert map_info_bracket is not None
        assert map_info_bracket["script_line"] == 5

        # Test get_chapter_mappings
        ch_maps = client.get_chapter_mappings("ZeldaMC", all_ch[0]["id"])
        assert len(ch_maps) == 1
        assert ch_maps[0]["bmg_id"] == "Str_100"

        # Test get_all_chapter_mappings
        all_maps = client.get_all_chapter_mappings("ZeldaMC")
        assert all_ch[0]["id"] in all_maps
        assert all_ch[1]["id"] in all_maps
        assert len(all_maps[all_ch[0]["id"]]) == 1

def test_get_all_character_lines(client):
    with patch.object(client, "is_server_available", return_value=False):
        client.add_wing("ZeldaMC")
        client.add_room("ZeldaMC", "Castle")
        
        # Test cleaning tags and grouping dialogue lines by character
        content = "ID: Str_1 | Text: {Color:Red}[Link] Hello Princess!\n[Str_2]: {tab}Hi there Link! [whisper]"
        metadata = {"speaker_map": {"Str_1": "Link", "Str_2": "Zelda"}}
        client.add_drawer("ZeldaMC", "Castle", "dialogues", content, metadata)

        lines = client.get_all_character_lines("ZeldaMC")
        assert "Link" in lines
        assert "Zelda" in lines
        assert lines["Link"] == ["Hello Princess!"]
        assert lines["Zelda"] == ["Hi there Link!"]

@patch("urllib.request.urlopen")
def test_external_server_api_calls(mock_urlopen, client):
    # Mock successful POST response
    mock_response = MagicMock()
    mock_response.status = 201
    mock_urlopen.return_value.__enter__.return_value = mock_response

    # Mock server as available
    with patch.object(client, "is_server_available", return_value=True):
        # Test add_wing makes POST request
        assert client.add_wing("ExternalWing", "Desc") is True
        assert mock_urlopen.called

        mock_urlopen.reset_mock()
        # Test add_room makes POST request
        assert client.add_room("ExternalWing", "ExternalRoom", "Desc") is True
        assert mock_urlopen.called

        mock_urlopen.reset_mock()
        # Test add_drawer makes POST request
        assert client.add_drawer("ExternalWing", "ExternalRoom", "Drawer", "Content", {}) is True
        assert mock_urlopen.called

        mock_urlopen.reset_mock()
        # Test add_relation makes POST request
        assert client.add_relation("ExternalWing", "A", "rel", "B", "now") is True
        assert mock_urlopen.called

        mock_urlopen.reset_mock()
        # Mock DELETE response for clear_wing
        mock_response_del = MagicMock()
        mock_response_del.status = 204
        mock_urlopen.return_value.__enter__.return_value = mock_response_del
        assert client.clear_wing("ExternalWing") is True
        assert mock_urlopen.called
