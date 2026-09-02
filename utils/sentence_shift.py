import re
from typing import Optional, List, Tuple, Any

from core.tag_utils import ALL_TAGS_PATTERN
from utils.text_tags import FORCED_ALIAS_PATTERN, is_visible_tag, remove_all_tags

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
        from utils.utils import get_active_tag_mappings, get_active_font_map, get_active_icon_sequences
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
