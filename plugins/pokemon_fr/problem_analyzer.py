import re
from typing import Optional, Set, List
from plugins.common.problem_analyzer import GenericProblemAnalyzer

class ProblemAnalyzer(GenericProblemAnalyzer):
    """Problem analyzer implementation for Pokemon FR."""
    def __init__(self, main_window_ref, tag_manager_ref, problem_definitions_ref, problem_ids_ref):
        """Initialize a new instance."""
        super().__init__(main_window_ref, tag_manager_ref, problem_definitions_ref, problem_ids_ref)

    def analyze_data_string(self, data_string: str, font_map: dict, threshold: int, logical_hard_limit: Optional[int] = None) -> List[Set[str]]:
        """Normalize line break control tags to newlines and run analysis."""
        if not data_string:
            return []
        normalized = re.sub(r'\\n|\\p|\\l', '\n', data_string)
        return super().analyze_data_string(normalized, font_map, threshold, logical_hard_limit)