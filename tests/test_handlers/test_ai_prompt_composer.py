import pytest
from unittest.mock import MagicMock
from handlers.translation.ai_prompt_composer import AIPromptComposer
from core.glossary_manager import GlossaryEntry


@pytest.fixture
def composer():
    mw = MagicMock()
    mw.data_store = mw
    main_handler = MagicMock()
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

    assert "World" in user  # current text
    assert "Test Game" in user
    assert "Block 0" in user


def test_batch_prompt_uses_manual_speaker_for_unlinked_system_row(composer):
    block = MagicMock()
    block.metadata = {
        "story_context_assignments": {"3": {
            "speaker": "System",
            "structure_id": 30,
            "structure_path": ["Act One", "Memory Card"],
            "item": "Save UI",
        }}
    }
    composer.mw.project_manager.project.blocks = [block]
    composer.mw.block_to_project_file_map = {0: 0}
    composer.mw.current_game_rules.get_display_name.return_value = "Test Game"
    composer.mw.data_store.block_names = {"0": "Block 0"}
    composer.main_handler._glossary_manager = MagicMock()
    composer.main_handler._glossary_manager.get_relevant_terms.return_value = []
    composer._get_mempalace_client = MagicMock(return_value=None)
    composer._find_speaker_in_script = MagicMock()

    _, user, _ = composer.compose_batch_request(
        "SysPrompt",
        [{"id": 3, "text": "Checking Memory Card in slot A."}],
        [{"id": 3, "text": "Checking Memory Card in slot A."}],
        block_idx=0,
        mode_description="TestMode",
    )

    assert '"speaker": "System"' in user
    assert '"story_structure": "Act One > Memory Card"' in user
    assert '"reference_item": "Save UI"' in user
    composer._find_speaker_in_script.assert_not_called()


def test_batch_prompt_carries_boss_name_window_context(composer):
    composer.mw.current_game_rules.get_display_name.return_value = "Test Game"
    composer.mw.current_game_rules.get_translation_context_for_string.return_value = {
        "window_type": "Boss name",
        "content_role": "BossName",
        "glossary_section": "Boss Names",
        "force_glossary": True,
    }
    composer.mw.data_store.block_names = {"0": "Block 0"}
    composer.main_handler._glossary_manager = MagicMock()
    composer.main_handler._glossary_manager.get_relevant_terms.return_value = []
    composer._find_speaker_in_script = MagicMock()

    _, user, _ = composer.compose_batch_request(
        "SysPrompt",
        [{"id": 5, "text": "Twilit Parasite\nDIABABA"}],
        [{"id": 5, "text": "Twilit Parasite\nDIABABA"}],
        block_idx=0,
        mode_description="translation",
    )

    assert '"window_type": "Boss name"' in user
    assert '"content_role": "BossName"' in user
    assert '"speaker": "NONE"' in user
    assert "standalone in-game boss title/name card" in user
    composer._find_speaker_in_script.assert_not_called()


def test_zelda_bmg_runtime_names_are_plain_words_in_ai_prompts(composer):
    from plugins.zelda_bmg.rules import GameRules

    composer.mw.current_game_rules = GameRules(None)
    composer.mw.default_tag_mappings = {}
    composer.mw.project_manager = None
    composer.main_handler._glossary_manager = MagicMock()
    composer.main_handler._glossary_manager.get_relevant_terms.return_value = []

    raw = "Hello {escape:0:0000} and {escape:0:0022} {escape:0:0001}"
    _, single_user = composer.compose_messages(
        "Translate into {target_lang}.", raw,
        block_idx=None, string_idx=None, expected_lines=1,
        mode_description="translation", request_type="translation",
    )
    _, batch_user, _ = composer.compose_batch_request(
        "Translate into {target_lang}.",
        [{"id": 0, "text": raw}], [{"id": 0, "text": raw}],
        block_idx=None, mode_description="translation",
    )

    for prompt in (single_user, batch_user):
        assert "Hello Link and Epona" in prompt
        assert "{escape:0:0000}" not in prompt
        assert "{escape:0:0022}" not in prompt
        assert "{escape:0:0001}" in prompt

    _, glossary_user = composer.compose_glossary_occurrence_update_request(
        "Update {target_lang} text.",
        source_text="Current Link", current_translation="Current Link",
        original_text=raw, term="Link", old_translation="Link",
        new_translation="Лінк", expected_lines=1,
    )
    assert "Hello Link and Epona" in glossary_user
    assert "{escape:0:0000}" not in glossary_user
    assert "{escape:0:0022}" not in glossary_user


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
    session_state.glossary_sent = True  # Already sent once

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
    temp_id_map = {0: (3, 5)}  # temp_id 0 corresponds to block 3, string 5

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


