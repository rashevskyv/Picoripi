"""Default AI translation settings and merging them with saved ones."""

from typing import Dict, Tuple


def merge_translation_config(base: Dict, custom: Dict) -> Dict:
    """Recursively merge custom config into base, avoiding deep mutation."""
    if not isinstance(custom, dict):
        return base
    
    merged = dict(base)
    
    for key, custom_value in custom.items():
        base_value = merged.get(key)
        
        if isinstance(base_value, dict) and isinstance(custom_value, dict):
            merged[key] = merge_translation_config(base_value, custom_value)
        elif custom_value is not None:
            merged[key] = custom_value
            
    return merged

# The review pass runs unless the translation config says otherwise (owner's call after the Minish Cap
# measurement, 2026-10-04). Read when the default config is built.
DEFAULT_REVIEW_ENABLED = True

SERIES_SENTENCE_WORDS = 2


def series_reuse_settings(config) -> Tuple[bool, int, bool]:
    """``(reuse on, words that make a sentence, safe matches start ticked)`` from a translation config (D45).

    A missing or unusable value takes its default: off, 2 words, ticked. The memory reads these; core keeps no config.
    """
    values = config if isinstance(config, dict) else {}
    try:
        words = max(int(values.get("series_sentence_words", SERIES_SENTENCE_WORDS)), 0)
    except (TypeError, ValueError):
        words = SERIES_SENTENCE_WORDS
    return bool(values.get("series_reuse_sentences", False)), words, bool(values.get("series_safe_ticked", True))


def build_default_translation_config() -> dict:
    """Create default translation config."""
    return {
        "provider": "disabled",
        "session_mode": "auto",
        "workers": 6,
        # The review pass: a second request per chunk in the translation's own conversation
        # (REVIEW_REQUEST); "review_model" may name another model for it. On by default since 2026-10-04;
        # the old "editor_review_enabled" belonged to the removed editor review and is not read.
        "review_enabled": DEFAULT_REVIEW_ENABLED,
        # The shorten pass: an item whose typeset text needs more windows than the source, or a line wider
        # than the limit, goes back once with "shorten by about N letters" (SHORTEN_REQUEST).
        "shorten_enabled": True,
        # Identical strings (same text, speaker, addressee and window) are sent
        # once per run and share the translation.
        "fold_duplicates": True,
        # Glossary sections whose entries are fixed outputs: a game string that
        # is exactly such a term takes the glossary translation, without a request.
        "fixed_output_sections": ["UI"],
        # Sentences of other games of the series (more words than "series_sentence_words") are offered only when
        # "series_reuse_sentences" is on (off by default). "series_safe_ticked": safe matches start ticked (D45).
        "series_reuse_sentences": False,
        "series_safe_ticked": True,
        "series_sentence_words": 2,
        "providers": {
            "openai": {
                "api_key": "",
                "api_key_env": "OPENAI_API_KEY",
                "endpoint": "",
                # auto | web2api | openai -- see core.translation.providers.detect_profile
                "profile": "auto",
                "model": "gpt-4o-mini",
                "temperature": 0.0,
                "max_output_tokens": 0,
                "timeout": 60,
                "extra_headers": {},
            },

            "ollama_chat": {
                "base_url": "http://localhost:11434",
                "model": "llama3",
                "temperature": 0.0,
                "timeout": 120,
                "keep_alive": "",
                "extra_headers": {},
            },

            "gemini": {
                "api_key": "",
                "api_key_env": "GEMINI_API_KEY",
                "model": "gemini-3.7-flash",
                "temperature": 0.0,
                "timeout": 120,
                "base_url": "",
            },
        },
    }
