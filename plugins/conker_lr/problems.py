"""Conker: Live & Reloaded problem rules: a line that is longer than the game's buffers or bubble holds.

All three are informational: the game scrolls a long bubble and the buffers are large, so no fix is offered and the
build is not blocked. See ``bubble.py`` for the limits and the wrap rule.
"""
from typing import List

from plugins.common.problem_analyzer import GenericProblemAnalyzer
from plugins.common.problem_rules.base import ProblemRule
from plugins.common.problem_rules.context import RuleContext
from plugins.common.problem_rules.models import FixResult, ProblemMatch

from . import bubble


class TextLimitRule(ProblemRule):
    """Reports ``problem_id`` when the line breaks the limit that ``bubble.problems`` names for it."""

    def __init__(self, problem_id: str):
        self._id = problem_id

    @property
    def id(self) -> str:
        return self._id

    def detect(self, context: RuleContext) -> List[ProblemMatch]:
        if self._id not in bubble.problems(str(context.text or "")):
            return []
        return [ProblemMatch(problem_id=self._id, line_index=0)]

    def fix(self, context: RuleContext, matches: List[ProblemMatch]) -> FixResult:
        return FixResult(text=context.text, changed=False)


class ProblemAnalyzer(GenericProblemAnalyzer):
    """The shared rules plus the three length rules."""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for problem_id in ("STRING_LIMIT", "LINE_LIMIT", "BUBBLE_LINES"):
            rule = TextLimitRule(problem_id)
            self.registry.rules.append(rule)
            self.registry._rules_by_id[rule.id] = rule
