import datetime
import re
import difflib # Додано
from typing import Optional, List, Tuple, Any
from plugins.common.markers import P_VISUAL_EDITOR_MARKER, L_VISUAL_EDITOR_MARKER
from .logging_utils import log_debug

SPACE_DOT_SYMBOL = "·"
ALL_TAGS_PATTERN = re.compile(r'\[[^\]]*\]|\{[^}]*\}|' + re.escape(P_VISUAL_EDITOR_MARKER) + r'|' + re.escape(L_VISUAL_EDITOR_MARKER))
FORCED_ALIAS_PATTERN = re.compile(r'\{[Ff]:([^}]*)\}')
DEFAULT_CHAR_WIDTH_FALLBACK = 6

def remove_all_tags(text: str, tag_mappings: Optional[dict] = None) -> str:
    """Remove all tags."""
    if text is None:
        return ""
    if tag_mappings is None:
        tag_mappings = get_active_tag_mappings()
    if tag_mappings:
        sorted_mappings = sorted(tag_mappings.items(), key=lambda item: len(item[1]), reverse=True)
        for alias, original_tag in sorted_mappings:
            if original_tag:
                text = text.replace(original_tag, alias)
    text = FORCED_ALIAS_PATTERN.sub(r"\1", text)
    return ALL_TAGS_PATTERN.sub("", text)

_ACTIVE_FONT_MAP = None
_ACTIVE_TAG_MAPPINGS = None
_ACTIVE_ICON_SEQUENCES = None

def get_active_font_map() -> dict:
    """Get the active font map."""
    if _ACTIVE_FONT_MAP is not None:
        return _ACTIVE_FONT_MAP
    try:
        from PyQt6.QtWidgets import QApplication
        app = QApplication.instance()
        if app:
            for widget in app.topLevelWidgets():
                if widget.objectName() == "MainWindow" or widget.__class__.__name__ == "MainWindow":
                    return getattr(widget, "font_map", {})
    except Exception:
        pass
    return {}

def get_active_icon_sequences() -> list:
    """Get the active icon sequences."""
    if _ACTIVE_ICON_SEQUENCES is not None:
        return _ACTIVE_ICON_SEQUENCES
    try:
        from PyQt6.QtWidgets import QApplication
        app = QApplication.instance()
        if app:
            for widget in app.topLevelWidgets():
                if widget.objectName() == "MainWindow" or widget.__class__.__name__ == "MainWindow":
                    return getattr(widget, "icon_sequences", [])
    except Exception:
        pass
    return []

def is_visible_tag(tag: str, mappings: Optional[dict] = None, font_map: Optional[dict] = None, icon_sequences: Optional[List[str]] = None) -> bool:
    """Check if is visible tag."""
    if tag is None:
        return False
    tag_lower = tag.lower()
    if tag_lower in ('{*}', '{tab}', '{escape:6:000a}', '{escape:6:000b}'):
        return False
    if '(' in tag and ')' in tag:
        return True

    if mappings is None:
        mappings = get_active_tag_mappings()
    if font_map is None:
        font_map = get_active_font_map()
    if icon_sequences is None:
        icon_sequences = get_active_icon_sequences()

    # Generate normalized variants to support tags with or without parentheses (e.g. {btn5} vs {(btn5)})
    normalized_tags = [tag]
    if tag.startswith('{') and tag.endswith('}'):
        inner = tag[1:-1]
        if not (inner.startswith('(') and inner.endswith(')')):
            normalized_tags.append(f"{{({inner})}}")
        else:
            normalized_tags.append(f"{{{inner[1:-1]}}}")
    elif tag.startswith('[') and tag.endswith(']'):
        inner = tag[1:-1]
        if not (inner.startswith('(') and inner.endswith(')')):
            normalized_tags.append(f"[({inner})]")
        else:
            normalized_tags.append(f"[{inner[1:-1]}]")

    for t in normalized_tags:
        is_known = False
        if icon_sequences and t in icon_sequences:
            return True

        if font_map and t in font_map:
            val = font_map.get(t)
            if val is not None:
                w = val.get("width", 0) if isinstance(val, dict) else int(val)
                if w > 0:
                    return True
                is_known = True

        width = get_tag_width(t, mappings, font_map, icon_sequences=icon_sequences)
        if width > 0:
            return True

        if mappings:
            if t in mappings:
                orig = mappings[t]
                if orig and '(' in orig and ')' in orig:
                    return True
                is_known = True
            else:
                for alias, orig in mappings.items():
                    if orig == t:
                        if alias and '(' in alias and ')' in alias:
                            return True
                        is_known = True
                        break

        # If the variant contains parentheses and is a known tag in the system, treat it as visible
        if '(' in t and ')' in t and is_known:
            return True

    return False


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

        # Punctuation followed by alphanumeric (always, even if not separated by tags)
        elif left_char in ('.', ',', '!', '?', ':', ';') and right_char.isalnum():
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


