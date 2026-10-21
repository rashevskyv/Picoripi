"""Problem analyzer of the Symphony of the Night plugin: a prologue caption line is measured at its 12 px pitch.

The generic checks measure a line with the 8x8 font and the dialogue width, which a caption line does not use,
so a caption line gets only its own check (``CAPTION_WIDTH``). Every other line keeps the generic checks.
"""
from typing import List, Optional, Set

from plugins.common.problem_analyzer import GenericProblemAnalyzer


class ProblemAnalyzer(GenericProblemAnalyzer):
    """The generic checks for every line; a caption line gets the caption width check instead."""

    def analyze_data_string(self, data_string: str, font_map: dict, threshold: int,
                            logical_hard_limit: Optional[int] = None) -> List[Set[str]]:
        rules = getattr(self, "game_rules", None)
        block_idx, string_idx = self._current_scan_block_idx, self._current_scan_string_idx
        if rules is not None and block_idx is not None and string_idx is not None:
            too_wide = rules.caption_too_wide(block_idx, string_idx, data_string)
            if too_wide is not None:
                return [{self.problem_ids.PROBLEM_CAPTION_WIDTH}] if too_wide else [set()]
        return super().analyze_data_string(data_string, font_map, threshold, logical_hard_limit)
