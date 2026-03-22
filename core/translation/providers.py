# --- START OF FILE core/translation/providers.py ---
import json
from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Sequence
import requests
from requests import Timeout
import os

from utils.logging_utils import log_debug

class TranslationProviderError(Exception):
    """Custom exception for provider-related errors."""
    pass

@dataclass
class ProviderResponse:
    """Standardized response from a translation provider."""
    text: Optional[str] = None
    raw_payload: Any = None
    message_id: Optional[str] = None
    conversation_id: Optional[str] = None
    annotations: Optional[List[Dict[str, Any]]] = None

class BaseTranslationProvider:
    supports_sessions = False
    """Abstract base class for all translation providers."""
    def __init__(self, settings: Dict[str, Any]) -> None:
        self.settings = settings

    def translate(self, messages: List[Dict[str, str]], session: Optional[dict] = None, settings_override: Optional[Dict[str, Any]] = None) -> ProviderResponse:
        raise NotImplementedError

    def translate_stream(self, messages: List[Dict[str, str]], session: Optional[dict] = None, settings_override: Optional[Dict[str, Any]] = None):
        # Fallback to non-streaming if not implemented
        response = self.translate(messages, session, settings_override)
        if response.text:
            yield response.text

class OpenAIChatProvider(BaseTranslationProvider):
    supports_sessions = True
    """Provider for OpenAI-compatible chat completion APIs."""
    def __init__(self, settings: Dict[str, Any]) -> None:
        super().__init__(settings)
        self.api_key = self.settings.get('api_key') or os.getenv(str(self.settings.get('api_key_env')))
        self.base_url = (self.settings.get('base_url') or "https://api.openai.com/v1").rstrip('/')
        self.model = self.settings.get('model')
        if not self.api_key:
            raise TranslationProviderError("OpenAI API key is not set.")
        if not self.model:
            raise TranslationProviderError("OpenAI model is not set.")

    def _prepare_body(self, messages: List[Dict[str, str]], current_settings: Dict[str, Any]) -> Dict[str, Any]:
        body: Dict[str, Any] = {"model": self.model, "messages": messages}
        
        if current_settings.get('web_search_enabled'):
            if self.model.startswith('gpt-4'):
                body['model'] = f"{self.model}-search-preview"

        if isinstance(current_settings.get('temperature'), (float, int)):
            body['temperature'] = current_settings['temperature']
        if isinstance(current_settings.get('max_output_tokens'), int) and current_settings['max_output_tokens'] > 0:
            body['max_tokens'] = current_settings['max_output_tokens']
        return body

    def translate(self, messages: List[Dict[str, str]], session: Optional[dict] = None, settings_override: Optional[Dict[str, Any]] = None) -> ProviderResponse:
        endpoint = f"{self.base_url}/chat/completions"
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }
        
        current_settings = self.settings.copy()
        if settings_override:
            current_settings.update(settings_override)

        extra_headers = current_settings.get('extra_headers')
        if isinstance(extra_headers, dict):
            headers.update(extra_headers)

        body = self._prepare_body(messages, current_settings)
        
        timeout = 60
        if isinstance(current_settings.get('timeout'), int) and current_settings['timeout'] > 0:
            timeout = current_settings['timeout']

        try:
            response = requests.post(endpoint, headers=headers, json=body, timeout=timeout)
            response.raise_for_status()
            data = response.json()
            text = data['choices'][0]['message']['content'] if data.get('choices') else None

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
        except Timeout:
            raise TranslationProviderError(f"Request timed out after {timeout} seconds.")
        except requests.RequestException as e:
            raise TranslationProviderError(f"API request failed: {e}")
    
    def translate_stream(self, messages: List[Dict[str, str]], session: Optional[dict] = None, settings_override: Optional[Dict[str, Any]] = None):
        endpoint = f"{self.base_url}/chat/completions"
        headers = {"Authorization": f"Bearer {self.api_key}", "Content-Type": "application/json"}
        current_settings = self.settings.copy()
        if settings_override:
            current_settings.update(settings_override)

        body = self._prepare_body(messages, current_settings)
        body['stream'] = True

        timeout = 60
        if isinstance(current_settings.get('timeout'), int) and current_settings['timeout'] > 0:
            timeout = current_settings['timeout']
        
        try:
            with requests.post(endpoint, headers=headers, json=body, stream=True, timeout=timeout) as response:
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
        except requests.RequestException as e:
            raise TranslationProviderError(f"API stream request failed: {e}")

