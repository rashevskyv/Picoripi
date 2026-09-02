"""UI translation catalogs. English source strings are the keys.

Look up the current language JSON under locales/; missing or empty keys fall
back to English, then to the key itself. Russian is not a supported UI language.

The Language menu lists a catalog only when the file exists and has UI strings.
Each file's own display name is the reserved key ``@language_name``.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Dict, Optional

ROOT = Path(__file__).resolve().parent.parent
LOCALES_DIR = ROOT / "locales"
LANGUAGE_NAME_KEY = "@language_name"

_catalog: Dict[str, str] = {}
_language = "en"


def _load_file(code: str) -> Dict[str, str]:
    path = LOCALES_DIR / f"{code}.json"
    if not path.exists():
        return {}
    data = json.loads(path.read_text(encoding="utf-8"))
    return {str(k): str(v) for k, v in data.items() if isinstance(v, str)}


def _has_ui_strings(data: Dict[str, str]) -> bool:
    return any(
        key and not key.startswith("@") and value.strip()
        for key, value in data.items()
    )


def available_languages() -> list:
    """Codes shown in the Language menu: catalogs on disk that have translations."""
    codes = []
    if LOCALES_DIR.is_dir():
        for path in sorted(LOCALES_DIR.glob("*.json")):
            code = path.stem
            if code == "ru":
                continue
            data = _load_file(code)
            if code == "en" or _has_ui_strings(data):
                codes.append(code)
    if "en" in codes:
        codes.remove("en")
    codes.insert(0, "en")
    return codes


def language_display_name(code: str) -> str:
    """Name as stored in that language's catalog."""
    name = _load_file(code).get(LANGUAGE_NAME_KEY, "").strip()
    if name:
        return name
    if code == "en":
        return "English"
    return code


def language_names() -> Dict[str, str]:
    """code -> label in the Language menu."""
    return {code: language_display_name(code) for code in available_languages()}


def current_language() -> str:
    return _language


def set_language(code: str) -> str:
    """Load catalogs for ``code``. Unknown codes become English."""
    global _catalog, _language
    if code not in available_languages():
        code = "en"
    en = _load_file("en")
    chosen = {} if code == "en" else _load_file(code)
    merged = dict(en)
    for key, value in chosen.items():
        if key.startswith("@"):
            continue
        if value.strip():
            merged[key] = value
    _catalog = merged
    _language = code
    return _language


def tr(text: str, *args, **kwargs) -> str:
    """Translate a UI string. Missing entries stay English (the key)."""
    if not text:
        return text
    out = _catalog.get(text, text)
    if not str(out).strip():
        out = text
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
