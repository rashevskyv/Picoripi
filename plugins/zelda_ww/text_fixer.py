from plugins.common.text_fixer import GenericTextFixer

class TextFixer(GenericTextFixer):
    """Text fixer implementation for Zelda WW."""
    def __init__(self, main_window_ref, tag_manager_ref, problem_analyzer_ref):
        """Initialize a new instance."""
        super().__init__(main_window_ref, tag_manager_ref, problem_analyzer_ref)