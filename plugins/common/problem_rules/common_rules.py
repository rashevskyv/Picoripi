import re
from typing import List, Tuple, Set, Optional, Dict, Any
from .base import ProblemRule
from .models import ProblemMatch, FixResult
from .context import RuleContext
import utils.utils as uu
from utils.utils import (
    remove_all_tags,
    convert_dots_to_spaces_from_editor,
    is_visible_tag,
    find_missing_icon_spacing_spans,
    fix_missing_icon_spacing,
    check_broken_icon_hyphen_boundary,
    has_visible_content,
    extract_first_word_with_tags,
    get_line_words_and_visible_tags,
    clean_spaces,
    ALL_TAGS_PATTERN
)

def _is_mock(obj) -> bool:
    typename = type(obj).__name__
    return "Mock" in typename or "mock" in typename

# Helper function to calculate width within rules
def _get_string_width(text: str, context: RuleContext) -> int:
    if context.game_profile and context.game_profile.width_calculator:
        val = context.game_profile.width_calculator(text, context.font_map)
        if val is not None and not _is_mock(val):
            try:
                return int(val)
            except (TypeError, ValueError):
                pass
    # Fallback to standard
    default_w = 8 if context.game_profile and context.game_profile.tag_style == "square" else 6
    w = uu.calculate_string_width(
        text,
        context.font_map,
        default_char_width=default_w,
        icon_sequences=context.icon_sequences,
        default_tag_mappings=context.default_tag_mappings
    )
    if _is_mock(w):
        try:
            return int(w)
        except (TypeError, ValueError):
            return len(text) * default_w
    return w

class WidthRule(ProblemRule):
    @property
    def id(self) -> str:
        return "WIDTH_EXCEEDED"

    def detect(self, context: RuleContext) -> List[ProblemMatch]:
        sublines = context.text.split('\n')
        matches = []
        limit = context.logical_hard_limit
        for i, line in enumerate(sublines):
            # If star section mode is active and we are in BMG, {*} / {tab} must be stripped before width calc.
            orig_line = line
            if context.game_profile and context.game_profile.star_section_mode:
                orig_line = re.sub(r'\{\*\}', '{escape:6:000a}', line)
                orig_line = re.sub(r'\{tab\}', '{escape:6:000b}', orig_line)

            w = _get_string_width(orig_line.rstrip(), context)
            if w > limit:
                matches.append(ProblemMatch(problem_id=self.id, line_index=i))
        return matches

    def fix(self, context: RuleContext, matches: List[ProblemMatch]) -> FixResult:
        sublines = context.text.split('\n')
        made_change = False
        final_lines = []
        under_star = False
        threshold = context.logical_hard_limit

        for line in sublines:
            stripped = line.lstrip()
            if context.game_profile and context.game_profile.star_section_mode:
                if stripped.startswith('{*}'):
                    under_star = True
                if under_star and not stripped.startswith('{*}') and not stripped.startswith('{tab}'):
                    leading_spaces = line[:len(line) - len(stripped)]
                    line = leading_spaces + '{tab}' + stripped
                    stripped = line.lstrip()
                    made_change = True

            if _get_string_width(line, context) <= threshold:
                final_lines.append(line)
                continue

            while _get_string_width(line, context) > threshold:
                made_change = True
                line_parts = re.findall(r'((?:\{[^}]*\}|\[[^\]]*\])-\S+|\{[^}]*\}|\[[^\]]*\]|\S+|\s+)', line)
                best_split_point = -1
                punctuation_chars = {',', '.', '!', '?', ':', ';', '…', ')', ']', '}', '»', '”', '’', '"', "'", '—', '–'}
                for j in range(len(line_parts) - 1, 0, -1):
                    line_part_one = "".join(line_parts[:j]).rstrip()
                    if _get_string_width(line_part_one, context) <= threshold:
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
                    if under_star:
                        line2_stripped = line2.lstrip()
                        if not line2_stripped.startswith('{tab}'):
                            leading_spaces = line2[:len(line2) - len(line2_stripped)]
                            line2 = leading_spaces + '{tab}' + line2_stripped
                    line = line2 
                else:
                    final_lines.append(line)
                    line = ""
                    break
            if line:
                final_lines.append(line)

        final_text = "\n".join(final_lines)
        return FixResult(text=final_text, changed=final_text != context.text, fixed_problem_ids={self.id})

