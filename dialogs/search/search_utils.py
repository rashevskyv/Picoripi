# dialogs/search/search_utils.py
from typing import List, Tuple
from utils.utils import ALL_TAGS_PATTERN, FORCED_ALIAS_PATTERN

def map_forced_aliases(text: str) -> Tuple[str, List[int]]:
    # Returns (processed_text, list of original indices)
    result_chars = []
    mapping = []
    idx = 0
    n = len(text)
    while idx < n:
        match = FORCED_ALIAS_PATTERN.match(text, idx)
        if match:
            content = match.group(1)
            content_start = match.start(1)
            for offset, char in enumerate(content):
                result_chars.append(char)
                mapping.append(content_start + offset)
            idx = match.end()
        else:
            result_chars.append(text[idx])
            mapping.append(idx)
            idx += 1
    return "".join(result_chars), mapping

def map_remove_all_tags(text: str, current_mapping: List[int]) -> Tuple[str, List[int]]:
    result_chars = []
    mapping = []
    idx = 0
    n = len(text)
    while idx < n:
        match = ALL_TAGS_PATTERN.match(text, idx)
        if match:
            idx = match.end()
        else:
            result_chars.append(text[idx])
            mapping.append(current_mapping[idx])
            idx += 1
    return "".join(result_chars), mapping

def prepare_text_for_tagless_search_with_mapping(text: str) -> Tuple[str, List[int]]:
    if text is None:
        return "", []

    t1, m1 = map_forced_aliases(text)
    t2, m2 = map_remove_all_tags(t1, m1)

    t3_chars = []
    for char in t2:
        if char == '+' or char == '·' or char == '\n':
            t3_chars.append(' ')
        else:
            t3_chars.append(char)
    t3 = "".join(t3_chars)
    m3 = m2

    t4_chars = []
    m4 = []
    n = len(t3)
    idx = 0
    while idx < n:
        if t3[idx] == ' ':
            t4_chars.append(' ')
            m4.append(m3[idx])
            idx += 1
            while idx < n and t3[idx] == ' ':
                idx += 1
        else:
            t4_chars.append(t3[idx])
            m4.append(m3[idx])
            idx += 1
    t4 = "".join(t4_chars)

    start_strip = 0
    while start_strip < len(t4) and t4[start_strip] == ' ':
        start_strip += 1

    end_strip = len(t4)
    while end_strip > start_strip and t4[end_strip - 1] == ' ':
        end_strip -= 1

    final_text = t4[start_strip:end_strip]
    final_mapping = m4[start_strip:end_strip]

    return final_text, final_mapping

def adjust_replacement_case(original: str, replacement: str, match_case: bool) -> str:
    if not replacement:
        return replacement
    # If the user explicitly enters a replacement starting with an uppercase letter,
    # respect their choice (user's input casing takes priority).
    if replacement[0].isupper():
        return replacement
    if not match_case:
        return replacement

    # Check original word casing
    # An all-uppercase word must have length > 1 to be considered truly all-caps,
    # otherwise a single letter (like "O" or "I") is treated as capitalized.
    if len(original) > 1 and original.isupper():
        return replacement.upper()
    if original and original[0].isupper():
        return replacement[0].upper() + replacement[1:] if len(replacement) > 1 else replacement.upper()
    return replacement
