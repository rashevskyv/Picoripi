from plugins.common.problem_analyzer import GenericProblemAnalyzer
from utils.utils import calculate_string_width

class ProblemAnalyzer(GenericProblemAnalyzer):
    """Problem analyzer implementation for Zelda WW."""
    def __init__(self, main_window_ref, tag_manager_ref, problem_definitions_ref, problem_ids_ref):
        """Initialize a new instance."""
        super().__init__(main_window_ref, tag_manager_ref, problem_definitions_ref, problem_ids_ref)