def clean_spaces(text: str) -> str:
    """Clean spaces."""
    if text is None:
        return ""

    # Normalize non-breaking spaces
    text = text.replace("\u00a0", " ")

    # Get active tag mappings and build lookahead prefix
    mappings = get_active_tag_mappings()
    font_map = get_active_font_map()
    icon_sequences = get_active_icon_sequences()

    curly_forced = ["f:", "F:"]
    bracket_forced = ["f:", "F:"]

    if mappings:
        for alias, original in mappings.items():
            if alias.lower().startswith("{f:") and original.startswith("{") and original.endswith("}"):
                curly_forced.append(re.escape(original[1:-1]))
            if alias.lower().startswith("{f:") and original.startswith("[") and original.endswith("]"):
                bracket_forced.append(re.escape(original[1:-1]))

    # Scan text for other tags that have non-zero width or are button tags
    tags_found = ALL_TAGS_PATTERN.findall(text)
    for tag in tags_found:
        if tag.startswith("{") and tag.endswith("}"):
            inner = tag[1:-1]
            if inner.lower().startswith("f:"):
                continue
            if is_visible_tag(tag, mappings, font_map, icon_sequences=icon_sequences):
                curly_forced.append(re.escape(inner))
        elif tag.startswith("[") and tag.endswith("]"):
            inner = tag[1:-1]
            if inner.lower().startswith("f:"):
                continue
            if is_visible_tag(tag, mappings, font_map, icon_sequences=icon_sequences):
                bracket_forced.append(re.escape(inner))

    curly_lookahead = "|".join(curly_forced)
    bracket_lookahead = "|".join(bracket_forced)

    lines = text.split('\n')
    cleaned_lines = []

    # Регулярний вираз для порожніх початкових/кінцевих тегів (фігурні теги або колірні квадратні теги)
    empty_tags_subpattern = rf"(?:\{{(?!(?:{curly_lookahead}))[^}}]*\}}|\[(?!(?:{bracket_lookahead}))(?:Red|Green|Blue|Yellow|l_Blue|Purple|Silver|Orange|White)\])*"
    leading_space_pat = re.compile(rf"^{empty_tags_subpattern}[ ·]")
    trailing_space_pat = re.compile(rf"[ ·]{empty_tags_subpattern}$")

    non_forced_tags_pattern = re.compile(
        rf'\[(?!(?:{bracket_lookahead}))[^\]]*\]|'
        rf'\{{(?!(?:{curly_lookahead}))[^}}]*\}}|' +
        re.escape(P_VISUAL_EDITOR_MARKER) + r'|' +
        re.escape(L_VISUAL_EDITOR_MARKER)
    )

    for line in lines:
        parts = re.split(f"({non_forced_tags_pattern.pattern})", line)

        # 1. Strip leading spaces: if line starts with leading space (optionally after empty tags), strip across tags.
        starts_with_space = bool(leading_space_pat.match(line))
        if starts_with_space:
            for i in range(0, len(parts), 2):
                stripped = parts[i].lstrip(" ")
                if stripped:
                    parts[i] = stripped
                    break
                else:
                    parts[i] = ""
        elif parts:
            parts[0] = parts[0].lstrip(" ")

        # 2. Strip trailing spaces: if line ends with trailing space (optionally before empty tags), strip across tags.
        ends_with_space = bool(trailing_space_pat.search(line))
        if ends_with_space:
            start_idx = len(parts) - 1 if len(parts) % 2 != 0 else len(parts) - 2
            for i in range(start_idx, -1, -2):
                stripped = parts[i].rstrip(" ")
                if stripped:
                    parts[i] = stripped
                    break
                else:
                    parts[i] = ""
        elif len(parts) % 2 != 0 and parts:
            parts[-1] = parts[-1].rstrip(" ")

        # 3. Collapse consecutive spaces inside each text part
        for i in range(len(parts)):
            if i % 2 == 0:
                parts[i] = re.sub(r' {2,}', ' ', parts[i])

        # 4. Collapse consecutive spaces across tags (skipping empty parts)
        last_ended_with_space = False
        if parts:
            if parts[0]:
                last_ended_with_space = parts[0].endswith(" ")

            for i in range(2, len(parts), 2):
                if parts[i].startswith(" "):
                    if last_ended_with_space:
                        parts[i] = parts[i].lstrip(" ")

                if parts[i]:
                    last_ended_with_space = parts[i].endswith(" ")

        cleaned_lines.append("".join(parts))

    return "\n".join(cleaned_lines)

