import re
import difflib
import string
from typing import List, Tuple

from core.tag_utils import ALL_TAGS_PATTERN

def is_fuzzy_match(word1: str, word2: str, threshold: float = 0.8) -> bool:
    """
    Checks if two words are similar enough using SequenceMatcher.
    Ignores case.
    """
    if not word1 or not word2:
        return False
    if word1.lower() == word2.lower():
        return True
    if abs(len(word1) - len(word2)) > 3:
        return False

    return difflib.SequenceMatcher(None, word1.lower(), word2.lower()).ratio() >= threshold

def prepare_text_for_tagless_search(text: str, keep_original_case: bool = False) -> str:
    """Prepare text for tagless search."""
    if text is None:
        return ""

    # Remove all bracket and curly tags (correctly replacing forced aliases with their words)
    from utils.text_tags import remove_all_tags
    no_tags_text = remove_all_tags(text)

    # Replace Zelda-style '+' separators with spaces
    text_with_normalized_plus = no_tags_text.replace('+', ' ')

    # Replace dots (display symbols) with spaces
    from utils.display_text import SPACE_DOT_SYMBOL
    text_with_normalized_dots = text_with_normalized_plus.replace(SPACE_DOT_SYMBOL, ' ')

    # Standardize newlines and multiple spaces
    text_with_spaces_instead_of_newlines = text_with_normalized_dots.replace('\n', ' ')
    normalized_spaces_text = re.sub(r' {2,}', ' ', text_with_spaces_instead_of_newlines)

    stripped_text = normalized_spaces_text.strip()
    return stripped_text

def suggest_smart_translation(current_text: str, old_translation: str, new_translation: str) -> str:
    """
    Suggests a translation by replacing occurrences of the old translation with the new translation.
    Tries direct replacement first, then falls back to word-by-word morphological replacement.
    Supports case declensions for Slavic languages.
    """
    if not current_text or not old_translation or not new_translation:
        return current_text if current_text is not None else ""

    # 1. Try direct substring replacement first
    if old_translation in current_text:
        return current_text.replace(old_translation, new_translation)

    # 2. Try word-by-word morphological replacement
    old_words = [w for w in re.split(r'\W+', old_translation) if w]
    new_words = [w for w in re.split(r'\W+', new_translation) if w]

    # We can only align if they have the same number of words
    if len(old_words) != len(new_words) or not old_words:
        return current_text

    # Identify which words changed
    changed_indices = []
    for idx in range(len(old_words)):
        if old_words[idx].lower() != new_words[idx].lower():
            changed_indices.append(idx)

    if not changed_indices:
        return current_text

    result_text = current_text

    # Find all words in the text with their spans
    # We iterate backwards to avoid span shifts during replacement
    words_in_text = list(re.finditer(r'\w+', current_text))
    for match in reversed(words_in_text):
        w_text = match.group(0)

        # Check if this word matches any changed word in the old translation
        for idx in changed_indices:
            w_old = old_words[idx]
            w_new = new_words[idx]

            # Find longest common prefix (case-insensitive)
            common_len = 0
            min_len = min(len(w_old), len(w_text))
            for char_idx in range(min_len):
                if w_old[char_idx].lower() == w_text[char_idx].lower():
                    common_len += 1
                else:
                    break

            # Check if it's a valid morphological match (inflection of the same word)
            # Threshold: prefix must be at least 3 chars, and difference must be at most 3 chars
            if common_len >= 3 and (len(w_old) - common_len <= 3) and (len(w_text) - common_len <= 3):
                e_old = w_old[common_len:]
                e_text = w_text[common_len:]

                w_new_modified = w_new
                if e_old:
                    if w_new.lower().endswith(e_old.lower()):
                        w_new_modified = w_new[:-len(e_old)] + e_text
                else:
                    w_new_modified = w_new + e_text

                # Preserve case of the original word in text
                if w_text[0].isupper():
                    w_new_modified = w_new_modified[0].upper() + w_new_modified[1:]
                else:
                    w_new_modified = w_new_modified[0].lower() + w_new_modified[1:]

                # Replace the word in result_text
                start, end = match.span()
                result_text = result_text[:start] + w_new_modified + result_text[end:]
                break # Move to next word in text

    return result_text

def extract_first_word_with_tags(text: str) -> Tuple[str, str]:
    """Extract first word with tags."""
    if not text or not text.strip():
        return "", text
    first_word_text = ""
    char_idx = 0
    while char_idx < len(text):
        char = text[char_idx]
        if char.isspace():
            if first_word_text:
                break
            else:
                first_word_text += char
                char_idx += 1
                continue
        is_tag_char = False
        for tag_match in ALL_TAGS_PATTERN.finditer(text[char_idx:]):
            if tag_match.start() == 0:
                tag_content = tag_match.group(0)
                first_word_text += tag_content
                char_idx += len(tag_content)
                is_tag_char = True
                break
        if is_tag_char:
            continue
        first_word_text += char
        char_idx += 1
    remaining_text = text[len(first_word_text):].lstrip()
    return first_word_text.rstrip(), remaining_text


PUNCTUATION_CHARS = set(string.punctuation + "«»—–“”„")

def clean_and_map_punctuation(text: str) -> Tuple[str, List[int]]:
    """Clean and map punctuation."""
    if text is None:
        return "", []
    clean_chars = []
    mapping = []
    for idx, char in enumerate(text):
        if char not in PUNCTUATION_CHARS:
            clean_chars.append(char)
            mapping.append(idx)
    return "".join(clean_chars), mapping

def find_smart_matches(text: str, query: str, case_sensitive: bool = False) -> List[Tuple[int, int]]:
    """Find smart matches."""
    if not query or not text:
        return []

    has_punctuation = any(c in PUNCTUATION_CHARS for c in query)

    if not has_punctuation:
        clean_text, mapping = clean_and_map_punctuation(text)
        clean_query, _ = clean_and_map_punctuation(query)
    else:
        clean_text = text
        mapping = list(range(len(text)))
        clean_query = query

    if not clean_query:
        return []

    # Build regex pattern for clean_query
    # Split by word characters to find individual words
    tokens = re.split(r'(\w+)', clean_query)
    pattern_parts = []

    for token in tokens:
        if not token:
            continue
        if token.isalnum(): # It's a word
            # Check if word has any uppercase characters
            has_upper = any(c.isupper() for c in token)
            escaped_token = re.escape(token)
            if case_sensitive or has_upper:
                pattern_parts.append(escaped_token)
            else:
                pattern_parts.append(f"(?i:{escaped_token})")
        else: # It's non-word (spaces, etc.)
            pattern_parts.append(re.escape(token))

    pattern = "".join(pattern_parts)

    matches = []
    try:
        for match in re.finditer(pattern, clean_text):
            start_in_clean = match.start()
            end_in_clean = match.end()
            if start_in_clean < end_in_clean:
                # Map back to original text indices
                orig_start = mapping[start_in_clean]
                orig_end = mapping[end_in_clean - 1] + 1
                matches.append((orig_start, orig_end))
    except re.error:
        # Fallback to simple find if regex fails
        pass
    return matches
