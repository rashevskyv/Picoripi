import json
from core.translation.ai_error_handler import handle_ai_error
from core.translation.providers import TranslationProviderError

def test_handle_ai_error_json_decode():
    task_details = {"type": "translate_single", "block_idx": 5}
    exc = json.JSONDecodeError("Expecting value", "{}", 0)
    
    msg, details = handle_ai_error(exc, task_details, response_text="bad response", context_info="test context")
    
    assert "Failed to parse AI response as JSON" in msg
    assert details["raw_response_text"] == "bad response"
    assert details["type"] == "translate_single"

def test_handle_ai_error_provider_exception():
    task_details = {"type": "chat_message"}
    exc = TranslationProviderError("API Key is missing")
    
    msg, details = handle_ai_error(exc, task_details, response_text=None)
    
    assert msg == "API Key is missing"
    assert details["raw_response_text"] == ""

def test_handle_ai_error_value_error():
    task_details = {"type": "fill_glossary"}
    exc = ValueError("Invalid inputs")
    
    msg, details = handle_ai_error(exc, task_details)
    
    assert "Value error during AI operation" in msg
    assert "Invalid inputs" in msg

def test_handle_ai_error_generic_exception():
    task_details = {"type": "classify_suggest_types"}
    exc = Exception("Connection lost")
    
    msg, details = handle_ai_error(exc, task_details)
    
    assert "Unexpected error: Connection lost" in msg
