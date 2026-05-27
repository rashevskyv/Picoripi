import pytest
from unittest.mock import MagicMock
from core.mempalace_worker import MemePalaceWorker

def test_mempalace_worker_chronological_weaving():
    client = MagicMock()
    
    # 1. Prepare scrambled BMG strings (like in raw game files)
    bmg_strings = [
        "Are you sure about the map portals, Link?", # Index 0 (Midna - late game)
        "Tell me... Do you ever feel a strange sadness as dusk falls?", # Index 1 (Rusl - early game)
        "Epona is waiting for you in the hot springs." # Index 2 (Ilia - early game)
    ]
    bmg_ids = ["BMG_Str_0", "BMG_Str_1", "BMG_Str_2"]
    
    # 2. Prepare perfectly ordered chronological script transcript
    # Chapter I: early game, Chapter IV: late game
    transcript_data = [
        {
            "text": "Tell me... Do you ever feel a strange sadness as dusk falls?",
            "speaker": "RUSL",
            "timestamp": "01:00",
            "room": "Chapter_I_Subservient_Twilight"
        },
        {
            "text": "Epona is waiting for you in the hot springs.",
            "speaker": "ILIA",
            "timestamp": "02:00",
            "room": "Chapter_I_Subservient_Twilight"
        },
        {
            "text": "Are you sure about the map portals, Link?",
            "speaker": "MIDNA",
            "timestamp": "25:00",
            "room": "Chapter_IV_Twilight_Realm"
        }
    ]
    
    worker = MemePalaceWorker(
        client=client,
        bmg_strings=bmg_strings,
        bmg_ids=bmg_ids,
        transcript_data=transcript_data,
        wing_name="Zelda_TP",
        mapping_only=True
    )
    
    # Run chronological weaving
    mapped_scenes = worker._weave_strings()
    
    # 3. Verify that mapped_scenes are sorted chronologically
    assert len(mapped_scenes) == 2 # Two rooms: Chapter_I and Chapter_IV
    
    # Find Chapter_I scene
    scene_ch1 = next(s for s in mapped_scenes if s["room_name"] == "Chapter_I_Subservient_Twilight")
    assert len(scene_ch1["bmg_texts"]) == 2
    # CRITICAL: Verify they are ordered strictly according to the Script sequence (Rusl first, then Ilia)
    assert scene_ch1["bmg_texts"][0] == "Tell me... Do you ever feel a strange sadness as dusk falls?"
    assert scene_ch1["bmg_texts"][1] == "Epona is waiting for you in the hot springs."
    assert scene_ch1["bmg_ids"][0] == "BMG_Str_1"
    assert scene_ch1["bmg_ids"][1] == "BMG_Str_2"
    
    # Find Chapter_IV scene (Midna)
    scene_ch4 = next(s for s in mapped_scenes if s["room_name"] == "Chapter_IV_Twilight_Realm")
    assert len(scene_ch4["bmg_texts"]) == 1
    assert scene_ch4["bmg_texts"][0] == "Are you sure about the map portals, Link?"
    assert scene_ch4["bmg_ids"][0] == "BMG_Str_0"
    
    # CRITICAL SUCCESS CRITERIA: Midna (BMG_Str_0) is in Chapter_IV and NEVER mixed with Rusl in Chapter_I!
    # The scenes are completely separated logically, keeping every chapter as a single cohesive unit!


def test_mempalace_worker_scene_based_chunking():
    client = MagicMock()
    
    # 1. Scramble BMG lines
    bmg_strings = [
        "First dialogue of scene A",
        "Second dialogue of scene A",
        "Third dialogue of scene A",
        "Generic dialogue 1",
        "Generic dialogue 2"
    ]
    bmg_ids = [f"BMG_Str_{i}" for i in range(5)]
    
    # 2. Prepare chronological transcript with mixed action and generic scenes
    transcript_data = [
        # Scene A: 3 lines belonging to the same Action context
        {
            "text": "First dialogue of scene A",
            "speaker": "ILIA",
            "timestamp": "Action: Link meets Ilia",
            "room": "Chapter_I"
        },
        {
            "text": "Second dialogue of scene A",
            "speaker": "ILIA",
            "timestamp": "Action: Link meets Ilia",
            "room": "Chapter_I"
        },
        {
            "text": "Third dialogue of scene A",
            "speaker": "ILIA",
            "timestamp": "Action: Link meets Ilia",
            "room": "Chapter_I"
        },
        # Generic dialogues: no Action tag
        {
            "text": "Generic dialogue 1",
            "speaker": "FADO",
            "timestamp": "Scene_3",
            "room": "Chapter_I"
        },
        {
            "text": "Generic dialogue 2",
            "speaker": "FADO",
            "timestamp": "Scene_4",
            "room": "Chapter_I"
        }
    ]
    
    worker = MemePalaceWorker(
        client=client,
        bmg_strings=bmg_strings,
        bmg_ids=bmg_ids,
        transcript_data=transcript_data,
        wing_name="Zelda_TP",
        mapping_only=True
    )
    
    mapped_scenes = worker._weave_strings()
    
    # 3. Verify that mapped_scenes are grouped by natural action scenes
    # We should have exactly 2 scenes:
    # Scene 1: Link meets Ilia (3 lines)
    # Scene 2: Generic dialogues (2 lines)
    assert len(mapped_scenes) == 2
    
    # Verify Scene 1 (Action)
    scene_action = mapped_scenes[0]
    assert scene_action["timestamp"] == "Action: Link meets Ilia"
    assert len(scene_action["bmg_texts"]) == 3
    assert scene_action["bmg_texts"][0] == "First dialogue of scene A"
    assert scene_action["bmg_texts"][2] == "Third dialogue of scene A"
    
    # Verify Scene 2 (Generic)
    scene_generic = mapped_scenes[1]
    assert scene_generic["timestamp"] == "Scene_3"
    assert len(scene_generic["bmg_texts"]) == 2
    assert scene_generic["bmg_texts"][0] == "Generic dialogue 1"
    assert scene_generic["bmg_texts"][1] == "Generic dialogue 2"