class BadSpacingRule(ProblemRule):
    @property
    def id(self) -> str:
        return "BAD_SPACING"

    def _check_bad_spacing(self, text: str, context: RuleContext) -> bool:
        if not text:
            return False
        clean_text_dots = convert_dots_to_spaces_from_editor(text)
        
        def repl(match):
            tag = match.group(0)
            if tag.lower().startswith("{f:") or tag.lower().startswith("[f:"):
                return "X"
            if is_visible_tag(tag, context.default_tag_mappings, context.font_map, context.icon_sequences):
                return "X"
            return ""
            
        clean_text_tags = ALL_TAGS_PATTERN.sub(repl, clean_text_dots)
        if clean_text_tags.startswith(" "):
            return True
        if "  " in clean_text_tags:
            return True
        return False

    def detect(self, context: RuleContext) -> List[ProblemMatch]:
        sublines = context.text.split('\n')
        matches = []
        for i, line in enumerate(sublines):
            if self._check_bad_spacing(line, context):
                matches.append(ProblemMatch(problem_id=self.id, line_index=i))
        return matches

    def fix(self, context: RuleContext, matches: List[ProblemMatch]) -> FixResult:
        sublines = context.text.split('\n')
        changed = False
        fixed_lines = []
        closing_tags = {"[/C]", "{COLOR_DEFAULT}", "{color:white}", "{escape:255:000000}"}
        if context.game_profile and context.game_profile.closing_color_tags:
            closing_tags.update(context.game_profile.closing_color_tags)

        # Helper to check forced tags
        def is_forced(tag: str) -> bool:
            if tag.lower().startswith("{f:") or tag.lower().startswith("[f:"):
                return True
            for alias, original in context.default_tag_mappings.items():
                if original == tag and (alias.lower().startswith("{f:") or alias.lower().startswith("[f:")):
                    return True
            return False

        for line in sublines:
            # Cleanup space around tags based on style
            pattern = re.compile(r"(?P<tag>\{[^}]*\}|\[[^\]]*\])(?P<space>[ \u00a0])(?P<after_space>.)?")
            current_pos = 0
            result_parts = []
            last_processed_end = 0
            while current_pos < len(line):
                match = pattern.search(line, current_pos)
                if not match:
                    result_parts.append(line[last_processed_end:])
                    break
                tag_start = match.start("tag")
                result_parts.append(line[last_processed_end:tag_start])
                tag_content = match.group("tag")
                space_content = match.group("space")
                after_char = match.group("after_space") if match.group("after_space") is not None else ""
                result_parts.append(tag_content)

                is_closing = tag_content.lower() in [c.lower() for c in closing_tags]
                should_remove_space = False
                if is_forced(tag_content):
                    should_remove_space = False
                elif is_closing:
                    if after_char and re.match(r'^[,\.!?]$', after_char):
                        should_remove_space = True
                else:
                    should_remove_space = True

                if not should_remove_space:
                    result_parts.append(space_content)
                last_processed_end = match.start("after_space") if after_char else match.end("space")
                current_pos = last_processed_end
            
            cleaned_line = "".join(result_parts)
            # Force remove spaces before punctuation marks after any tags
            cleaned_line = re.sub(r'(\{[^}]*\}|\[[^\]]*\])\s+([,\.!?;:…])', r'\1\2', cleaned_line)
            cleaned_line = clean_spaces(cleaned_line)
            if cleaned_line != line:
                changed = True
            fixed_lines.append(cleaned_line)

        final_text = "\n".join(fixed_lines)
        return FixResult(text=final_text, changed=changed, fixed_problem_ids={self.id})

class MissingIconSpacingRule(ProblemRule):
    @property
    def id(self) -> str:
        return "MISSING_ICON_SPACING"

    def detect(self, context: RuleContext) -> List[ProblemMatch]:
        sublines = context.text.split('\n')
        matches = []
        
        def check_visible(t):
            return is_visible_tag(t, context.default_tag_mappings, context.font_map, context.icon_sequences)

        for i, line in enumerate(sublines):
            spans = find_missing_icon_spacing_spans(line, check_visible, context.font_map, context.default_tag_mappings, context.icon_sequences)
            if spans:
                matches.append(ProblemMatch(problem_id=self.id, line_index=i))
        return matches

    def fix(self, context: RuleContext, matches: List[ProblemMatch]) -> FixResult:
        sublines = context.text.split('\n')
        changed = False
        fixed_lines = []

        def check_visible(t):
            return is_visible_tag(t, context.default_tag_mappings, context.font_map, context.icon_sequences)

        for line in sublines:
            fixed = fix_missing_icon_spacing(line, check_visible, context.font_map, context.default_tag_mappings, context.icon_sequences)
            if fixed != line:
                changed = True
            fixed_lines.append(fixed)

        final_text = "\n".join(fixed_lines)
        return FixResult(text=final_text, changed=changed, fixed_problem_ids={self.id})

