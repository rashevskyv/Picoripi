# --- START OF FILE utils/utils.py ---
import datetime
import re
import difflib # Додано
from typing import Optional, List
from plugins.common.markers import P_VISUAL_EDITOR_MARKER, L_VISUAL_EDITOR_MARKER
from .logging_utils import log_debug

SPACE_DOT_SYMBOL = "·"
ALL_TAGS_PATTERN = re.compile(r'\[[^\]]*\]|\{[^}]*\}|' + re.escape(P_VISUAL_EDITOR_MARKER) + r'|' + re.escape(L_VISUAL_EDITOR_MARKER))
DEFAULT_CHAR_WIDTH_FALLBACK = 6

def remove_all_tags(text: str) -> str:
    if text is None:
        return ""
    return ALL_TAGS_PATTERN.sub("", text)

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


def calculate_string_width(text: str, font_map: dict, default_char_width: int = 8, icon_sequences: Optional[List[str]] = None) -> int:
    if not text:
        return 0
        
    trie, char_widths = _get_trie_and_flat_map(font_map, default_char_width, icon_sequences, strict=False)
    
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
                total_width += best_width
                i += best_len
                continue

        if ch == '[':
            end_index = text.find(']', i)
            if end_index != -1:
                i = end_index + 1
                continue
        if ch == '{':
            end_index = text.find('}', i)
            if end_index != -1:
                i = end_index + 1
                continue

        total_width += char_widths.get(ch, default_char_width)
        i += 1
        
    return total_width

def calculate_strict_string_width(text: str, font_map: dict, icon_sequences: Optional[List[str]] = None) -> Optional[int]:
    """
    Calculates string width strictly based on the font_map.
    If ANY character is missing from the font_map, it returns None.
    Does not use a default fallback width.
    """
    if not text:
        return 0
        
    trie, char_widths = _get_trie_and_flat_map(font_map, 8, icon_sequences, strict=True)
    
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
                if best_width is None:
                    return None
                total_width += best_width
                i += best_len
                continue

        if ch == '[':
            end_index = text.find(']', i)
            if end_index != -1:
                i = end_index + 1
                continue
        if ch == '{':
            end_index = text.find('}', i)
            if end_index != -1:
                i = end_index + 1
                continue

        width = char_widths.get(ch)
        if width is None:
            return None
            
        total_width += width
        i += 1
        
    return total_width

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
    
    no_tags_text = ALL_TAGS_PATTERN.sub("", text)
    
    text_with_spaces_instead_of_newlines = no_tags_text.replace('\n', ' ')
    
    normalized_spaces_text = re.sub(r' {2,}', ' ', text_with_spaces_instead_of_newlines)
    
    stripped_text = normalized_spaces_text.strip()
    
    return stripped_text