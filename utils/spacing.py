from typing import List, Tuple

from core.tag_utils import ALL_TAGS_PATTERN

def analyze_missing_icon_spacing(
    text: str,
    is_visible_tag_func,
    font_map=None,
    default_tag_mappings=None,
    icon_sequences=None
) -> Tuple[List[Tuple[int, int]], List[Tuple]]:
    """
    Analyzes text for missing spacing around icons/tags.
    Returns:
        warning_spans: List of (start, end) tuples in original coordinates.
        edits: List of ('insert', idx, char) or ('delete', start, end) tuples.
    """
    if not text:
        return [], []

    if font_map is None:
        from utils.utils import get_active_font_map
        font_map = get_active_font_map()
    if default_tag_mappings is None:
        from utils.utils import get_active_tag_mappings
        default_tag_mappings = get_active_tag_mappings()
    if icon_sequences is None:
        from utils.utils import get_active_icon_sequences
        icon_sequences = get_active_icon_sequences()

    def should_keep_tag_in_clean_text(tag: str) -> bool:
        if is_visible_tag_func(tag):
            return True
        tag_lower = tag.lower()
        if tag_lower in ('{*}', '{tab}', '{escape:6:000a}', '{escape:6:000b}'):
            return True
        from utils.utils import get_tag_width
        if get_tag_width(tag, default_tag_mappings, font_map, icon_sequences=icon_sequences) > 0:
            return True
        return False

    clean_text_parts = []
    clean_to_orig = []

    last_idx = 0
    tags = []
    for match in ALL_TAGS_PATTERN.finditer(text):
        tags.append((match.start(), match.end(), match.group(0)))

    def add_normal_text(start, end):
        for i in range(start, end):
            clean_to_orig.append(i)
            clean_text_parts.append(text[i])

    for start, end, tag_str in tags:
        if start > last_idx:
            add_normal_text(last_idx, start)

        if should_keep_tag_in_clean_text(tag_str):
            for i in range(len(tag_str)):
                clean_to_orig.append(start + i)
                clean_text_parts.append(tag_str[i])
        last_idx = end

    if last_idx < len(text):
        add_normal_text(last_idx, len(text))

    clean_to_orig.append(len(text))
    clean_str = "".join(clean_text_parts)

    warning_spans = []
    edits = []

    # Rule 1: check alphanumeric transitions
    kept_tags = []
    for match in ALL_TAGS_PATTERN.finditer(clean_str):
        kept_tags.append((match.start(), match.end(), match.group(0)))

    inside_tag_transitions = set()
    for start, end, tag_str in kept_tags:
        for k in range(start, end - 1):
            inside_tag_transitions.add(k)

    for i in range(len(clean_str) - 1):
        if i in inside_tag_transitions:
            continue

        left_char = clean_str[i]
        right_char = clean_str[i+1]

        orig_left = clean_to_orig[i]
        orig_right = clean_to_orig[i+1]
        separated_by_tags = (orig_right - orig_left > 1)

        # Alphanumeric next to alphanumeric (only if separated by tags)
        if left_char.isalnum() and right_char.isalnum():
            if separated_by_tags:
                warning_spans.append((orig_left + 1, orig_right))
                edits.append(('insert', orig_left + 1, ' '))

        # Punctuation followed by alphanumeric across one or more zero-width tags.
        # Adjacent punctuation and text without an intervening tag belongs to other
        # spacing rules and must not produce a Missing Tag Spacing warning.
        elif (
            separated_by_tags
            and left_char in ('.', ',', '!', '?', ':', ';')
            and right_char.isalnum()
        ):
            # Exclude decimals
            if left_char in ('.', ',') and right_char.isdigit() and i > 0 and clean_str[i-1].isdigit():
                continue
            # Span always covers punctuation mark, zero-width tags, and the first letter:
            warning_spans.append((orig_left, orig_right + 1))
            edits.append(('insert', orig_left + 1, ' '))

    # Rule 2: kept tag boundary checks
    for start, end, tag_str in kept_tags:
        if not is_visible_tag_func(tag_str):
            # Only visual icon tags have spacing warnings around them
            continue

        orig_start = clean_to_orig[start]
        orig_end = clean_to_orig[end]

        # Check before the tag
        if start > 0:
            left_char = clean_str[start - 1]
            if left_char.isalnum():
                warning_spans.append((orig_start, orig_end))
                edits.append(('insert', orig_start, ' '))

        # Check after the tag
        if end < len(clean_str):
            right_char = clean_str[end]
            if right_char.isalnum():
                warning_spans.append((orig_start, orig_end))
                edits.append(('insert', orig_end, ' '))

        # Space before hyphen exception check
        if end < len(clean_str):
            rem = clean_str[end:]
            # Must start with space(s) followed by hyphen followed by alnum (no space after hyphen)
            import re
            m = re.match(r"^(\s+)-[a-zA-Z0-9а-яА-ЯёЁіІїЇєЄґҐ]", rem)
            if m:
                spaces_str = m.group(1)
                num_spaces = len(spaces_str)
                warning_spans.append((orig_start, orig_end))
                edits.append(('delete', clean_to_orig[end], clean_to_orig[end + num_spaces]))

    # Unique lists
    warning_spans = sorted(list(set(warning_spans)))
    edits = list(set(edits))

    return warning_spans, edits

def find_missing_icon_spacing_spans(
    text: str,
    is_visible_tag_func,
    font_map=None,
    default_tag_mappings=None,
    icon_sequences=None
) -> List[Tuple[int, int]]:
    """Find missing icon spacing spans."""
    spans, _ = analyze_missing_icon_spacing(
        text,
        is_visible_tag_func,
        font_map=font_map,
        default_tag_mappings=default_tag_mappings,
        icon_sequences=icon_sequences
    )
    return spans

