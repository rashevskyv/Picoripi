"""Tests for glossary AI config resolution (shared by both glossary entry points)."""
from unittest.mock import MagicMock

from handlers.translation.glossary_ai_config import (
    flatten_active_translation_config,
    resolve_glossary_ai_config,
    resolve_translation_credentials,
)


def _mw(glossary_ai=None, translation_config=None):
    mw = MagicMock()
    mw.glossary_ai = glossary_ai if glossary_ai is not None else {}
    mw.translation_config = translation_config if translation_config is not None else {}
    return mw


# A working "OpenAI Compatible" setup pointed at a local proxy, as configured in
# Settings -> AI Translation.
LOCAL_PROXY_CONFIG = {
    "provider": "OpenAI Compatible",
    "providers": {
        "openai": {
            "api_key": "sk-local",
            "endpoint": "http://localhost:8081/v1",
            "model": "gemini-3.6-flash",
        }
    },
}


class TestResolveTranslationCredentials:
    def test_openai_compatible_reads_openai_section(self):
        creds = resolve_translation_credentials(LOCAL_PROXY_CONFIG, "OpenAI Compatible")
        assert creds["api_key"] == "sk-local"
        assert creds["endpoint"] == "http://localhost:8081/v1"
        assert creds["base_url"] == "http://localhost:8081/v1"

    def test_unknown_provider_returns_empty(self):
        assert resolve_translation_credentials(LOCAL_PROXY_CONFIG, "Nonexistent") == {}

    def test_non_dict_config_safe(self):
        assert resolve_translation_credentials(None, "OpenAI") == {}


class TestFlatten:
    def test_flattens_active_provider(self):
        flat = flatten_active_translation_config(LOCAL_PROXY_CONFIG)
        assert flat["provider"] == "OpenAI Compatible"
        assert flat["api_key"] == "sk-local"
        assert flat["endpoint"] == "http://localhost:8081/v1"

    def test_flattens_when_provider_is_section_key(self):
        config = {"provider": "openai", "providers": LOCAL_PROXY_CONFIG["providers"]}
        flat = flatten_active_translation_config(config)
        assert flat["api_key"] == "sk-local"

    def test_missing_active_section_returns_empty(self):
        assert flatten_active_translation_config({"provider": "gemini", "providers": {}}) == {}

    def test_disabled_provider_returns_empty(self):
        assert flatten_active_translation_config(
            {"provider": "disabled", "providers": LOCAL_PROXY_CONFIG["providers"]}
        ) == {}


class TestResolveGlossaryAiConfig:
    def test_glossary_own_credentials_win(self):
        mw = _mw(glossary_ai={"provider": "Gemini", "api_key": "own-key"})
        config = resolve_glossary_ai_config(mw)
        assert config["api_key"] == "own-key"

    def test_use_translation_key_merges_credentials(self):
        mw = _mw(
            glossary_ai={"provider": "OpenAI Compatible", "use_translation_api_key": True},
            translation_config=LOCAL_PROXY_CONFIG,
        )
        config = resolve_glossary_ai_config(mw)
        assert config["api_key"] == "sk-local"
        assert config["endpoint"] == "http://localhost:8081/v1"

    def test_empty_glossary_settings_fall_back_to_translation(self):
        """A working AI Translate setup alone must be enough to build a glossary."""
        mw = _mw(glossary_ai={}, translation_config=LOCAL_PROXY_CONFIG)
        config = resolve_glossary_ai_config(mw)
        assert config["provider"] == "OpenAI Compatible"
        assert config["api_key"] == "sk-local"
        assert config["endpoint"] == "http://localhost:8081/v1"

    def test_keyless_glossary_provider_falls_back(self):
        # provider named but no key and no endpoint -> cannot reach anything
        mw = _mw(
            glossary_ai={"provider": "OpenAI", "model": "gpt-4o"},
            translation_config=LOCAL_PROXY_CONFIG,
        )
        config = resolve_glossary_ai_config(mw)
        assert config["api_key"] == "sk-local"
        assert config["model"] == "gpt-4o"  # glossary-specific knob preserved

    def test_local_endpoint_without_key_is_usable(self):
        mw = _mw(glossary_ai={"provider": "Ollama", "base_url": "http://localhost:11434"})
        config = resolve_glossary_ai_config(mw)
        assert config["provider"] == "Ollama"
        assert config["base_url"] == "http://localhost:11434"

    def test_nothing_configured_returns_glossary_config_unchanged(self):
        mw = _mw(glossary_ai={"provider": "OpenAI"}, translation_config={})
        assert resolve_glossary_ai_config(mw) == {"provider": "OpenAI"}