class TrieNode:
    """Trie node implementation."""
    __slots__ = ('children', 'width', 'length')
    def __init__(self):
        """Initialize a new instance."""
        self.children: dict = {}
        self.width = None
        self.length: int = 0

_WIDTH_CACHE = {}
_STRING_WIDTH_CACHE = {}

def clear_width_caches():
    """Clear all width calculation caches."""
    global _WIDTH_CACHE, _STRING_WIDTH_CACHE
    _WIDTH_CACHE.clear()
    _STRING_WIDTH_CACHE.clear()


def _get_trie_and_flat_map(font_map: dict, default_char_width: int, icon_sequences: Optional[List[str]], strict: bool = False):
    """Internal helper to get the trie and flat map."""
    cache_key = (id(font_map), default_char_width, tuple(icon_sequences) if icon_sequences else None, strict)
    if cache_key in _WIDTH_CACHE:
        return _WIDTH_CACHE[cache_key]

    root = TrieNode()

    font_map_icons = [str(k) for k in font_map.keys() if len(str(k)) > 1]
    if not icon_sequences:
        seqs_to_use = font_map_icons
    else:
        seqs_to_use = list(set(icon_sequences + font_map_icons))

    for seq in seqs_to_use:
        if not seq:
            continue
        node = root
        for ch in seq:
            if ch not in node.children:
                node.children[ch] = TrieNode()
            node = node.children[ch]

        info = font_map.get(seq)
        if strict:
            if info is None or (isinstance(info, dict) and 'width' not in info):
                width = None
            else:
                width = info['width'] if isinstance(info, dict) else None
        else:
            info_dict = info if isinstance(info, dict) else {}
            width = info_dict.get('width', default_char_width * len(seq))

        node.width = width
        node.length = len(seq)

    flat_widths = {}
    for k, v in font_map.items():
        if len(str(k)) == 1:
            if strict:
                w = v.get('width') if isinstance(v, dict) else None
            else:
                w = v.get('width', default_char_width) if isinstance(v, dict) else default_char_width
            flat_widths[str(k)] = w

    _WIDTH_CACHE[cache_key] = (root, flat_widths)
    return root, flat_widths


def get_active_tag_mappings() -> dict:
    """Get the active tag mappings."""
    if _ACTIVE_TAG_MAPPINGS is not None:
        return _ACTIVE_TAG_MAPPINGS
    try:
        from PyQt6.QtWidgets import QApplication
        app = QApplication.instance()
        if app:
            for widget in app.topLevelWidgets():
                if widget.objectName() == "MainWindow" or widget.__class__.__name__ == "MainWindow":
                    return getattr(widget, "default_tag_mappings", {})
    except Exception:
        pass
    return {}

def get_tag_width(tag: str, default_tag_mappings: Optional[dict], font_map: dict, default_char_width: int = 8, icon_sequences: Optional[List[str]] = None, strict: bool = False) -> int:
    """Get the tag width."""
    if tag.startswith('{') and tag.endswith('}'):
        inner = tag[1:-1]
        if inner.lower().startswith('f:'):
            forced_text = inner[2:]
            return _calculate_string_width_impl(forced_text, font_map, default_char_width, icon_sequences, strict, default_tag_mappings) or 0

    if default_tag_mappings is None:
        default_tag_mappings = get_active_tag_mappings()

    # Generate normalized variants to support tags with or without parentheses (e.g. {btn5} vs {(btn5)})
    normalized_tags = [tag]
    if tag.startswith('{') and tag.endswith('}'):
        inner = tag[1:-1]
        if not (inner.startswith('(') and inner.endswith(')')):
            normalized_tags.append(f"{{({inner})}}")
        else:
            normalized_tags.append(f"{{{inner[1:-1]}}}")
    elif tag.startswith('[') and tag.endswith(']'):
        inner = tag[1:-1]
        if not (inner.startswith('(') and inner.endswith(')')):
            normalized_tags.append(f"[({inner})]")
        else:
            normalized_tags.append(f"[{inner[1:-1]}]")

    for t in normalized_tags:
        alias = None
        if default_tag_mappings:
            if t in default_tag_mappings:
                alias = t
            else:
                for a, orig in default_tag_mappings.items():
                    if orig == t:
                        alias = a
                        break

        if alias:
            if font_map and alias in font_map:
                alias_info = font_map.get(alias)
                if alias_info is not None:
                    if isinstance(alias_info, dict):
                        return alias_info.get("width", 0)
                    elif isinstance(alias_info, (int, float)):
                        return int(alias_info)
            if alias.startswith('{') and alias.endswith('}'):
                alias_inner = alias[1:-1]
                if alias_inner.lower().startswith('f:'):
                    forced_text = alias_inner[2:]
                    return _calculate_string_width_impl(forced_text, font_map, default_char_width, icon_sequences, strict, default_tag_mappings) or 0

    return 0

