from unittest.mock import MagicMock
from core.translation.session_manager import TranslationSessionState
from core.translation.providers import ProviderResponse
from handlers.translation.ai_prompt_composer import AIPromptComposer

def test_session_state_no_compression_under_limit():
    state = TranslationSessionState(
        provider_key="openai",
        base_system_prompt="system",
        current_system_prompt="system"
    )
    mock_provider = MagicMock()
    
    # Under limit (20 messages, i.e. 10 pairs)
    state.history = [{"role": "user", "content": "hi"}] * 10
    state.compress_history(mock_provider)
    
    assert len(state.history) == 10
    mock_provider.translate.assert_not_called()

def test_session_state_compression_triggered():
    state = TranslationSessionState(
        provider_key="openai",
        base_system_prompt="system",
        current_system_prompt="system"
    )
    
    mock_provider = MagicMock()
    mock_response = ProviderResponse(text="This is a summary of the tone and style.")
    mock_provider.translate.return_value = mock_response
    
    # Fill history up to limit + 2 messages (exceeding limit)
    # MAX_HISTORY_MESSAGES is 20, limit to trigger is MAX_HISTORY_MESSAGES * 2 = 40
    state.history = []
    for i in range(21):
        state.history.append({"role": "user", "content": f"user {i}"})
        state.history.append({"role": "assistant", "content": f"ai {i}"})
        
    assert len(state.history) == 42
    
    state.compress_history(mock_provider)
    
    # First half of history (20 messages) should be compressed into 1 system message,
    # leaving 1 summary + 22 remaining messages = 23 total.
    assert len(state.history) == 23
    assert state.history[0]["role"] == "system"
    assert "Style and context summary" in state.history[0]["content"]
    assert "This is a summary" in state.history[0]["content"]
    
    # Check that translate was called with the history
    mock_provider.translate.assert_called_once()
    sent_messages = mock_provider.translate.call_args[0][0]
    assert sent_messages[0]["role"] == "system"
    assert "Summarize the style" in sent_messages[0]["content"]
    assert "USER: user 0" in sent_messages[1]["content"]

def test_session_state_compression_fallback_on_error():
    state = TranslationSessionState(
        provider_key="openai",
        base_system_prompt="system",
        current_system_prompt="system"
    )
    
    mock_provider = MagicMock()
    mock_provider.translate.side_effect = Exception("API error")
    
    # Exceed limit
    for i in range(21):
        state.history.append({"role": "user", "content": f"user {i}"})
        state.history.append({"role": "assistant", "content": f"ai {i}"})
        
    state.compress_history(mock_provider)
    
    # Should fallback to truncating the first 20 messages, leaving 22
    assert len(state.history) == 22
    assert state.history[0]["content"] == "user 10"

def test_lookahead_glossary_prompt_composer():
    class MockMainWindow:
        def __init__(self):
            self.current_game_rules = None
            self.active_game_rules = None
            class MockDataStore:
                def __init__(self):
                    self.block_names = {}
                    self.json_path = "main.json"
                    self.data = [[]]
            self.data_store = MockDataStore()
            self.project_manager = None
            
    class MockMainHandler:
        def __init__(self, mw):
            self.mw = mw
            self.data_processor = None
            self.ui_updater = None
            class MockGlossaryManager:
                def __init__(self):
                    self.terms_checked = []
                def get_relevant_terms(self, text):
                    self.terms_checked.append(text)
                    return []
                def get_entries(self):
                    return []
            self._glossary_manager = MockGlossaryManager()

    mw = MockMainWindow()
    main_handler = MockMainHandler(mw)
    composer = AIPromptComposer(main_handler=main_handler)

    source_items = [{"id": 0, "text": "Hello world"}]
    all_source_items = []
    # Build list of 100 items to check lookahead limit (60)
    for i in range(100):
        all_source_items.append({"id": i, "text": f"Line {i} text"})

    # Set the first item of source_items to be part of all_source_items
    source_items = [all_source_items[0]]

    # Run compose_batch_request
    composer.compose_batch_request(
        system_prompt="system",
        source_items=source_items,
        all_source_items=all_source_items,
        block_idx=0,
        mode_description="test"
    )

    # Verify that get_relevant_terms was called with lookahead text
    # consisting of the first 60 lines
    checked_text = main_handler._glossary_manager.terms_checked[0]
    assert "Line 0 text" in checked_text
    assert "Line 59 text" in checked_text
    assert "Line 60 text" not in checked_text
