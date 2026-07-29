# handlers/translation/text_formatter.py

import re
from typing import Any, List
from utils.utils import calculate_string_width
from core.tag_utils import ANY_TAG_PATTERN_STR


class TextFormatter:
    """
    Handles formatting, word wrapping, tag-aware sentence splitting, and pagination
    for translations.
    """
    def __init__(self, main_window: Any):
        """Initialize a new instance."""
        self.mw = main_window

    def convert_translation_preserving_layout(self, text: str) -> str:
        """Convert editor-visible AI text to game data without wrapping or reflow."""
        value = str(text or "").replace("\r\n", "\n").replace("\r", "\n")
        if self.mw.current_game_rules:
            return self.mw.current_game_rules.convert_editor_text_to_data(value)
        return value

    def format_and_wrap_translation(self, text: str, block_idx: int, string_idx: int) -> str:
        """
        Cleans the incoming translation, wraps lines to balance between line_width_warning_threshold_pixels
        and game_dialog_max_width_pixels, and splits sentences into pages according to lines_per_page.
        Respects original newlines/page breaks where possible.
        """
        if not text:
            return ""

        if not isinstance(text, str):
            text = str(text)

        # Get font map
        font_map = getattr(self.mw, 'current_font_map', None) or getattr(self.mw, 'font_map', None) or {}

        # Retrieve thresholds
        string_meta = self.mw.string_metadata.get((block_idx, string_idx), {})
        
        # Max allowed width (hard threshold, e.g. 460px):
        # per-string override > plugin window-kind layout > global setting
        from utils.utils import resolve_width_limits
        _, max_width_raw = resolve_width_limits(
            string_meta, getattr(self.mw, 'current_game_rules', None),
            block_idx, string_idx,
            self.mw.line_width_warning_threshold_pixels,
            self.mw.game_dialog_max_width_pixels)
        try:
            max_width = int(max_width_raw)
        except (TypeError, ValueError):
            max_width = 200

        # Warning threshold (desired soft threshold, e.g. 410px)
        warning_threshold_raw = self.mw.line_width_warning_threshold_pixels
        try:
            warning_threshold = int(warning_threshold_raw)
        except (TypeError, ValueError):
            warning_threshold = 200

        global_max = self.mw.game_dialog_max_width_pixels
        try:
            global_max_val = int(global_max)
        except (TypeError, ValueError):
            global_max_val = 200

        if max_width != global_max_val and global_max_val > 0:
            warning_threshold = int(max_width * (warning_threshold / global_max_val))

        # Ensure warning threshold is <= max_width
        if warning_threshold > max_width:
            warning_threshold = max_width

        # Lines per page
        lines_per_page = self.mw.lines_per_page
        try:
            lines_per_page = int(lines_per_page)
        except (TypeError, ValueError):
            lines_per_page = 4

        # Page and control character retrievals
        shift_enter_char = self.mw.current_game_rules.get_shift_enter_char() if self.mw.current_game_rules else "\n"
        ctrl_enter_char = None
        if self.mw.current_game_rules and hasattr(self.mw.current_game_rules, 'get_ctrl_enter_char'):
            ctrl_enter_char = self.mw.current_game_rules.get_ctrl_enter_char()

        icon_sequences = getattr(self.mw, 'icon_sequences', []) if self.mw else []
        default_tag_mappings = getattr(self.mw, 'default_tag_mappings', {}) if self.mw else {}

        # 1. Clean and normalize each deliberate line individually
        def clean_single_line(line_text: str) -> str:
            cleaned = re.sub(r' +', ' ', line_text).strip()
            cleaned = re.sub(rf'^((?:{ANY_TAG_PATTERN_STR})*)\s+', r'\1', cleaned)
            cleaned = re.sub(rf'({ANY_TAG_PATTERN_STR})\s+([,\.!?;:…])', r'\1\2', cleaned)
            return cleaned

        # Helper to wrap a single sentence/text into lines based on warning_threshold and max_width
        def wrap_text_segment(segment_text: str) -> List[str]:
            """Wrap text segment."""
            parts = re.findall(rf'({ANY_TAG_PATTERN_STR}|\S+|\s+)', segment_text)
            segment_lines = []
            current_line = ""
            current_w = 0
            needs_space_flag = False

            for part in parts:
                part_width = calculate_string_width(part, font_map, icon_sequences=icon_sequences, default_tag_mappings=default_tag_mappings)

                # Calculate width including space if needed
                is_punctuation = part in (',', '.', '!', '?', ';', ':', '…')
                current_needs_space = (needs_space_flag and not part.isspace() and
                                      not is_punctuation and current_line and
                                      not current_line.endswith(" "))

                space_w = calculate_string_width(" ", font_map) if current_needs_space else 0
                new_width_if_added = current_w + space_w + part_width

                # Fit condition:
                # 1. Line is empty
                # 2. Or part is punctuation
                # 3. Or the new width is <= warning_threshold
                # 4. Or the current width is <= warning_threshold AND the new width is <= max_width
                if (not current_line or
                    is_punctuation or
                    new_width_if_added <= warning_threshold or
                    (current_w <= warning_threshold and new_width_if_added <= max_width)):

                    if current_needs_space:
                        current_line += " "
                    current_line += part
                    current_w = calculate_string_width(current_line, font_map, icon_sequences=icon_sequences, default_tag_mappings=default_tag_mappings)
                    needs_space_flag = not part.isspace()
                else:
                    # Part does not fit, start a new line
                    if current_line:
                        segment_lines.append(current_line.rstrip())
                    current_line = part.strip()
                    current_w = calculate_string_width(current_line, font_map, icon_sequences=icon_sequences, default_tag_mappings=default_tag_mappings)
                    needs_space_flag = not part.isspace()

            if current_line:
                segment_lines.append(current_line.rstrip())
            return segment_lines

        # Split sentences tag-aware
        def split_sentences_tag_aware(txt: str) -> List[str]:
            """Split sentences tag aware."""
            sentences_list = []
            current_sentence = []
            in_curly = False
            in_square = False

            i = 0
            n = len(txt)
            while i < n:
                c = txt[i]
                if c == '{':
                    in_curly = True
                elif c == '}':
                    in_curly = False
                elif c == '[':
                    in_square = True
                elif c == ']':
                    in_square = False

                current_sentence.append(c)

                # Split condition: punctuation not in tags, followed by space or end of string
                if not in_curly and not in_square and c in ('.', '!', '?', '…'):
                    j = i + 1
                    while j < n and txt[j].isspace():
                        j += 1
                    if j > i + 1:
                        # Append the spaces to current sentence
                        current_sentence.extend(txt[i+1:j])
                        sentences_list.append("".join(current_sentence).strip())
                        current_sentence = []
                        i = j - 1
                i += 1

            if current_sentence:
                sent_str = "".join(current_sentence).strip()
                if sent_str:
                    sentences_list.append(sent_str)
            return sentences_list

        # Formatting and wrapping logic for a single page segment
        def format_segment_within_page(segment_text: str) -> str:
            deliberate_lines = segment_text.split('\n')
            all_wrapped_sentences = []
            for line in deliberate_lines:
                cleaned_line = clean_single_line(line)
                if not cleaned_line:
                    all_wrapped_sentences.append([""])
                    continue
                
                line_w = calculate_string_width(cleaned_line, font_map, icon_sequences=icon_sequences, default_tag_mappings=default_tag_mappings)
                if line_w <= warning_threshold:
                    all_wrapped_sentences.append([cleaned_line])
                else:
                    line_sentences = split_sentences_tag_aware(cleaned_line)
                    for s in line_sentences:
                        s_lines = wrap_text_segment(s)
                        if s_lines:
                            all_wrapped_sentences.append(s_lines)

            # Build pages using lines_per_page
            pages = []
            current_page_lines = []

            for s_lines in all_wrapped_sentences:
                num_s_lines = len(s_lines)

                # If a single sentence exceeds the page limit, split it across pages
                if num_s_lines > lines_per_page:
                    if current_page_lines:
                        pages.append(current_page_lines)
                        current_page_lines = []

                    for i in range(0, num_s_lines, lines_per_page):
                        chunk = s_lines[i:i + lines_per_page]
                        if len(chunk) < lines_per_page and i + lines_per_page >= num_s_lines:
                            current_page_lines = chunk
                        else:
                            pages.append(chunk)
                else:
                    # Check if sentence fits on the current page
                    if len(current_page_lines) + num_s_lines > lines_per_page:
                        pages.append(current_page_lines)
                        current_page_lines = list(s_lines)
                    else:
                        current_page_lines.extend(s_lines)

            if current_page_lines:
                pages.append(current_page_lines)

            page_strings = []
            for page_lines in pages:
                page_strings.append("\n".join(page_lines))

            return shift_enter_char.join(page_strings)

        # Build a regex to split the text by page breaks if they are distinct from \n
        page_break_seps = []
        if shift_enter_char and isinstance(shift_enter_char, str) and shift_enter_char != "\n":
            page_break_seps.append(re.escape(shift_enter_char))
        if ctrl_enter_char and isinstance(ctrl_enter_char, str) and ctrl_enter_char != "\n":
            page_break_seps.append(re.escape(ctrl_enter_char))

        if page_break_seps:
            page_break_pattern = re.compile('(' + '|'.join(page_break_seps) + ')')
            parts = page_break_pattern.split(text)
            formatted_parts = []
            for i, part in enumerate(parts):
                if i % 2 == 1:
                    # Separator: keep as is
                    formatted_parts.append(part)
                else:
                    # Content: format segment
                    formatted_parts.append(format_segment_within_page(part))
            formatted_editor_text = "".join(formatted_parts)
        else:
            formatted_editor_text = format_segment_within_page(text)

        # Clean each line: remove leading spaces and double spaces, treating regular tags
        # {tag}/[tag] as zero-width but forced aliases {f:...}/{F:...} as actual text.
        _token_re = re.compile(
            r'(\{[fF]:[^}]*\})'           # group 1: forced alias → counts as text
            r'|(\{(?![fF]:)[^}]*\}|\[[^\]]*\])'  # group 2: regular tag → zero-width
            r'|( +)'                        # group 3: spaces
            r'|([^ \{\[\]]+)'              # group 4: regular text
        )
        clean_lines = []
        for raw_line in formatted_editor_text.split('\n'):
            tokens = _token_re.findall(raw_line)
            result = []
            last_is_space = True   # True = no visible text seen yet (leading position)
            for forced_alias, reg_tag, spaces, text_part in tokens:
                if forced_alias or text_part:
                    result.append(forced_alias if forced_alias else text_part)
                    last_is_space = False
                elif reg_tag:
                    # Keep in output but don't affect space state
                    result.append(reg_tag)
                elif spaces:
                    if not last_is_space:
                        result.append(' ')
                        last_is_space = True
            clean_lines.append(''.join(result).rstrip())
        formatted_editor_text = '\n'.join(clean_lines)

        # Convert to data format expected by update_edited_data
        final_data_text = self.mw.current_game_rules.convert_editor_text_to_data(formatted_editor_text) if self.mw.current_game_rules else formatted_editor_text

        return final_data_text
