import pytest
from unittest.mock import MagicMock
from handlers.translation.ai_prompt_composer import AIPromptComposer
from core.glossary_manager import GlossaryEntry

@pytest.fixture
def composer():
    mw = MagicMock()
    mw.data_store = mw
    main_handler = MagicMock()
    # Mocking current_game_rules to avoid errors in __init__?
    # Actually AIPromptComposer inherits from BaseTranslationHandler
    # which takes main_handler and mw is accessed via main_handler.mw
    main_handler.mw = mw
    composer = AIPromptComposer(main_handler)
    return composer

def test_AIPromptComposer_glossary_entries_to_text(composer):
    entries = [
        GlossaryEntry("Sword", "Меч", "Weapon"),
        GlossaryEntry("Shield", "Щит", "Armor")
    ]
    output = composer._glossary_entries_to_text(entries)
    assert "| Original | Translation | Notes |" in output
    assert "| Sword | Меч | Weapon |" in output
    assert "| Shield | Щит | Armor |" in output

def test_AIPromptComposer_compose_batch_request_context(composer):
    all_items = [
        {"id": 0, "text": "Hello"},
        {"id": 1, "text": "World"},
        {"id": 2, "text": "Goodbye"}
    ]
    source_items = [{"id": 1, "text": "World"}]

    # Mock glossary manager
    composer.main_handler._glossary_manager = MagicMock()
    composer.main_handler._glossary_manager.get_relevant_terms.return_value = []

    composer.mw.current_game_rules.get_display_name.return_value = "Test Game"
    composer.mw.data_store.block_names = {"0": "Block 0"}

    system, user, pmap = composer.compose_batch_request(
        "SysPrompt", source_items, all_items, block_idx=0, mode_description="TestMode"
    )

    assert "World" in user # current text
    assert "Test Game" in user
    assert "Block 0" in user

def test_AIPromptComposer_prepare_glossary_for_prompt_full(composer):
    gm = MagicMock()
    gm.get_entries.return_value = [GlossaryEntry("Term", "Тлумач", "")]
    gm.get_session_changes.return_value = {}
    composer.main_handler._glossary_manager = gm

    session_state = MagicMock()
    session_state.glossary_sent = False

    prompt = composer._prepare_glossary_for_prompt("Base", session_state)
    assert prompt == "Base"  # Now returns system_prompt as-is for glossary unification

def test_AIPromptComposer_prepare_glossary_for_prompt_updates(composer):
    gm = MagicMock()
    updated_entry = GlossaryEntry("New", "Новий", "Note")
    gm.get_session_changes.return_value = {"New": updated_entry, "Deleted": None}
    composer.main_handler._glossary_manager = gm

    session_state = MagicMock()
    session_state.glossary_sent = True # Already sent once

    prompt = composer._prepare_glossary_for_prompt("Base", session_state)
    assert prompt == "Base"  # Now returns system_prompt as-is for glossary unification

def test_AIPromptComposer_restore_placeholders(composer):
    # Setup normal tag mappings
    composer.mw.default_tag_mappings = {"{L-Stick}": "{escape:3:0009}"}

    # 1. Test restoring normal tag aliases
    translated = "натисни {L-Stick}, щоб дати знак!"
    res = composer.restore_placeholders(translated, placeholder_map=None, key=None)
    assert res == "натисни {escape:3:0009}, щоб дати знак!"

    # 2. Test case-insensitivity of normal tag aliases
    translated_lower = "натисни {l-stick}, щоб дати знак!"
    res_lower = composer.restore_placeholders(translated_lower, placeholder_map=None, key=None)
    assert res_lower == "натисни {escape:3:0009}, щоб дати знак!"


