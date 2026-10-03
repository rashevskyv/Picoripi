import pytest
from unittest.mock import MagicMock, patch
import requests
from core.translation.providers import OpenAIProvider, TranslationProviderError
from core.translation.transport import ErrorKind, TransportError


def _ok_response(payload):
    resp = MagicMock()
    resp.status_code = 200
    resp.headers = {"content-type": "application/json"}
    resp.json.return_value = payload
    return resp


def _failed_response(status, body="", headers=None):
    resp = requests.Response()
    resp.status_code = status
    resp._content = body.encode("utf-8")
    resp.headers.update(headers or {})
    resp.url = "http://localhost:20128/v1/chat/completions"
    return resp


def _local_provider(**settings):
    return OpenAIProvider({"endpoint": "http://localhost:20128/v1", "model": "local-model", **settings})


@patch('core.translation.providers.requests.post')
def test_connect_timeout_is_short_for_any_host(mock_post):
    mock_post.return_value = _ok_response({"choices": [{"message": {"content": "ok"}}]})
    OpenAIProvider({"endpoint": "https://proxy.lan/v1", "model": "m", "timeout": 180}).translate([])
    assert mock_post.call_args[1]["timeout"] == (10.0, 180.0)


@pytest.mark.parametrize("payload", [{"choices": []}, {"choices": [{"message": {"content": "  "}}]}, {}])
@patch('core.translation.providers.requests.post')
def test_empty_response_is_an_error_not_a_silent_success(mock_post, payload):
    mock_post.return_value = _ok_response(payload)
    with pytest.raises(TransportError) as info:
        _local_provider().translate([{"role": "user", "content": "Hi"}])
    assert info.value.kind is ErrorKind.EMPTY


@patch('core.translation.providers.requests.post')
def test_rate_limit_carries_retry_after_and_is_not_retried_by_default(mock_post):
    mock_post.return_value = _failed_response(429, "busy", {"Retry-After": "42"})
    with pytest.raises(TransportError) as info:
        _local_provider().translate([{"role": "user", "content": "Hi"}])
    assert (info.value.kind, info.value.retry_after) == (ErrorKind.RATE_LIMIT, 42.0)
    assert mock_post.call_count == 1


@patch('core.translation.transport.TransportPolicy._wait')
@patch('core.translation.providers.AbortableSession.post')
def test_a_cancellable_caller_gets_one_automatic_retry(mock_post, mock_sleep):
    mock_post.side_effect = [
        _failed_response(503),
        _ok_response({"choices": [{"message": {"content": "second try"}}]}),
    ]
    provider = _local_provider()
    provider.enable_retries(lambda: False)
    assert provider.translate([{"role": "user", "content": "Hi"}]).text == "second try"
    assert mock_post.call_count == 2
    assert mock_sleep.called


@patch('core.translation.providers.AbortableSession.post')
def test_fatal_status_is_never_retried(mock_post):
    mock_post.return_value = _failed_response(401, "bad key")
    provider = _local_provider()
    provider.enable_retries(lambda: False, max_attempts=4)
    with pytest.raises(TransportError) as info:
        provider.translate([{"role": "user", "content": "Hi"}])
    assert info.value.kind is ErrorKind.AUTH
    assert mock_post.call_count == 1


@patch('core.translation.providers.requests.post')
def test_breaker_stops_calling_a_dead_backend(mock_post):
    mock_post.return_value = _failed_response(503)
    provider = _local_provider()
    for _ in range(provider._breaker.threshold):
        with pytest.raises(TransportError):
            provider.translate([{"role": "user", "content": "Hi"}])
    calls = mock_post.call_count
    with pytest.raises(TransportError, match="cooling down"):
        provider.translate([{"role": "user", "content": "Hi"}])
    assert mock_post.call_count == calls


@patch('core.translation.providers.requests.post')
def test_gemini_native_error_does_not_leak_the_api_key(mock_post):
    from core.translation.providers import GeminiProvider
    mock_post.side_effect = requests.ConnectionError(
        "Max retries exceeded with url: /v1beta/models/gemini:generateContent?key=SECRET123"
    )
    provider = GeminiProvider({"api_key": "SECRET123", "model": "gemini"})
    with pytest.raises(TransportError) as info:
        provider.translate([{"role": "user", "content": "Hi"}])
    assert "SECRET123" not in str(info.value)
    assert info.value.kind is ErrorKind.CONNECT


@patch('core.translation.providers.requests.post')
def test_gemini_compat_route_passes_think_and_rejects_non_json(mock_post):
    from core.translation.providers import GeminiProvider
    provider = GeminiProvider({"base_url": "http://127.0.0.1:8081", "model": "gemini-3.7-flash"})

    mock_post.return_value = _ok_response({"choices": [{"message": {"content": "ok"}}]})
    provider.translate([{"role": "user", "content": "Hi"}], settings_override={"think": 1})
    assert mock_post.call_args[1]["json"]["think"] == 1
    assert mock_post.call_args[1]["timeout"] == (10.0, 180.0)

    broken = _ok_response(None)
    broken.json.side_effect = ValueError("Expecting value")
    broken.text = "<html>captcha</html>"
    mock_post.return_value = broken
    with pytest.raises(TransportError) as info:
        provider.translate([{"role": "user", "content": "Hi"}])
    assert info.value.kind is ErrorKind.PARSE


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


