"""Problem analyzer of the Pokemon FireRed plugin."""
import re
from typing import Optional, Set, List
from plugins.common.problem_analyzer import GenericProblemAnalyzer

class ProblemAnalyzer(GenericProblemAnalyzer):
    """Problem analyzer implementation for Pokemon FR."""

    escaped_line_breaks = True

    def analyze_data_string(self, data_string: str, font_map: dict, threshold: int, logical_hard_limit: Optional[int] = None) -> List[Set[str]]:
        """Normalize line break control tags to newlines and run analysis; a fixed name field over its budget is flagged."""
        if not data_string:
            return []
        normalized = re.sub(r'\\n|\\p|\\l', '\n', data_string)
        result = super().analyze_data_string(normalized, font_map, threshold, logical_hard_limit)
        if self._over_byte_budget(data_string):
            if not result:
                result = [set()]
            result[0].add(self.problem_ids.PROBLEM_BYTE_BUDGET)
        return result

    def _over_byte_budget(self, data_string: str) -> bool:
        """The game rules know which string is checked (the scan context); a message has no budget."""
        rules = getattr(self, "game_rules", None)
        block_idx, string_idx = self._current_scan_block_idx, self._current_scan_string_idx
        if rules is None or block_idx is None or string_idx is None:
            return False
        return rules.exceeds_byte_budget(block_idx, string_idx, data_string)