class ShortLineRule(ProblemRule):
    @property
    def id(self) -> str:
        return "SHORT_LINE"

    def _ends_with_sentence_punctuation(self, text_no_tags_stripped: str) -> bool:
        if not text_no_tags_stripped:
            return False
        last_char = text_no_tags_stripped[-1]
        punctuation = {'.', '!', '?'}
        if last_char in ['"', "'"]:
            if len(text_no_tags_stripped) > 1:
                return text_no_tags_stripped[-2] in punctuation
            return False
        return last_char in punctuation

    def _check_short_line(self, current: str, next_line: str, context: RuleContext) -> bool:
        if next_line.lstrip().startswith("{*}") or next_line.lstrip().startswith("{tab}"):
            return False
        if re.search(r'^\s*[\{\[](?:escape:0:(?:0007|7000)[0-9a-fA-F]*|pause[0-9]*)[\}\]]', next_line, re.IGNORECASE):
            return False
        if not next_line.strip():
            return False

        if not has_visible_content(current, context.default_tag_mappings, context.font_map, context.icon_sequences):
            return False

        current_no_tags = remove_all_tags(current).strip()
        if self._ends_with_sentence_punctuation(current_no_tags):
            return False

        first_word_next, remaining_next = extract_first_word_with_tags(next_line)
        if not first_word_next:
            return False

        width_current = _get_string_width(current.rstrip(), context)
        space_width = _get_string_width(" ", context)

        clean_first = remove_all_tags(first_word_next).strip()
        clean_first_letters = re.sub(r'[^\w]', '', clean_first)
        is_single_letter = len(clean_first_letters) == 1 and clean_first_letters.isalpha()

        if is_single_letter and remaining_next.strip():
            second_word_next, _ = extract_first_word_with_tags(remaining_next)
            combined_word = first_word_next + " " + second_word_next
            width_first_word_next = _get_string_width(combined_word, context)
        else:
            width_first_word_next = _get_string_width(first_word_next, context)

        mw_ref = context.game_profile.main_window if context.game_profile else None
        next_words = get_line_words_and_visible_tags(next_line, mw_ref)
        threshold = context.width_threshold

        if len(next_words) == 2:
            width_next_full = _get_string_width(next_line.strip(), context)
            return (threshold - width_current) >= (width_next_full + space_width)

        return (threshold - width_current) >= (width_first_word_next + space_width)

    def detect(self, context: RuleContext) -> List[ProblemMatch]:
        sublines = context.text.split('\n')
        matches = []
        lines_per_page = context.lines_per_page
        for i in range(len(sublines) - 1):
            current = sublines[i]
            next_line = sublines[i + 1]
            is_boundary = (i + 1) % lines_per_page == 0
            if is_boundary:
                continue
            if self._check_short_line(current, next_line, context):
                matches.append(ProblemMatch(problem_id=self.id, line_index=i))
        return matches

    def fix(self, context: RuleContext, matches: List[ProblemMatch]) -> FixResult:
        sublines = context.text.split('\n')
        if len(sublines) <= 1:
            return FixResult(text=context.text, changed=False)

        original_text = context.text
        made_change_overall = True
        lines_per_page = context.lines_per_page
        threshold = context.width_threshold
        logical_hard_limit = context.logical_hard_limit

        while made_change_overall:
            made_change_overall = False
            new_sub_lines = list(sublines)
            i = len(new_sub_lines) - 2
            while i >= 0:
                current_line = new_sub_lines[i]
                next_line = new_sub_lines[i + 1]

                if '{tab}' in current_line.lower() or '{escape:6:000b}' in current_line.lower():
                    i -= 1
                    continue
                if '{tab}' in next_line.lower() or '{escape:6:000b}' in next_line.lower():
                    i -= 1
                    continue
                if re.search(r'^\s*[\{\[](?:escape:0:(?:0007|7000)[0-9a-fA-F]*|pause[0-9]*)[\}\]]', next_line, re.IGNORECASE):
                    i -= 1
                    continue
                if not next_line.strip():
                    i -= 1
                    continue

                is_boundary = (i + 1) % lines_per_page == 0
                if is_boundary:
                    mw_ref = context.game_profile.main_window if context.game_profile else None
                    words_next = get_line_words_and_visible_tags(next_line, mw_ref)
                    is_next_single_word_lowercase = False
                    if len(words_next) == 1:
                        word = words_next[0]
                        first_letter = re.search(r'[a-zA-Zа-яА-ЯіїІїЄєґҐ]', word)
                        if first_letter and first_letter.group(0).islower():
                            is_next_single_word_lowercase = True

                    if not is_next_single_word_lowercase:
                        i -= 1
                        continue

                    limit = logical_hard_limit
                    width_current = _get_string_width(current_line.rstrip(), context)
                    width_next = _get_string_width(next_line.strip(), context)
                    space_width = _get_string_width(" ", context)
                    if width_current + space_width + width_next > limit:
                        i -= 1
                        continue

                if self._check_short_line(current_line, next_line, context) or is_boundary:
                    first_word_next_raw, rest_of_next_line_raw = extract_first_word_with_tags(next_line)
                    current_line_rstripped = current_line.rstrip()
                    merged_line = current_line_rstripped
                    if current_line_rstripped and first_word_next_raw:
                        needs_space = False
                        if not current_line_rstripped.endswith(" ") and not first_word_next_raw.startswith(" "):
                            last_char_current = current_line_rstripped[-1]
                            first_char_next = first_word_next_raw[0]
                            is_current_ends_tag = last_char_current in ['}', ']']
                            is_next_starts_tag = first_char_next in ['{', '[']
                            is_next_starts_word_char = re.match(r"^[a-zA-Zа-яА-ЯіїєґІЇЄҐ]$", first_char_next) is not None
                            if is_current_ends_tag and is_next_starts_word_char:
                                needs_space = True
                            elif not is_current_ends_tag and not is_next_starts_tag:
                                needs_space = True
                            elif not is_current_ends_tag and is_next_starts_tag:
                                needs_space = True
                        if needs_space:
                            merged_line += " "
                    merged_line += first_word_next_raw
                    new_sub_lines[i] = merged_line
                    new_sub_lines[i + 1] = rest_of_next_line_raw
                    if not new_sub_lines[i + 1].strip() and len(new_sub_lines) > i + 1:
                        del new_sub_lines[i + 1]
                    made_change_overall = True
                    sublines = list(new_sub_lines)
                    break
                i -= 1
            if not made_change_overall:
                break

        final_text = "\n".join(sublines)
        return FixResult(text=final_text, changed=final_text != original_text, fixed_problem_ids={self.id})

