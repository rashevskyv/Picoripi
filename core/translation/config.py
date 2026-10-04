"""Default AI translation settings and merging them with saved ones."""

from typing import Dict

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
        # Identical strings (same text, speaker, addressee and window) are sent
        # once per run and share the translation.
        "fold_duplicates": True,
        # Glossary sections whose entries are fixed outputs: a game string that
        # is exactly such a term takes the glossary translation, without a request.
        "fixed_output_sections": ["UI"],
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
