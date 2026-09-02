"""UI translation catalogs. English source strings are the keys.

Look up the current language JSON under locales/; missing keys fall back to
English, then to the key itself. Russian is not a supported UI language.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Dict, Optional

ROOT = Path(__file__).resolve().parent.parent
LOCALES_DIR = ROOT / "locales"
LANGS_PATH = ROOT / "tools" / "i18n-translate" / "languages.json"

# Languages the running app offers. Other catalogs may exist for deploy-time
# translation; they stay out of the Language menu until added here.
SHIPPED_UI_LANGUAGES = ("en", "uk")

_catalog: Dict[str, str] = {}
_language = "en"
_names: Dict[str, str] = {}


def language_names() -> Dict[str, str]:
    """code -> label in the Language menu."""
    global _names
    if _names:
        return _names
    _names = {"en": "English", "uk": "Українська"}
    if LANGS_PATH.exists():
        extra = json.loads(LANGS_PATH.read_text(encoding="utf-8"))
        extra.pop("ru", None)
        for code, name in extra.items():
            _names.setdefault(code, name)
    return _names


def available_languages() -> list:
    """Codes shown in the in-app Language menu (English + Ukrainian)."""
    return [c for c in SHIPPED_UI_LANGUAGES]


def current_language() -> str:
    return _language


def _load_file(code: str) -> Dict[str, str]:
    path = LOCALES_DIR / f"{code}.json"
    if not path.exists():
        return {}
    data = json.loads(path.read_text(encoding="utf-8"))
    return {str(k): str(v) for k, v in data.items() if isinstance(v, str)}


def set_language(code: str) -> str:
    """Load catalogs for ``code``. Unknown codes become English."""
    global _catalog, _language
    names = language_names()
    if code not in SHIPPED_UI_LANGUAGES:
        code = "en"
    en = _load_file("en")
    chosen = {} if code == "en" else _load_file(code)
    merged = dict(en)
    for key, value in chosen.items():
        if value.strip():
            merged[key] = value
    _catalog = merged
    _language = code
    return _language


def tr(text: str, *args, **kwargs) -> str:
    """Translate a UI string. ``text`` is the English source (and the catalog key)."""
    if not text:
        return text
    out = _catalog.get(text, text)
    if args or kwargs:
        try:
            out = out.format(*args, **kwargs)
        except (IndexError, KeyError, ValueError):
            try:
                out = text.format(*args, **kwargs)
            except (IndexError, KeyError, ValueError):
                return out
    return out


def init(code: Optional[str] = None) -> str:
    """Load language at startup. Default English."""
    return set_language(code or "en")