class SingleWordSublineRule(ProblemRule):
    @property
    def id(self) -> str:
        return "SINGLE_WORD_SUBLINE"

    def _check_single_word_subline(self, text: str, context: RuleContext) -> bool:
        mw_ref = context.game_profile.main_window if context.game_profile else None
        words = get_line_words_and_visible_tags(text, mw_ref)
        if len(words) != 1:
            return False
        word = words[0]
        return bool(re.search(r'[\wа-яА-ЯіїІїЄєґҐ]+', word))

    def _is_single_word_ok(self, text: str, context: RuleContext) -> bool:
        mw_ref = context.game_profile.main_window if context.game_profile else None
        words = get_line_words_and_visible_tags(text, mw_ref)
        if len(words) != 1:
            return True
        word = words[0]
        first_letter = re.search(r'[a-zA-Zа-яА-ЯіїІїЄєґҐ]', word)
        if not first_letter:
            return True
        return first_letter.group(0).isupper()

    def _is_single_word_orphan_allowed(self, current: str, prev: str, context: RuleContext) -> bool:
        mw_ref = context.game_profile.main_window if context.game_profile else None
        prev_words = get_line_words_and_visible_tags(prev, mw_ref)
        if not prev_words:
            return True
        last_word = prev_words[-1]
        if last_word and last_word[-1] in ['.', '!', '?', '…']:
            return True

        prev_parts = re.findall(r'(\{[^}]*\}|\[[^\]]*\]|\S+|\s+)', prev)
        last_word_idx = -1
        for k in range(len(prev_parts) - 1, -1, -1):
            part = prev_parts[k]
            if not part.strip():
                continue
            is_tag = (part.startswith('{') and part.endswith('}')) or (part.startswith('[') and part.endswith(']'))
            if is_tag:
                is_visible = is_visible_tag(part, context.default_tag_mappings, context.font_map, context.icon_sequences)
                is_forced = bool(re.match(r'^[\{\[](?:F|f):', part))
                if is_visible or is_forced:
                    is_tag = False
            if not is_tag:
                last_word_idx = k
                break

        if last_word_idx == -1:
            return True

        prev_part_fixed = "".join(prev_parts[:last_word_idx]).rstrip()
        moved_part = "".join(prev_parts[last_word_idx:])
        spacer = " "
        if moved_part.endswith(" ") or current.startswith(" "):
            spacer = ""
        new_current = (moved_part + spacer + current).rstrip()

        w_prev_after = _get_string_width(prev_part_fixed, context)
        w_curr_after = _get_string_width(new_current, context)
        return w_curr_after > w_prev_after

    def detect(self, context: RuleContext) -> List[ProblemMatch]:
        sublines = context.text.split('\n')
        matches = []
        if len(sublines) <= 1:
            return matches

        if context.game_profile and context.game_profile.star_section_mode and "{*}" in context.text:
            return matches

        lines_per_page = context.lines_per_page
        for i, line in enumerate(sublines):
            if self._check_single_word_subline(line, context):
                if not self._is_single_word_ok(line, context):
                    is_allowed = False
                    if i > 0:
                        is_allowed = self._is_single_word_orphan_allowed(line, sublines[i - 1], context)

                    if not is_allowed:
                        if i % lines_per_page == 0:
                            page_lines = sublines[i : i + lines_per_page]
                            has_content_after = any(l.strip() for l in page_lines[1:])
                            pid = "SINGLE_WORD_SUBLINE" if has_content_after else "SINGLE_WORD_SUBLINE_NON_START"
                        else:
                            pid = "SINGLE_WORD_SUBLINE_NON_START"
                        matches.append(ProblemMatch(problem_id=pid, line_index=i))
        return matches

    def fix(self, context: RuleContext, matches: List[ProblemMatch]) -> FixResult:
        text = context.text
        if not text:
            return FixResult(text=text, changed=False)

        pattern = re.compile(r'(\n|\\n|\\p|\\l)')
        parts = pattern.split(text)
        num_lines = len(parts) // 2 + 1
        if num_lines <= 1:
            return FixResult(text=text, changed=False)

        made_change = False
        mw_ref = context.game_profile.main_window if context.game_profile else None

        for idx in range(len(parts) - 1, 1, -2):
            current_line = parts[idx]
            prev_line = parts[idx - 2]

            if '{tab}' in current_line.lower() or '{escape:6:000b}' in current_line.lower():
                continue
            if '{tab}' in prev_line.lower() or '{escape:6:000b}' in prev_line.lower():
                continue

            current_words = get_line_words_and_visible_tags(current_line, mw_ref)
            if len(current_words) != 1:
                continue

            word = current_words[0]
            first_letter = re.search(r'[a-zA-Zа-яА-ЯіїІїЄєґҐ]', word)
            if not first_letter or not first_letter.group(0).islower():
                continue

            prev_words = get_line_words_and_visible_tags(prev_line, mw_ref)
            if not prev_words:
                continue
            last_word = prev_words[-1]
            if last_word and last_word[-1] in ['.', '!', '?', '…']:
                continue

            if self._is_single_word_orphan_allowed(current_line, prev_line, context):
                continue

            prev_parts = re.findall(r'(\{[^}]*\}|\[[^\]]*\]|\S+|\s+)', prev_line)
            last_word_idx = -1
            for k in range(len(prev_parts) - 1, -1, -1):
                part = prev_parts[k]
                if not part.strip():
                    continue
                is_tag = (part.startswith('{') and part.endswith('}')) or (part.startswith('[') and part.endswith(']'))
                if is_tag:
                    is_visible = is_visible_tag(part, context.default_tag_mappings, context.font_map, context.icon_sequences)
                    is_forced = bool(re.match(r'^[\{\[](?:F|f):', part))
                    if is_visible or is_forced:
                        is_tag = False
                if not is_tag:
                    last_word_idx = k
                    break

            if last_word_idx == -1:
                continue

            prev_part_fixed = "".join(prev_parts[:last_word_idx]).rstrip()
            moved_part = "".join(prev_parts[last_word_idx:])

            parts[idx - 2] = prev_part_fixed
            spacer = " "
            if moved_part.endswith(" ") or current_line.startswith(" "):
                spacer = ""
            parts[idx] = moved_part + spacer + current_line
            made_change = True

        final_text = "".join(parts)
        return FixResult(text=final_text, changed=made_change, fixed_problem_ids={"SINGLE_WORD_SUBLINE", "SINGLE_WORD_SUBLINE_NON_START"})