def _calculate_string_width_impl(text: str, font_map: dict, default_char_width: int = 8, icon_sequences: Optional[List[str]] = None, strict: bool = False, default_tag_mappings: Optional[dict] = None) -> Optional[int]:
    """Internal helper to calculate string width impl."""
    if not text:
        return 0

    cache_key = (
        text,
        id(font_map),
        default_char_width,
        tuple(icon_sequences) if icon_sequences else None,
        strict,
        id(default_tag_mappings) if default_tag_mappings is not None else None
    )

    global _STRING_WIDTH_CACHE
    if cache_key in _STRING_WIDTH_CACHE:
        return _STRING_WIDTH_CACHE[cache_key]

    if SPACE_DOT_SYMBOL in text or "\u00a0" in text:
        text = text.replace(SPACE_DOT_SYMBOL, " ").replace("\u00a0", " ")

    trie, char_widths = _get_trie_and_flat_map(font_map, default_char_width, icon_sequences, strict=strict)

    total_width = 0
    i = 0
    text_len = len(text)

    while i < text_len:
        ch = text[i]

        node = trie.children.get(ch)
        if node is not None:
            best_width = None
            best_len = 0
            is_match = False
            j = i + 1
            while node is not None and j <= text_len:
                if node.length > 0:
                    best_width = node.width
                    best_len = node.length
                    is_match = True
                if j < text_len:
                    node = node.children.get(text[j])
                else:
                    break
                j += 1

            if is_match:
                if strict and best_width is None:
                    return None
                total_width += best_width
                i += best_len
                continue

        if ch == '[':
            end_index = text.find(']', i)
            if end_index != -1:
                tag = text[i:end_index + 1]
                total_width += get_tag_width(tag, default_tag_mappings, font_map, default_char_width, icon_sequences, strict)
                i = end_index + 1
                continue
            else:
                break
        if ch == '{':
            end_index = text.find('}', i)
            if end_index != -1:
                tag = text[i:end_index + 1]
                total_width += get_tag_width(tag, default_tag_mappings, font_map, default_char_width, icon_sequences, strict)
                i = end_index + 1
                continue
            else:
                break

        if strict:
            width = char_widths.get(ch)
            if width is None:
                return None
            total_width += width
        else:
            total_width += char_widths.get(ch, default_char_width)
        i += 1

    if len(_STRING_WIDTH_CACHE) > 10000:
        _STRING_WIDTH_CACHE.clear()
    _STRING_WIDTH_CACHE[cache_key] = total_width
    return total_width



def calculate_string_width(text: str, font_map: dict, default_char_width: int = 8, icon_sequences: Optional[List[str]] = None, default_tag_mappings: Optional[dict] = None) -> int:
    """Calculate string width."""
    return _calculate_string_width_impl(text, font_map, default_char_width, icon_sequences, strict=False, default_tag_mappings=default_tag_mappings)


def calculate_strict_string_width(text: str, font_map: dict, icon_sequences: Optional[List[str]] = None, default_tag_mappings: Optional[dict] = None) -> Optional[int]:
    """Calculate strict string width."""
    return _calculate_string_width_impl(text, font_map, 8, icon_sequences, strict=True, default_tag_mappings=default_tag_mappings)

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

_SPACE_DOT_RE = re.compile(f'[ {re.escape(SPACE_DOT_SYMBOL)}]+')

def _make_replacer(line_len: int):
    """Internal helper to create replacer."""
    def _replace(match: re.Match) -> str:
        """Internal helper to replace."""
        cluster = match.group(0)
        if match.start() == 0 or match.end() == line_len or len(cluster) > 1:
            return SPACE_DOT_SYMBOL * len(cluster)
        return cluster
    return _replace

