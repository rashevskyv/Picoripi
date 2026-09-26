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
      1. Resolves conditional language blocks:
         [IF_TARGET_LANG: Ukrainian]...[/IF_TARGET_LANG]
         When target_lang matches the specified language, the block tags are unwrapped
         and its content is preserved. When target_lang differs, the entire block is removed.
      2. Replaces "{target_lang}" with the resolved target language (e.g. "Spanish").
      3. Legacy Fallback: Replaces literal "Ukrainian" with target_lang for backward compatibility.
    """
    if not text:
        return ""
    if not isinstance(target_lang, str) or not target_lang.strip():
        target_lang = "Ukrainian"

    current_lang_clean = target_lang.strip().lower()

    def _replace_conditional_block(match: re.Match) -> str:
        specified_lang = match.group(1).strip().lower()
        content = match.group(2)
        if specified_lang == current_lang_clean:
            return content
        return ""

    text = re.sub(
        r"\[IF_TARGET_LANG:\s*([a-zA-Z_-]+)\][ \t]*\r?\n?([\s\S]*?)\[/IF_TARGET_LANG\][ \t]*\r?\n?",
        _replace_conditional_block,
        text,
        flags=re.IGNORECASE,
    )

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