def test_non_default_target_language_resolution(composer):
    composer.mw.target_language = "Spanish"

    # Mock dependencies
    composer.main_handler._glossary_manager = MagicMock()
    composer.main_handler._glossary_manager.get_relevant_terms.return_value = []
    composer.mw.current_game_rules.get_display_name.return_value = "Test Game"
    composer.mw.data_store.block_names = {"0": "Block 0"}

    # 1. Batch translation request
    system, user, pmap = composer.compose_batch_request(
        "Translate Ukrainian term to Spanish in this test.",
        [{"id": 1, "text": "World"}],
        [{"id": 1, "text": "World"}],
        block_idx=0,
        mode_description="TestMode"
    )
    # The helper replaces "Ukrainian" with target_language ("Spanish")
    assert "Spanish" in system
    assert "Ukrainian" not in system
    assert "Spanish" in user
    assert "Ukrainian" not in user

    # 2. Single translation request
    system_single, user_single = composer.compose_messages(
        "Translate this Ukrainian sentence.",
        "Hello world",
        block_idx=0,
        string_idx=0,
        expected_lines=1,
        mode_description="Translate",
        request_type="translation"
    )
    assert "Spanish" in system_single
    assert "Ukrainian" not in system_single
    assert "Spanish" in user_single
    # "Ukrainian" should not be in the instructions
    assert "Ukrainian" not in user_single

    # 3. Variations request
    system_var, user_var = composer.compose_messages(
        "Translate this Ukrainian sentence.",
        "Hello world",
        block_idx=0,
        string_idx=0,
        expected_lines=1,
        mode_description="Variations",
        request_type="variation_list"
    )
    assert "Spanish" in system_var
    assert "Ukrainian" not in system_var
    assert "Spanish" in user_var
    assert "Ukrainian" not in user_var

    # 4. Glossary occurrence update request
    system_occ, user_occ = composer.compose_glossary_occurrence_update_request(
        "Update Ukrainian glossary term.",
        source_text="Hola",
        current_translation="Hola",
        original_text="Hello",
        term="Hello",
        old_translation="Hola",
        new_translation="Hola",
        expected_lines=1
    )
    assert "Spanish" in system_occ
    assert "Ukrainian" not in system_occ
    assert "Spanish" in user_occ
    assert "Ukrainian" not in user_occ

    # 5. Glossary occurrence batch request
    system_batch, user_batch = composer.compose_glossary_occurrence_batch_request(
        "Update Ukrainian glossary batch.",
        term="Hello",
        old_translation="Hola",
        new_translation="Hola",
        batch_items=[{"id": "0", "translation": "Hola"}]
    )
    assert "Spanish" in system_batch
    assert "Ukrainian" not in system_batch
    assert "Spanish" in user_batch
    assert "Ukrainian" not in user_batch


def test_story_context_manager_spanish_relations():
    from core.translation.story_context_manager import StoryContextManager
    mw = MagicMock()
    mw.target_language = "Spanish"
    mw.data_store = MagicMock()
    mw.data_store.block_names = {}

    # Mock MemePalaceClient and its relations
    client_mock = MagicMock()
    client_mock.get_cached_context.return_value = {
        "room": "Room_0",
        "speaker": "Hero",
        "timestamp": "12:00"
    }
    client_mock.get_relations.return_value = [
        {"source": "Hero", "relation": "friend", "target": "Princess"}
    ]

    scm = StoryContextManager(mw)
    scm.get_mempalace_client = MagicMock(return_value=client_mock)
    scm.get_block_label = MagicMock(return_value="Block_0")

    context = scm.fetch_story_context(
        block_idx=0,
        s_idx=0,
        text="Hello Princess",
        script_speaker_finder=None,
        data_processor=None
    )

    assert "CHARACTER & STORY RELATIONS (Spanish Grammar Priority):" in context
    assert "Spanish" in context
    assert "Ukrainian" not in context
    assert "Hero -[friend]-> Princess" in context