def fix_missing_icon_spacing_for_line(
    line: str,
    is_visible_tag_func,
    font_map=None,
    default_tag_mappings=None,
    icon_sequences=None
) -> str:
    if not line:
        return line

    _, edits = analyze_missing_icon_spacing(
        line,
        is_visible_tag_func,
        font_map=font_map,
        default_tag_mappings=default_tag_mappings,
        icon_sequences=icon_sequences
    )

    if not edits:
        return line

    # Apply edits descending
    def sort_key(edit):
        if edit[0] == 'delete':
            return (edit[1], 0)
        else:
            return (edit[1], 1)

    edits.sort(key=sort_key, reverse=True)

    current_line = line
    for edit in edits:
        if edit[0] == 'delete':
            start, end = edit[1], edit[2]
            current_line = current_line[:start] + current_line[end:]
        elif edit[0] == 'insert':
            idx, char = edit[1], edit[2]
            current_line = current_line[:idx] + char + current_line[idx:]

    return current_line

def fix_missing_icon_spacing(
    text: str,
    is_visible_tag_func,
    font_map=None,
    default_tag_mappings=None,
    icon_sequences=None
) -> str:
    """Fix missing icon spacing."""
    if not text:
        return text
    lines = text.split('\n')
    fixed_lines = [
        fix_missing_icon_spacing_for_line(
            line,
            is_visible_tag_func,
            font_map=font_map,
            default_tag_mappings=default_tag_mappings,
            icon_sequences=icon_sequences
        ) for line in lines
    ]
    return "\n".join(fixed_lines)

def tokenize_string_for_spacing(s: str, is_visible_tag_func) -> list:
    """Tokenize a string for spacing checks, identifying visible tags, zero-width tags, spaces, and text."""
    if not s:
        return []
    tags = []
    for match in ALL_TAGS_PATTERN.finditer(s):
        tags.append((match.start(), match.end(), match.group(0)))

    tokens = []
    last_idx = 0

    def add_non_tag_tokens(start_idx, end_idx):
        i = start_idx
        while i < end_idx:
            ch = s[i]
            if ch == ' ' or ch == '·' or ch.isspace():
                start_sp = i
                while i < end_idx and (s[i] == ' ' or s[i] == '·' or s[i].isspace()):
                    i += 1
                tokens.append({'type': 'space', 'text': s[start_sp:i]})
            else:
                start_txt = i
                while i < end_idx and not (s[i] == ' ' or s[i] == '·' or s[i].isspace()):
                    i += 1
                tokens.append({'type': 'text', 'text': s[start_txt:i]})

    for start, end, tag_str in tags:
        if start > last_idx:
            add_non_tag_tokens(last_idx, start)
        if is_visible_tag_func(tag_str):
            tokens.append({'type': 'visible_tag', 'text': tag_str})
        else:
            tokens.append({'type': 'zero_width_tag', 'text': tag_str})
        last_idx = end

    if last_idx < len(s):
        add_non_tag_tokens(last_idx, len(s))

    return tokens

def check_broken_icon_hyphen_boundary(text: str, next_text: str, is_visible_tag_func) -> bool:
    """Check if a tag-hyphen-word construct is broken across a line boundary."""
    if not text or not next_text:
        return False

    raw_text_tokens = tokenize_string_for_spacing(text, is_visible_tag_func)
    raw_next_tokens = tokenize_string_for_spacing(next_text, is_visible_tag_func)

    text_tokens = [t for t in raw_text_tokens if t['type'] not in ('zero_width_tag', 'space')]
    next_tokens = [t for t in raw_next_tokens if t['type'] not in ('zero_width_tag', 'space')]

    if not text_tokens or not next_tokens:
        return False

    # Case 1: Ends with visible tag, next starts with hyphen-word
    # e.g., "{(L)}" and "-наведення"
    if text_tokens[-1]['type'] == 'visible_tag':
        first_non_zw = None
        for t in raw_next_tokens:
            if t['type'] != 'zero_width_tag':
                first_non_zw = t
                break
        if first_non_zw and first_non_zw['type'] == 'text':
            next_t = first_non_zw['text']
            if next_t and next_t.startswith('-') and len(next_t) > 1 and next_t[1].isalnum():
                return True

    # Case 2: Ends with visible tag followed by hyphen, next starts with alphanumeric
    # e.g., "{(L)}-" and "наведення"
    if len(text_tokens) >= 2 and text_tokens[-1]['type'] == 'text' and text_tokens[-1]['text'] == '-':
        if text_tokens[-2]['type'] == 'visible_tag':
            # Ensure no space after hyphen in text
            hyphen_idx = -1
            for idx in range(len(raw_text_tokens) - 1, -1, -1):
                if raw_text_tokens[idx]['type'] == 'text' and raw_text_tokens[idx]['text'] == '-':
                    hyphen_idx = idx
                    break

            has_space_after_hyphen = False
            if hyphen_idx != -1:
                chk_idx = hyphen_idx + 1
                while chk_idx < len(raw_text_tokens):
                    if raw_text_tokens[chk_idx]['type'] == 'space':
                        has_space_after_hyphen = True
                        break
                    if raw_text_tokens[chk_idx]['type'] != 'zero_width_tag':
                        break
                    chk_idx += 1

            if not has_space_after_hyphen:
                first_non_zw = None
                for t in raw_next_tokens:
                    if t['type'] != 'zero_width_tag':
                        first_non_zw = t
                        break
                if first_non_zw and first_non_zw['type'] == 'text':
                    next_t = first_non_zw['text']
                    if next_t and next_t[0].isalnum():
                        return True

    return False
