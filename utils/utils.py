import datetime
import re
import difflib # Додано
from typing import Optional, List, Tuple
from plugins.common.markers import P_VISUAL_EDITOR_MARKER, L_VISUAL_EDITOR_MARKER
from .logging_utils import log_debug

SPACE_DOT_SYMBOL = "·"
ALL_TAGS_PATTERN = re.compile(r'\[[^\]]*\]|\{[^}]*\}|' + re.escape(P_VISUAL_EDITOR_MARKER) + r'|' + re.escape(L_VISUAL_EDITOR_MARKER))
FORCED_ALIAS_PATTERN = re.compile(r'\{[Ff]:([^}]*)\}')
DEFAULT_CHAR_WIDTH_FALLBACK = 6

def remove_all_tags(text: str, tag_mappings: Optional[dict] = None) -> str:
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

def get_active_font_map() -> dict:
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
    if tag is None:
        return False
    if '(' in tag and ')' in tag:
        return True
    
    if mappings is None:
        mappings = get_active_tag_mappings()
    if font_map is None:
        font_map = get_active_font_map()
    if icon_sequences is None:
        icon_sequences = get_active_icon_sequences()
        
    if icon_sequences and tag in icon_sequences:
        return True
        
    if font_map and tag in font_map:
        val = font_map.get(tag)
        if val is not None:
            w = val.get("width", 0) if isinstance(val, dict) else int(val)
            if w > 0:
                return True
        
    width = get_tag_width(tag, mappings, font_map, icon_sequences=icon_sequences)
    if width > 0:
        return True
        
    if mappings:
        if tag in mappings:
            orig = mappings[tag]
            if orig and '(' in orig and ')' in orig:
                return True
        else:
            for alias, orig in mappings.items():
                if orig == tag:
                    if alias and '(' in alias and ')' in alias:
                        return True
                    break
    return False


def find_missing_icon_spacing_spans(text: str, is_visible_tag_func) -> List[Tuple[int, int]]:
    if not text:
        return []
    tags = []
    for match in ALL_TAGS_PATTERN.finditer(text):
        tags.append((match.start(), match.end(), match.group(0)))
        
    tokens = []
    last_idx = 0
    
    def add_non_tag_tokens(start_idx, end_idx):
        i = start_idx
        while i < end_idx:
            ch = text[i]
            if ch == ' ' or ch == '·':
                s = i
                while i < end_idx and (text[i] == ' ' or text[i] == '·'):
                    i += 1
                tokens.append({'type': 'space', 'start': s, 'end': i, 'text': text[s:i]})
            else:
                s = i
                while i < end_idx and not (text[i] == ' ' or text[i] == '·'):
                    i += 1
                tokens.append({'type': 'text', 'start': s, 'end': i, 'text': text[s:i]})
                
    for start, end, tag_str in tags:
        if start > last_idx:
            add_non_tag_tokens(last_idx, start)
        if is_visible_tag_func(tag_str):
            tokens.append({'type': 'visible_tag', 'start': start, 'end': end, 'text': tag_str})
        else:
            tokens.append({'type': 'zero_width_tag', 'start': start, 'end': end, 'text': tag_str})
        last_idx = end
        
    if last_idx < len(text):
        add_non_tag_tokens(last_idx, len(text))
        
    warning_spans = []
    
    for i, token in enumerate(tokens):
        if token['type'] != 'visible_tag':
            continue
            
        need_space_before = False
        prev_idx = i - 1
        while prev_idx >= 0 and tokens[prev_idx]['type'] == 'zero_width_tag':
            prev_idx -= 1
        if prev_idx >= 0:
            if tokens[prev_idx]['type'] == 'text':
                prev_text = tokens[prev_idx]['text']
                if prev_text and prev_text[-1].isalnum():
                    need_space_before = True
                
        need_space_after = False
        next_idx = i + 1
        while next_idx < len(tokens) and tokens[next_idx]['type'] == 'zero_width_tag':
            next_idx += 1
        if next_idx < len(tokens):
            if tokens[next_idx]['type'] == 'text':
                next_text = tokens[next_idx]['text']
                if next_text and next_text[0].isalnum():
                    need_space_after = True
                
        if need_space_before or need_space_after:
            warning_spans.append((token['start'], token['end']))
            
    return warning_spans


