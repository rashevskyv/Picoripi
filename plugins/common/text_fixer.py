from typing import Tuple, List, Optional, Set
import re
from utils.utils import calculate_string_width, remove_all_tags, ALL_TAGS_PATTERN

class GenericTextFixer:
    """Generic text fixer implementation."""
    def __init__(self, main_window_ref, tag_manager_ref, problem_analyzer_ref):
        """Initialize a new instance."""
        self.mw = main_window_ref
        self.tag_manager = tag_manager_ref
        self.problem_analyzer = problem_analyzer_ref

    def _calculate_width(self, text: str, font_map: dict) -> int:
        """Internal helper to calculate width."""
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
        """Internal helper to extract first word with tags generic."""
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
        """Internal helper to fix width exceeded generic."""
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
        """Internal helper to fix single word orphans generic."""
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
        """Internal helper to merge and clean pagination."""
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
        """Internal helper to shift split sentences."""
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

        This step runs *after* _shift_split_sentences has already arranged text
        into pages (either via empty-line padding or via page-break escape codes).

        Strategy: iterate over lines. Whenever line K ends a sentence and there
        are empty slot(s) remaining on the same physical page (K // lines_per_page),
        try to pull the next sentence onto that page by merging it with line K.
        If the merged+rewrapped text fits in the remaining page slots, keep the
        merge.  Otherwise leave everything unchanged.

        This method NEVER pushes a sentence to a different page than the one it
        was placed on by _shift_split_sentences.

        Sentence boundary: last visible character is one of ``.!?;`` (or a
        closing quote/paren after such char).  Lines containing page-break escape
        codes are always hard boundaries.
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

        PAGE_BREAK_RE = re.compile(
            r"[\{\[](?:escape:0:(?:0007|7000)[0-9a-fA-F]*|pause[0-9]*)[\}\]]",
            re.IGNORECASE,
        )
        SENTENCE_END_CHARS = frozenset(".!?;。！？")
        CLOSING_CHARS = frozenset("\"'»`)")

        def _is_sentence_end(line: str) -> bool:
            """Internal helper to check if is sentence end."""
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
            """Internal helper to starts with page break."""
            return bool(re.match(
                r"^\s*[\{\[](?:escape:0:(?:0007|7000)[0-9a-fA-F]*|pause[0-9]*)[\}\]]",
                line,
                re.IGNORECASE,
            ))

        lines = list(text.split("\n"))
        original_lines = list(lines)
        changed = False

        i = 0
        while i < len(lines):
            line = lines[i]

            # Only act on sentence-ending non-empty lines
            if not line.strip() or not _is_sentence_end(line):
                i += 1
                continue

            # Page of line i
            page_i = i // lines_per_page
            # Last index on this page
            page_end_idx = (page_i + 1) * lines_per_page - 1

            # Count empty slots remaining on this page after line i
            empty_slots = 0
            j = i + 1
            while j <= page_end_idx and j < len(lines) and not lines[j].strip():
                empty_slots += 1
                j += 1

            if empty_slots == 0:
                # No room to pull anything in — advance
                i += 1
                continue

            # Find start of next non-empty sentence (may be across the page
            # boundary — that's fine, we will detect that below).
            next_start = i + 1
            while next_start < len(lines) and not lines[next_start].strip():
                next_start += 1

            if next_start >= len(lines):
                break

            # Don't merge if next sentence starts with a page-break code
            if _starts_with_page_break(lines[next_start]):
                i += 1
                continue

            # Don't merge if the next sentence is on a different page
            # (empty padding lines between pages must not be "consumed")
            if next_start // lines_per_page != page_i:
                i += 1
                continue

            # Find end of next sentence (stop at page boundary or empty line)
            next_end = next_start
            while next_end < len(lines):
                if not lines[next_end].strip():
                    break
                if next_end // lines_per_page != page_i:
                    break
                if _is_sentence_end(lines[next_end]):
                    break
                next_end += 1

            if next_end >= len(lines) or not lines[next_end].strip() and next_end == next_start:
                # Empty — nothing to merge
                i += 1
                continue

            # next sentence is lines[next_start .. next_end] inclusive
            next_sent_lines = lines[next_start:next_end + 1]

            # Merge: append all of next sentence after line i on the same line
            next_text = " ".join(l.strip() for l in next_sent_lines)
            combined = (line.rstrip() + " " + next_text).strip()

            # Rewrap to see how many lines the combined text needs
            wrapped, _ = self._fix_width_exceeded_generic(combined, font_map, threshold)
            wrapped_lines = wrapped.split("\n")

            # The combined text replaces lines[i .. next_end] (+ empty lines in between)
            original_span = next_end - i + 1  # total slots from i to next_end inclusive
            # How many of those slots come after line i?
            # slots_after_i = original_span - 1 (we replace line i too but it counts)
            # Simpler: merged takes len(wrapped_lines) slots instead of original_span
            if len(wrapped_lines) > original_span:
                # Merged text is longer than original space — skip
                i += 1
                continue

            # Also make sure the wrapped lines don't cross the page boundary
            last_merged_idx = i + len(wrapped_lines) - 1
            if last_merged_idx // lines_per_page != page_i:
                i += 1
                continue

            # Apply merge
            padding_count = original_span - len(wrapped_lines)
            if prevent_empty_lines:
                padding = []
            else:
                padding = [""] * padding_count

            new_segment = wrapped_lines + padding
            lines = lines[:i] + new_segment + lines[next_end + 1:]
            changed = True
            # Re-check from i (wrapped_lines[-1] might itself be a sentence end)
            continue

        final_text = "\n".join(lines)
        # Normalize: only report changed if text actually differs
        return final_text, final_text != text

    def autofix_page_local_wrapper(self,
                                   autofix_func,
                                   data_string: str,
                                   editor_font_map: dict,
                                   editor_line_width_threshold: int,
                                   logical_hard_limit: Optional[int] = None,
                                   allowed_problems: Optional[Set[str]] = None,
                                   block_idx: Optional[int] = None,
                                   string_idx: Optional[int] = None) -> Tuple[str, bool]:
        """Autofix page local wrapper."""
        if not data_string:
            return data_string, False
            
        lines_per_page = getattr(self.mw, 'lines_per_page', 4) if self.mw else 4
        lines = data_string.split('\n')
        
        # Split into chunks of lines_per_page
        pages_chunks = [lines[i:i + lines_per_page] for i in range(0, len(lines), lines_per_page)]
        
        fixed_pages = []
        any_changed = False
        
        for idx, chunk in enumerate(pages_chunks):
            original_len = len(chunk)
            page_text = "\n".join(chunk)
            # Call the actual autofix function on this page chunk
            fixed_page_text, changed = autofix_func(
                page_text,
                editor_font_map,
                editor_line_width_threshold,
                logical_hard_limit=logical_hard_limit,
                allowed_problems=allowed_problems,
                block_idx=block_idx,
                string_idx=string_idx,
                page_local=False, # Disable recursion
                disable_pagination=True
            )
            
            # Pad back to original height if the lines decreased during merging.
            # Local page autofix (Shift+AutoFix) must preserve physical page boundaries,
            # so we always pad back to original chunk length.
            # However, for the last page, there are no subsequent pages that could shift up,
            # so we do not need to pad it.
            is_last_page = (idx == len(pages_chunks) - 1)
            fixed_chunk_lines = fixed_page_text.split('\n')
            if not is_last_page and len(fixed_chunk_lines) < original_len:
                fixed_chunk_lines.extend([""] * (original_len - len(fixed_chunk_lines)))
                fixed_page_text = "\n".join(fixed_chunk_lines)
                
            fixed_pages.append(fixed_page_text)
            if changed or fixed_page_text != page_text:
                any_changed = True
                
        final_text = "\n".join(fixed_pages)
        return final_text, final_text != data_string