class OllamaChatProvider(BaseTranslationProvider):
    supports_sessions = True
    """Provider for Ollama chat APIs."""
    def __init__(self, settings: Dict[str, Any]) -> None:
        super().__init__(settings)
        self.base_url = (self.settings.get('base_url') or "http://localhost:11434").rstrip('/')
        self.model = self.settings.get('model')
        if not self.model:
            raise TranslationProviderError("Ollama model is not set.")

    def translate(self, messages: List[Dict[str, str]], session: Optional[dict] = None, settings_override: Optional[Dict[str, Any]] = None) -> ProviderResponse:
        full_text = ""
        for chunk in self.translate_stream(messages, session, settings_override):
            full_text += chunk
        return ProviderResponse(text=full_text)

    def translate_stream(self, messages: List[Dict[str, str]], session: Optional[dict] = None, settings_override: Optional[Dict[str, Any]] = None):
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
        
        if current_settings.get('keep_alive'):
            body['keep_alive'] = current_settings['keep_alive']

        timeout = 120
        if isinstance(current_settings.get('timeout'), int) and current_settings['timeout'] > 0:
            timeout = current_settings['timeout']

        try:
            with requests.post(endpoint, headers=headers, json=body, stream=True, timeout=timeout) as response:
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
        except requests.RequestException as e:
            raise TranslationProviderError(f"API stream request failed: {e}")



class DeepLProvider(BaseTranslationProvider):
    def translate(self, messages: list, session: Optional[dict] = None, settings_override: Optional[Dict[str, Any]] = None) -> ProviderResponse:
        raise NotImplementedError("DeepL provider is not yet implemented.")

