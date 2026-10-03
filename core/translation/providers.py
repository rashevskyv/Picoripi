"""AI providers (OpenAI-compatible, Gemini, Ollama, Perplexity) behind one translate() contract."""
import json
from dataclasses import dataclass
from typing import Any, Callable, Dict, List, Optional
from urllib.parse import urlparse
import requests
import os

from core.translation.transport import (
    AbortableSession,
    CircuitBreaker,
    ErrorKind,
    TranslationProviderError,
    TransportError,
    TransportPolicy,
    classify,
    run_cancellable,
)
from utils.logging_utils import log_debug, log_info

PROFILES = ("web2api", "openai", "ollama", "gemini")
# Hosted APIs: they reject request fields they do not know (`think`).
_HOSTED_OPENAI_HOSTS = ("api.openai.com", "api.perplexity.ai")
# A Web2API-style proxy paces its accounts and retries across them before it
# answers; the 60 s default gives up while it is still working.
WEB2API_TIMEOUT_FLOOR = 180.0


def detect_profile(settings: Optional[Dict[str, Any]], base_url: str) -> str:
    """Which kind of OpenAI-style endpoint this is.

    ``settings['profile']`` wins when it names one. Otherwise the hosted APIs are
    ``openai`` and every self-hosted endpoint is treated as a ``web2api`` proxy:
    that is what a custom URL is here, and guessing ``openai`` for a proxy on an
    unusual host would silently drop ``think``.
    """
    explicit = str((settings or {}).get('profile') or '').strip().lower()
    if explicit in PROFILES:
        return explicit
    host = (urlparse(base_url or "").hostname or "").lower()
    if any(host == hosted or host.endswith("." + hosted) for hosted in _HOSTED_OPENAI_HOSTS):
        return "openai"
    return "web2api"


@dataclass
class ProviderResponse:
    """Standardized response from a translation provider."""
    text: Optional[str] = None
    raw_payload: Any = None
    message_id: Optional[str] = None
    conversation_id: Optional[str] = None
    annotations: Optional[List[Dict[str, Any]]] = None

