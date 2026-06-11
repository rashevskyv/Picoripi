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
        
        if self.mw and getattr(self.mw, 'current_game_rules', None):
            if not hasattr(self.mw.current_game_rules, '_mock_self'):
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
            if self._calculate_width(line, font_map) <= threshold:
                final_lines.append(line)
                continue

            while self._calculate_width(line, font_map) > threshold:
                made_change = True
                line_parts = re.findall(r'(\{[^}]*\}|\[[^\]]*\]|\S+|\s+)', line)
                best_split_point = -1
                punctuation_chars = {',', '.', '!', '?', ':', ';', '…', ')', ']', '}', '»', '”', '’', '"', "'"}
                for j in range(len(line_parts) - 1, 0, -1):
                    line_part_one = "".join(line_parts[:j]).rstrip()
                    if self._calculate_width(line_part_one, font_map) <= threshold:
                        line_part_two = "".join(line_parts[j:]).lstrip()
                        if line_part_two and line_part_two[0] in punctuation_chars:
                            continue
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
        
        lines_per_page = getattr(self.mw, 'lines_per_page', 4)
        
        # Текстові рядки на парних індексах
        for idx in range(len(parts) - 1, 1, -2):
            current_line = parts[idx]
            prev_line = parts[idx - 2]
            
            # 1. Перевіряємо, чи на поточному рядку рівно одне слово (враховуючи видимі теги)
            from utils.utils import get_line_words_and_visible_tags
            current_words = get_line_words_and_visible_tags(current_line, self.mw)
            if len(current_words) != 1:
                continue
                
            word = current_words[0]
            
            # 2. Слово має бути з маленької літери
            first_letter_match = re.search(r'[a-zA-Zа-яА-ЯіїІїЄєґҐ]', word)
            if not first_letter_match or not first_letter_match.group(0).islower():
                continue

            # 4. Попередній рядок не повинен закінчуватися розділовими знаками кінця речення
            prev_words = get_line_words_and_visible_tags(prev_line, self.mw)
            if not prev_words:
                continue
            last_word = prev_words[-1]
            if last_word and last_word[-1] in ['.', '!', '?', '…']:
                continue
                
            # 6. Спробуємо перенести останнє слово з попереднього рядка
            prev_parts = re.findall(r'(\{[^}]*\}|\[[^\]]*\]|\S+|\s+)', prev_line)
            
            last_word_idx = -1
            for k in range(len(prev_parts) - 1, -1, -1):
                part = prev_parts[k]
                if not part.strip():
                    continue
                is_tag = (part.startswith('{') and part.endswith('}')) or (part.startswith('[') and part.endswith(']'))
                if is_tag:
                    from utils.utils import is_visible_tag, FORCED_ALIAS_PATTERN
                    if self.mw is not None:
                        mappings = getattr(self.mw, "default_tag_mappings", {})
                        font_map = getattr(self.mw, "font_map", {})
                        icon_sequences = getattr(self.mw, "icon_sequences", [])
                    else:
                        from utils.utils import get_active_tag_mappings, get_active_font_map, get_active_icon_sequences
                        mappings = get_active_tag_mappings()
                        font_map = get_active_font_map()
                        icon_sequences = get_active_icon_sequences()
                    
                    is_visible = is_visible_tag(part, mappings, font_map, icon_sequences)
                    is_forced = bool(FORCED_ALIAS_PATTERN.match(part))
                    if is_visible or is_forced:
                        is_tag = False
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

    def _merge_and_clean_pagination(self, text: str) -> str:
        if not text:
            return ""
        lines = text.split('\n')
        cleaned_lines = []
        for line in lines:
            stripped = line.strip()
            # Skip empty lines and single "0" lines (which are padding)
            if not stripped or stripped == "0":
                continue
            cleaned_lines.append(line)
            
        if not cleaned_lines:
            return ""
            
        merged_parts = []
        current_part = ""
        for line in cleaned_lines:
            # Check if line starts with a page break / pause code (supporting both {} and [])
            starts_with_page_break = bool(re.search(r'^\s*[\{\[](?:escape:0:(?:0007|7000)[0-9a-fA-F]*|pause[0-9]*)[\}\]]', line, re.IGNORECASE))
            
            if starts_with_page_break:
                if current_part:
                    merged_parts.append(current_part.strip())
                current_part = line
            else:
                if current_part:
                    current_part_stripped = current_part.rstrip()
                    line_lstripped = line.lstrip()
                    if current_part_stripped and line_lstripped:
                        needs_space = not current_part_stripped.endswith(" ") and not line_lstripped.startswith(" ")
                        current_part = current_part_stripped + (" " if needs_space else "") + line_lstripped
                    else:
                        current_part += line
                else:
                    current_part = line
                    
            cleaned_end = remove_all_tags(line).strip()
            if cleaned_end:
                last_char = cleaned_end[-1]
                if last_char in ('.', '!', '?', '。', '！', '？'):
                    merged_parts.append(current_part.strip())
                    current_part = ""
                elif last_char in ('"', "'", '»', '`', ')') and len(cleaned_end) > 1:
                    if cleaned_end[-2] in ('.', '!', '?', '。', '！', '？'):
                        merged_parts.append(current_part.strip())
                        current_part = ""
                        
        if current_part:
            merged_parts.append(current_part.strip())
            
        return "\n".join(merged_parts)

    def _shift_split_sentences(self, text: str, lines_per_page: int, original_text: Optional[str] = None, block_idx: Optional[int] = None, string_idx: Optional[int] = None) -> Tuple[str, bool]:
        original_input = text
        
        align_enabled = getattr(self.mw, 'align_sentences_to_original_pages', False) if self.mw else False
        prevent_empty_lines = getattr(self.mw, 'prevent_empty_lines_in_autofix', False) if self.mw else False
        if align_enabled and original_text:
            # 1. Clean old pagination first (only if alignment is enabled)
            text = self._merge_and_clean_pagination(text)
            
            # 2. Re-wrap by width threshold since merged lines might be too long
            if self.mw:
                font_map = getattr(self.mw, 'font_map', {})
                b_idx = block_idx if block_idx is not None else getattr(self.mw.data_store, 'current_block_idx', -1)
                s_idx = string_idx if string_idx is not None else getattr(self.mw.data_store, 'current_string_idx', -1)
                
                # Check for MagicMock
                if getattr(self.mw, 'helper', None) and not hasattr(self.mw.helper, '_mock_self') and b_idx != -1 and s_idx != -1:
                    font_map = self.mw.helper.get_font_map_for_string(b_idx, s_idx)
                
                threshold = getattr(self.mw, 'line_width_warning_threshold_pixels', 200)
                if hasattr(self.mw, 'string_metadata') and isinstance(self.mw.string_metadata, dict) and b_idx != -1 and s_idx != -1:
                    string_meta = self.mw.string_metadata.get((b_idx, s_idx), {})
                    threshold = string_meta.get("width", threshold)
                    
                text, _ = self._fix_width_exceeded_generic(text, font_map, threshold)
                
            from utils.utils import shift_split_sentences_aligned
            final_text, changed = shift_split_sentences_aligned(text, original_text, lines_per_page, prevent_empty_lines=prevent_empty_lines)
        else:
            from utils.utils import shift_split_sentences
            final_text, changed = shift_split_sentences(text, lines_per_page, prevent_empty_lines=prevent_empty_lines)
            
        return final_text, final_text != original_input
    def _compact_sentences_on_pages(
        self,
        text: str,
        font_map: dict,
        threshold: int,
        lines_per_page: int,
    ) -> "Tuple[str, bool]":
        """Try to merge consecutive sentences onto the same page.

        After _shift_split_sentences has arranged the text into pages, this step
        looks at each pair of adjacent sentences.  If the next sentence fits in
        the remaining space on the current page (starting right after the last
        line of the previous sentence), the two are merged.  Otherwise the next
        sentence is pushed to a new page (empty padding lines are added or
        removed depending on the *prevent_empty_lines_in_autofix* flag).

        Sentence boundaries: a line whose last visible character is one of
        ``.``, ``!``, ``?``, ``;`` (or a closing quote/paren after such char).
        Page-break escape codes are always hard boundaries.
        """
        if not text:
            return text, False

        try:
            lines_per_page = int(lines_per_page)
        except (TypeError, ValueError):
            lines_per_page = 4

        if lines_per_page <= 0:
            return text, False

        prevent_empty_lines = (
            getattr(self.mw, "prevent_empty_lines_in_autofix", False) if self.mw else False
        )

        lines = text.split("\n")
        original_text = text

        # ------------------------------------------------------------------ #
        # Step 1 – segment lines into sentences (same boundary logic as
        #          shift_split_sentences in utils.py).
        # Each sentence is stored as a list of line strings.
        # ------------------------------------------------------------------ #
        PAGE_BREAK_RE = re.compile(
            r"[\{\[](?:escape:0:(?:0007|7000)[0-9a-fA-F]*|pause[0-9]*)[\}\]]",
            re.IGNORECASE,
        )
        SENTENCE_END_CHARS = frozenset(".!?;。！？")
        CLOSING_CHARS = frozenset("\"'»`)")

        def _is_sentence_end(line: str) -> bool:
            from utils.utils import remove_all_tags
            cleaned = remove_all_tags(line).strip()
            if not cleaned:
                return False
            if PAGE_BREAK_RE.search(line):
                return True
            last = cleaned[-1]
            if last in SENTENCE_END_CHARS:
                return True
            if last in CLOSING_CHARS and len(cleaned) > 1 and cleaned[-2] in SENTENCE_END_CHARS:
                return True
            return False

        def _starts_with_page_break(line: str) -> bool:
            return bool(re.match(
                r"^\s*[\{\[](?:escape:0:(?:0007|7000)[0-9a-fA-F]*|pause[0-9]*)[\}\]]",
                line,
                re.IGNORECASE,
            ))

        sentences: "list[list[str]]" = []
        current: "list[str]" = []

        for line in lines:
            if not line.strip():
                # Empty line → flush current, treat empty as its own sentence
                if current:
                    sentences.append(current)
                    current = []
                sentences.append([line])
                continue

            if _starts_with_page_break(line) and current:
                sentences.append(current)
                current = []

            current.append(line)

            if _is_sentence_end(line):
                sentences.append(current)
                current = []

        if current:
            sentences.append(current)

        if len(sentences) <= 1:
            return text, False

        # ------------------------------------------------------------------ #
        # Step 2 – try to merge consecutive non-empty sentences that fit on
        #           the same page.
        # ------------------------------------------------------------------ #
        result_sentences: "list[list[str]]" = []
        page_pos = 0           # how many lines on the current page so far
        i = 0

        while i < len(sentences):
            sent = sentences[i]
            s_len = len(sent)
            is_empty_sent = (s_len == 1 and not sent[0].strip())
            has_page_break = sent and _starts_with_page_break(sent[0])

            if has_page_break:
                result_sentences.append(sent)
                page_pos = s_len % lines_per_page
                i += 1
                continue

            if is_empty_sent:
                if not prevent_empty_lines:
                    result_sentences.append(sent)
                    page_pos = (page_pos + 1) % lines_per_page
                # When prevent_empty_lines=True: silently skip
                i += 1
                continue

            # Normal sentence → look ahead at the next non-empty sentence
            if result_sentences or page_pos > 0:
                remaining = lines_per_page - (page_pos % lines_per_page)
                if remaining == 0:
                    remaining = lines_per_page
            else:
                remaining = lines_per_page

            # Try to merge: append next sentence right after the last line of
            # the current sentence and rewrap to see how many lines it takes.
            next_idx = i + 1
            # Skip any empty-line sentences between them (they count as padding)
            while next_idx < len(sentences) and (
                len(sentences[next_idx]) == 1 and not sentences[next_idx][0].strip()
            ):
                next_idx += 1

            if next_idx < len(sentences):
                next_sent = sentences[next_idx]
                next_has_break = next_sent and _starts_with_page_break(next_sent[0])

                if not next_has_break and len(next_sent) <= lines_per_page:
                    # Attempt to fit sent + next_sent on the current page
                    # starting right after the last line of sent.
                    last_line_of_sent = sent[-1].rstrip()
                    next_text = " ".join(line.strip() for line in next_sent)
                    combined = (last_line_of_sent + " " + next_text).strip() if last_line_of_sent else next_text

                    # Rewrap combined starting from the last line position
                    # (lines before the last line of sent are already placed)
                    lines_before_last = sent[:-1]
                    lines_used_before_last = len(lines_before_last)

                    remaining_for_merge = remaining - lines_used_before_last
                    if remaining_for_merge > 0:
                        wrapped, _ = self._fix_width_exceeded_generic(combined, font_map, threshold)
                        wrapped_lines = wrapped.split("\n")
                        if len(wrapped_lines) <= remaining_for_merge:
                            # Merge: build new sentence = lines before last + wrapped
                            merged_sent = lines_before_last + wrapped_lines
                            result_sentences.append(merged_sent)
                            page_pos = (page_pos + len(merged_sent)) % lines_per_page
                            # Skip the empty-line padding sentences between them
                            # and skip the next real sentence (it's been merged)
                            i = next_idx + 1
                            continue

            # No merge: place sentence as-is, filling page if needed
            # How many lines does this sentence need vs what's available?
            if page_pos > 0:
                remaining = lines_per_page - (page_pos % lines_per_page)
                if remaining == 0:
                    remaining = lines_per_page
                if s_len > remaining:
                    # Push to new page
                    if not prevent_empty_lines and result_sentences:
                        # Pad current page to boundary
                        padding = [""] * remaining
                        result_sentences.append(padding)
                    page_pos = 0
            result_sentences.append(sent)
            page_pos = (page_pos + s_len) % lines_per_page
            i += 1

        # ------------------------------------------------------------------ #
        # Step 3 – flatten back to text
        # ------------------------------------------------------------------ #
        final_lines: "list[str]" = []
        for sent in result_sentences:
            final_lines.extend(sent)

        final_text = "\n".join(final_lines)
        return final_text, final_text != original_text


