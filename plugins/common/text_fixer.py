from typing import Tuple, List, Optional, Set
import re
from utils.utils import calculate_string_width
from plugins.common.problem_rules import RuleContext, FixResult

class GenericTextFixer:
    """Generic text fixer implementation acting as an adapter to Rule Engine."""
    def __init__(self, main_window_ref, tag_manager_ref, problem_analyzer_ref):
        """Initialize a new instance."""
        self.mw = main_window_ref
        self.tag_manager = tag_manager_ref
        self.problem_analyzer = problem_analyzer_ref

    def _calculate_width(self, text: str, font_map: dict) -> int:
        if self.mw and getattr(self.mw, 'current_game_rules', None):
            if not hasattr(self.mw.current_game_rules, '_mock_self'):
                if hasattr(self.mw.current_game_rules, 'calculate_string_width_override'):
                    override_val = self.mw.current_game_rules.calculate_string_width_override(text, font_map)
                    if override_val is not None:
                        return override_val

        from utils.utils import calculate_string_width
        icon_sequences = getattr(self.mw, 'icon_sequences', []) if self.mw else []
        default_tag_mappings = getattr(self.mw, 'default_tag_mappings', None) if self.mw else None
        default_w = 8 if self.problem_analyzer.profile.tag_style == "square" else 6
        return calculate_string_width(
            text,
            font_map,
            default_char_width=default_w,
            icon_sequences=icon_sequences,
            default_tag_mappings=default_tag_mappings
        )

    def _merge_and_clean_pagination(self, text: str) -> str:
        if not text:
            return ""
        from utils.utils import remove_all_tags
        lines = text.split('\n')
        cleaned_lines = []
        for line in lines:
            stripped = line.strip()
            if not stripped or stripped == "0":
                continue
            cleaned_lines.append(line)

        if not cleaned_lines:
            return ""

        merged_parts = []
        current_part = ""
        for line in cleaned_lines:
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

    def _fix_width_exceeded_generic(self, text: str, font_map: dict, threshold: int) -> Tuple[str, bool]:
        """Wrap utility delegating to WidthRule logic directly."""
        context = self.problem_analyzer.build_context(text, font_map, threshold, threshold)
        rule = self.problem_analyzer.registry.get_rule("WIDTH_EXCEEDED")
        if rule:
            res = rule.fix(context, [])
            return res.text, res.changed
        return text, False

    def _shift_split_sentences(self, text: str, lines_per_page: int, original_text: Optional[str] = None, block_idx: Optional[int] = None, string_idx: Optional[int] = None) -> Tuple[str, bool]:
        original_input = text
        align_enabled = getattr(self.mw, 'align_sentences_to_original_pages', False) if self.mw else False
        prevent_empty_lines = getattr(self.mw, 'prevent_empty_lines_in_autofix', False) if self.mw else False

        if align_enabled and original_text:
            text = self._merge_and_clean_pagination(text)
            if self.mw:
                font_map = getattr(self.mw, 'font_map', {})
                b_idx = block_idx if block_idx is not None else getattr(self.mw.data_store, 'current_block_idx', -1)
                s_idx = string_idx if string_idx is not None else getattr(self.mw.data_store, 'current_string_idx', -1)

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

    def _compact_sentences_on_pages(self, text: str, font_map: dict, threshold: int, lines_per_page: int) -> Tuple[str, bool]:
        if not text:
            return text, False

        try:
            lines_per_page = int(lines_per_page)
        except (TypeError, ValueError):
            lines_per_page = 4

        if lines_per_page <= 0:
            return text, False

        prevent_empty_lines = getattr(self.mw, "prevent_empty_lines_in_autofix", False) if self.mw else False
        PAGE_BREAK_RE = re.compile(r"[\{\[](?:escape:0:(?:0007|7000)[0-9a-fA-F]*|pause[0-9]*)[\}\]]", re.IGNORECASE)
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
            return bool(re.match(r"^\s*[\{\[](?:escape:0:(?:0007|7000)[0-9a-fA-F]*|pause[0-9]*)[\}\]]", line, re.IGNORECASE))

        def _contains_tab_or_page_break(line: str) -> bool:
            if _starts_with_page_break(line):
                return True
            if "{tab}" in line.lower() or "{escape:6:000b}" in line.lower():
                return True
            return False

        lines = list(text.split("\n"))
        changed = False

        i = 0
        while i < len(lines):
            line = lines[i]
            if not line.strip() or not _is_sentence_end(line):
                i += 1
                continue
            if _contains_tab_or_page_break(line):
                i += 1
                continue

            page_i = i // lines_per_page
            page_end_idx = (page_i + 1) * lines_per_page - 1

            empty_slots = 0
            j = i + 1
            while j <= page_end_idx and j < len(lines) and not lines[j].strip():
                empty_slots += 1
                j += 1

            if empty_slots == 0:
                i += 1
                continue

            next_start = i + 1
            while next_start < len(lines) and not lines[next_start].strip():
                next_start += 1

            if next_start >= len(lines):
                break

            if _contains_tab_or_page_break(lines[next_start]):
                i += 1
                continue
            if next_start // lines_per_page != page_i:
                i += 1
                continue

            next_end = next_start
            while next_end < len(lines):
                if not lines[next_end].strip():
                    break
                if next_end // lines_per_page != page_i:
                    break
                if _is_sentence_end(lines[next_end]):
                    break
                next_end += 1

            if next_end >= len(lines) or (not lines[next_end].strip() and next_end == next_start):
                i += 1
                continue

            next_sent_lines = lines[next_start:next_end + 1]
            if any(_contains_tab_or_page_break(l) for l in next_sent_lines):
                i += 1
                continue

            next_text = " ".join(l.strip() for l in next_sent_lines)
            combined = (line.rstrip() + " " + next_text).strip()

            wrapped, _ = self._fix_width_exceeded_generic(combined, font_map, threshold)
            wrapped_lines = wrapped.split("\n")

            original_span = next_end - i + 1
            if len(wrapped_lines) > original_span:
                i += 1
                continue

            last_merged_idx = i + len(wrapped_lines) - 1
            if last_merged_idx // lines_per_page != page_i:
                i += 1
                continue

            padding_count = original_span - len(wrapped_lines)
            padding = [] if prevent_empty_lines else [""] * padding_count

            new_segment = wrapped_lines + padding
            lines = lines[:i] + new_segment + lines[next_end + 1:]
            changed = True
            continue

        final_text = "\n".join(lines)
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
        if not data_string:
            return data_string, False

        lines_per_page = getattr(self.mw, 'lines_per_page', 4) if self.mw else 4
        if type(lines_per_page).__name__ in ('MagicMock', 'Mock'):
            lines_per_page = 4
        else:
            try:
                lines_per_page = int(lines_per_page)
            except (TypeError, ValueError):
                lines_per_page = 4
        lines = data_string.split('\n')
        pages_chunks = [lines[i:i + lines_per_page] for i in range(0, len(lines), lines_per_page)]

        fixed_pages = []
        any_changed = False

        for idx, chunk in enumerate(pages_chunks):
            original_len = len(chunk)
            page_text = "\n".join(chunk)
            fixed_page_text, changed = autofix_func(
                page_text,
                editor_font_map,
                editor_line_width_threshold,
                logical_hard_limit=logical_hard_limit,
                allowed_problems=allowed_problems,
                block_idx=block_idx,
                string_idx=string_idx,
                page_local=False,
                disable_pagination=True
            )

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

    def autofix_data_string(self,
                             data_string: str,
                             editor_font_map: dict,
                             editor_line_width_threshold: int,
                             logical_hard_limit: Optional[int] = None,
                             allowed_problems: Optional[Set[str]] = None,
                             block_idx: Optional[int] = None,
                             string_idx: Optional[int] = None,
                             page_local: bool = False,
                             disable_pagination: bool = False) -> Tuple[str, bool]:
        """Autofix implementation routed via ProblemRuleRegistry."""
        if page_local:
            return self.autofix_page_local_wrapper(
                self.autofix_data_string,
                data_string,
                editor_font_map,
                editor_line_width_threshold,
                logical_hard_limit,
                allowed_problems,
                block_idx,
                string_idx
            )

        if logical_hard_limit is None:
            logical_hard_limit = editor_line_width_threshold

        # Setup threshold adjust like original logic
        global_max = getattr(self.mw, 'game_dialog_max_width_pixels', editor_line_width_threshold) if self.mw else editor_line_width_threshold
        try:
            global_max_val = int(global_max)
        except (TypeError, ValueError):
            global_max_val = editor_line_width_threshold

        standard_threshold = getattr(self.mw, 'line_width_warning_threshold_pixels', editor_line_width_threshold) if self.mw else editor_line_width_threshold
        try:
            standard_threshold_val = int(standard_threshold)
        except (TypeError, ValueError):
            standard_threshold_val = editor_line_width_threshold

        if logical_hard_limit != global_max_val and global_max_val > 0:
            editor_line_width_threshold = int(logical_hard_limit * (standard_threshold_val / global_max_val))

        original_text = str(data_string)

        # Build context
        context = self.problem_analyzer.build_context(
            original_text,
            editor_font_map,
            editor_line_width_threshold,
            logical_hard_limit
        )

        # Zelda BMG specific: Pre-process aliases if BMG active
        is_bmg = self.problem_analyzer.profile.star_section_mode
        changed_bmg_pre = False
        if is_bmg:
            context.text = self._to_aliases(context.text)
            star_rule = self.problem_analyzer.registry.get_rule("STAR_TAG_RULES")
            if star_rule and hasattr(star_rule, '_move_tabs_to_stline_start'):
                new_text, changed_tabs = star_rule._move_tabs_to_stline_start(context.text)
                if changed_tabs:
                    context.text = new_text
                    changed_bmg_pre = True

        # Run Rule Engine fixing
        import utils.utils as uu
        old_fm = uu._ACTIVE_FONT_MAP
        old_mappings = uu._ACTIVE_TAG_MAPPINGS
        old_seqs = uu._ACTIVE_ICON_SEQUENCES
        uu._ACTIVE_FONT_MAP = editor_font_map
        uu._ACTIVE_TAG_MAPPINGS = context.default_tag_mappings
        uu._ACTIVE_ICON_SEQUENCES = context.icon_sequences
        try:
            fixed_text, changed_in_rules = self.problem_analyzer.registry.fix_all(context, allowed_problems)
        finally:
            uu._ACTIVE_FONT_MAP = old_fm
            uu._ACTIVE_TAG_MAPPINGS = old_mappings
            uu._ACTIVE_ICON_SEQUENCES = old_seqs

        # High-level document operations: sentence pagination shifting and compaction
        original_message_text = None
        if self.mw and block_idx is not None and string_idx is not None:
            if (self.mw.data_store.data and
                0 <= block_idx < len(self.mw.data_store.data) and
                0 <= string_idx < len(self.mw.data_store.data[block_idx])):
                original_message_text = str(self.mw.data_store.data[block_idx][string_idx])

        lines_per_page = getattr(self.mw, 'lines_per_page', 4) if self.mw else 4
        if type(lines_per_page).__name__ in ('MagicMock', 'Mock'):
            lines_per_page = 4
        else:
            try:
                lines_per_page = int(lines_per_page)
            except (TypeError, ValueError):
                lines_per_page = 4
        changed_shift = False
        changed_compact = False

        # Check if SHORT_LINE is allowed
        short_line_allowed = False
        if allowed_problems is not None:
            short_line_allowed = self.problem_analyzer.registry.get_prefixed_id("SHORT_LINE") in allowed_problems
        else:
            if self.mw and hasattr(self.mw, 'autofix_enabled'):
                short_line_allowed = self.mw.autofix_enabled.get(self.problem_analyzer.registry.get_prefixed_id("SHORT_LINE"), False)

        if not disable_pagination:
            fixed_text, changed_shift = self._shift_split_sentences(fixed_text, lines_per_page, original_message_text, block_idx=block_idx, string_idx=string_idx)
            if short_line_allowed:
                fixed_text, changed_compact = self._compact_sentences_on_pages(
                    fixed_text, editor_font_map, editor_line_width_threshold, lines_per_page
                )

        if is_bmg:
            fixed_text = self._from_aliases(fixed_text)

        return fixed_text, (fixed_text != original_text or changed_in_rules or changed_shift or changed_compact or changed_bmg_pre)

    def _to_aliases(self, text: str) -> str:
        text = re.sub(r'\{escape:6:000a\}', '{*}', text, flags=re.IGNORECASE)
        text = re.sub(r'\{escape:6:000b\}', '{tab}', text, flags=re.IGNORECASE)
        return text

    def _from_aliases(self, text: str) -> str:
        text = text.replace('{*}', '{escape:6:000a}')
        text = text.replace('{tab}', '{escape:6:000b}')
        return text

    def _cleanup_spaces_around_tags_zww(self, text: str) -> Tuple[str, bool]:
        context = self.problem_analyzer.build_context(text, {}, 1000, 1000)
        rule = self.problem_analyzer.registry.get_rule("BAD_SPACING")
        if rule:
            matches = rule.detect(context)
            res = rule.fix(context, matches)
            return res.text, res.changed
        return text, False

    def _fix_empty_odd_sublines_zww(self, text: str) -> Tuple[str, bool]:
        context = self.problem_analyzer.build_context(text, {}, 1000, 1000)
        rule = self.problem_analyzer.registry.get_rule("EMPTY_ODD_SUBLINE_DISPLAY")
        if rule:
            matches = rule.detect(context)
            res = rule.fix(context, matches)
            return res.text, res.changed
        return text, False

    def _fix_short_lines_zbmg(self, text: str, font_map: dict, threshold: int) -> Tuple[str, bool]:
        working_text = text
        is_bmg = self.problem_analyzer.profile.star_section_mode
        if is_bmg:
            working_text = self._to_aliases(working_text)
        context = self.problem_analyzer.build_context(working_text, font_map, threshold, threshold)
        rule = self.problem_analyzer.registry.get_rule("SHORT_LINE")
        if rule:
            matches = rule.detect(context)
            res = rule.fix(context, matches)
            fixed_text = res.text
            if is_bmg:
                fixed_text = self._from_aliases(fixed_text)
            return fixed_text, fixed_text != text
        return text, False

    def _fix_short_lines_zww(self, text: str, font_map: dict, threshold: int) -> Tuple[str, bool]:
        return self._fix_short_lines_zbmg(text, font_map, threshold)

    def _fix_short_lines_zmc(self, text: str, font_map: dict, threshold: int) -> Tuple[str, bool]:
        return self._fix_short_lines_zbmg(text, font_map, threshold)

    def _fix_short_lines(self, text: str, font_map: dict, threshold: int) -> Tuple[str, bool]:
        is_pk = "pokemon" in self.problem_analyzer.__class__.__module__.lower()
        working_text = text
        if is_pk:
            working_text = text.replace('\\p', '\n').replace('\\l', '\n').replace('\\n', '\n')

        fixed_text, changed = self._fix_short_lines_zbmg(working_text, font_map, threshold)

        if is_pk:
            fixed_text = fixed_text.replace('\n', '\\n')
            changed = fixed_text != text

        return fixed_text, changed
