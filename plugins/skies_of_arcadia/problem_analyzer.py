"""Problem analyzer of the Skies of Arcadia Legends plugin: a fixed-size script's text over its byte budget is flagged."""
from typing import List, Optional, Set

from plugins.common.problem_analyzer import GenericProblemAnalyzer


class ProblemAnalyzer(GenericProblemAnalyzer):
    """The generic checks, plus the byte budget of a string in a script that cannot grow."""

    def analyze_data_string(self, data_string: str, font_map: dict, threshold: int,
                            logical_hard_limit: Optional[int] = None) -> List[Set[str]]:
        result = super().analyze_data_string(data_string, font_map, threshold, logical_hard_limit)
        if self._over_byte_budget(data_string):
            if not result:
                result = [set()]
            result[0].add(self.problem_ids.PROBLEM_BYTE_BUDGET)
        return result

    def _over_byte_budget(self, data_string: str) -> bool:
        rules = getattr(self, "game_rules", None)
        block_idx, string_idx = self._current_scan_block_idx, self._current_scan_string_idx
        if rules is None or block_idx is None or string_idx is None:
            return False
        return rules.exceeds_byte_budget(block_idx, string_idx, data_string)
