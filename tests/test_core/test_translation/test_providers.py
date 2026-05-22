import pytest
from unittest.mock import MagicMock, patch
import requests
from core.translation.providers import OpenAIProvider, TranslationProviderError, ProviderResponse

def test_openai_provider_init_default_url_requires_key():
    # Default URL, no key -> raises error
    with pytest.raises(TranslationProviderError, match="OpenAI API key is not set"):
        OpenAIProvider({
            "endpoint": "https://api.openai.com/v1",
            "model": "gpt-4o"
        })

    # Default URL, empty endpoint -> raises error
    with pytest.raises(TranslationProviderError, match="OpenAI API key is not set"):
        OpenAIProvider({
            "endpoint": "",
            "model": "gpt-4o"
        })

def test_openai_provider_init_custom_url_allows_no_key():
    # Custom URL, no key -> succeeds
    provider = OpenAIProvider({
        "endpoint": "http://localhost:20128/v1",
        "model": "kr/claude-sonnet-4.5"
    })
    assert provider.base_url == "http://localhost:20128/v1"
    assert provider.model == "kr/claude-sonnet-4.5"
    assert provider.api_key is None

@patch('core.translation.providers.requests.post')
def test_openai_provider_translate_success(mock_post):
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.headers = {"content-type": "application/json"}
    mock_resp.json.return_value = {
        "id": "chatcmpl-123",
        "choices": [{
            "message": {
                "role": "assistant",
                "content": "Hello translated"
            }
        }]
    }
    mock_post.return_value = mock_resp

    provider = OpenAIProvider({
        "endpoint": "http://localhost:20128/v1",
        "model": "kr/claude-sonnet-4.5",
        "api_key": "some-key"
    })
    res = provider.translate([{"role": "user", "content": "Hello"}])
    assert res.text == "Hello translated"
    assert res.message_id == "chatcmpl-123"

@patch('core.translation.providers.requests.post')
def test_openai_provider_translate_non_json(mock_post):
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.headers = {"content-type": "application/json"}
    mock_resp.text = "Missing bearer token in the authorization header."
    mock_resp.json.side_effect = ValueError("Expecting value")
    mock_post.return_value = mock_resp

    provider = OpenAIProvider({
        "endpoint": "http://localhost:20128/v1",
        "model": "kr/claude-sonnet-4.5",
        "api_key": "some-key"
    })
    with pytest.raises(TranslationProviderError, match="API returned non-JSON response.*Missing bearer token"):
        provider.translate([{"role": "user", "content": "Hello"}])

@patch('core.translation.providers.requests.post')
def test_openai_provider_translate_request_fail(mock_post):
    mock_resp = MagicMock()
    mock_resp.raise_for_status.side_effect = requests.RequestException("Connection refused")
    mock_resp.text = "Error detail"
    mock_post.return_value = mock_resp

    provider = OpenAIProvider({
        "endpoint": "http://localhost:20128/v1",
        "model": "kr/claude-sonnet-4.5"
    })
    with pytest.raises(TranslationProviderError, match="API request failed: Connection refused"):
        provider.translate([{"role": "user", "content": "Hello"}])

@patch('core.translation.providers.requests.post')
def test_openai_provider_translate_sse_stream(mock_post):
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.headers = {"content-type": "text/event-stream"}
    
    mock_resp.iter_lines.return_value = [
        b'data: {"id": "chatcmpl-sse-123", "choices": [{"delta": {"content": "Hello"}}]}',
        b'data: {"id": "chatcmpl-sse-123", "choices": [{"delta": {"content": " SSE world"}}]}',
        b'data: [DONE]'
    ]
    mock_post.return_value = mock_resp

    provider = OpenAIProvider({
        "endpoint": "http://localhost:20128/v1",
        "model": "kr/claude-sonnet-4.5"
    })
    res = provider.translate([{"role": "user", "content": "Hello"}])
    assert res.text == "Hello SSE world"
    assert res.message_id == "chatcmpl-sse-123"