class BaseTranslationProvider:
    """Base translation provider implementation."""
    supports_sessions = False
    profile = "openai"
    """Abstract base class for all translation providers."""
    def __init__(self, settings: Dict[str, Any]) -> None:
        """Initialize a new instance."""
        self.settings = settings
        self._active_stream_response = None
        self._is_cancelled: Optional[Callable[[], bool]] = None
        self._max_attempts = 1
        # One breaker per provider instance: the threads of a chunked run share
        # it, so a backend that stopped answering is noticed across all of them.
        self._breaker = CircuitBreaker()

    def enable_retries(self, is_cancelled: Callable[[], bool], max_attempts: int = 2) -> None:
        """Let a cancellable caller opt into automatic retries.

        Retries are off by default: the backoff sleeps on the calling thread, so
        only a caller that can interrupt it may ask for them. The glossary
        pipeline never does -- its endpoint already retries across accounts, and
        a client-side loop on top of that is how addresses got blocked.
        """
        self._is_cancelled = is_cancelled
        self._max_attempts = max(1, int(max_attempts))

    def _policy(self, current_settings: Dict[str, Any], default_timeout: float) -> TransportPolicy:
        """The retry/timeout policy for one request."""
        timeout = _extract_timeout(current_settings, default=default_timeout)
        if self.profile == "web2api":
            timeout = max(timeout, WEB2API_TIMEOUT_FLOOR)
        try:
            attempts = int(current_settings.get('max_attempts', self._max_attempts))
        except (TypeError, ValueError):
            attempts = self._max_attempts
        # The whole call shares one timeout budget: a quick failure can be
        # retried inside it, but a request that already timed out is not sent
        # again while the server may still be working on the first one.
        return TransportPolicy(timeout=timeout, max_attempts=attempts, total_deadline=timeout)

    def _post(self, endpoint: str, headers: Dict[str, str], body: Dict[str, Any], policy: TransportPolicy) -> requests.Response:
        """POST ``body`` under ``policy``. Raises ``TransportError``."""
        def send() -> requests.Response:
            if self._is_cancelled is None:
                response = requests.post(endpoint, headers=headers, json=body, timeout=policy.requests_timeout())
            else:
                # A session per request: a cancel shuts its socket down, so the
                # server sees the client leave instead of finishing the request.
                with AbortableSession() as session:
                    response = run_cancellable(
                        lambda: session.post(endpoint, headers=headers, json=body, timeout=policy.requests_timeout()),
                        self._is_cancelled,
                        on_cancel=session.abort,
                    )
            log_info(f"{self.__class__.__name__}: Response received. Status code: {response.status_code}", category="ai")
            response.raise_for_status()
            return response

        return policy.run(send, self._is_cancelled, breaker=self._breaker)

    def _stream_error(self, exc: Exception) -> TransportError:
        """Classify a failed streaming request and tell the breaker.

        Streams share the timeouts, the classification and the breaker, but are
        never retried: a stream cannot be replayed from the middle.
        """
        error = classify(exc)
        self._breaker.record_failure(error)
        return error

    def clamp_workers(self, workers: int) -> int:
        """How many parallel requests are worth sending. Call off the UI thread."""
        return max(1, int(workers))

    def translate(self, messages: List[Dict[str, str]], session: Optional[dict] = None, settings_override: Optional[Dict[str, Any]] = None) -> ProviderResponse:
        """Translate."""
        raise NotImplementedError

    def translate_stream(self, messages: List[Dict[str, str]], session: Optional[dict] = None, settings_override: Optional[Dict[str, Any]] = None):
        # Fallback to non-streaming if not implemented
        """Translate stream."""
        response = self.translate(messages, session, settings_override)
        if response.text:
            yield response.text

    def _set_active_stream_response(self, response):
        """Track an open streaming response so cancellation can close the socket."""
        self._active_stream_response = response

    def _clear_active_stream_response(self, response):
        """Clear the tracked streaming response if it is still current."""
        if self._active_stream_response is response:
            self._active_stream_response = None

    def cancel_active_stream(self):
        """Close any active streaming HTTP response."""
        response = self._active_stream_response
        if response is None:
            return
        try:
            response.close()
        except Exception as e:
            log_debug(f"{self.__class__.__name__}: Failed to close active stream response: {e}")

def _extract_timeout(settings: Dict[str, Any], default: float = 60.0) -> float:
    """Safely extracts timeout from settings dict, supporting int, float, or string values."""
    if not isinstance(settings, dict):
        return default
    raw = settings.get('timeout')
    if raw is None:
        return default
    try:
        val = float(raw)
        if val > 0:
            return val
    except (ValueError, TypeError):
        pass
    return default