@patch('core.translation.providers.requests.post')
def test_openai_provider_cancel_active_stream_closes_response(mock_post):
    class FakeStreamResponse:
        status_code = 200

        def __init__(self):
            self.closed = False

        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):
            self.close()

        def raise_for_status(self):
            return None

        def iter_lines(self):
            yield b'data: {"choices": [{"delta": {"content": "Hello"}}]}'
            yield b'data: [DONE]'

        def close(self):
            self.closed = True

    fake_response = FakeStreamResponse()
    mock_post.return_value = fake_response

    provider = OpenAIProvider({
        "endpoint": "http://localhost:20128/v1",
        "model": "kr/claude-sonnet-4.5"
    })
    stream = provider.translate_stream([{"role": "user", "content": "Hello"}])

    assert next(stream) == "Hello"
    assert provider._active_stream_response is fake_response

    provider.cancel_active_stream()
    assert fake_response.closed is True

    stream.close()
    assert provider._active_stream_response is None


def test_provider_endpoint_normalization():
    from core.translation.providers import GeminiProvider

    p_root = OpenAIProvider({"endpoint": "http://127.0.0.1:8081", "model": "gemini-3.7-flash"})
    assert p_root._get_chat_endpoint() == "http://127.0.0.1:8081/v1/chat/completions"

    p_v1 = OpenAIProvider({"endpoint": "http://127.0.0.1:8081/v1", "model": "gemini-3.7-flash"})
    assert p_v1._get_chat_endpoint() == "http://127.0.0.1:8081/v1/chat/completions"

    g_root = GeminiProvider({"base_url": "http://127.0.0.1:8081", "model": "gemini-3.7-flash"})
    assert g_root._get_openai_compat_endpoint() == "http://127.0.0.1:8081/v1/chat/completions"

    g_v1 = GeminiProvider({"base_url": "http://127.0.0.1:8081/v1", "model": "gemini-3.7-flash"})
    assert g_v1._get_openai_compat_endpoint() == "http://127.0.0.1:8081/v1/chat/completions"


@patch('core.translation.providers.requests.post')
def test_gemini_provider_openai_compat_mode(mock_post):
    from core.translation.providers import GeminiProvider
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.headers = {"content-type": "application/json"}
    mock_resp.json.return_value = {
        "id": "proxy-123",
        "choices": [{"message": {"role": "assistant", "content": "Proxy translation"}}]
    }
    mock_post.return_value = mock_resp

    provider = GeminiProvider({
        "base_url": "http://127.0.0.1:8081",
        "model": "gemini-3.7-flash",
    })
    res = provider.translate([{"role": "user", "content": "Hi"}])
    assert res.text == "Proxy translation"
    assert res.message_id == "proxy-123"
    assert mock_post.call_args[0][0] == "http://127.0.0.1:8081/v1/chat/completions"
    assert mock_post.call_args[1]["headers"]["Authorization"] == "Bearer dummy"


def test_extract_timeout_utility():
    from core.translation.providers import _extract_timeout

    assert _extract_timeout({}, default=60.0) == 60.0
    assert _extract_timeout({"timeout": 120}, default=60.0) == 120.0
    assert _extract_timeout({"timeout": "300"}, default=60.0) == 300.0
    assert _extract_timeout({"timeout": 45.5}, default=60.0) == 45.5
    assert _extract_timeout({"timeout": -10}, default=60.0) == 60.0
    assert _extract_timeout({"timeout": "invalid"}, default=60.0) == 60.0
    assert _extract_timeout(None, default=60.0) == 60.0


@patch('core.translation.providers.requests.post')
def test_openai_provider_timeout_override(mock_post):
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.headers = {"content-type": "application/json"}
    mock_resp.json.return_value = {
        "choices": [{"message": {"role": "assistant", "content": "Done"}}]
    }
    mock_post.return_value = mock_resp

    provider = OpenAIProvider({
        "endpoint": "http://localhost:8081",
        "model": "local-model",
        "timeout": 60,
    })

    # A self-hosted proxy paces and retries inside: 60 s is raised to the 180 s floor.
    provider.translate([{"role": "user", "content": "Hi"}])
    assert mock_post.call_args[1]["timeout"] == (10.0, 180.0)

    # Override timeout in settings_override
    provider.translate(
        [{"role": "user", "content": "Hi"}],
        settings_override={"timeout": 300}
    )
    assert mock_post.call_args[1]["timeout"] == (10.0, 300.0)


