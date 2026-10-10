"""Animal Crossing 3DS problem rules on top of the shared ones: answers of a question that differ in number from the
original (the game shows one answer per line, so a joined or split answer breaks the menu), and a page with more
lines than a fixed-row window holds (letters and the bulletin board have 6 rows; the dialogue box goes on by itself
every 3 lines, so it is not checked)."""
from typing import List

from plugins.common.problem_analyzer import GenericProblemAnalyzer
from plugins.common.problem_rules.base import ProblemRule
from plugins.common.problem_rules.context import RuleContext
from plugins.common.problem_rules.models import FixResult, ProblemMatch

from . import fit


class ChoiceAnswersRule(ProblemRule):
    @property
    def id(self) -> str:
        return "CHOICE_ANSWERS"

    def detect(self, context: RuleContext) -> List[ProblemMatch]:
        if context.original_text is None:
            return []
        body, answers = fit.split_choice(context.text)
        _, original = fit.split_choice(str(context.original_text))
        if len(answers) == len(original):
            return []
        return [ProblemMatch(problem_id=self.id, line_index=body.count("\n") + (1 if answers else 0))]

    def fix(self, context: RuleContext, matches: List[ProblemMatch]) -> FixResult:
        return FixResult(text=context.text, changed=False)


class PageLinesRule(ProblemRule):
    @property
    def id(self) -> str:
        return "PAGE_LINES"

    def detect(self, context: RuleContext) -> List[ProblemMatch]:
        main_window = getattr(context.game_profile, "main_window", None)
        rules = getattr(main_window, "current_game_rules", None)
        block = context.block_idx if context.block_idx is not None else \
            getattr(getattr(main_window, "data_store", None), "physical_block_idx", None)    # the string being edited
        spec = rules.window_spec(block) if hasattr(rules, "window_spec") else {}
        limit = spec.get("lines_per_page")
        if not limit or spec.get("auto_pages"):     # the dialogue box goes on by itself every 3 lines
            return []
        body, _answers = fit.split_choice(context.text)
        matches, line = [], 0
        for page in fit.pages(body):
            for index in range(len(page)):
                if index >= limit:
                    matches.append(ProblemMatch(problem_id=self.id, line_index=line + index))
            line += len(page) - 1
        return matches

    def fix(self, context: RuleContext, matches: List[ProblemMatch]) -> FixResult:
        return FixResult(text=context.text, changed=False)


class ProblemAnalyzer(GenericProblemAnalyzer):
    """The shared rules plus the two above."""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for rule in (ChoiceAnswersRule(), PageLinesRule()):
            self.registry.rules.append(rule)
            self.registry._rules_by_id[rule.id] = rule