class OpenAIProvider(BaseTranslationProvider):
    """Open a i provider implementation."""
    supports_sessions = True
    """Provider for OpenAI-compatible chat completion APIs."""
    def __init__(self, settings: Dict[str, Any]) -> None:
        """Initialize a new instance."""
        super().__init__(settings)
        self._compat_stream_provider = None
        self.api_key = self.settings.get('api_key') or os.getenv(str(self.settings.get('api_key_env')))
        endpoint_val = (self.settings.get('endpoint') or self.settings.get('base_url') or "").strip()
        is_default_openai = not endpoint_val or endpoint_val.rstrip('/').lower() == "https://api.openai.com/v1"
        
        self.base_url = (endpoint_val or "https://api.openai.com/v1").rstrip('/')
        self.model = self.settings.get('model')
        if is_default_openai and not self.api_key:
            raise TranslationProviderError("OpenAI API key is not set.")
        if not self.model:
            raise TranslationProviderError("OpenAI model is not set.")
        self.profile = detect_profile(self.settings, self.base_url)
        self._active_accounts: Optional[int] = None

    def clamp_workers(self, workers: int) -> int:
        """No more threads than the proxy has usable accounts.

        Extra threads only queue inside the proxy on some account's cooldown and
        push every request toward its timeout. The count comes from the proxy's
        ``/healthz``; a proxy without one (or any other endpoint) keeps the
        user's number. Does a short network call once -- call off the UI thread.
        """
        workers = max(1, int(workers))
        if self.profile != "web2api":
            return workers
        if self._active_accounts is None:
            self._active_accounts = -1
            parsed = urlparse(self.base_url)
            try:
                reply = requests.get(f"{parsed.scheme}://{parsed.netloc}/healthz", timeout=3)
                reply.raise_for_status()
                self._active_accounts = int(reply.json()["accounts"]["active"])
            except Exception as e:
                log_debug(f"OpenAIProvider: no account count from /healthz ({e}); keeping {workers} worker(s).")
        if self._active_accounts < 0:
            return workers
        return min(workers, max(1, self._active_accounts))

    def _get_chat_endpoint(self) -> str:
        """Resolve the full OpenAI chat completions endpoint."""
        url = self.base_url.rstrip('/')
        if url.endswith('/chat/completions'):
            return url
        if url.endswith('/v1'):
            return f"{url}/chat/completions"
        return f"{url}/v1/chat/completions"

    def _prepare_body(self, messages: List[Dict[str, str]], current_settings: Dict[str, Any]) -> Dict[str, Any]:
        """Internal helper to prepare body."""
        model = current_settings.get('model') or self.model
        body: Dict[str, Any] = {"model": model, "messages": messages}
        
        # `think` is a Web2API extension; a hosted API answers 400 to it.
        if self.profile == "web2api":
            if 'think' in current_settings:
                body['think'] = current_settings['think']
            elif 'think_mode' in current_settings:
                body['think_mode'] = current_settings['think_mode']

        if current_settings.get('web_search_enabled'):
            if model.startswith('gpt-4'):
                body['model'] = f"{model}-search-preview"

        if isinstance(current_settings.get('temperature'), (float, int)):
            body['temperature'] = current_settings['temperature']
        if isinstance(current_settings.get('max_output_tokens'), int) and current_settings['max_output_tokens'] > 0:
            body['max_tokens'] = current_settings['max_output_tokens']
        # Native JSON mode, when the caller expects one JSON object back. Only
        # where it is known to exist: a proxy may reject the field, and
        # Perplexity accepts only schema-typed formats.
        if current_settings.get('json') and self.profile == "openai" and "perplexity" not in self.base_url.lower():
            body['response_format'] = {"type": "json_object"}
        return body

    def translate(self, messages: List[Dict[str, str]], session: Optional[dict] = None, settings_override: Optional[Dict[str, Any]] = None) -> ProviderResponse:
        """Translate."""
        endpoint = self._get_chat_endpoint()
        headers = {
            "Content-Type": "application/json",
        }
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"
        elif "Authorization" not in headers:
            headers["Authorization"] = "Bearer dummy"
        
        current_settings = self.settings.copy()
        if settings_override:
            current_settings.update(settings_override)

        extra_headers = current_settings.get('extra_headers')
        if isinstance(extra_headers, dict):
            headers.update(extra_headers)

        body = self._prepare_body(messages, current_settings)

        policy = self._policy(current_settings, default_timeout=60.0)
        log_info(f"OpenAIProvider: Sending request to {endpoint} with timeout {policy.timeout}s (model: {self.model})", category="ai")
        response = self._post(endpoint, headers, body, policy)

        is_sse = response.headers.get('content-type', '').startswith('text/event-stream')
        if is_sse:
            full_text = []
            last_message_id = None
            for line in response.iter_lines():
                if line:
                    line_str = line.decode('utf-8')
                    if line_str.startswith('data: '):
                        json_str = line_str[6:]
                        if json_str.strip() == '[DONE]':
                            break
                        try:
                            chunk_data = json.loads(json_str)
                            if isinstance(chunk_data, dict):
                                if 'id' in chunk_data:
                                    last_message_id = chunk_data['id']
                                if 'choices' in chunk_data and chunk_data['choices']:
                                    choice = chunk_data['choices'][0]
                                    if 'delta' in choice and 'content' in choice['delta']:
                                        content = choice['delta']['content']
                                        if content:
                                            full_text.append(content)
                                    elif 'message' in choice and 'content' in choice['message']:
                                        content = choice['message']['content']
                                        if content:
                                            full_text.append(content)
                                    elif 'text' in choice:
                                        content = choice['text']
                                        if content:
                                            full_text.append(content)
                        except json.JSONDecodeError:
                            log_debug(f"SSE decode error for line in translate(): {json_str}")
                            continue
            text = "".join(full_text)
            data = {
                "choices": [{
                    "message": {
                        "role": "assistant",
                        "content": text
                    }
                }]
            }
            if last_message_id:
                data["id"] = last_message_id
        else:
            try:
                data = response.json()
            except ValueError:
                raise TransportError(
                    f"API returned non-JSON response (status {response.status_code}): {response.text[:200]}",
                    kind=ErrorKind.PARSE,
                    status=response.status_code,
                    raw_text=response.text,
                )

        try:
            text = None
            if data.get('choices'):
                first_choice = data['choices'][0]
                message = first_choice.get('message')
                if isinstance(message, dict):
                    text = message.get('content')
                if text is None:
                    text = first_choice.get('text')
            # A 200 with nothing in it is a failure, not a translation: left as
            # text=None it reaches json.loads('') or is silently dropped.
            if not (text or "").strip():
                raise TransportError("AI returned an empty response.", kind=ErrorKind.EMPTY, status=response.status_code)

            message_id = None
            conversation_id = None
            if isinstance(data, dict):
                message_id = data.get('id')
                first_choice = data.get('choices')[0] if data.get('choices') else None
                if isinstance(first_choice, dict):
                    message = first_choice.get('message') or {}
                    message_id = message.get('id') or message_id
                conversation_id = (
                    data.get('conversation_id')
                    or data.get('conversationId')
                    or (data.get('conversation') or {}).get('id')
                    or (data.get('conversation') or {}).get('conversation_id')
                    or (data.get('meta') or {}).get('conversation_id')
                )

            return ProviderResponse(text=text, raw_payload=data, message_id=message_id, conversation_id=conversation_id)
        except TransportError:
            raise
        except Exception as e:
            raise TransportError(f"Failed to parse provider response: {e}", kind=ErrorKind.PARSE)

    def translate_stream(self, messages: List[Dict[str, str]], session: Optional[dict] = None, settings_override: Optional[Dict[str, Any]] = None):
        """Translate stream."""
        endpoint = self._get_chat_endpoint()
        headers = {"Content-Type": "application/json"}
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"
        elif "Authorization" not in headers:
            headers["Authorization"] = "Bearer dummy"
        current_settings = self.settings.copy()
        if settings_override:
            current_settings.update(settings_override)

        body = self._prepare_body(messages, current_settings)
        body['stream'] = True

        policy = self._policy(current_settings, default_timeout=60.0)
        timeout = policy.timeout

        self._breaker.check()
        try:
            log_info(f"OpenAIProvider: Sending stream request to {endpoint} with timeout {timeout}s (model: {self.model})", category="ai")
            with requests.post(endpoint, headers=headers, json=body, stream=True, timeout=policy.requests_timeout()) as response:
                self._set_active_stream_response(response)
                try:
                    log_info(f"OpenAIProvider: Stream response received. Status code: {response.status_code}", category="ai")
                    response.raise_for_status()
                    for line in response.iter_lines():
                        if line:
                            line_str = line.decode('utf-8')
                            if line_str.startswith('data: '):
                                json_str = line_str[6:]
                                if json_str.strip() == '[DONE]':
                                    break
                                try:
                                    data = json.loads(json_str)
                                    if 'choices' in data and data['choices']:
                                        delta = data['choices'][0].get('delta', {})
                                        content = delta.get('content')
                                        if content:
                                            yield content
                                except json.JSONDecodeError:
                                    log_debug(f"Stream decode error for line: {json_str}")
                                    continue
                finally:
                    self._clear_active_stream_response(response)
            self._breaker.record_success()
        except requests.RequestException as e:
            raise self._stream_error(e) from e