def test_mempalace_worker_mapping_only_saves_data():
    client = MagicMock()
    
    bmg_strings = ["Hello there!", "General Kenobi!"]
    bmg_ids = ["BMG_Str_0", "BMG_Str_1"]
    transcript_data = [
        {"text": "Hello there!", "speaker": "Obi-Wan", "timestamp": "00:01", "room": "RoomA"},
        {"text": "General Kenobi!", "speaker": "Grievous", "timestamp": "00:02", "room": "RoomA"}
    ]
    
    worker = MemePalaceWorker(
        client=client,
        bmg_strings=bmg_strings,
        bmg_ids=bmg_ids,
        transcript_data=transcript_data,
        wing_name="Zelda_TP",
        mapping_only=True
    )
    
    # We trigger the run method
    worker.run()
    
    # Verify that add_wing, add_room, and add_drawer were called during run on the mock client
    assert client.add_wing.called
    assert client.add_room.called
    assert client.add_drawer.called


def test_mempalace_client_cache_and_mapping(tmp_path):
    import sqlite3
    import json
    from core.mempalace_client import MemePalaceClient
    
    # 1. Create a temporary db file
    db_file = tmp_path / "mempalace_local.db"
    
    # Initialize client manually overriding db_path
    client = MemePalaceClient()
    client.db_path = str(db_file)
    client._init_local_db()
    
    # 2. Add some mock scenes, drawers, speakers
    wing_name = "Test_Wing"
    room_name = "Test_Room"
    drawer_name = "dialogue_verbatim"
    
    metadata = {
        "timestamp": "12:34",
        "speaker_map": {
            "BMG_Str_0": "MIDNA",
            "BMG_Str_1": "LINK"
        }
    }
    content = "BMG_Str_0: Hello Link!\nBMG_Str_1: Hi Midna!\nBMG_Str_2: System Message"
    
    # Write to local database
    client.add_drawer(wing_name, room_name, drawer_name, content, metadata)
    
    # Preload cache
    client.preload_cache(force=True)
    
    # 3. Test caching & instant lookup
    # A. Match by exact BMG ID
    ctx = client.get_cached_context("BMG_Str_0", "Hello Link!")
    assert ctx is not None
    assert ctx["room"] == "Test_Room"
    assert ctx["speaker"] == "MIDNA"
    assert ctx["timestamp"] == "12:34"
    
    # B. Match by bracketed BMG ID
    ctx = client.get_cached_context("[BMG_Str_1]", "Hi Midna!")
    assert ctx is not None
    assert ctx["speaker"] == "LINK"
    
    # C. Match by clean text (for duplicate / system message fallback)
    ctx = client.get_cached_context("BMG_Str_99", "System Message")
    assert ctx is not None
    assert ctx["room"] == "Test_Room"
    assert ctx["speaker"] is None
    
    # Clean text case insensitive
    ctx = client.get_cached_context("BMG_Str_99", "  SYSTEM MESSAGE  ")
    assert ctx is not None
    assert ctx["room"] == "Test_Room"


