"""Resolve a provider-ready AI config for glossary tasks.

``get_provider_for_config`` expects a FLAT config (``api_key``, ``endpoint``,
``model`` at the top level), but ``translation_config`` is nested
(``providers.<name>.api_key``) and ``glossary_ai`` may deliberately carry no key
of its own when the user ticked "use the AI Translation key".

Both glossary entry points -- the per-block builder and the text-sweep pipeline
-- resolve their config through here so they behave identically.
"""
from __future__ import annotations

from typing import Any, Dict


# Which provider sections of translation_config can satisfy a glossary provider.
_PROVIDER_KEY_MAP = {
    'OpenAI': ['openai', 'openai_chat', 'perplexity'],
    'OpenAI Compatible': ['openai', 'openai_chat', 'perplexity'],
    'Gemini': ['gemini'],
    'Ollama': ['ollama_chat'],
}


def resolve_translation_credentials(translation_config: Dict[str, Any], provider_name: str) -> Dict[str, Any]:
    """Pull credentials for ``provider_name`` out of the nested translation config."""
    providers_cfg = {}
    if isinstance(translation_config, dict):
        providers_cfg = translation_config.get('providers', {}) or {}

    base_url = ''
    for key in _PROVIDER_KEY_MAP.get(provider_name, []):
        cfg = providers_cfg.get(key, {}) or {}

        url_val = cfg.get('endpoint') or cfg.get('base_url')
        if not base_url and url_val:
            base_url = url_val

        api_key = cfg.get('api_key')
        api_key_env = cfg.get('api_key_env')
        if api_key or api_key_env or base_url:
            credentials: Dict[str, Any] = {
                'api_key': api_key or '',
                'api_key_env': api_key_env or '',
            }
            if base_url:
                credentials['base_url'] = base_url
                credentials['endpoint'] = base_url
            if cfg.get('timeout'):
                credentials['timeout'] = cfg.get('timeout')
            return credentials

    if provider_name == 'Ollama' and base_url:
        return {'base_url': base_url}

    return {}


def flatten_active_translation_config(translation_config: Dict[str, Any]) -> Dict[str, Any]:
    """Flatten the *active* provider of translation_config into a flat config.

    This is the fallback when the glossary has no usable settings of its own:
    whatever powers AI Translate should also power a glossary build.

    ``provider`` may be a section key (``openai``) or a display name
    (``OpenAI Compatible``), so both are resolved.
    """
    if not isinstance(translation_config, dict):
        return {}

    provider_name = translation_config.get('provider') or ''
    if not provider_name or provider_name == 'disabled':
        return {}

    providers_cfg = translation_config.get('providers', {}) or {}
    settings = providers_cfg.get(provider_name, {}) or {}
    if not settings:
        # Display name -> section key (e.g. "OpenAI Compatible" -> "openai").
        for key in _PROVIDER_KEY_MAP.get(provider_name, []):
            candidate = providers_cfg.get(key, {}) or {}
            if candidate:
                settings = candidate
                break
    if not settings:
        return {}

    flat: Dict[str, Any] = {'provider': provider_name}
    flat.update(settings)
    # OpenAI-compatible providers accept either spelling; supply both.
    url_val = settings.get('endpoint') or settings.get('base_url')
    if url_val:
        flat['endpoint'] = url_val
        flat['base_url'] = url_val
    return flat


def _has_usable_credentials(config: Dict[str, Any]) -> bool:
    """Whether a flat config can plausibly reach a provider."""
    if config.get('api_key') or config.get('api_key_env'):
        return True
    # Local / self-hosted endpoints legitimately need no key.
    return bool(config.get('endpoint') or config.get('base_url'))


def resolve_glossary_ai_config(mw) -> Dict[str, Any]:
    """Return a flat, provider-ready config for glossary AI work.

    Resolution order:
    1. ``glossary_ai`` as configured;
    2. if it defers to the translation key, merge those credentials in;
    3. if it still cannot reach a provider, fall back to the active
       AI Translation provider (flattened), so a working AI Translate setup is
       always enough to build a glossary.
    """
    translation_config = getattr(mw, 'translation_config', {}) or {}
    config: Dict[str, Any] = dict(getattr(mw, 'glossary_ai', {}) or {})

    if config.get('use_translation_api_key'):
        config.update(resolve_translation_credentials(translation_config, config.get('provider', '')))

    if config.get('provider') and _has_usable_credentials(config):
        return config

    fallback = flatten_active_translation_config(translation_config)
    if fallback:
        # Keep glossary-specific knobs (model, chunk size) when they were set.
        for key in ('model', 'chunk_size', 'temperature'):
            if config.get(key):
                fallback[key] = config[key]
        return fallback

    return config