class OllamaChatProvider(BaseTranslationProvider):
    """Ollama chat provider implementation."""
    supports_sessions = True
    profile = "ollama"
    """Provider for Ollama chat APIs."""
    def __init__(self, settings: Dict[str, Any]) -> None:
        """Initialize a new instance."""
        super().__init__(settings)
        self.base_url = (self.settings.get('base_url') or "http://localhost:11434").rstrip('/')
        self.model = self.settings.get('model')
        if not self.model:
            raise TranslationProviderError("Ollama model is not set.")

    def translate(self, messages: List[Dict[str, str]], session: Optional[dict] = None, settings_override: Optional[Dict[str, Any]] = None) -> ProviderResponse:
        """Translate."""
        full_text = ""
        for chunk in self.translate_stream(messages, session, settings_override):
            full_text += chunk
        return ProviderResponse(text=full_text)

    def translate_stream(self, messages: List[Dict[str, str]], session: Optional[dict] = None, settings_override: Optional[Dict[str, Any]] = None):
        """Translate stream."""
        endpoint = f"{self.base_url}/api/chat"
        headers = {"Content-Type": "application/json"}

        current_settings = self.settings.copy()
        if settings_override:
            current_settings.update(settings_override)

        extra_headers = current_settings.get('extra_headers')
        if isinstance(extra_headers, dict):
            headers.update(extra_headers)
        
        system_prompt = next((m['content'] for m in messages if m['role'] == 'system'), None)
        user_prompts = [m for m in messages if m['role'] != 'system']

        body: Dict[str, Any] = {"model": self.model, "messages": user_prompts, "stream": True}
        if system_prompt:
            body['system'] = system_prompt
        
        options: Dict[str, Any] = {}
        if isinstance(current_settings.get('temperature'), (float, int)):
            options['temperature'] = current_settings['temperature']
        if options:
            body['options'] = options
        if current_settings.get('json'):
            body['format'] = 'json'

        if current_settings.get('keep_alive'):
            body['keep_alive'] = current_settings['keep_alive']

        policy = self._policy(current_settings, default_timeout=120.0)

        self._breaker.check()
        try:
            with requests.post(endpoint, headers=headers, json=body, stream=True, timeout=policy.requests_timeout()) as response:
                self._set_active_stream_response(response)
                try:
                    response.raise_for_status()
                    for line in response.iter_lines():
                        if line:
                            try:
                                data = json.loads(line.decode('utf-8'))
                                content = data.get('message', {}).get('content')
                                if content:
                                    yield content
                            except json.JSONDecodeError:
                                log_debug(f"Ollama stream decode error for line: {line}")
                                continue
                finally:
                    self._clear_active_stream_response(response)
            self._breaker.record_success()
        except requests.RequestException as e:
            raise self._stream_error(e) from e



