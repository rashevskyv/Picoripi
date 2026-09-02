"""Case-preserving string replacement helpers for glossary edits."""
from __future__ import annotations

import re


def preserve_case(match_text: str, replacement: str) -> str:
    """
    Detects the casing of match_text and returns replacement with the same casing.
    Supports ALL CAPS, Title Case (Capitalized), and lowercase.
    """
    if not match_text or not replacement:
        return replacement
    if match_text.isupper():
        return replacement.upper()
    if match_text.islower():
        return replacement.lower()
    if match_text[0].isupper():
        return replacement[0].upper() + replacement[1:]
    return replacement

def replace_preserve_case(text: str, find_word: str, replace_word: str) -> str:
    """
    Case-insensitive substring replacement that preserves the case of the matched portion.
    """
    if not text or not find_word:
        return text
    
    pattern = re.compile(re.escape(find_word), re.IGNORECASE)
    
    def repl(match):
        """Repl."""
        return preserve_case(match.group(0), replace_word)
        
    return pattern.sub(repl, text)
