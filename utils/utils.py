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

def calculate_string_width(text: str, font_map: dict, default_char_width: int = 8, icon_sequences: Optional[List[str]] = None) -> int:
    total_width = 0
    i = 0
    text_len = len(text)
    
    # Сортуємо послідовності від найдовшої до найкоротшої, щоб уникнути неправильного визначення
    # наприклад, [L] замість [L-Stick]
    font_map_icons = [str(k) for k in font_map.keys() if len(str(k)) > 1]
    
    if not icon_sequences:
        icon_sequences = font_map_icons
    else:
        icon_sequences = list(set(icon_sequences + font_map_icons))
    sequences_to_use = sorted(icon_sequences, key=len, reverse=True)

    while i < text_len:
        # 1. Найвищий пріоритет: перевірка на icon_sequence
        matched_sequence = None
        for seq in sequences_to_use:
            if text.startswith(seq, i):
                matched_sequence = seq
                break
        
        if matched_sequence:
            # Якщо знайдено icon_sequence, додаємо її ширину і переходимо далі
            total_width += font_map.get(matched_sequence, {}).get('width', default_char_width * len(matched_sequence))
            i += len(matched_sequence)
            continue

        # 2. Якщо це не icon_sequence, перевіряємо на загальний тег
        char = text[i]
        if char == '[':
            end_index = text.find(']', i)
            if end_index != -1:
                # Знайдено загальний тег [], його ширина 0. Пропускаємо його.
                i = end_index + 1
                continue
        
        if char == '{':
            end_index = text.find('}', i)
            if end_index != -1:
                # Знайдено загальний тег {}, його ширина 0. Пропускаємо його.
                i = end_index + 1
                continue

        # 3. Якщо це не іконка і не тег, обробляємо як звичайний символ
        char_info = font_map.get(char)
        if char_info is None:
            total_width += default_char_width
        else:
            total_width += char_info.get('width', default_char_width)
        i += 1
        
    return total_width

def calculate_strict_string_width(text: str, font_map: dict, icon_sequences: Optional[List[str]] = None) -> Optional[int]:
    """
    Calculates string width strictly based on the font_map.
    If ANY character is missing from the font_map, it returns None.
    Does not use a default fallback width.
    """
    total_width = 0
    i = 0
    text_len = len(text)
    
    font_map_icons = [str(k) for k in font_map.keys() if len(str(k)) > 1]
    
    if not icon_sequences:
        icon_sequences = font_map_icons
    else:
        icon_sequences = list(set(icon_sequences + font_map_icons))
    sequences_to_use = sorted(icon_sequences, key=len, reverse=True)

    while i < text_len:
        matched_sequence = None
        for seq in sequences_to_use:
            if text.startswith(seq, i):
                matched_sequence = seq
                break
        
        if matched_sequence:
            seq_info = font_map.get(matched_sequence)
            if seq_info is None or 'width' not in seq_info:
                return None
            total_width += seq_info['width']
            i += len(matched_sequence)
            continue

        char = text[i]
        if char == '[':
            end_index = text.find(']', i)
            if end_index != -1:
                i = end_index + 1
                continue
        
        if char == '{':
            end_index = text.find('}', i)
            if end_index != -1:
                i = end_index + 1
                continue

        char_info = font_map.get(char)
        if char_info is None or 'width' not in char_info:
            return None # Missing character or width definition
            
        total_width += char_info['width']
        i += 1
        
    return total_width

def is_fuzzy_match(word1: str, word2: str, threshold: float = 0.8) -> bool:
    """
    Checks if two words are similar enough using SequenceMatcher.
    Ignores case.
    """
    if not word1 or not word2:
        return False
    # Оптимізація: якщо слова ідентичні, не запускаємо важкий алгоритм
    if word1.lower() == word2.lower():
        return True
    # Оптимізація: якщо довжина відрізняється занадто сильно, це не збіг
    if abs(len(word1) - len(word2)) > 3: 
        return False
        
    return difflib.SequenceMatcher(None, word1.lower(), word2.lower()).ratio() >= threshold

def convert_spaces_to_dots_for_display(text: str, enable_conversion: bool) -> str:
    if not enable_conversion or text is None:
        return text if text is not None else ""
    
    def replace_match(m):
        return SPACE_DOT_SYMBOL * len(m.group(0))

    # (?m) enables multiline mode for ^ and $
    # 1. Matches spaces at the beginning of any line: ^ +
    # 2. Matches spaces at the end of any line:  +$(?=\r?\n|$)
    #    Note: we use a positive lookahead to find effectively the end of a logical line 
    #    without consuming the newline character itself.
    # 3. Matches 2 or more spaces anywhere:  {2,}
    
    # Updated regex to be more precise about start/end of line
    # We use a combined regex to avoid replacing the same character twice
    # - ^ + : Leading spaces (any number)
    # -  +$(?=\n|$) : Trailing spaces (any number) - handled line by line
    
    lines = text.splitlines(keepends=True)
    processed_lines = []
    
    for line in lines:
        # Check if line has a trailing newline to strip it for $ matching
        line_content = line.rstrip('\r\n')
        line_endings = line[len(line_content):]
        import re
        line_content = line.rstrip('\r\n')
        line_endings = line[len(line_content):]
        
        # We find ALL sequences of spaces
        def replace_spaces(match):
            spaces = match.group(0)
            start_pos = match.start()
            end_pos = match.end()
            
            # Rule: Always dots if:
            # 1. At the very start of line
            # 2. At the very end of line
            # 3. Sequence length > 1
            if start_pos == 0 or end_pos == len(line_content) or len(spaces) > 1:
                return SPACE_DOT_SYMBOL * len(spaces)
            
            # Otherwise, it's a single middle space
            return spaces
            
        new_content = re.sub(r" +", replace_spaces, line_content)
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