class GeminiProvider(BaseTranslationProvider):
    """Gemini provider implementation."""
    supports_sessions = True
    """Provider for Google Gemini API."""
    BASE_URL = "https://generativelanguage.googleapis.com/v1beta/models"

    def __init__(self, settings: Dict[str, Any]) -> None:
        """Initialize a new instance."""
        super().__init__(settings)
        self.api_key = self.settings.get('api_key') or os.getenv(str(self.settings.get('api_key_env')))
        self.model = self.settings.get('model')
        raw_base_url = (self.settings.get('base_url') or "").strip()
        self._use_openai_compat = bool(raw_base_url) and "generativelanguage.googleapis.com" not in raw_base_url
        if raw_base_url:
            self.base_url = raw_base_url.rstrip('/')
        else:
            self.base_url = self.BASE_URL
        if not self._use_openai_compat and not self.api_key:
            raise TranslationProviderError("Gemini API key is not set for native API usage.")
        if not self.model:
            raise TranslationProviderError("Gemini model is not set.")
        self.profile = detect_profile(self.settings, self.base_url) if self._use_openai_compat else "gemini"

    def clamp_workers(self, workers: int) -> int:
        if self._use_openai_compat:
            return self._compat_provider().clamp_workers(workers)
        return super().clamp_workers(workers)

    def _get_openai_compat_endpoint(self) -> str:
        """Resolve the full OpenAI chat completions endpoint for custom base URL."""
        url = self.base_url.rstrip('/')
        if url.endswith('/chat/completions'):
            return url
        if url.endswith('/v1'):
            return f"{url}/chat/completions"
        return f"{url}/v1/chat/completions"

    def start_new_chat_session(self):
        """If using a custom base URL, attempts to start a new chat session."""
        if not self._use_openai_compat:
            log_debug("New chat session request is only applicable for custom base URLs (OpenAI compatibility mode).")
            return

        try:
            # Construct the URL for the new-chat endpoint
            new_chat_url = f"{self.base_url}/api/new-chat"
            
            log_debug(f"Requesting new chat session from: {new_chat_url}")
            response = requests.post(new_chat_url, timeout=10) # 10-second timeout
            response.raise_for_status()
            
            response_data = response.json()
            if response_data.get("success"):
                log_debug("Successfully created a new chat session via API.")
            else:
                log_debug(f"API indicated failure in creating new chat session: {response_data.get('message')}")

        except requests.RequestException as e:
            log_debug(f"Failed to request a new chat session: {e}")

    def translate(self, messages: List[Dict[str, str]], session: Optional[dict] = None, settings_override: Optional[Dict[str, Any]] = None) -> ProviderResponse:
        """Translate."""
        current_settings = self.settings.copy()
        if settings_override:
            current_settings.update(settings_override)

        if self._use_openai_compat:
            return self._compat_provider().translate(messages, session, settings_override)

        extra_headers = current_settings.get('extra_headers')
        headers = {"Content-Type": "application/json"}
        if isinstance(extra_headers, dict):
            headers.update(extra_headers)
        return self._translate_via_native_api(messages, headers, current_settings)

    def _compat_provider(self) -> "OpenAIProvider":
        """The OpenAI-style provider behind a custom base URL.

        One request path for both spellings of the same proxy: the compat route
        gets the retry policy, the empty/non-JSON checks and ``think`` for free.
        """
        compat_settings = dict(self.settings)
        compat_settings['base_url'] = self.base_url
        compat_settings.setdefault('timeout', 120)
        if not compat_settings.get('api_key'):
            compat_settings['api_key'] = self.api_key
        provider = OpenAIProvider(compat_settings)
        # Share the breaker and the caller's retry opt-in with the delegate.
        provider._breaker = self._breaker
        provider._is_cancelled = self._is_cancelled
        provider._max_attempts = self._max_attempts
        return provider

    def translate_stream(self, messages: List[Dict[str, str]], session: Optional[dict] = None, settings_override: Optional[Dict[str, Any]] = None):
        """Translate stream."""
        current_settings = self.settings.copy()
        if settings_override:
            current_settings.update(settings_override)

        extra_headers = current_settings.get('extra_headers')
        headers = {"Content-Type": "application/json"}
        if isinstance(extra_headers, dict):
            headers.update(extra_headers)

        if self._use_openai_compat:
            # Assuming the compatible endpoint also supports OpenAI's stream format
            compat_provider = self._compat_provider()
            self._compat_stream_provider = compat_provider
            try:
                yield from compat_provider.translate_stream(messages, session, settings_override)
            finally:
                self._compat_stream_provider = None
            return

        timeout = self._policy(current_settings, default_timeout=120.0).requests_timeout()
        self._breaker.check()
        try:
            yield from self._translate_via_native_stream(messages, headers, current_settings, timeout)
            self._breaker.record_success()
        except requests.RequestException as e:
            # classify() also masks the ?key= the native URL carries.
            raise self._stream_error(e) from e

    def cancel_active_stream(self):
        """Close any active Gemini stream, including OpenAI-compatible delegated streams."""
        super().cancel_active_stream()
        compat_provider = self._compat_stream_provider
        if compat_provider is not None:
            compat_provider.cancel_active_stream()

    def _translate_via_native_api(self, messages: List[Dict[str, str]], headers: Dict[str, str], current_settings: Dict[str, Any]) -> ProviderResponse:
        """Internal helper to translate via native api."""
        endpoint = f"{self.base_url}/{self.model}:generateContent?key={self.api_key}"
        system_prompt = next((m['content'] for m in messages if m['role'] == 'system'), "")
        user_prompt = next((m['content'] for m in messages if m['role'] == 'user'), "")

        full_prompt = f"{system_prompt}\n\n{user_prompt}".strip()
        contents = [{"role": "user", "parts": [{"text": full_prompt}]}]
        body: Dict[str, Any] = {"contents": contents}

        generation_config: Dict[str, Any] = {}
        if isinstance(current_settings.get('temperature'), (float, int)):
            generation_config['temperature'] = current_settings['temperature']
        if current_settings.get('json'):
            generation_config['responseMimeType'] = 'application/json'
        if generation_config:
            body['generationConfig'] = generation_config

        response = self._post(endpoint, headers, body, self._policy(current_settings, default_timeout=120.0))
        try:
            data = response.json()
        except ValueError:
            raise TransportError(
                f"API returned non-JSON response (status {response.status_code}): {response.text[:200]}",
                kind=ErrorKind.PARSE,
                status=response.status_code,
                raw_text=response.text,
            )

        text = None
        if data.get('candidates'):
            first_candidate = data['candidates'][0]
            parts = first_candidate.get('content', {}).get('parts')
            if parts:
                text = parts[0].get('text')
        if not (text or "").strip():
            raise TransportError("AI returned an empty response.", kind=ErrorKind.EMPTY, status=response.status_code)

        return ProviderResponse(text=text, raw_payload=data)

    def _translate_via_native_stream(self, messages: List[Dict[str, str]], headers: Dict[str, str], current_settings: Dict[str, Any], timeout: int):
        """Internal helper to translate via native stream."""
        endpoint = f"{self.base_url}/{self.model}:streamGenerateContent?key={self.api_key}"
        system_prompt = next((m['content'] for m in messages if m['role'] == 'system'), "")
        user_prompt = next((m['content'] for m in messages if m['role'] == 'user'), "")

        full_prompt = f"{system_prompt}\n\n{user_prompt}".strip()
        contents = [{"role": "user", "parts": [{"text": full_prompt}]}]
        body: Dict[str, Any] = {"contents": contents}

        generation_config: Dict[str, Any] = {}
        if isinstance(current_settings.get('temperature'), (float, int)):
            generation_config['temperature'] = current_settings['temperature']
        if generation_config:
            body['generationConfig'] = generation_config

        with requests.post(endpoint, headers=headers, json=body, stream=True, timeout=timeout) as response:
            self._set_active_stream_response(response)
            try:
                response.raise_for_status()
                for line in response.iter_lines():
                    if line:
                        line_str = line.decode('utf-8').strip()
                        if line_str.startswith('"text":'):
                            # This is a simplified parser for Gemini's stream format
                            # It might need to be more robust for production
                            try:
                                # Extract the content between the quotes
                                content = line_str.split(':', 1)[1].strip()
                                if content.startswith('"') and content.endswith('"'):
                                    yield json.loads(content)
                            except (json.JSONDecodeError, IndexError):
                                continue
            finally:
                self._clear_active_stream_response(response)