# --- provider profile ---------------------------------------------------------

@pytest.mark.parametrize("settings, url, profile", [
    ({}, "http://127.0.0.1:8081/v1", "web2api"),
    ({}, "http://proxy.lan:9000/v1", "web2api"),
    ({}, "https://api.openai.com/v1", "openai"),
    ({}, "https://api.perplexity.ai", "openai"),
    ({"profile": "auto"}, "https://api.openai.com/v1", "openai"),
    ({"profile": "openai"}, "http://127.0.0.1:8081/v1", "openai"),
    ({"profile": "web2api"}, "https://api.openai.com/v1", "web2api"),
])
def test_detect_profile(settings, url, profile):
    from core.translation.providers import detect_profile
    assert detect_profile(settings, url) == profile


def test_think_is_sent_to_a_proxy_and_never_to_a_hosted_api():
    proxy = OpenAIProvider({"endpoint": "http://127.0.0.1:8081/v1", "model": "gemini-3.7-flash"})
    hosted = OpenAIProvider({"endpoint": "https://api.openai.com/v1", "model": "gpt-4o-mini", "api_key": "k"})
    messages = [{"role": "user", "content": "Hi"}]

    assert proxy._prepare_body(messages, {"think": 2})["think"] == 2
    assert proxy._prepare_body(messages, {"think_mode": "x"})["think_mode"] == "x"
    body = hosted._prepare_body(messages, {"think": 2, "think_mode": "x", "temperature": 0.2})
    assert "think" not in body and "think_mode" not in body
    assert body["temperature"] == 0.2


@patch('core.translation.providers.requests.post')
def test_hosted_api_keeps_the_users_timeout(mock_post):
    mock_post.return_value = _ok_response({"choices": [{"message": {"content": "ok"}}]})
    OpenAIProvider({"endpoint": "https://api.openai.com/v1", "model": "m", "api_key": "k", "timeout": 60}).translate([])
    assert mock_post.call_args[1]["timeout"] == (10.0, 60.0)


@pytest.mark.parametrize("health, asked, expected", [
    ({"accounts": {"active": 2}}, 6, 2),
    ({"accounts": {"active": 0}}, 6, 1),
    ({"accounts": {"active": 9}}, 6, 6),
    ({"status": "ok"}, 6, 6),          # a proxy that does not report accounts
])
@patch('core.translation.providers.requests.get')
def test_workers_are_clamped_to_the_proxys_active_accounts(mock_get, health, asked, expected):
    mock_get.return_value = _ok_response(health)
    provider = _local_provider()
    assert provider.clamp_workers(asked) == expected
    assert provider.clamp_workers(asked) == expected
    assert mock_get.call_count == 1  # asked once per provider
    assert mock_get.call_args[0][0] == "http://localhost:20128/healthz"


@patch('core.translation.providers.requests.get')
def test_workers_are_left_alone_without_healthz_or_for_a_hosted_api(mock_get):
    mock_get.side_effect = requests.ConnectionError("refused")
    assert _local_provider().clamp_workers(6) == 6
    hosted = OpenAIProvider({"endpoint": "https://api.openai.com/v1", "model": "m", "api_key": "k"})
    assert hosted.clamp_workers(6) == 6
    assert mock_get.call_count == 1


# --- native JSON mode (WP2 2.7) ---------------------------------------------

def test_json_mode_is_requested_only_where_it_is_known_to_exist():
    messages = [{"role": "user", "content": "Return JSON"}]
    hosted = OpenAIProvider({"endpoint": "https://api.openai.com/v1", "model": "gpt-4o-mini", "api_key": "k"})
    proxy = OpenAIProvider({"endpoint": "http://127.0.0.1:8081/v1", "model": "gemini-3.7-flash"})
    perplexity = OpenAIProvider({"endpoint": "https://api.perplexity.ai", "model": "sonar", "api_key": "k"})

    assert hosted._prepare_body(messages, {"json": True})["response_format"] == {"type": "json_object"}
    assert "response_format" not in hosted._prepare_body(messages, {})
    assert "response_format" not in proxy._prepare_body(messages, {"json": True})
    assert "response_format" not in perplexity._prepare_body(messages, {"json": True})


@patch('core.translation.providers.requests.post')
def test_native_gemini_json_mode(mock_post):
    from core.translation.providers import GeminiProvider
    mock_post.return_value = _ok_response({"candidates": [{"content": {"parts": [{"text": "{}"}]}}]})
    provider = GeminiProvider({"api_key": "k", "model": "gemini"})

    provider.translate([{"role": "user", "content": "Hi"}], settings_override={"json": True, "temperature": 0.1})
    assert mock_post.call_args[1]["json"]["generationConfig"] == {
        "temperature": 0.1, "responseMimeType": "application/json"}

    provider.translate([{"role": "user", "content": "Hi"}])
    assert "generationConfig" not in mock_post.call_args[1]["json"]