def test_AIPromptComposer_compose_batch_request_chapter(composer):
    all_items = [{"id": 0, "text": "Hello, world!"}]
    source_items = [{"id": 0, "text": "Hello, world!"}]
    temp_id_map = {0: (3, 5)} # temp_id 0 corresponds to block 3, string 5

    composer.main_handler._glossary_manager = MagicMock()
    composer.main_handler._glossary_manager.get_relevant_terms.return_value = []

    composer.mw.current_game_rules.get_display_name.return_value = "Zelda: TP"
    composer.mw.project_manager = None

    # Configure mock data_store
    data_store = MagicMock()
    data_store.block_names = {"3": "Block 3", "-2": "Chapter 2"}
    composer.mw.data_store = data_store

    # Mock script path and file opening so _find_speaker_in_script resolves speaker
    composer._find_script_path = MagicMock(return_value="/dummy/script.txt")
    composer.script_speaker_finder.find_script_path = composer._find_script_path

    import os
    original_exists = os.path.exists
    def mock_exists(path):
        if path == "/dummy/script.txt":
            return True
        return original_exists(path)

    import builtins
    original_open = builtins.open
    def mock_open(file, *args, **kwargs):
        if str(file) == "/dummy/script.txt":
            from unittest.mock import mock_open as m_open
            # _find_speaker_in_script:
            # Line index 5 is line 6. But let's check:
            # 1. Direct DB mapping is not used here (client returns None or does not map).
            # 2. Distilled query fallback will read Cp1252.
            # Let's provide a file where the speaker is RUSL on line 2, and text matches on line 3.
            # If line 3 is "Hello, world!", len(re.findall('\w+', text)) = 2.
            # In _find_speaker_in_script:
            # distilled_query = "helloworld"
            # search_query = "helloworld"
            # It matches on line 3, line_num = 3.
            # It scans backwards from line 2 to find uppercase speaker "RUSL".
            file_content = "[Metadata]\nRUSL\nHello, world!\n"
            return m_open(read_data=file_content)()
        return original_open(file, *args, **kwargs)

    from unittest.mock import patch
    with patch("os.path.exists", mock_exists), patch("builtins.open", mock_open):
        system, user, pmap = composer.compose_batch_request(
            "SysPrompt",
            source_items,
            all_items,
            block_idx=-2,
            mode_description="ChapterMode",
            temp_id_map=temp_id_map
        )

    assert "Hello, world!" in user
    assert "Zelda: TP" in user
    assert "Chapter 2" in user
    # Check that speaker was successfully resolved to RUSL!
    assert '"speaker": "RUSL"' in user


def test_AIPromptComposer_script_cache_invalidation(composer, tmp_path):
    import os
    # Create a dummy script file
    script_file = tmp_path / "test_script.txt"
    script_file.write_text("RUSL\nHello, world!\n", encoding="utf-8")

    # Mock self._find_script_path to return our temp script
    composer._find_script_path = MagicMock(return_value=str(script_file))
    composer.script_speaker_finder.find_script_path = composer._find_script_path

    # Set display name for game rules
    composer.mw.current_game_rules = MagicMock()
    composer.mw.current_game_rules.get_display_name.return_value = "Zelda: MC"
    composer.mw.data_store = MagicMock()
    composer.mw.data_store.data = [["Hello, world!"]]

    # First search should cache files and properties
    res1 = composer._find_speaker_in_script(block_idx=0, s_idx=0, text="Hello, world!")
    assert res1 is not None
    assert res1[0] == "RUSL"

    cached_path = composer._cached_script_path
    cached_mtime = composer._cached_mtime
    cached_size = composer._cached_size
    cached_plugin = composer._cached_plugin_name

    assert cached_path == str(script_file)
    assert cached_mtime > 0
    assert cached_size > 0
    assert cached_plugin == "Zelda: MC"
    assert composer._script_lines_cache is not None

    # Second search should hit cache directly without reloading (script_lines_cache should be the same object)
    old_cache = composer._script_lines_cache
    res2 = composer._find_speaker_in_script(block_idx=0, s_idx=0, text="Hello, world!")
    assert res2[0] == "RUSL"
    assert composer._script_lines_cache is old_cache

    # Case 1: Invalidation by size/content change (modifying size)
    script_file.write_text("RUSL\nHello, world!\nLine extra to increase size.\n", encoding="utf-8")
    res3 = composer._find_speaker_in_script(block_idx=0, s_idx=0, text="Hello, world!")
    assert composer._cached_size != cached_size

    # Case 2: Invalidation by plugin change
    composer.mw.current_game_rules.get_display_name.return_value = "Zelda: WW"
    res4 = composer._find_speaker_in_script(block_idx=0, s_idx=0, text="Hello, world!")
    assert composer._cached_plugin_name == "Zelda: WW"