def fix_missing_icon_spacing(text: str, is_visible_tag_func) -> str:
    if not text:
        return text
    lines = text.split('\n')
    fixed_lines = []
    for line in lines:
        tags = []
        for match in ALL_TAGS_PATTERN.finditer(line):
            tags.append((match.start(), match.end(), match.group(0)))
            
        tokens = []
        last_idx = 0
        
        def add_non_tag_tokens(start_idx, end_idx):
            i = start_idx
            while i < end_idx:
                ch = line[i]
                if ch == ' ' or ch == '·':
                    s = i
                    while i < end_idx and (line[i] == ' ' or line[i] == '·'):
                        i += 1
                    tokens.append({'type': 'space', 'text': line[s:i]})
                else:
                    s = i
                    while i < end_idx and not (line[i] == ' ' or line[i] == '·'):
                        i += 1
                    tokens.append({'type': 'text', 'text': line[s:i]})
                    
        for start, end, tag_str in tags:
            if start > last_idx:
                add_non_tag_tokens(last_idx, start)
            if is_visible_tag_func(tag_str):
                tokens.append({'type': 'visible_tag', 'text': tag_str})
            else:
                tokens.append({'type': 'zero_width_tag', 'text': tag_str})
            last_idx = end
            
        if last_idx < len(line):
            add_non_tag_tokens(last_idx, len(line))
            
        new_tokens = []
        for i, token in enumerate(tokens):
            if token['type'] == 'visible_tag':
                need_space_before = False
                prev_idx = i - 1
                while prev_idx >= 0 and tokens[prev_idx]['type'] == 'zero_width_tag':
                    prev_idx -= 1
                if prev_idx >= 0:
                    if tokens[prev_idx]['type'] == 'text':
                        prev_text = tokens[prev_idx]['text']
                        if prev_text and prev_text[-1].isalnum():
                            need_space_before = True
                        
                need_space_after = False
                next_idx = i + 1
                while next_idx < len(tokens) and tokens[next_idx]['type'] == 'zero_width_tag':
                    next_idx += 1
                if next_idx < len(tokens):
                    if tokens[next_idx]['type'] == 'text':
                        next_text = tokens[next_idx]['text']
                        if next_text and next_text[0].isalnum():
                            need_space_after = True
                        
                if need_space_before:
                    new_tokens.append({'type': 'space', 'text': ' '})
                new_tokens.append(token)
                if need_space_after:
                    new_tokens.append({'type': 'space', 'text': ' '})
            else:
                new_tokens.append(token)
                
        fixed_lines.append("".join(t['text'] for t in new_tokens))
        
    return "\n".join(fixed_lines)


def clean_spaces(text: str) -> str:
    if text is None:
        return ""
    
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
    empty_tags_subpattern = rf"(?:\{{(?!(?:{curly_lookahead}))[^}}]*\}}|\[(?!(?:{bracket_lookahead}))(?:Red|Green|Blue|Yellow|l_Blue|Purple|Silver|Orange|White|/C)\])*"
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
    __slots__ = ('children', 'width', 'length')
    def __init__(self):
        self.children: dict = {}
        self.width = None
        self.length: int = 0

_WIDTH_CACHE = {}

def _get_trie_and_flat_map(font_map: dict, default_char_width: int, icon_sequences: Optional[List[str]], strict: bool = False):
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
    if tag.startswith('{') and tag.endswith('}'):
        inner = tag[1:-1]
        if inner.lower().startswith('f:'):
            forced_text = inner[2:]
            return _calculate_string_width_impl(forced_text, font_map, default_char_width, icon_sequences, strict, default_tag_mappings) or 0

    if default_tag_mappings is None:
        default_tag_mappings = get_active_tag_mappings()

    alias = None
    if default_tag_mappings:
        if tag in default_tag_mappings:
            alias = tag
        else:
            for a, orig in default_tag_mappings.items():
                if orig == tag:
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
    if not text:
        return 0
        
    if SPACE_DOT_SYMBOL in text:
        text = text.replace(SPACE_DOT_SYMBOL, " ")
        
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
        
    return total_width