def convert_spaces_to_dots_for_display(text: str, enable_conversion: bool) -> str:
    """Convert spaces to dots for display."""
    if not enable_conversion or text is None:
        return text if text is not None else ""

    lines = text.splitlines(keepends=True)
    processed_lines = []

    for line in lines:
        line_content = line.rstrip('\r\n')
        line_endings = line[len(line_content):]

        replacer = _make_replacer(len(line_content))
        new_content = _SPACE_DOT_RE.sub(replacer, line_content)
        processed_lines.append(new_content + line_endings)

    return "".join(processed_lines)


def convert_dots_to_spaces_from_editor(text: str) -> str:
    """Convert dots to spaces from editor."""
    if text is None:
        return ""
    return text.replace(SPACE_DOT_SYMBOL, " ").replace("\u00a0", " ")

def remove_curly_tags(text: str, tag_mappings: Optional[dict] = None) -> str:
    """Remove curly tags."""
    if text is None:
        return ""
    if tag_mappings is None:
        tag_mappings = get_active_tag_mappings()
    if tag_mappings:
        sorted_mappings = sorted(tag_mappings.items(), key=lambda item: len(item[1]), reverse=True)
        for alias, original_tag in sorted_mappings:
            if original_tag:
                text = text.replace(original_tag, alias)
    text = FORCED_ALIAS_PATTERN.sub(r"\1", text)
    return re.sub(r"\{[^}]*\}", "", text)

def convert_raw_to_display_text(raw_text: str, show_dots: bool, newline_char_for_preview: str = "") -> str:
    """Convert raw to display text."""
    if raw_text is None:
        return ""

    text_with_dots = convert_spaces_to_dots_for_display(str(raw_text), show_dots)

    if newline_char_for_preview:
        text_with_dots = text_with_dots.replace('\n', newline_char_for_preview)

    return text_with_dots

def prepare_text_for_tagless_search(text: str, keep_original_case: bool = False) -> str:
    """Prepare text for tagless search."""
    if text is None:
        return ""

    # Remove all bracket and curly tags (correctly replacing forced aliases with their words)
    no_tags_text = remove_all_tags(text)

    # Replace Zelda-style '+' separators with spaces
    text_with_normalized_plus = no_tags_text.replace('+', ' ')

    # Replace dots (display symbols) with spaces
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


