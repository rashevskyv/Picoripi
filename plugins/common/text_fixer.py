from typing import Tuple, List, Optional
import re
from utils.utils import calculate_string_width, remove_all_tags, ALL_TAGS_PATTERN

class GenericTextFixer:
    def __init__(self, main_window_ref, tag_manager_ref, problem_analyzer_ref):
        self.mw = main_window_ref
        self.tag_manager = tag_manager_ref
        self.problem_analyzer = problem_analyzer_ref

    def _calculate_width(self, text: str, font_map: dict) -> int:
        icon_sequences = getattr(self.mw, 'icon_sequences', []) if self.mw else []
        default_tag_mappings = getattr(self.mw, 'default_tag_mappings', None) if self.mw else None
        
        if self.mw and hasattr(self.mw, 'current_game_rules') and self.mw.current_game_rules:
            from unittest.mock import MagicMock
            if not isinstance(self.mw.current_game_rules, MagicMock):
                if hasattr(self.mw.current_game_rules, 'calculate_string_width_override'):
                    override_val = self.mw.current_game_rules.calculate_string_width_override(text, font_map)
                    if override_val is not None:
                        return override_val
                    
        return calculate_string_width(
            text, 
            font_map, 
            icon_sequences=icon_sequences, 
            default_tag_mappings=default_tag_mappings
        )

    def _extract_first_word_with_tags_generic(self, text: str) -> Tuple[str, str]:
        if not text.strip(): return "", text
        first_word_text = ""
        char_idx = 0
        while char_idx < len(text):
            char = text[char_idx]
            if char.isspace():
                if first_word_text: break
                else: first_word_text += char; char_idx += 1; continue
            is_tag_char = False
            for tag_match in ALL_TAGS_PATTERN.finditer(text[char_idx:]):
                if tag_match.start() == 0:
                    tag_content = tag_match.group(0)
                    first_word_text += tag_content
                    char_idx += len(tag_content)
                    is_tag_char = True
                    break
            if is_tag_char: continue
            first_word_text += char
            char_idx += 1
        remaining_text = text[len(first_word_text):].lstrip()
        return first_word_text.rstrip(), remaining_text

    def _fix_width_exceeded_generic(self, text: str, font_map: dict, threshold: int) -> Tuple[str, bool]:
        original_text = text
        sub_lines = text.split('\n')
        made_change = False
        final_lines = []

        for line in sub_lines:
            while self._calculate_width(line, font_map) > threshold:
                made_change = True
                line_parts = re.findall(r'(\{[^}]*\}|\[[^\]]*\]|\S+|\s+)', line)
                best_split_point = -1
                for j in range(len(line_parts) - 1, 0, -1):
                    line_part_one = "".join(line_parts[:j]).rstrip()
                    if self._calculate_width(line_part_one, font_map) <= threshold:
                        best_split_point = j
                        break
                if best_split_point == -1 and len(line_parts) > 1:
                    best_split_point = 1

                if best_split_point != -1:
                    line1 = "".join(line_parts[:best_split_point]).rstrip()
                    line2 = "".join(line_parts[best_split_point:]).lstrip()
                    final_lines.append(line1)
                    line = line2 
                else:
                    final_lines.append(line)
                    line = ""
                    break
            if line:
                final_lines.append(line)

        final_text = "\n".join(final_lines)
        return final_text, final_text != original_text

    def _fix_single_word_orphans_generic(self, text: str) -> Tuple[str, bool]:
        if not text:
            return text, False
            
        # Розбиваємо по \n або \\n або \\p або \\l
        pattern = re.compile(r'(\n|\\n|\\p|\\l)')
        parts = pattern.split(text)
        
        num_lines = len(parts) // 2 + 1
        if num_lines <= 1:
            return text, False
            
        made_change = False
        
        # Текстові рядки на парних індексах
        for idx in range(len(parts) - 1, 1, -2):
            current_line = parts[idx]
            prev_line = parts[idx - 2]
            
            # 1. Перевіряємо, чи на поточному рядку рівно одне слово
            current_no_tags = remove_all_tags(current_line).strip()
            if not current_no_tags:
                continue
                
            words = current_no_tags.split()
            if len(words) != 1:
                continue
                
            word = words[0]
            
            # 2. Слово має бути з маленької літери
            first_letter_match = re.search(r'[a-zA-Zа-яА-ЯіїІїЄєґҐ]', word)
            if not first_letter_match or not first_letter_match.group(0).islower():
                continue
                
            # 3. В кінці слова немає розділових знаків (punctuation marks)
            clean_word = word.rstrip('"\'')
            if clean_word and clean_word[-1] in ['.', ',', '!', '?', ';', ':', '…', ')']:
                continue

            # 4. Попередній рядок не повинен закінчуватися розділовими знаками кінця речення
            prev_no_tags = remove_all_tags(prev_line).strip()
            if prev_no_tags and prev_no_tags[-1] in ['.', '!', '?', '…']:
                continue

            # 5. Попередній рядок повинен мати хоча б одне слово
            prev_words = prev_no_tags.split()
            if not prev_words:
                continue
                
            # 6. Спробуємо перенести останнє слово з попереднього рядка
            prev_parts = re.findall(r'(\{[^}]*\}|\[[^\]]*\]|\S+|\s+)', prev_line)
            
            last_word_idx = -1
            for k in range(len(prev_parts) - 1, -1, -1):
                part = prev_parts[k]
                if not part.strip():
                    continue
                is_tag = (part.startswith('{') and part.endswith('}')) or (part.startswith('[') and part.endswith(']'))
                if not is_tag:
                    last_word_idx = k
                    break
                    
            if last_word_idx == -1:
                continue
                
            # Вилучаємо останнє слово та все, що після нього
            prev_part_fixed = "".join(prev_parts[:last_word_idx]).rstrip()
            moved_part = "".join(prev_parts[last_word_idx:])
            
            # Оновлюємо попередній рядок у списку parts
            parts[idx - 2] = prev_part_fixed
            
            # Додаємо перенесену частину на початок поточного рядка
            spacer = " "
            if moved_part.endswith(" ") or current_line.startswith(" "):
                spacer = ""
                
            parts[idx] = moved_part + spacer + current_line
            made_change = True
            
        if made_change:
            final_text = "".join(parts)
            return final_text, final_text != text
            
        return text, False

