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
