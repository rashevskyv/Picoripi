import re

def is_control_modifier_pressed() -> bool:
    """Check if Ctrl key modifier is physically or logically pressed.

    This encapsulates ctypes User32 queries on Windows and QApplication state checks,
    providing a centralized and reliable keyboard query API for tests and production.
    """
    try:
        import ctypes
        if hasattr(ctypes, 'windll') and hasattr(ctypes.windll, 'user32'):
            # Try GetAsyncKeyState (0x11 is VK_CONTROL) to check the physical keyboard state directly
            if bool(ctypes.windll.user32.GetAsyncKeyState(0x11) & 0x8000):
                return True
            if bool(ctypes.windll.user32.GetKeyState(0x11) & 0x8000):
                return True
    except Exception:
        pass

    try:
        from PyQt6.QtWidgets import QApplication
        from PyQt6.QtCore import Qt
        modifiers = QApplication.keyboardModifiers()
        if hasattr(modifiers, 'value'):
            return bool(modifiers.value & Qt.KeyboardModifier.ControlModifier.value)
        elif isinstance(modifiers, int):
            return bool(modifiers & Qt.KeyboardModifier.ControlModifier.value)
        else:
            return bool(modifiers & Qt.KeyboardModifier.ControlModifier)
    except Exception:
        pass
    return False

def resolve_target_language_prompt(text: str, target_lang: str) -> str:
    """Centralized helper to resolve target language placeholders in AI prompts.

    Main workflow:
      Replaces "{target_lang}" with the resolved target language (e.g. "Spanish").
      This is the primary and recommended path for all bundled and custom prompts.

    Legacy Fallback:
      Also replaces the literal word "Ukrainian" with target_lang for backward
      compatibility with older user files or plugins.

      WARNING: This replacement is a simple string replacement and CANNOT automatically
      translate Ukrainian text, Cyrillic letters, grammar-specific examples, or rules
      into the target language. Bundled prompts should rely on explicit {target_lang}
      placeholders and neutral English instructions.
    """
    if not text:
        return ""
    if not isinstance(target_lang, str) or not target_lang.strip():
        target_lang = "Ukrainian"

    temp_placeholder = "___TARGET_LANG_TEMP_PLACEHOLDER___"
    text = text.replace("{target_lang}", temp_placeholder)
    text = text.replace("Ukrainian", target_lang)
    text = text.replace(temp_placeholder, target_lang)
    return text

_NATURAL_CHUNK_RE = re.compile(r"(\d+)")

def natural_sort_key(value: str):
    """Sort key that orders embedded numbers by value, not by digit.

    Plain alphabetical ordering puts "Voice 100" between "Voice 10" and
    "Voice 11", which reads as broken to anyone scanning a list. Digits are
    compared as integers and everything else case-insensitively.
    """
    parts = _NATURAL_CHUNK_RE.split(str(value or ""))
    # (0, n) sorts numbers before text of equal position without ever comparing
    # an int against a str.
    return [(0, int(p), "") if p.isdigit() else (1, 0, p.casefold()) for p in parts]
