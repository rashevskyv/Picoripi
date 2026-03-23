# --- START OF FILE core/translation/config.py ---

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

def build_default_translation_config() -> dict:
    return {
        "provider": "disabled",
        "session_mode": "auto",
        "providers": {
            "openai": {
                "api_key": "",
                "api_key_env": "OPENAI_API_KEY",
                "base_url": "",
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
                "model": "gemini-1.5-flash-latest",
                "temperature": 0.0,
                "timeout": 120,
                "base_url": "",
            },
        },
    }