def shift_split_sentences(text: str, lines_per_page: int, prevent_empty_lines: bool = False) -> Tuple[str, bool]:
    """Shift split sentences."""
    if not isinstance(lines_per_page, int):
        try:
            lines_per_page = int(lines_per_page)
        except Exception:
            lines_per_page = 4

    if not text:
        return text, False

    sublines = text.split('\n')

    if not any(sublines):
        return "", True

    # Segment sublines into sentences
    sentences = [] # list of lists of lines
    current_sentence = []

    for idx in range(len(sublines)):
        line = sublines[idx]

        # 1. If line is empty, it acts as a page boundary/separate sentence
        if not line.strip():
            if current_sentence:
                sentences.append(current_sentence)
                current_sentence = []
            continue

        # 2. If line starts with a page break/pause escape code, end the previous group
        if re.search(r'^\s*[\{\[](?:escape:0:(?:0007|7000)[0-9a-fA-F]*|pause[0-9]*)[\}\]]', line, re.IGNORECASE):
            if current_sentence:
                sentences.append(current_sentence)
                current_sentence = []

        current_sentence.append(line)
        cleaned = remove_all_tags(line).strip()
        is_end = False
        if cleaned:
            # 3. If line contains a page break escape code anywhere, end the group
            if re.search(r'[\{\[](?:escape:0:(?:0007|7000)[0-9a-fA-F]*|pause[0-9]*)[\}\]]', line, re.IGNORECASE):
                is_end = True
            else:
                last_char = cleaned[-1]
                if last_char in ('.', '!', '?', '。', '！', '？'):
                    is_end = True
                elif last_char in ('"', "'", '»', '`', ')') and len(cleaned) > 1:
                    if cleaned[-2] in ('.', '!', '?', '。', '！', '？'):
                        is_end = True

        if is_end:
            sentences.append(current_sentence)
            current_sentence = []

    if current_sentence:
        sentences.append(current_sentence)

    # Optimize sentences list: remove intermediate empty line sentences
    # if the surrounding text sentences can fit together on a single page.
    optimized_sentences = []
    current_page_len = 0
    i = 0
    while i < len(sentences):
        s = sentences[i]
        s_len = len(s)

        # Check if s is an empty line
        is_empty_line = (s_len == 1 and not s[0].strip())

        if is_empty_line:
            # We only optimize if it's not the first line of the page
            # and there is a next sentence
            if current_page_len > 0 and i + 1 < len(sentences):
                next_s = sentences[i+1]
                next_len = len(next_s)

                # Check if next sentence is not an empty line and doesn't start with page break
                next_is_empty = (next_len == 1 and not next_s[0].strip())
                next_starts_with_page_break = False
                if next_s:
                    first_line = next_s[0]
                    if re.search(r'^\s*[\{\[](?:escape:0:(?:0007|7000)[0-9a-fA-F]*|pause[0-9]*)[\}\]]', first_line, re.IGNORECASE):
                        next_starts_with_page_break = True

                if not next_is_empty and not next_starts_with_page_break:
                    # Would next_s fit on the current page if we skip this empty line?
                    remaining_space_with_empty = lines_per_page - current_page_len - 1
                    remaining_space_without_empty = lines_per_page - current_page_len

                    if next_len > remaining_space_with_empty and next_len <= remaining_space_without_empty:
                        # Yes! Skipping the empty line allows the next sentence to fit on this page!
                        # So we skip this empty line!
                        i += 1
                        continue

        # Add sentence and update current_page_len
        optimized_sentences.append(s)

        # If it starts with page break, it starts a new page
        starts_with_page_break = False
        if s:
            first_line = s[0]
            if re.search(r'^\s*[\{\[](?:escape:0:(?:0007|7000)[0-9a-fA-F]*|pause[0-9]*)[\}\]]', first_line, re.IGNORECASE):
                starts_with_page_break = True

        if starts_with_page_break:
            current_page_len = s_len
        else:
            # If s_len doesn't fit in the current page, it starts a new page (of size lines_per_page)
            remaining_space = lines_per_page - current_page_len
            if current_page_len > 0 and s_len > remaining_space and s_len <= lines_per_page:
                current_page_len = s_len
            else:
                current_page_len = (current_page_len + s_len) % lines_per_page
                if current_page_len == 0 and s_len > 0:
                    current_page_len = lines_per_page

        i += 1
    sentences = optimized_sentences

    # Pack sentences into pages
    pages = [[]]
    for s_lines in sentences:
        s_len = len(s_lines)

        # Check if the sentence starts with a page break/pause code
        starts_with_page_break = False
        if s_lines:
            first_line = s_lines[0]
            if re.search(r'^\s*[\{\[](?:escape:0:(?:0007|7000)[0-9a-fA-F]*|pause[0-9]*)[\}\]]', first_line, re.IGNORECASE):
                starts_with_page_break = True

        if starts_with_page_break:
            total_len = sum(len(p) for p in pages)
            remaining_space = max(0, lines_per_page - (total_len % lines_per_page))
            if remaining_space == 0:
                remaining_space = lines_per_page
            if total_len > 0 and (total_len % lines_per_page) != 0:
                if not prevent_empty_lines:
                    pages[-1].extend([""] * remaining_space)
            pages.append(s_lines)
            continue

        if s_len > lines_per_page:
            # Too long to fit on a single page anyway.
            # Append directly to the current page.
            pages[-1].extend(s_lines)
        else:
            total_len = sum(len(p) for p in pages)
            remaining_space = max(0, lines_per_page - (total_len % lines_per_page))
            if remaining_space == 0:
                remaining_space = lines_per_page

            # If current page has some lines, check if it fits in remaining space
            if total_len > 0 and (total_len % lines_per_page) != 0:
                if s_len <= remaining_space:
                    pages[-1].extend(s_lines)
                else:
                    if prevent_empty_lines:
                        pages[-1].extend(s_lines)
                    else:
                        # Always pad current page to page boundary if next sentence doesn't fit
                        pages[-1].extend([""] * remaining_space)
                        pages.append(s_lines)
            else:
                # Page is empty (or currently at exact boundary)
                if total_len == 0:
                    pages[-1].extend(s_lines)
                else:
                    pages.append(s_lines)

    # Reconstruct final text
    final_lines = []
    for page in pages:
        final_lines.extend(page)

    final_text = "\n".join(final_lines)
    return final_text, final_text != text