class GeminiProvider(BaseTranslationProvider):
    supports_sessions = True
    """Provider for Google Gemini API."""
    BASE_URL = "https://generativelanguage.googleapis.com/v1beta/models"

    def __init__(self, settings: Dict[str, Any]) -> None:
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

    def start_new_chat_session(self):
        """If using a custom base URL, attempts to start a new chat session."""
        if not self._use_openai_compat:
            log_debug("New chat session request is only applicable for custom base URLs (OpenAI compatibility mode).")
            return

        try:
            # Construct the URL for the new-chat endpoint
            # Assumes the base_url is something like http://host:port
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
        current_settings = self.settings.copy()
        if settings_override:
            current_settings.update(settings_override)

        timeout = 120
        if isinstance(current_settings.get('timeout'), int) and current_settings['timeout'] > 0:
            timeout = current_settings['timeout']

        extra_headers = current_settings.get('extra_headers')
        headers = {"Content-Type": "application/json"}
        if isinstance(extra_headers, dict):
            headers.update(extra_headers)

        try:
            if self._use_openai_compat:
                return self._translate_via_openai_compat(messages, headers, current_settings, timeout)
            return self._translate_via_native_api(messages, headers, current_settings, timeout)
        except Timeout:
            raise TranslationProviderError(f"Request timed out after {timeout} seconds.")
        except requests.RequestException as e:
            error_details = ""
            try:
                error_details = e.response.json()
            except Exception:
                error_details = e.response.text if e.response else "No response body"
            raise TranslationProviderError(f"API request failed: {e}\nDetails: {error_details}")

    def translate_stream(self, messages: List[Dict[str, str]], session: Optional[dict] = None, settings_override: Optional[Dict[str, Any]] = None):
        current_settings = self.settings.copy()
        if settings_override:
            current_settings.update(settings_override)

        timeout = 120
        if isinstance(current_settings.get('timeout'), int) and current_settings['timeout'] > 0:
            timeout = current_settings['timeout']

        extra_headers = current_settings.get('extra_headers')
        headers = {"Content-Type": "application/json"}
        if isinstance(extra_headers, dict):
            headers.update(extra_headers)

        try:
            if self._use_openai_compat:
                # Assuming the compatible endpoint also supports OpenAI's stream format
                compat_provider = OpenAIChatProvider(self.settings)
                yield from compat_provider.translate_stream(messages, session, settings_override)
            else:
                yield from self._translate_via_native_stream(messages, headers, current_settings, timeout)
        except requests.RequestException as e:
            error_details = ""
            try:
                error_details = e.response.json()
            except Exception:
                error_details = e.response.text if e.response else "No response body"
            raise TranslationProviderError(f"API request failed: {e}\nDetails: {error_details}")

    def _translate_via_openai_compat(self, messages: List[Dict[str, str]], headers: Dict[str, str], current_settings: Dict[str, Any], timeout: int) -> ProviderResponse:
        request_headers = dict(headers)
        auth_token = self.api_key or "dummy"
        request_headers["Authorization"] = f"Bearer {auth_token}"

        body: Dict[str, Any] = {"model": self.model, "messages": messages}
        if isinstance(current_settings.get('temperature'), (float, int)):
            body['temperature'] = current_settings['temperature']
        max_tokens = current_settings.get('max_output_tokens')
        if isinstance(max_tokens, int) and max_tokens > 0:
            body['max_tokens'] = max_tokens

        endpoint = f"{self.base_url}/v1/chat/completions"
        response = requests.post(endpoint, headers=request_headers, json=body, timeout=timeout)
        response.raise_for_status()
        data = response.json()
        text = None
        if data.get('choices'):
            first_choice = data['choices'][0]
            message = first_choice.get('message')
            if isinstance(message, dict):
                text = message.get('content')
            if text is None:
                text = first_choice.get('text')
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
        
    def _translate_via_native_api(self, messages: List[Dict[str, str]], headers: Dict[str, str], current_settings: Dict[str, Any], timeout: int) -> ProviderResponse:
        endpoint = f"{self.base_url}/{self.model}:generateContent?key={self.api_key}"
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

        response = requests.post(endpoint, headers=headers, json=body, timeout=timeout)
        response.raise_for_status()
        data = response.json()

        text = None
        if data.get('candidates'):
            first_candidate = data['candidates'][0]
            parts = first_candidate.get('content', {}).get('parts')
            if parts:
                text = parts[0].get('text')

        return ProviderResponse(text=text, raw_payload=data)

    def _translate_via_native_stream(self, messages: List[Dict[str, str]], headers: Dict[str, str], current_settings: Dict[str, Any], timeout: int):
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

def create_translation_provider(provider_key: str, settings: Dict[str, Any]) -> BaseTranslationProvider:
    """Factory function to create a translation provider instance."""
    if provider_key == 'openai_chat':
        return OpenAIChatProvider(settings)

    if provider_key == 'ollama_chat':
        return OllamaChatProvider(settings)

    if provider_key == 'deepl':
        return DeepLProvider(settings)
    if provider_key == 'gemini':
        return GeminiProvider(settings)
    if provider_key == 'perplexity':
        return OpenAIChatProvider(settings)
    raise TranslationProviderError(f"Unknown provider key: {provider_key}")

def get_provider_for_config(config: Dict[str, Any]) -> BaseTranslationProvider:
    """
    Initializes and returns a translation provider based on a configuration dictionary.
    This is intended for one-off tasks like glossary building.
    """
    provider_name = config.get("provider", "").lower()
    
    # The config passed here is the specific config for the task,
    # e.g., mw.glossary_ai, which already contains api_key, model, etc.
    
    if provider_name == 'openai':
        return OpenAIChatProvider(config)
    elif provider_name == 'ollama':
        # Ollama provider expects 'base_url' and 'model' in its settings,
        # which should be present in the passed config.
        return OllamaChatProvider(config)
    elif provider_name == 'gemini':
        return GeminiProvider(config)
    
    raise TranslationProviderError(f"Unknown or unsupported provider for this task: {provider_name}")