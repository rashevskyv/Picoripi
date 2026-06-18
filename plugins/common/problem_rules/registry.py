from typing import List, Set, Dict, Any, Tuple
from .models import ProblemMatch, FixResult
from .context import RuleContext, GameProblemProfile
from .base import ProblemRule

class ProblemRuleRegistry:
    """
    Registry for managing and executing a set of ProblemRules.
    """
    def __init__(self, profile: GameProblemProfile, rules: List[ProblemRule] = None):
        self.profile = profile
        self.rules = rules or []
        self._rules_by_id = {r.id: r for r in self.rules}

    def get_rule(self, rule_id: str) -> ProblemRule:
        return self._rules_by_id.get(rule_id)

    def get_prefixed_id(self, logical_id: str) -> str:
        """
        Maps a logical ID (e.g. 'WIDTH_EXCEEDED') to the prefixed ID (e.g. 'ZWW_WIDTH_EXCEEDED').
        """
        return self.profile.problem_ids.get(logical_id, logical_id)

    def get_logical_id(self, prefixed_id: str) -> str:
        """
        Reverse map prefixed ID to logical ID.
        """
        for log_id, pref_id in self.profile.problem_ids.items():
            if pref_id == prefixed_id:
                return log_id
        return prefixed_id

    def detect_all(self, context: RuleContext) -> List[Set[str]]:
        """
        Runs all rules and returns a list of sets of prefixed problem IDs per line.
        Matches the legacy analyze_data_string API.
        """
        sublines = context.text.split('\n')
        problems_per_subline = [set() for _ in sublines]

        for rule in self.rules:
            # Check if this rule is enabled in detection settings
            prefixed_id = self.get_prefixed_id(rule.id)
            
            # Skip if not present in problem definitions
            if self.profile.problem_definitions and prefixed_id not in self.profile.problem_definitions:
                continue
            
            # If main window is present, check detection_enabled setting
            enabled = True
            if self.profile.main_window and hasattr(self.profile.main_window, 'detection_enabled'):
                enabled = self.profile.main_window.detection_enabled.get(prefixed_id, True)

            if not enabled:
                continue

            matches = rule.detect(context)
            for m in matches:
                if 0 <= m.line_index < len(problems_per_subline):
                    p_id = self.get_prefixed_id(m.problem_id)
                    problems_per_subline[m.line_index].add(p_id)

        return problems_per_subline

    def fix_all(self, context: RuleContext, allowed_problems: Set[str] = None) -> Tuple[str, bool]:
        """
        Runs rules to fix the text. Respects allowed_problems (prefixed IDs).
        If allowed_problems is None, checks main_window autofix settings.
        """
        original_text = context.text
        changed_overall = False

        # Load autofix settings if allowed_problems is not provided
        if allowed_problems is None:
            autofix_enabled = {}
            if self.profile.main_window and hasattr(self.profile.main_window, 'autofix_enabled'):
                autofix_enabled = self.profile.main_window.autofix_enabled
            
            # Helper to check if a rule is allowed to autofix
            def is_allowed(logical_id: str) -> bool:
                prefixed_id = self.get_prefixed_id(logical_id)
                if self.profile.problem_definitions and prefixed_id not in self.profile.problem_definitions:
                    return False
                if not autofix_enabled:
                    return True
                return autofix_enabled.get(prefixed_id, False)
        else:
            def is_allowed(logical_id: str) -> bool:
                prefixed_id = self.get_prefixed_id(logical_id)
                if self.profile.problem_definitions and prefixed_id not in self.profile.problem_definitions:
                    return False
                return prefixed_id in allowed_problems

        # 1. EMPTY_FIRST_LINE_OF_PAGE (if present and allowed)
        if self.get_rule("EMPTY_FIRST_LINE_OF_PAGE") and is_allowed("EMPTY_FIRST_LINE_OF_PAGE"):
            rule = self.get_rule("EMPTY_FIRST_LINE_OF_PAGE")
            matches = rule.detect(context)
            res = rule.fix(context, matches)
            if res.changed:
                context.text = res.text
                changed_overall = True

        # 2. EMPTY_ODD_SUBLINE_DISPLAY
        if self.get_rule("EMPTY_ODD_SUBLINE_DISPLAY") and is_allowed("EMPTY_ODD_SUBLINE_DISPLAY"):
            rule = self.get_rule("EMPTY_ODD_SUBLINE_DISPLAY")
            matches = rule.detect(context)
            res = rule.fix(context, matches)
            if res.changed:
                context.text = res.text
                changed_overall = True

        # 3. Iterative pass for SHORT_LINE and WIDTH_EXCEEDED (since they interact)
        max_iterations = 10
        width_rule = self.get_rule("WIDTH_EXCEEDED")
        short_line_rule = self.get_rule("SHORT_LINE")

        for _ in range(max_iterations):
            text_before = context.text
            changed_in_pass = False

            if short_line_rule and is_allowed("SHORT_LINE"):
                matches = short_line_rule.detect(context)
                res = short_line_rule.fix(context, matches)
                if res.changed:
                    context.text = res.text
                    changed_in_pass = True

            if width_rule and is_allowed("WIDTH_EXCEEDED"):
                matches = width_rule.detect(context)
                res = width_rule.fix(context, matches)
                if res.changed:
                    context.text = res.text
                    changed_in_pass = True

            if not changed_in_pass or context.text == text_before:
                break

        # 4. BAD_SPACING
        if self.get_rule("BAD_SPACING") and is_allowed("BAD_SPACING"):
            rule = self.get_rule("BAD_SPACING")
            matches = rule.detect(context)
            res = rule.fix(context, matches)
            if res.changed:
                context.text = res.text
                changed_overall = True

        # 5. MISSING_ICON_SPACING
        if self.get_rule("MISSING_ICON_SPACING") and is_allowed("MISSING_ICON_SPACING"):
            rule = self.get_rule("MISSING_ICON_SPACING")
            matches = rule.detect(context)
            res = rule.fix(context, matches)
            if res.changed:
                context.text = res.text
                changed_overall = True

        # 6. STAR_TAG_RULES (Zelda BMG specific star/tab sections formatting)
        if self.get_rule("STAR_TAG_RULES") and is_allowed("STAR_TAG_RULES"):
            rule = self.get_rule("STAR_TAG_RULES")
            matches = rule.detect(context)
            res = rule.fix(context, matches)
            if res.changed:
                context.text = res.text
                changed_overall = True

        # Note: Sentence shifting and compaction are high-level document operations 
        # and are handled outside individual line-based rules, but they are driven by context limits.
        
        # 7. SINGLE_WORD_SUBLINE (Orphan fixing)
        # Check if single word fixing is allowed
        single_word_allowed = is_allowed("SINGLE_WORD_SUBLINE") or is_allowed("SINGLE_WORD_SUBLINE_NON_START")
        if single_word_allowed and self.get_rule("SINGLE_WORD_SUBLINE"):
            rule = self.get_rule("SINGLE_WORD_SUBLINE")
            matches = rule.detect(context)
            res = rule.fix(context, matches)
            if res.changed:
                context.text = res.text
                changed_overall = True

        return context.text, context.text != original_text