def test_mempalace_worker_keyword_overlap_matching():
    from unittest.mock import MagicMock
    client = MagicMock()
    
    # BMG string is long and has some words shortened/omitted compared to transcript (just like in Hyrule Castle scene)
    bmg_strings = [
        "In the {escape:255:000001}kingdom of Hyrule {escape:255:000000}there great {escape:255:000001}castle{escape:255:000000}, and around it is Town, a community far bigger than our little village. ...And far bigger than Hyrule is the rest of the world the gods created. You should look upon it all with your own eyes."
    ]
    bmg_ids = ["BMG_Str_1519"]
    
    # Transcript has it split into 3 distinct items with complete words: "there is a great", "Castle Town"
    transcript_data = [
        {
            "text": "In the kingdom of Hyrule there is a great castle, and around it is Castle Town, a community far bigger than our little village.",
            "speaker": "RUSL",
            "timestamp": "01:00",
            "room": "Chapter_I_Ordon"
        },
        {
            "text": "...And far bigger than Hyrule is the rest of the world the gods created.",
            "speaker": "RUSL",
            "timestamp": "01:05",
            "room": "Chapter_I_Ordon"
        },
        {
            "text": "You should look upon it all with your own eyes.",
            "speaker": "RUSL",
            "timestamp": "01:10",
            "room": "Chapter_I_Ordon"
        }
    ]
    
    worker = MemePalaceWorker(
        client=client,
        bmg_strings=bmg_strings,
        bmg_ids=bmg_ids,
        transcript_data=transcript_data,
        wing_name="Zelda_TP",
        mapping_only=True
    )
    
    mapped_scenes = worker._weave_strings()
    
    # We should have successfully mapped the items due to Keyword Overlap fallback!
    assert len(mapped_scenes) == 1
    scene = mapped_scenes[0]
    assert scene["room_name"] == "Chapter_I_Ordon"
    assert "BMG_Str_1519" in scene["bmg_ids"]


def test_mempalace_worker_target_lang_and_glossary_prompt():
    from unittest.mock import MagicMock
    from core.glossary_manager import GlossaryEntry
    
    client = MagicMock()
    client.has_room.return_value = False
    ai_provider = MagicMock()
    
    # Mock AI Provider response
    mock_response = MagicMock()
    mock_response.text = '{"visual_context": "Тест сцени", "relations": [], "speaker_map": {}}'
    ai_provider.translate.return_value = mock_response
    
    bmg_strings = ["Hello Rusl"]
    bmg_ids = ["BMG_Str_0"]
    
    transcript_data = [{
        "text": "Hello Rusl",
        "speaker": "RUSL",
        "timestamp": "01:00",
        "room": "Chapter_I"
    }]
    
    # Mock GlossaryEntry
    glossary_entries = [
        GlossaryEntry(original="Rusl", translation="Руслан", notes="Character"),
        GlossaryEntry(original="Midna", translation="Мідна", notes="Unrelated")
    ]
    
    worker = MemePalaceWorker(
        client=client,
        bmg_strings=bmg_strings,
        bmg_ids=bmg_ids,
        transcript_data=transcript_data,
        ai_provider=ai_provider,
        wing_name="Zelda_TP",
        mapping_only=False,
        target_lang="Ukrainian",
        glossary_entries=glossary_entries
    )
    
    mapped_scenes = worker._weave_strings()
    assert len(mapped_scenes) == 1
    
    # Run _generate_palace_via_llm which triggers translate
    worker._generate_palace_via_llm(mapped_scenes)
    
    # Verify AI was called and the prompt has Ukrainian instructions and Glossary injected
    assert ai_provider.translate.called
    args, kwargs = ai_provider.translate.call_args
    messages = args[0]
    
    # Check that prompt has Ukrainian instructions and Glossary entry
    user_content = next(m["content"] for m in messages if m["role"] == "user")
    assert "GLOSSARY FOR TERMINOLOGY" in user_content
    assert "Rusl" in user_content
    assert "Руслан" in user_content
    assert "Midna" not in user_content
    assert "Мідна" not in user_content
    assert "Ukrainian" in user_content


def test_mempalace_client_cache_mtime_invalidation(tmp_path):
    import os
    import time
    from core.mempalace_client import MemePalaceClient
    
    db_file = tmp_path / "mempalace_local.db"
    
    # 1. Initialize client
    client = MemePalaceClient()
    client.db_path = str(db_file)
    client._init_local_db()
    
    # 2. Add initial drawer
    wing_name = "Test_Wing"
    room_name = "Test_Room"
    drawer_name = "dialogue_verbatim"
    
    metadata = {
        "timestamp": "10:00",
        "speaker_map": {
            "BMG_Str_0": "FIRST SPEAKER"
        }
    }
    content = "BMG_Str_0: Hello!"
    client.add_drawer(wing_name, room_name, drawer_name, content, metadata)
    
    # Preload cache
    client.preload_cache()
    
    # Verify cached value is correct
    ctx = client.get_cached_context("BMG_Str_0", "Hello!")
    assert ctx is not None
    assert ctx["speaker"] == "FIRST SPEAKER"
    
    # Wait a tiny bit to ensure mtime changes if we overwrite the DB file in a separate connection/client simulation
    time.sleep(0.01)
    
    # 3. Simulate another connection modifying the database by creating a new client instance and writing to it
    another_client = MemePalaceClient()
    another_client.db_path = str(db_file)
    
    metadata_updated = {
        "timestamp": "11:00",
        "speaker_map": {
            "BMG_Str_0": "UPDATED SPEAKER"
        }
    }
    another_client.add_drawer(wing_name, room_name, drawer_name, content, metadata_updated)
    
    # Verify the original client automatically reloads and sees the update because the DB file mtime has changed!
    ctx_updated = client.get_cached_context("BMG_Str_0", "Hello!")
    assert ctx_updated is not None
    assert ctx_updated["speaker"] == "UPDATED SPEAKER"