def get_line_words_and_visible_tags(line: str, mw: Optional[Any] = None) -> List[str]:
    """Get the line words and visible tags."""
    if not line:
        return []

    if mw is not None:
        mappings = getattr(mw, "default_tag_mappings", {})
        font_map = getattr(mw, "font_map", {})
        icon_sequences = getattr(mw, "icon_sequences", [])
    else:
        mappings = get_active_tag_mappings()
        font_map = get_active_font_map()
        icon_sequences = get_active_icon_sequences()

    line_resolved = FORCED_ALIAS_PATTERN.sub(r"\1", line)
    tags = ALL_TAGS_PATTERN.findall(line_resolved)

    unique_tags = sorted(list(set(tags)), key=len, reverse=True)
    for tag in unique_tags:
        is_word = is_visible_tag(tag, mappings, font_map, icon_sequences)
        if not is_word:
            # Determine alias for matching
            alias = tag
            if mappings and tag not in mappings:
                for a, orig in mappings.items():
                    if orig == tag:
                        alias = a
                        break

            tag_lower = tag.lower()
            alias_lower = alias.lower() if alias else ""

            # Check if tag is placeholder, variable, forced text, or button [...]
            if ("player" in tag_lower or "player" in alias_lower or
                "var:" in tag_lower or "var:" in alias_lower or
                "variable" in tag_lower or "variable" in alias_lower or
                "string:" in tag_lower or "string:" in alias_lower or
                "number:" in tag_lower or "number:" in alias_lower):
                is_word = True
            elif (tag.startswith('[') and tag.endswith(']')) or (alias and alias.startswith('[') and alias.endswith(']')):
                is_word = True
            elif tag_lower.startswith('{f:') or tag_lower.startswith('[f:') or (alias_lower.startswith('{f:') or alias_lower.startswith('[f:')):
                is_word = True

        if is_word:
            line_resolved = line_resolved.replace(tag, "visibleword")
        else:
            line_resolved = line_resolved.replace(tag, "")

    line_clean = ALL_TAGS_PATTERN.sub("", line_resolved)
    words = line_clean.split()
    return words


