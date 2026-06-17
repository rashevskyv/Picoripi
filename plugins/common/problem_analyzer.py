from typing import Optional, Set, List
import re
from utils.utils import calculate_string_width, remove_all_tags, convert_dots_to_spaces_from_editor, get_tag_width, ALL_TAGS_PATTERN

class GenericProblemAnalyzer:
    """Generic problem analyzer implementation."""
    def __init__(self, main_window_ref, tag_manager_ref, problem_definitions_ref, problem_ids_ref):
        """Initialize a new instance."""
        self.mw = main_window_ref
        self.tag_manager = tag_manager_ref
        self.problem_definitions = problem_definitions_ref
        self.problem_ids = problem_ids_ref
        self.tag_exceptions = {"Link", "Epona"}

    def _check_bad_spacing(self, text: str) -> bool:
        """Internal helper to check bad spacing."""
        if not text:
            return False
        clean_text = convert_dots_to_spaces_from_editor(text)
        
        font_map = getattr(self.mw, 'font_map', {}) if self.mw else {}
        default_tag_mappings = getattr(self.mw, 'default_tag_mappings', {}) if self.mw else {}
        icon_sequences = getattr(self.mw, 'icon_sequences', []) if self.mw else []
        
        from utils.utils import is_visible_tag
        def repl(match):
            """Repl."""
            tag = match.group(0)
            if tag.lower().startswith("{f:") or tag.lower().startswith("[f:"):
                return "X"
            if is_visible_tag(tag, default_tag_mappings, font_map, icon_sequences):
                return "X"
            return ""
            
        clean_text = ALL_TAGS_PATTERN.sub(repl, clean_text)
        
        if clean_text.startswith(" "):
            return True
        if "  " in clean_text:
            return True
        return False

    def _check_missing_icon_spacing(self, text: str) -> bool:
        """Internal helper to check missing icon spacing."""
        missing_spacing_id = getattr(self.problem_ids, 'PROBLEM_MISSING_ICON_SPACING', None)
        if not missing_spacing_id and isinstance(self.problem_ids, dict):
            missing_spacing_id = self.problem_ids.get('MISSING_ICON_SPACING', None)
            
        if not missing_spacing_id:
            return False
            
        # Check if enabled in detection_enabled
        enabled = True
        if self.mw and hasattr(self.mw, 'detection_enabled'):
            enabled = self.mw.detection_enabled.get(missing_spacing_id, True)
            
        if not enabled:
            return False
            
        from utils.utils import find_missing_icon_spacing_spans, is_visible_tag
        font_map = getattr(self.mw, 'font_map', {}) if self.mw else {}
        default_tag_mappings = getattr(self.mw, 'default_tag_mappings', {}) if self.mw else {}
        icon_sequences = getattr(self.mw, 'icon_sequences', []) if self.mw else []
        
        def check_visible(t):
            """Check visible."""
            return is_visible_tag(t, default_tag_mappings, font_map, icon_sequences)
            
        spans = find_missing_icon_spacing_spans(text, check_visible)
        return len(spans) > 0

    def _check_broken_icon_hyphen(self, text: str, next_text: Optional[str]) -> bool:
        """Internal helper to check broken icon hyphen wrap."""
        if not next_text:
            return False
            
        broken_hyphen_id = getattr(self.problem_ids, 'PROBLEM_BROKEN_ICON_HYPHEN', None)
        if not broken_hyphen_id and isinstance(self.problem_ids, dict):
            broken_hyphen_id = self.problem_ids.get('BROKEN_ICON_HYPHEN', None)
            
        if not broken_hyphen_id:
            # Dynamic fallback: find ID in problem definitions
            defs = self.problem_definitions
            for pid in defs.keys():
                if pid.endswith('_BROKEN_ICON_HYPHEN'):
                    broken_hyphen_id = pid
                    break
                    
        if not broken_hyphen_id:
            return False
            
        # Check if enabled in detection_enabled
        enabled = True
        if self.mw and hasattr(self.mw, 'detection_enabled'):
            enabled = self.mw.detection_enabled.get(broken_hyphen_id, True)
            
        if not enabled:
            return False
            
        from utils.utils import check_broken_icon_hyphen_boundary, is_visible_tag
        font_map = getattr(self.mw, 'font_map', {}) if self.mw else {}
        default_tag_mappings = getattr(self.mw, 'default_tag_mappings', {}) if self.mw else {}
        icon_sequences = getattr(self.mw, 'icon_sequences', []) if self.mw else []
        
        def check_visible(t):
            """Check visible."""
            return is_visible_tag(t, default_tag_mappings, font_map, icon_sequences)
            
        return check_broken_icon_hyphen_boundary(text, next_text, check_visible)

    def _check_single_word_subline_generic(self, subline_text: str) -> bool:
        """Internal helper to check single word subline generic."""
        from utils.utils import get_line_words_and_visible_tags
        words = get_line_words_and_visible_tags(subline_text, self.mw)
        if len(words) != 1:
            return False
        word = words[0]
        word_content_pattern = re.compile(r'[\wа-яА-ЯіїІїЄєґҐ]+') 
        return bool(word_content_pattern.search(word))

    def _is_single_word_ok_generic(self, subline_text: str) -> bool:
        """Internal helper to check if is single word ok generic."""
        from utils.utils import get_line_words_and_visible_tags
        words = get_line_words_and_visible_tags(subline_text, self.mw)
        if len(words) != 1:
            return True
        word = words[0]
        
        first_letter_match = re.search(r'[a-zA-Zа-яА-ЯіїІїЄєґҐ]', word)
        if not first_letter_match:
            return True
            
        is_capital = first_letter_match.group(0).isupper()
        
        # Word starting with a capital letter is ALWAYS ok (no warning)
        if is_capital:
            return True
            
        return False

    def analyze_subline(self,
                        text: str,
                        next_text: Optional[str],
                        subline_number_in_data_string: int,
                        qtextblock_number_in_editor: int,
                        is_last_subline_in_data_string: bool,
                        editor_font_map: dict,
                        editor_line_width_threshold: int,
                        full_data_string_text_for_logical_check: str,
                        is_target_for_debug: bool = False,
                        logical_hard_limit: Optional[int] = None) -> Set[str]:
        """Analyze subline."""
        found_problems = set()
        
        # Common width check
        limit = logical_hard_limit if logical_hard_limit is not None else getattr(self.mw, 'game_dialog_max_width_pixels', editor_line_width_threshold)
        if not isinstance(limit, (int, float)):
            limit = editor_line_width_threshold
        pixel_width = calculate_string_width(text.rstrip(), editor_font_map)
        if pixel_width > limit:
            if hasattr(self.problem_ids, 'PROBLEM_WIDTH_EXCEEDED'):
                found_problems.add(self.problem_ids.PROBLEM_WIDTH_EXCEEDED)
            elif 'WIDTH' in self.problem_ids:
                 found_problems.add(self.problem_ids['WIDTH'])

        # Spacing check
        if self._check_bad_spacing(text):
            if isinstance(self.problem_ids, dict):
                if 'BAD_SPACING' in self.problem_ids:
                    found_problems.add(self.problem_ids['BAD_SPACING'])
            else:
                if hasattr(self.problem_ids, 'PROBLEM_BAD_SPACING'):
                    found_problems.add(self.problem_ids.PROBLEM_BAD_SPACING)

        # Missing icon spacing check
        if self._check_missing_icon_spacing(text):
            missing_spacing_id = getattr(self.problem_ids, 'PROBLEM_MISSING_ICON_SPACING', None)
            if not missing_spacing_id and isinstance(self.problem_ids, dict):
                missing_spacing_id = self.problem_ids.get('MISSING_ICON_SPACING', None)
            if missing_spacing_id:
                found_problems.add(missing_spacing_id)

        # Broken icon hyphen check
        if self._check_broken_icon_hyphen(text, next_text):
            broken_hyphen_id = getattr(self.problem_ids, 'PROBLEM_BROKEN_ICON_HYPHEN', None)
            if not broken_hyphen_id and isinstance(self.problem_ids, dict):
                broken_hyphen_id = self.problem_ids.get('BROKEN_ICON_HYPHEN', None)
            if not broken_hyphen_id:
                defs = self.problem_definitions
                for pid in defs.keys():
                    if pid.endswith('_BROKEN_ICON_HYPHEN'):
                        broken_hyphen_id = pid
                        break
            if broken_hyphen_id:
                found_problems.add(broken_hyphen_id)

        return found_problems

    def check_tags_mismatch(self, original_text: str, translated_text: str) -> bool:
        """
        Check if the translated text has tag count mismatch compared to the original,
        or if tags from the original are missing in the translation (respecting exceptions).
        """
        if original_text is None or translated_text is None:
            return False
            
        from utils.utils import ALL_TAGS_PATTERN
        
        orig_tags = ALL_TAGS_PATTERN.findall(str(original_text))
        trans_tags = ALL_TAGS_PATTERN.findall(str(translated_text))
        
        # Determine tag exceptions
        exceptions = self.tag_exceptions
        if self.mw and hasattr(self.mw, 'current_game_rules'):
            rules = self.mw.current_game_rules
            if hasattr(rules, 'tag_exceptions'):
                if isinstance(rules.tag_exceptions, (list, set)):
                    exceptions = set(rules.tag_exceptions)
                elif isinstance(rules.tag_exceptions, str):
                    exceptions = {rules.tag_exceptions}
                    
        exceptions_lower = {e.lower() for e in exceptions}
        
        def clean_tags(tags_list):
            cleaned = []
            for tag in tags_list:
                # Strip curly/square brackets to check the tag body
                inner = tag[1:-1] if (tag.startswith('{') and tag.endswith('}')) or (tag.startswith('[') and tag.endswith(']')) else tag
                if inner.lower() in exceptions_lower or tag.lower() in exceptions_lower:
                    continue
                cleaned.append(tag)
            return cleaned
            
        orig_cleaned = clean_tags(orig_tags)
        trans_cleaned = clean_tags(trans_tags)
        
        # 1. Total count check
        if len(orig_cleaned) != len(trans_cleaned):
            return True
            
        # 2. Tag match and count presence check
        from collections import Counter
        orig_counter = Counter(orig_cleaned)
        trans_counter = Counter(trans_cleaned)
        
        for tag, count in orig_counter.items():
            if trans_counter[tag] < count:
                return True
                
        return False

    def _is_single_word_orphan_allowed(self, current_line: str, prev_line: str, font_map: dict) -> bool:
        """
        Check if a single word orphan on the current line is allowed (should not trigger warning or autofix)
        because moving the last word from the previous line would make the current line wider than the previous one.
        """
        from utils.utils import get_line_words_and_visible_tags
        prev_words = get_line_words_and_visible_tags(prev_line, self.mw)
        if not prev_words:
            return True # No words to move anyway
            
        last_word = prev_words[-1]
        if last_word and last_word[-1] in ['.', '!', '?', '…']:
            return True # Ends sentence, don't move
            
        prev_parts = re.findall(r'(\{[^}]*\}|\[[^\]]*\]|\S+|\s+)', prev_line)
        last_word_idx = -1
        for k in range(len(prev_parts) - 1, -1, -1):
            part = prev_parts[k]
            if not part.strip():
                continue
            is_tag = (part.startswith('{') and part.endswith('}')) or (part.startswith('[') and part.endswith(']'))
            if is_tag:
                from utils.utils import is_visible_tag, FORCED_ALIAS_PATTERN
                mappings = getattr(self.mw, "default_tag_mappings", {}) if self.mw else {}
                icon_sequences = getattr(self.mw, "icon_sequences", []) if self.mw else {}
                is_visible = is_visible_tag(part, mappings, font_map, icon_sequences)
                is_forced = bool(FORCED_ALIAS_PATTERN.match(part))
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
        if moved_part.endswith(" ") or current_line.startswith(" "):
            spacer = ""
            
        new_current_line = (moved_part + spacer + current_line).rstrip()
        
        # Calculate widths
        def get_w(t):
            if self.mw and getattr(self.mw, 'current_game_rules', None):
                if not hasattr(self.mw.current_game_rules, '_mock_self') and hasattr(self.mw.current_game_rules, 'calculate_string_width_override'):
                    val = self.mw.current_game_rules.calculate_string_width_override(t, font_map)
                    if val is not None:
                        return val
            icon_seqs = getattr(self.mw, 'icon_sequences', []) if self.mw else []
            def_mappings = getattr(self.mw, 'default_tag_mappings', None) if self.mw else None
            return calculate_string_width(t, font_map, icon_sequences=icon_seqs, default_tag_mappings=def_mappings)
            
        width_prev_after_move = get_w(prev_part_fixed)
        width_current_after_move = get_w(new_current_line)
        
        return width_current_after_move > width_prev_after_move

