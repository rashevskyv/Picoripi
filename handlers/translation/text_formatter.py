# handlers/translation/text_formatter.py

import re
from typing import Any, List
from utils.utils import calculate_string_width, remove_all_tags


class TextFormatter:
    """
    Handles formatting, word wrapping, tag-aware sentence splitting, and pagination
    for translations.
    """
    def __init__(self, main_window: Any):
        """Initialize a new instance."""
        self.mw = main_window

    def format_and_wrap_translation(self, text: str, block_idx: int, string_idx: int) -> str:
        """
        Cleans the incoming translation, wraps lines to balance between line_width_warning_threshold_pixels 
        and game_dialog_max_width_pixels, and splits sentences into pages according to lines_per_page.
        """
        if not text:
            return ""

        if not isinstance(text, str):
            text = str(text)

        # 1. Clean incoming translation: replace all newlines with spaces
        cleaned_text = text.replace('\n', ' ')
        # Normalize double/multiple spaces to single space
        cleaned_text = re.sub(r' +', ' ', cleaned_text).strip()
        # Remove spaces immediately following leading tags
        cleaned_text = re.sub(r'^((?:\{[^}]*\}|\[[^\]]*\])*)\s+', r'\1', cleaned_text)
        # Remove spaces between tags and punctuation marks (e.g. "{tag} ," -> "{tag},")
        cleaned_text = re.sub(r'(\{[^}]*\}|\[[^\]]*\])\s+([,\.!?;:…])', r'\1\2', cleaned_text)

        # Get font map
        font_map = getattr(self.mw, 'current_font_map', None) or getattr(self.mw, 'font_map', None) or {}

        # Retrieve thresholds
        string_meta = self.mw.string_metadata.get((block_idx, string_idx), {})
        
        # Max allowed width (hard threshold, e.g. 460px)
        max_width_raw = string_meta.get("width", self.mw.game_dialog_max_width_pixels)
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

        # 2. Split text into sentences (tag-aware).
        # We split by (. ! ? …) followed by spaces, but ignoring punctuation inside {...} or [...] tags.
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

        sentences = split_sentences_tag_aware(cleaned_text)
        if not sentences:
            return ""

        # Helper to wrap a single sentence/text into lines based on warning_threshold and max_width
        def wrap_text_segment(segment_text: str) -> List[str]:
            """Wrap text segment."""
            parts = re.findall(r'(\{[^}]*\}|\[[^\]]*\]|\S+|\s+)', segment_text)
            segment_lines = []
            current_line = ""
            current_w = 0
            needs_space_flag = False

            icon_sequences = getattr(self.mw, 'icon_sequences', []) if self.mw else []
            default_tag_mappings = getattr(self.mw, 'default_tag_mappings', {}) if self.mw else {}

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
                # 4. Or the current width is <= warning_threshold AND the new width is <= max_width (single word crosses the threshold)
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

        # Wrap each sentence individually
        wrapped_sentences = []
        for s in sentences:
            s_lines = wrap_text_segment(s)
            if s_lines:
                wrapped_sentences.append(s_lines)

        # 3. Build pages using lines_per_page
        pages = []
        current_page_lines = []

        for s_lines in wrapped_sentences:
            num_s_lines = len(s_lines)

            # If a single sentence exceeds the page limit, we have to split it across pages
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
                # If adding this sentence to the current page would exceed lines_per_page,
                # we close the current page and start a new one with this sentence.
                if len(current_page_lines) + num_s_lines > lines_per_page:
                    pages.append(current_page_lines)
                    current_page_lines = list(s_lines)
                else:
                    current_page_lines.extend(s_lines)

        if current_page_lines:
            pages.append(current_page_lines)

        # 4. Join pages with page breaks (shift-enter char) and lines with newlines
        shift_enter_char = self.mw.current_game_rules.get_shift_enter_char() if self.mw.current_game_rules else "\n"

        page_strings = []
        for page_lines in pages:
            page_strings.append("\n".join(page_lines))

        formatted_editor_text = shift_enter_char.join(page_strings)

        # Clean each line: remove leading spaces and double spaces, treating regular tags
        # {tag}/[tag] as zero-width (ignored for spacing purposes) but forced aliases
        # {f:...}/{F:...} as actual text.
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
            for forced_alias, reg_tag, spaces, text in tokens:
                if forced_alias or text:
                    result.append(forced_alias if forced_alias else text)
                    last_is_space = False
                elif reg_tag:
                    # Zero-width: keep in output but don't affect space state
                    result.append(reg_tag)
                elif spaces:
                    if not last_is_space:
                        # Not leading/consecutive → keep exactly one space
                        result.append(' ')
                        last_is_space = True
                    # else: leading or double space after invisible tags → skip
            clean_lines.append(''.join(result).rstrip())
        formatted_editor_text = '\n'.join(clean_lines)

        # Convert to data format expected by update_edited_data
        final_data_text = self.mw.current_game_rules.convert_editor_text_to_data(formatted_editor_text) if self.mw.current_game_rules else formatted_editor_text

        return final_data_text