def test_translation_session_history_compression_spanish():
    from core.translation.session_manager import TranslationSessionState

    session = TranslationSessionState(
        provider_key="test_provider",
        base_system_prompt="Base",
        current_system_prompt="Current",
        target_lang="Spanish"
    )

    # Add dummy history to exceed MAX_HISTORY_MESSAGES * 2 (which is 40 messages)
    for i in range(25):
        session.history.append({"role": "user", "content": f"Hello {i}"})
        session.history.append({"role": "assistant", "content": f"Hola {i}"})

    provider_mock = MagicMock()
    # Mock provider.translate to verify the compression prompt has Spanish
    def mock_translate(messages):
        # Find the system message in the compression request
        sys_msg = next(msg["content"] for msg in messages if msg["role"] == "system")
        assert "Spanish" in sys_msg
        assert "Ukrainian" not in sys_msg

        response = MagicMock()
        response.text = "Compressed summary of style and context"
        return response

    provider_mock.translate = mock_translate

    session.compress_history(provider_mock)

    # Verify that the history was compressed down
    assert len(session.history) < 50
    assert session.history[0]["role"] == "system"
    assert "Style and context summary" in session.history[0]["content"]


def test_global_settings_target_language_serialization(tmp_path):
    from core.settings.global_settings import GlobalSettings

    class LocalMockMainWindow:
        def __init__(self):
            self.data_store = self
            self.hide_empty_strings = False
            self.active_game_plugin = "zelda_mc"
            self.current_font_size = 10
            self.theme = "auto"
            self.restore_unsaved_on_startup = False
            self.show_multiple_spaces_as_dots = True
            self.space_dot_color_hex = "#BBBBBB"
            self.window_was_maximized_on_close = False
            self.window_normal_geometry_on_close = None
            self.prompt_editor_enabled = True
            self.recent_projects = []
            self.translation_ai = {}
            self.glossary_ai = {}
            self.spellchecker_enabled = False
            self.spellchecker_language = 'uk'
            self.last_browse_dir = ""
            self.enable_console_logging = True
            self.enable_file_logging = True
            self.settings_window_width = 800
            self.log_file_path = ""
            self.enabled_log_categories = []
            self.edited_data = {}
            self.json_path = None
            self.edited_json_path = None
            self.main_splitter = None
            self.right_splitter = None
            self.bottom_right_splitter = None
            self.ui_updater = MagicMock()
            self.statusBar = MagicMock()

    mw = LocalMockMainWindow()
    mw.target_language = "Spanish"

    settings_file = tmp_path / "settings.json"
    gs = GlobalSettings(mw, settings_file_path=str(settings_file))
    settings_dict = {}
    gs.save(settings_dict)

    # Read settings file to assert value is correct
    import json
    with open(str(settings_file), "r", encoding="utf-8") as f:
        loaded_data = json.load(f)
    assert loaded_data.get("target_language") == "Spanish"


def test_mempalace_chapter_ai_analyzer_worker_target_language():
    from core.mempalace.chapter_ai_analyzer import MemePalaceChapterAIAnalyzerWorker
    client = MagicMock()
    ai_provider = MagicMock()

    worker = MemePalaceChapterAIAnalyzerWorker(
        client=client,
        ai_provider=ai_provider,
        chapter_id=1,
        num="1",
        title="Intro",
        content="Line 1\nLine 2",
        start_line=1,
        target_lang="Spanish"
    )

    # Mock ai_provider.translate to capture prompts
    captured_messages = []
    def mock_translate(messages, session=None):
        nonlocal captured_messages
        captured_messages = messages
        resp = MagicMock()
        resp.text = "[]"
        return resp

    ai_provider.translate = mock_translate

    # Call run synchronously
    worker.run()

    # Assert
    assert len(captured_messages) == 2
    system_msg = captured_messages[0]["content"]
    user_msg = captured_messages[1]["content"]

    # Verify Spanish is requested and summary_translated is requested
    assert "Spanish" in user_msg
    assert "Ukrainian" not in user_msg
    assert "summary_translated" in system_msg


