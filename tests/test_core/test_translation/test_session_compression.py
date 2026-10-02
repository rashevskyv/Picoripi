from unittest.mock import MagicMock
from core.translation.session_manager import TranslationSessionState
from core.translation.providers import ProviderResponse

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