def calculate_string_width(text: str, font_map: dict, default_char_width: int = 8, icon_sequences: Optional[List[str]] = None, default_tag_mappings: Optional[dict] = None) -> int:
    return _calculate_string_width_impl(text, font_map, default_char_width, icon_sequences, strict=False, default_tag_mappings=default_tag_mappings)


def calculate_strict_string_width(text: str, font_map: dict, icon_sequences: Optional[List[str]] = None, default_tag_mappings: Optional[dict] = None) -> Optional[int]:
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
    def _replace(match: re.Match) -> str:
        cluster = match.group(0)
        if match.start() == 0 or match.end() == line_len or len(cluster) > 1:
            return SPACE_DOT_SYMBOL * len(cluster)
        return cluster
    return _replace

def convert_spaces_to_dots_for_display(text: str, enable_conversion: bool) -> str:
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
    if text is None:
        return ""
    return text.replace(SPACE_DOT_SYMBOL, " ")

def remove_curly_tags(text: str, tag_mappings: Optional[dict] = None) -> str:
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
    if raw_text is None:
        return ""
    
    text_with_dots = convert_spaces_to_dots_for_display(str(raw_text), show_dots)
    
    if newline_char_for_preview:
        text_with_dots = text_with_dots.replace('\n', newline_char_for_preview)
        
    return text_with_dots

def prepare_text_for_tagless_search(text: str, keep_original_case: bool = False) -> str:
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


def shift_split_sentences(text: str, lines_per_page: int) -> Tuple[str, bool]:
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
            sentences.append([line])
            continue
            
        # 2. If line starts with a page break/pause escape code, end the previous group
        if re.search(r'^\s*\{(?:escape:0:(?:0007|7000)[0-9a-fA-F]*|pause[0-9]*)\}', line, re.IGNORECASE):
            if current_sentence:
                sentences.append(current_sentence)
                current_sentence = []
                
        current_sentence.append(line)
        cleaned = remove_all_tags(line).strip()
        is_end = False
        if cleaned:
            # 3. If line contains a page break escape code anywhere, end the group
            if re.search(r'\{(?:escape:0:(?:0007|7000)[0-9a-fA-F]*|pause[0-9]*)\}', line, re.IGNORECASE):
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

    # Pack sentences into pages
    pages = [[]]
    for s_lines in sentences:
        s_len = len(s_lines)
        
        # Check if the sentence starts with a page break/pause code
        starts_with_page_break = False
        if s_lines:
            first_line = s_lines[0]
            if re.search(r'^\s*\{(?:escape:0:(?:0007|7000)[0-9a-fA-F]*|pause[0-9]*)\}', first_line, re.IGNORECASE):
                starts_with_page_break = True
                
        if starts_with_page_break:
            current_len = len(pages[-1])
            remaining_space = max(0, lines_per_page - (current_len % lines_per_page))
            if remaining_space == 0:
                remaining_space = lines_per_page
            if current_len > 0 and (current_len % lines_per_page) != 0:
                pages[-1].extend([""] * remaining_space)
            pages.append(s_lines)
            continue
            
        if s_len > lines_per_page:
            # Too long to fit on a single page anyway.
            # Append directly to the current page.
            pages[-1].extend(s_lines)
        else:
            current_len = len(pages[-1])
            remaining_space = max(0, lines_per_page - (current_len % lines_per_page))
            if remaining_space == 0:
                remaining_space = lines_per_page
                
            # If current page has some lines, check if it fits in remaining space
            if current_len > 0 and (current_len % lines_per_page) != 0:
                if s_len <= remaining_space:
                    pages[-1].extend(s_lines)
                else:
                    # Pad current page to page boundary
                    pages[-1].extend([""] * remaining_space)
                    pages.append(s_lines)
            else:
                # Page is empty (or currently at exact boundary)
                if current_len == 0:
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
        if is_visible_tag(tag, mappings, font_map, icon_sequences):
            line_resolved = line_resolved.replace(tag, "visibleword")
        else:
            line_resolved = line_resolved.replace(tag, "")
            
    line_clean = ALL_TAGS_PATTERN.sub("", line_resolved)
    words = line_clean.split()
    return words