class EmptyFirstLineOfPageRule(ProblemRule):
    @property
    def id(self) -> str:
        return "EMPTY_FIRST_LINE_OF_PAGE"

    def detect(self, context: RuleContext) -> List[ProblemMatch]:
        if context.game_profile and context.game_profile.star_section_mode:
            text_alias = re.sub(r'\{escape:6:000a\}', '{*}', context.text, flags=re.IGNORECASE)
            if "{*}" in text_alias:
                return []

        lines = context.text.split('\n')
        matches = []
        lines_per_page = context.lines_per_page
        for i in range(len(lines)):
            if i % lines_per_page == 0:
                is_empty = not lines[i].strip()
                if is_empty:
                    page_lines = lines[i : i + lines_per_page]
                    if len(page_lines) > 1:
                        has_content_after = any(line.strip() for line in page_lines[1:])
                        if has_content_after:
                            matches.append(ProblemMatch(problem_id=self.id, line_index=i))
        return matches

    def fix(self, context: RuleContext, matches: List[ProblemMatch]) -> FixResult:
        lines = context.text.split('\n')
        indices_to_remove = {m.line_index for m in matches}
        new_lines = [line for i, line in enumerate(lines) if i not in indices_to_remove]
        new_text = '\n'.join(new_lines)
        return FixResult(text=new_text, changed=new_text != context.text, fixed_problem_ids={self.id})