def shift_split_sentences_aligned(text: str, original_text: str, lines_per_page: int, prevent_empty_lines: bool = False) -> Tuple[str, bool]:
    """Shift split sentences aligned."""
    if not isinstance(lines_per_page, int):
        try:
            lines_per_page = int(lines_per_page)
        except Exception:
            lines_per_page = 4

    if not text or not original_text:
        return text, False

    # Helper function to segment text into sentences (list of lists of lines)
    def segment_into_sentences(txt: str) -> List[List[str]]:
        """Segment into sentences."""
        sublines = txt.split('\n')
        if not any(sublines):
            return []
        sentences = []
        current_sentence = []
        for line in sublines:
            if not line.strip():
                if current_sentence:
                    sentences.append(current_sentence)
                    current_sentence = []
                continue
            if re.search(r'^\s*[\{\[](?:escape:0:(?:0007|7000)[0-9a-fA-F]*|pause[0-9]*)[\}\]]', line, re.IGNORECASE):
                if current_sentence:
                    sentences.append(current_sentence)
                    current_sentence = []
            current_sentence.append(line)
            cleaned = remove_all_tags(line).strip()
            is_end = False
            if cleaned:
                if re.search(r'[\{\[](?:escape:0:(?:0007|7000)[0-9a-fA-F]*|pause[0-9]*)[\}\]]', line, re.IGNORECASE):
                    is_end = True
                else:
                    last_char = cleaned[-1]
                    if last_char in ('.', '!', '?', '。', '！', '？'):
                        is_end = True
                    elif last_char in ('"', "'", '»', '`', ')') and len(cleaned) > 1:
                        if cleaned[-2] in ('.', '!', '?', '。', '！', '？'):
                            is_end = True
            if is_end:
                sentences.append(current_sentence)
                current_sentence = []
        if current_sentence:
            sentences.append(current_sentence)
        return sentences

    orig_sentences = segment_into_sentences(original_text)
    trans_sentences = segment_into_sentences(text)

    if not orig_sentences or not trans_sentences or len(orig_sentences) != len(trans_sentences):
        # Fallback to standard shift_split_sentences if lengths don't match
        return shift_split_sentences(text, lines_per_page, prevent_empty_lines=prevent_empty_lines)

    # Align page break/pause codes from original sentences to translation sentences
    PAGE_BREAK_PATTERN = re.compile(r'^\s*([\{\[](?:escape:0:(?:0007|7000)[0-9a-fA-F]*|pause[0-9]*)[\}\]])', re.IGNORECASE)
    for i in range(len(trans_sentences)):
        orig_s = orig_sentences[i]
        trans_s = trans_sentences[i]

        orig_pb = None
        if orig_s:
            match = PAGE_BREAK_PATTERN.match(orig_s[0])
            if match:
                orig_pb = match.group(1)

        if trans_s:
            first_line = trans_s[0]
            # Remove any existing page break codes from the start of the translated sentence
            while True:
                m = PAGE_BREAK_PATTERN.match(first_line)
                if m:
                    first_line = first_line[m.end():].lstrip()
                else:
                    break

            # Prepend original page break code if it was present
            if orig_pb:
                first_line = orig_pb + first_line
            trans_s[0] = first_line

    # Paginate original lines to assign page number to each original sentence
    orig_sublines = original_text.split('\n')
    orig_line_pages = []
    curr_page = 0
    curr_line_count = 0
    for line in orig_sublines:
        starts_with_page_break = False
        if re.search(r'^\s*[\{\[](?:escape:0:(?:0007|7000)[0-9a-fA-F]*|pause[0-9]*)[\}\]]', line, re.IGNORECASE):
            starts_with_page_break = True

        if starts_with_page_break and curr_line_count > 0:
            curr_page += 1
            curr_line_count = 0

        orig_line_pages.append(curr_page)
        curr_line_count += 1

        if curr_line_count == lines_per_page:
            curr_page += 1
            curr_line_count = 0

    # Map each original sentence to its end page
    orig_sentence_end_page = []
    orig_line_idx = 0
    for s_lines in orig_sentences:
        s_len = len(s_lines)
        end_line_idx = orig_line_idx + s_len - 1
        end_page = orig_line_pages[end_line_idx] if end_line_idx < len(orig_line_pages) else curr_page
        orig_sentence_end_page.append(end_page)
        orig_line_idx += s_len

    # Pack trans sentences to pages using original sentence page boundaries
    pages = [[]]
    for i in range(len(trans_sentences)):
        s_lines = trans_sentences[i]

        should_start_new_page = False
        if i > 0:
            orig_prev_page = orig_sentence_end_page[i-1]
            orig_curr_page = orig_sentence_end_page[i]
            if orig_curr_page > orig_prev_page:
                should_start_new_page = True

        if should_start_new_page:
            total_len = sum(len(p) for p in pages)
            if total_len > 0 and (total_len % lines_per_page) != 0:
                remaining_space = lines_per_page - (total_len % lines_per_page)
                starts_with_page_break = False
                if s_lines:
                    first_line = s_lines[0]
                    if re.search(r'^\s*[\{\[](?:escape:0:(?:0007|7000)[0-9a-fA-F]*|pause[0-9]*)[\}\]]', first_line, re.IGNORECASE):
                        starts_with_page_break = True

                # Always pad to page boundary unless prevent_empty_lines is True
                if not prevent_empty_lines:
                    pages[-1].extend([""] * remaining_space)
            pages.append(s_lines)
        else:
            s_len = len(s_lines)
            total_len = sum(len(p) for p in pages)
            remaining_space = lines_per_page - (total_len % lines_per_page)
            if remaining_space == 0:
                remaining_space = lines_per_page

            if total_len > 0 and (total_len % lines_per_page) != 0:
                if s_len <= remaining_space:
                    pages[-1].extend(s_lines)
                else:
                    if prevent_empty_lines:
                        pages[-1].extend(s_lines)
                    else:
                        # Always pad to page boundary to prevent sentence from getting split
                        pages[-1].extend([""] * remaining_space)
                        pages.append(s_lines)
            else:
                if total_len == 0:
                    pages[-1].extend(s_lines)
                else:
                    pages.append(s_lines)

    final_lines = []
    for page in pages:
        final_lines.extend(page)

    final_text = "\n".join(final_lines)
    return final_text, final_text != text


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


def has_visible_content(text: str, mappings: Optional[dict] = None, font_map: Optional[dict] = None, icon_sequences: Optional[List[str]] = None) -> bool:
    """Check if has visible content."""
    if not text:
        return False
    text_no_tags = remove_all_tags(text, mappings)
    if text_no_tags.strip():
        return True
    for tag_match in ALL_TAGS_PATTERN.finditer(text):
        tag = tag_match.group(0)
        if is_visible_tag(tag, mappings, font_map, icon_sequences):
            return True
    return False


import string

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
