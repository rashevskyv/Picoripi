"""Guardian Heroes problem rule: a line longer than the game's own translations ever use (advisory, no fix)."""
import re
from typing import List

from plugins.common.problem_analyzer import GenericProblemAnalyzer
from plugins.common.problem_rules.base import ProblemRule
from plugins.common.problem_rules.context import RuleContext
from plugins.common.problem_rules.models import FixResult, ProblemMatch

LINE_LIMIT = 34
BATTLE_QUOTE_LIMIT = 50   # strings that open with {E200:...} (the winner quotes of a battle) use a wider window
_TAG = re.compile(r"\{[0-9A-Fa-f:]{4,9}\}")


def long_lines(text: str) -> List[int]:
    """Indexes of the lines that have more visible characters than the limit of this string's kind."""
    limit = BATTLE_QUOTE_LIMIT if text.startswith("{E200") else LINE_LIMIT
    return [index for index, line in enumerate(text.split("\n")) if len(_TAG.sub("", line)) > limit]


class LineLongRule(ProblemRule):
    """Reports ``GHR_LINE_LONG`` for each line over the limit."""

    @property
    def id(self) -> str:
        return "LINE_LONG"

    def detect(self, context: RuleContext) -> List[ProblemMatch]:
        return [ProblemMatch(problem_id=self.id, line_index=index) for index in long_lines(str(context.text or ""))]

    def fix(self, context: RuleContext, matches: List[ProblemMatch]) -> FixResult:
        return FixResult(text=context.text, changed=False)


class ProblemAnalyzer(GenericProblemAnalyzer):
    """The shared rules plus the line-length rule."""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        rule = LineLongRule()
        self.registry.rules.append(rule)
        self.registry._rules_by_id[rule.id] = rule