class EmptyOddSublineDisplayRule(ProblemRule):
    @property
    def id(self) -> str:
        return "EMPTY_ODD_SUBLINE_DISPLAY"

    def detect(self, context: RuleContext) -> List[ProblemMatch]:
        sublines = context.text.split('\n')
        if len(sublines) <= 1:
            return []
        matches = []
        for i, line in enumerate(sublines):
            is_odd = (i + 1) % 2 != 0
            if is_odd:
                has_tags = ALL_TAGS_PATTERN.search(line)
                if has_tags:
                    continue
                clean = remove_all_tags(line).strip()
                if not clean or clean == "0":
                    matches.append(ProblemMatch(problem_id=self.id, line_index=i))
        return matches

    def fix(self, context: RuleContext, matches: List[ProblemMatch]) -> FixResult:
        sublines = context.text.split('\n')
        if len(sublines) <= 1:
            return FixResult(text=context.text, changed=False)
        indices_to_remove = {m.line_index for m in matches}
        new_sub_lines = [line for i, line in enumerate(sublines) if i not in indices_to_remove]
        
        final_text_list = []
        for i in range(len(new_sub_lines)):
            if i > 0 and not new_sub_lines[i].strip() and not new_sub_lines[i-1].strip():
                continue
            final_text_list.append(new_sub_lines[i])
        joined_text = "\n".join(final_text_list)
        return FixResult(text=joined_text, changed=joined_text != context.text, fixed_problem_ids={self.id})

class BrokenIconHyphenRule(ProblemRule):
    @property
    def id(self) -> str:
        return "BROKEN_ICON_HYPHEN"

    def detect(self, context: RuleContext) -> List[ProblemMatch]:
        sublines = context.text.split('\n')
        matches = []
        def check_visible(t):
            return is_visible_tag(t, context.default_tag_mappings, context.font_map, context.icon_sequences)

        for i in range(len(sublines) - 1):
            if check_broken_icon_hyphen_boundary(sublines[i], sublines[i+1], check_visible):
                matches.append(ProblemMatch(problem_id=self.id, line_index=i))
        return matches

    def fix(self, context: RuleContext, matches: List[ProblemMatch]) -> FixResult:
        return FixResult(text=context.text, changed=False)

class TagWarningRule(ProblemRule):
    @property
    def id(self) -> str:
        return "TAG_WARNING"

    def detect(self, context: RuleContext) -> List[ProblemMatch]:
        if context.original_text is None or context.text is None:
            return []
        
        orig_tags = ALL_TAGS_PATTERN.findall(str(context.original_text))
        trans_tags = ALL_TAGS_PATTERN.findall(str(context.text))
        
        exceptions = {"Link", "Epona"}
        mw_ref = context.game_profile.main_window if context.game_profile else None
        if mw_ref and hasattr(mw_ref, 'current_game_rules') and mw_ref.current_game_rules:
            rules = mw_ref.current_game_rules
            if hasattr(rules, 'tag_exceptions'):
                if isinstance(rules.tag_exceptions, (list, set)):
                    exceptions = set(rules.tag_exceptions)
                elif isinstance(rules.tag_exceptions, str):
                    exceptions = {rules.tag_exceptions}
                    
        exceptions_lower = {e.lower() for e in exceptions}
        
        def clean_tags(tags_list):
            cleaned = []
            for tag in tags_list:
                inner = tag[1:-1] if (tag.startswith('{') and tag.endswith('}')) or (tag.startswith('[') and tag.endswith(']')) else tag
                if inner.lower() in exceptions_lower or tag.lower() in exceptions_lower:
                    continue
                cleaned.append(tag)
            return cleaned
            
        orig_cleaned = clean_tags(orig_tags)
        trans_cleaned = clean_tags(trans_tags)
        
        mismatch = False
        if len(orig_cleaned) != len(trans_cleaned):
            mismatch = True
        else:
            from collections import Counter
            orig_counter = Counter(orig_cleaned)
            trans_counter = Counter(trans_cleaned)
            for tag, count in orig_counter.items():
                if trans_counter[tag] < count:
                    mismatch = True
                    break
                    
        if mismatch:
            return [ProblemMatch(problem_id=self.id, line_index=0)]
        return []

    def fix(self, context: RuleContext, matches: List[ProblemMatch]) -> FixResult:
        return FixResult(text=context.text, changed=False)

