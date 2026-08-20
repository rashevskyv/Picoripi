from core.translation.config import build_default_translation_config, merge_translation_config


def test_build_default_translation_config():
    cfg = build_default_translation_config()
    assert cfg["provider"] == "disabled"
    assert cfg["workers"] == 6
    assert "openai" in cfg["providers"]
    assert "gemini" in cfg["providers"]
    assert cfg["providers"]["gemini"]["model"] == "gemini-3.7-flash"


def test_merge_translation_config():
    base = build_default_translation_config()
    custom = {
        "provider": "openai",
        "workers": 8,
        "providers": {
            "openai": {
                "endpoint": "http://127.0.0.1:8081/v1",
                "model": "gemini-3.7-flash",
            }
        }
    }
    merged = merge_translation_config(base, custom)
    assert merged["provider"] == "openai"
    assert merged["workers"] == 8
    assert merged["providers"]["openai"]["endpoint"] == "http://127.0.0.1:8081/v1"
    assert merged["providers"]["openai"]["model"] == "gemini-3.7-flash"
    # Verify non-overridden fields are preserved
    assert merged["providers"]["openai"]["temperature"] == 0.0
    assert merged["providers"]["gemini"]["model"] == "gemini-3.7-flash"