def test_resolved_defaults_prompts_have_no_cyrillic(composer):
    import json
    import re
    from pathlib import Path
    from utils.utils import resolve_target_language_prompt

    cyrillic_pattern = re.compile(r"[а-яА-ЯіїІїЄєґҐёЁ]")

    # 1. Check plugins/common/defaults/prompts.json
    defaults_path = Path("plugins") / "common" / "defaults" / "prompts.json"
    assert defaults_path.exists()

    with open(defaults_path, "r", encoding="utf-8") as f:
        prompts = json.load(f)

    # System translation prompt
    sys_prompt = prompts["translation"]["system_prompt"]
    resolved_sys = resolve_target_language_prompt(sys_prompt, "Spanish")
    assert not cyrillic_pattern.search(resolved_sys), f"Cyrillic characters found in resolved defaults system prompt: {cyrillic_pattern.findall(resolved_sys)}"

    # Glossary prompt template
    glossary_template = prompts["glossary"]["prompt_template"]
    resolved_glossary = resolve_target_language_prompt(glossary_template, "Spanish")
    assert not cyrillic_pattern.search(resolved_glossary)

    # Glossary occurrence update system prompt
    occ_sys = prompts["glossary_occurrence_update"]["system_prompt"]
    resolved_occ = resolve_target_language_prompt(occ_sys, "Spanish")
    assert not cyrillic_pattern.search(resolved_occ)

    # 2. Check translation_prompts/prompts.json
    proj_prompts_path = Path("translation_prompts") / "prompts.json"
    if proj_prompts_path.exists():
        with open(proj_prompts_path, "r", encoding="utf-8") as f:
            proj_prompts = json.load(f)
        resolved_proj_sys = resolve_target_language_prompt(proj_prompts["translation"]["system_prompt"], "Spanish")
        assert not cyrillic_pattern.search(resolved_proj_sys), f"Cyrillic characters found in resolved project system prompt: {cyrillic_pattern.findall(resolved_proj_sys)}"

    # 3. Check translation_prompts/glossary_builder_prompts.json
    builder_prompts_path = Path("translation_prompts") / "glossary_builder_prompts.json"
    if builder_prompts_path.exists():
        with open(builder_prompts_path, "r", encoding="utf-8") as f:
            builder_prompts = json.load(f)
        resolved_builder_sys = resolve_target_language_prompt(builder_prompts["system_prompt"], "Spanish")
        resolved_builder_user = resolve_target_language_prompt(builder_prompts["user_prompt_template"], "Spanish")
        assert not cyrillic_pattern.search(resolved_builder_sys), f"Cyrillic characters found in resolved builder system prompt: {cyrillic_pattern.findall(resolved_builder_sys)}"
        assert not cyrillic_pattern.search(resolved_builder_user), f"Cyrillic characters found in resolved builder user prompt: {cyrillic_pattern.findall(resolved_builder_user)}"

    # 4. Check plugins/zelda_mc/translation_prompts/prompts.json
    mc_prompts_path = Path("plugins") / "zelda_mc" / "translation_prompts" / "prompts.json"
    if mc_prompts_path.exists():
        with open(mc_prompts_path, "r", encoding="utf-8") as f:
            mc_prompts = json.load(f)
        resolved_mc_sys = resolve_target_language_prompt(mc_prompts["translation"]["system_prompt"], "Spanish")
        assert not cyrillic_pattern.search(resolved_mc_sys), f"Cyrillic characters found in resolved Minish Cap system prompt: {cyrillic_pattern.findall(resolved_mc_sys)}"


def test_AIPromptComposer_tag_alias_legend_and_newlines(composer):
    # Setup tag mappings
    composer.mw.default_tag_mappings = {
        "{Color:Red}": "{0}",
        "{f:dummy}": "forced"
    }

    composer.main_handler._glossary_manager = MagicMock()
    composer.main_handler._glossary_manager.get_relevant_terms.return_value = []
    composer.mw.current_game_rules.get_display_name.return_value = "Test Game"
    composer.mw.data_store.block_names = {"0": "Block 0"}

    # Test compose_batch_request preserves newlines and collects tag_alias_legend
    source_items = [{"id": 0, "text": "Line1\nLine2"}]
    all_items = [{"id": 0, "text": "Line1\nLine2"}]

    system, user, pmap = composer.compose_batch_request(
        "SysPrompt", source_items, all_items, block_idx=0, mode_description="TestMode"
    )

    # Check that newlines are preserved in the JSON payload sent to AI
    assert "Line1\\nLine2" in user or "Line1\nLine2" in user

    # Check that forced alias {f:dummy} was excluded but {Color:Red} was included
    assert "tag_alias_legend" in user
    assert "{Color:Red}" in user
    assert "{f:dummy}" not in user
    assert "TAG ALIAS LEGEND" in user
    assert "ANCHORED TAGS" in user

    # Test compose_messages collects tag_alias_legend
    system_msg, user_msg = composer.compose_messages(
        "SysPrompt",
        "Line1\nLine2",
        block_idx=0,
        string_idx=0,
        expected_lines=2,
        mode_description="TestMode",
        request_type="translation"
    )

    assert "TAG ALIAS LEGEND" in user_msg
    assert "{Color:Red}" in user_msg
    assert "{f:dummy}" not in user_msg
