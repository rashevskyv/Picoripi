from typing import Optional, Set, List
import re
from plugins.common.problem_rules import (
    create_default_registry,
    GameProblemProfile,
    RuleContext
)

class GenericProblemAnalyzer:
    """Generic problem analyzer implementation acting as an adapter to Rule Engine."""
    def __init__(self, main_window_ref, tag_manager_ref, problem_definitions_ref, problem_ids_ref):
        """Initialize a new instance."""
        self.mw = main_window_ref
        self.tag_manager = tag_manager_ref
        self.problem_definitions = problem_definitions_ref
        self.problem_ids = problem_ids_ref
        self.tag_exceptions = {"Link", "Epona"}

        # Build GameProblemProfile
        pids_dict = {}
        if isinstance(problem_ids_ref, dict):
            pids_dict = problem_ids_ref
        else:
            for attr in dir(problem_ids_ref):
                if not attr.startswith('__'):
                    val = getattr(problem_ids_ref, attr)
                    if isinstance(val, str):
                        pids_dict[attr] = val

        logical_map = {}
        for k, v in pids_dict.items():
            logical_key = k.replace("PROBLEM_", "")
            logical_map[logical_key] = v

        for log_key in ["WIDTH_EXCEEDED", "BAD_SPACING", "MISSING_ICON_SPACING", "SHORT_LINE", "SINGLE_WORD_SUBLINE", "SINGLE_WORD_SUBLINE_NON_START", "EMPTY_FIRST_LINE_OF_PAGE", "EMPTY_ODD_SUBLINE_DISPLAY", "BROKEN_ICON_HYPHEN", "TAG_WARNING", "STAR_TAG_RULES"]:
            if log_key not in logical_map:
                for k, v in pids_dict.items():
                    if log_key in k:
                        logical_map[log_key] = v
                        break
                else:
                    logical_map[log_key] = log_key

        module_name = self.__class__.__module__.lower()

        tag_style = "curly"
        if "ww" in module_name or "plain_text" in module_name:
            tag_style = "square"
        elif main_window_ref and hasattr(main_window_ref, 'current_game_rules') and main_window_ref.current_game_rules:
            # Detect tag style based on plugin type
            rules_name = main_window_ref.current_game_rules.__class__.__name__
            if "WW" in rules_name or "PlainText" in rules_name:
                tag_style = "square"

        star_section_mode = False
        if "bmg" in module_name or "bmg" in str(problem_ids_ref).lower():
            star_section_mode = True
        elif main_window_ref and hasattr(main_window_ref, 'current_game_rules') and main_window_ref.current_game_rules:
            if "BMG" in main_window_ref.current_game_rules.__class__.__name__:
                star_section_mode = True

        closing_color_tags = []
        if star_section_mode:
            closing_color_tags = ["{COLOR_DEFAULT}", "{color:white}", "{escape:255:000000}"]
        else:
            closing_color_tags = ["[/C]", "{COLOR_WHITE}"]

        def custom_width_calc(t, fm):
            default_w = 8 if tag_style == "square" else 6
            if hasattr(self, 'game_rules') and self.game_rules:
                if hasattr(self.game_rules, 'calculate_string_width_override'):
                    return self.game_rules.calculate_string_width_override(t, fm, default_w)
            if main_window_ref and hasattr(main_window_ref, 'current_game_rules') and main_window_ref.current_game_rules:
                if hasattr(main_window_ref.current_game_rules, 'calculate_string_width_override'):
                    return main_window_ref.current_game_rules.calculate_string_width_override(t, fm, default_w)
            return None

        self.profile = GameProblemProfile(
            problem_ids=logical_map,
            tag_style=tag_style,
            closing_color_tags=closing_color_tags,
            star_section_mode=star_section_mode,
            width_calculator=custom_width_calc,
            main_window=main_window_ref,
            problem_definitions=self.problem_definitions
        )
        self.registry = create_default_registry(self.profile)

    def build_context(self, text: str, font_map: dict, threshold: int, logical_hard_limit: Optional[int] = None, original_text: Optional[str] = None) -> RuleContext:
        limit = logical_hard_limit if logical_hard_limit is not None else getattr(self.mw, 'game_dialog_max_width_pixels', threshold)
        if not isinstance(limit, (int, float)):
            limit = threshold

        lines_per_page = 4
        if self.mw and hasattr(self.mw, 'lines_per_page'):
            val = getattr(self.mw, 'lines_per_page', 4)
            if isinstance(val, (int, float, str)):
                try:
                    lines_per_page = int(val)
                except (TypeError, ValueError):
                    lines_per_page = 4

        default_tag_mappings = getattr(self.mw, 'default_tag_mappings', {}) if self.mw else {}
        if not isinstance(default_tag_mappings, dict):
            default_tag_mappings = {}

        icon_sequences = getattr(self.mw, 'icon_sequences', []) if self.mw else []
        if not isinstance(icon_sequences, list):
            icon_sequences = []

        # Support context block and string idx
        block_idx = getattr(self, '_current_scan_block_idx', None)
        string_idx = getattr(self, '_current_scan_string_idx', None)

        return RuleContext(
            text=text,
            font_map=font_map,
            width_threshold=threshold,
            logical_hard_limit=limit,
            lines_per_page=lines_per_page,
            default_tag_mappings=default_tag_mappings,
            icon_sequences=icon_sequences,
            original_text=original_text,
            block_idx=block_idx,
            string_idx=string_idx,
            game_profile=self.profile
        )

    def analyze_data_string(self, data_string: str, font_map: dict, threshold: int, logical_hard_limit: Optional[int] = None) -> List[Set[str]]:
        """Analyze data string using Rule Engine."""
        # Check original text for tag warnings (we fetch it if we have context indexes)
        original_text = None
        block_idx = getattr(self, '_current_scan_block_idx', None)
        string_idx = getattr(self, '_current_scan_string_idx', None)
        if self.mw and block_idx is not None and string_idx is not None:
            if (self.mw.data_store.data and
                0 <= block_idx < len(self.mw.data_store.data) and
                0 <= string_idx < len(self.mw.data_store.data[block_idx])):
                original_text = str(self.mw.data_store.data[block_idx][string_idx])

        working_text = data_string
        if self.profile.star_section_mode:
            working_text = re.sub(r'\{escape:6:000a\}', '{*}', working_text, flags=re.IGNORECASE)
            working_text = re.sub(r'\{escape:6:000b\}', '{tab}', working_text, flags=re.IGNORECASE)

        context = self.build_context(working_text, font_map, threshold, logical_hard_limit, original_text=original_text)

        import utils.utils as uu
        old_fm = uu._ACTIVE_FONT_MAP
        old_mappings = uu._ACTIVE_TAG_MAPPINGS
        old_seqs = uu._ACTIVE_ICON_SEQUENCES
        uu._ACTIVE_FONT_MAP = font_map
        uu._ACTIVE_TAG_MAPPINGS = context.default_tag_mappings
        uu._ACTIVE_ICON_SEQUENCES = context.icon_sequences
        try:
            return self.registry.detect_all(context)
        finally:
            uu._ACTIVE_FONT_MAP = old_fm
            uu._ACTIVE_TAG_MAPPINGS = old_mappings
            uu._ACTIVE_ICON_SEQUENCES = old_seqs

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
        """Analyze subline by slicing analyze_data_string output."""
        # For single subline analysis, construct context with full text if available
        full_text = full_data_string_text_for_logical_check or text
        problems_list = self.analyze_data_string(full_text, editor_font_map, editor_line_width_threshold, logical_hard_limit)

        if subline_number_in_data_string < len(problems_list):
            return problems_list[subline_number_in_data_string]
        return set()

    def check_tags_mismatch(self, original_text: str, translated_text: str) -> bool:
        """Compatibility wrapper for tag warning detection."""
        context = self.build_context(translated_text, {}, 1000, 1000, original_text=original_text)
        rule = self.registry.get_rule("TAG_WARNING")
        if rule:
            matches = rule.detect(context)
            return len(matches) > 0
        return False

    def _is_single_word_orphan_allowed(self, current_line: str, prev_line: str, font_map: dict) -> bool:
        """Orphan helper delegation."""
        context = self.build_context(current_line, font_map, 1000, 1000)
        rule = self.registry.get_rule("SINGLE_WORD_SUBLINE")
        if rule and hasattr(rule, '_is_single_word_orphan_allowed'):
            return rule._is_single_word_orphan_allowed(current_line, prev_line, context)
        return True

    def _check_short_line_zww(self, current: str, next_line: str, font_map: dict, threshold: int) -> bool:
        context = self.build_context(current + "\n" + next_line, font_map, threshold, threshold)
        rule = self.registry.get_rule("SHORT_LINE")
        if rule and hasattr(rule, '_check_short_line'):
            return rule._check_short_line(current, next_line, context)
        return False

    def _check_short_line_zbmg(self, current: str, next_line: str, font_map: dict, threshold: int) -> bool:
        working_curr = current
        working_next = next_line
        if self.profile.star_section_mode:
            working_curr = re.sub(r'\{escape:6:000a\}', '{*}', working_curr, flags=re.IGNORECASE)
            working_curr = re.sub(r'\{escape:6:000b\}', '{tab}', working_curr, flags=re.IGNORECASE)
            working_next = re.sub(r'\{escape:6:000a\}', '{*}', working_next, flags=re.IGNORECASE)
            working_next = re.sub(r'\{escape:6:000b\}', '{tab}', working_next, flags=re.IGNORECASE)
        context = self.build_context(working_curr + "\n" + working_next, font_map, threshold, threshold)
        rule = self.registry.get_rule("SHORT_LINE")
        if rule and hasattr(rule, '_check_short_line'):
            return rule._check_short_line(working_curr, working_next, context)
        return False

    def check_for_empty_first_line_of_page(self, text: str) -> List[int]:
        context = self.build_context(text, {}, 1000, 1000)
        rule = self.registry.get_rule("EMPTY_FIRST_LINE_OF_PAGE")
        if rule:
            matches = rule.detect(context)
            return [m.line_index for m in matches]
        return []

    def _check_bad_spacing(self, text: str) -> bool:
        context = self.build_context(text, {}, 1000, 1000)
        rule = self.registry.get_rule("BAD_SPACING")
        if rule and hasattr(rule, '_check_bad_spacing'):
            return rule._check_bad_spacing(text, context)
        return False

    def _check_missing_icon_spacing(self, text: str) -> bool:
        context = self.build_context(text, {}, 1000, 1000)
        rule = self.registry.get_rule("MISSING_ICON_SPACING")
        if rule:
            matches = rule.detect(context)
            return len(matches) > 0
        return False

    def _check_single_word_subline_generic(self, text: str) -> bool:
        context = self.build_context(text, {}, 1000, 1000)
        rule = self.registry.get_rule("SINGLE_WORD_SUBLINE")
        if rule and hasattr(rule, '_check_single_word_subline'):
            return rule._check_single_word_subline(text, context)
        return False

    def _is_single_word_ok_generic(self, text: str) -> bool:
        context = self.build_context(text, {}, 1000, 1000)
        rule = self.registry.get_rule("SINGLE_WORD_SUBLINE")
        if rule and hasattr(rule, '_is_single_word_ok'):
            return rule._is_single_word_ok(text, context)
        return True
