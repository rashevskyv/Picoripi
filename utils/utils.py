import datetime
import re
import difflib # Додано
from typing import Optional, List
from plugins.common.markers import P_VISUAL_EDITOR_MARKER, L_VISUAL_EDITOR_MARKER
from .logging_utils import log_debug

SPACE_DOT_SYMBOL = "·"
ALL_TAGS_PATTERN = re.compile(r'\[[^\]]*\]|\{[^}]*\}|' + re.escape(P_VISUAL_EDITOR_MARKER) + r'|' + re.escape(L_VISUAL_EDITOR_MARKER))
FORCED_ALIAS_PATTERN = re.compile(r'\{[Ff]:([^}]*)\}')
DEFAULT_CHAR_WIDTH_FALLBACK = 6

def remove_all_tags(text: str) -> str:
    if text is None:
        return ""
    text = FORCED_ALIAS_PATTERN.sub(r"\1", text)
    return ALL_TAGS_PATTERN.sub("", text)

def clean_spaces(text: str) -> str:
    if text is None:
        return ""
    
    lines = text.split('\n')
    cleaned_lines = []
    
    # Регулярний вираз для порожніх початкових/кінцевих тегів (фігурні теги або колірні квадратні теги)
    empty_tags_subpattern = r"(?:\{(?!f:|F:)[^}]*\}|\[(?:Red|Green|Blue|Yellow|l_Blue|Purple|Silver|Orange|White|/C)\])*"
    leading_space_pat = re.compile(rf"^{empty_tags_subpattern}[ ·]")
    trailing_space_pat = re.compile(rf"[ ·]{empty_tags_subpattern}$")
    
    non_forced_tags_pattern = re.compile(
        r'\[[^\]]*\]|\{(?!f:|F:)[^}]*\}|' +
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
        from PyQt5.QtWidgets import QApplication
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

def remove_curly_tags(text: str) -> str:
    if text is None:
        return ""
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