# Zelda BMG specific StarTagRule for Enforcing {*} and {tab} layouts
class StarTagRule(ProblemRule):
    @property
    def id(self) -> str:
        return "STAR_TAG_RULES"

    def detect(self, context: RuleContext) -> List[ProblemMatch]:
        text_alias = re.sub(r'\{escape:6:000a\}', '{*}', context.text, flags=re.IGNORECASE)
        text_alias = re.sub(r'\{escape:6:000b\}', '{tab}', text_alias, flags=re.IGNORECASE)
        sublines = text_alias.split('\n')
        matches = []
        
        in_tab_section = False
        for i, subline in enumerate(sublines):
            stripped_subline = subline.strip()
            if stripped_subline.startswith("{*}"):
                in_tab_section = True
                if re.search(r'^\{\*\}\s', subline.lstrip()) or "{tab}" in subline:
                    matches.append(ProblemMatch(problem_id=self.id, line_index=i))
            elif in_tab_section:
                starts_with_tab = subline.startswith("{tab}")
                has_space_after_tab = subline.startswith("{tab} ")
                has_other_tabs = "{tab}" in subline[5:] if starts_with_tab else "{tab}" in subline
                if not starts_with_tab or has_space_after_tab or has_other_tabs:
                    matches.append(ProblemMatch(problem_id=self.id, line_index=i))
            else:
                if "{tab}" in subline:
                    matches.append(ProblemMatch(problem_id=self.id, line_index=i))
        return matches

    def _split_into_star_sections(self, lines: List[str]) -> List[Tuple[bool, List[str]]]:
        sections: List[Tuple[bool, List[str]]] = []
        current_lines: List[str] = []
        current_is_star = False
        started = False
        for line in lines:
            stripped = line.lstrip()
            is_star_start = stripped.startswith('{*}')
            if is_star_start:
                if current_lines or started:
                    sections.append((current_is_star, current_lines))
                current_lines = [line]
                current_is_star = True
                started = True
            else:
                if not started:
                    current_is_star = False
                    started = True
                current_lines.append(line)
        if current_lines or started:
            sections.append((current_is_star, current_lines))
        return sections

    def _wrap_tab_lines(self, lines: List[str], context: RuleContext, is_first_line: bool) -> List[str]:
        starts_with_star = is_first_line
        clean_parts: List[str] = []
        for i, line in enumerate(lines):
            stripped = line.strip()
            if is_first_line and i == 0:
                stripped = re.sub(r'^\{\*\}\s*', '', stripped)
                stripped = re.sub(r'^\{\*\}\s*', '', stripped)
            else:
                stripped = re.sub(r'^(\{tab\}\s*)+', '', stripped)
            stripped = re.sub(r'\{\*\}', '', stripped)
            stripped = re.sub(r'\{tab\}', '', stripped)
            if stripped:
                clean_parts.append(stripped)

        if not clean_parts:
            return []

        threshold = context.logical_hard_limit

        result: List[str] = []
        for part_idx, clean_part in enumerate(clean_parts):
            remaining = clean_part
            use_star_prefix = is_first_line and part_idx == 0
            while remaining:
                prefix = '{*}' if use_star_prefix else '{tab}'
                test_line = prefix + remaining
                test_line_orig = re.sub(r'\{\*\}', '{escape:6:000a}', test_line)
                test_line_orig = re.sub(r'\{tab\}', '{escape:6:000b}', test_line_orig)

                if _get_string_width(test_line_orig, context) <= threshold:
                    result.append(prefix + remaining)
                    break

                parts = re.findall(r'(\{[^}]*\}|\[[^\]]*\]|\S+|\s+)', remaining)
                best_split = -1
                for j in range(len(parts) - 1, 0, -1):
                    candidate = ''.join(parts[:j]).rstrip()
                    candidate_line = prefix + candidate
                    candidate_line_orig = re.sub(r'\{\*\}', '{escape:6:000a}', candidate_line)
                    candidate_line_orig = re.sub(r'\{tab\}', '{escape:6:000b}', candidate_line_orig)
                    if _get_string_width(candidate_line_orig, context) <= threshold:
                        best_split = j
                        break
                if best_split == -1:
                    best_split = 1 if len(parts) > 1 else len(parts)

                line1 = ''.join(parts[:best_split]).rstrip()
                line2 = ''.join(parts[best_split:]).lstrip()
                result.append(prefix + line1)
                remaining = line2
                use_star_prefix = False
        return result

    def _fix_star_section(self, section_lines: List[str], context: RuleContext) -> List[str]:
        if not section_lines:
            return []
            
        first_line_clean = section_lines[0].strip()
        first_line_clean = re.sub(r'^\{\\*\}\s*', '', first_line_clean)
        first_line_clean = re.sub(r'^\{\*\}\s*', '', first_line_clean)
        first_line_clean = re.sub(r'\{\*\}', '', first_line_clean)
        first_line_clean = re.sub(r'\{tab\}', '', first_line_clean).strip()
        
        if not first_line_clean:
            remaining_lines = section_lines[1:]
            if not remaining_lines:
                return ['{*}']
            wrapped_remaining = self._wrap_tab_lines(remaining_lines, context, is_first_line=False)
            return ['{*}'] + wrapped_remaining
        else:
            return self._wrap_tab_lines(section_lines, context, is_first_line=True)

    def _move_tabs_to_stline_start(self, text: str) -> Tuple[str, bool]:
        lines = text.split('\n')
        new_lines = []
        changed = False
        pending_tab = False
        
        for i, line in enumerate(lines):
            if pending_tab:
                stripped_line = line.lstrip()
                if stripped_line and not stripped_line.startswith('{*}') and not stripped_line.startswith('{tab}'):
                    leading_spaces = line[:len(line) - len(stripped_line)]
                    line = leading_spaces + '{tab}' + stripped_line
                    changed = True
                pending_tab = False

            if '{tab}' in line:
                stripped = line.lstrip()
                if stripped.startswith('{tab}'):
                    prefix_space = line[:line.find('{tab}')]
                    content_after = line[line.find('{tab}') + 5:]
                    content_after_clean = content_after.replace('{tab}', '').strip()
                    if not content_after_clean:
                        pending_tab = True
                        changed = True
                    else:
                        if '{tab}' in content_after:
                            content_clean = content_after.replace('{tab}', ' ')
                            content_normalized = re.sub(r'\s+', ' ', content_clean).strip()
                            cleaned_line = prefix_space + '{tab}' + content_normalized
                            new_lines.append(cleaned_line)
                            changed = True
                        else:
                            cleaned_line = prefix_space + '{tab}' + content_after.strip()
                            if cleaned_line != line:
                                new_lines.append(cleaned_line)
                                changed = True
                            else:
                                new_lines.append(line)
                else:
                    idx = line.find('{tab}')
                    first_part = line[:idx].rstrip()
                    second_part = line[idx:].strip()
                    second_part_clean = second_part.replace('{tab}', '').strip()
                    if not second_part_clean:
                        new_lines.append(first_part)
                        pending_tab = True
                        changed = True
                    else:
                        new_lines.append(first_part)
                        content_after_tab = second_part[5:].strip()
                        if '{tab}' in content_after_tab:
                            parts = content_after_tab.split('{tab}')
                            for part in parts:
                                part_stripped = part.strip()
                                if part_stripped:
                                    new_lines.append('{tab}' + part_stripped)
                        else:
                            new_lines.append('{tab}' + content_after_tab)
                        changed = True
            else:
                new_lines.append(line)
                
        if pending_tab:
            if new_lines and not new_lines[-1].strip():
                new_lines[-1] = '{tab}'
            else:
                new_lines.append('{tab}')
                
        return '\n'.join(new_lines), changed

    def fix(self, context: RuleContext, matches: List[ProblemMatch]) -> FixResult:
        original_text = context.text
        # Convert escape codes to aliases
        text_alias = re.sub(r'\{escape:6:000a\}', '{*}', original_text, flags=re.IGNORECASE)
        text_alias = re.sub(r'\{escape:6:000b\}', '{tab}', text_alias, flags=re.IGNORECASE)

        if '{tab}' in text_alias and '{*}' not in text_alias:
            text_alias = '{*}' + text_alias.lstrip()

        working_text, changed_tabs = self._move_tabs_to_stline_start(text_alias)
        lines = working_text.split('\n')
        sections = self._split_into_star_sections(lines)
        result_lines: List[str] = []
        
        for is_star_section, sec_lines in sections:
            if is_star_section:
                fixed = self._fix_star_section(sec_lines, context)
                result_lines.extend(fixed)
            else:
                # Standard re-wrap is done outside StarTagRule, but we keep the plain section
                result_lines.extend(sec_lines)

        final_text = '\n'.join(result_lines)
        final_text, changed_tabs_end = self._move_tabs_to_stline_start(final_text)
        
        # Convert aliases back
        final_text = final_text.replace('{*}', '{escape:6:000a}')
        final_text = final_text.replace('{tab}', '{escape:6:000b}')
        
        return FixResult(text=final_text, changed=final_text != original_text or changed_tabs or changed_tabs_end, fixed_problem_ids={self.id})