def create_translation_provider(provider_key: str, settings: Dict[str, Any]) -> BaseTranslationProvider:
    """Factory function to create a translation provider instance."""
    if provider_key in ('openai', 'openai compatible', 'openai_compatible'):
        return OpenAIProvider(settings)

    if provider_key == 'ollama_chat':
        return OllamaChatProvider(settings)

    if provider_key == 'gemini':
        return GeminiProvider(settings)
    if provider_key == 'perplexity':
        return OpenAIProvider(settings)
    raise TranslationProviderError(f"Unknown provider key: {provider_key}")

def get_provider_for_config(config: Dict[str, Any]) -> BaseTranslationProvider:
    """
    Initializes and returns a translation provider based on a configuration dictionary.
    This is intended for one-off tasks like glossary building.
    """
    provider_name = config.get("provider", "").lower()
    
    # The config passed here is the specific config for the task,
    # e.g., mw.glossary_ai, which already contains api_key, model, etc.
    
    if provider_name in ('openai', 'openai compatible', 'openai_compatible'):
        return OpenAIProvider(config)
    elif provider_name == 'ollama':
        # Ollama provider expects 'base_url' and 'model' in its settings,
        # which should be present in the passed config.
        return OllamaChatProvider(config)
    elif provider_name == 'gemini':
        return GeminiProvider(config)
    
    raise TranslationProviderError(f"Unknown or unsupported provider for this task: {provider_name}")
