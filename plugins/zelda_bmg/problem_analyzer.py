"""Problem analyzer of the Twilight Princess plugin."""
from plugins.common.problem_analyzer import GenericProblemAnalyzer


class ProblemAnalyzer(GenericProblemAnalyzer):
    """Problem analyzer for Zelda BMG: curly tags, star-tag sections."""

    tag_style = "curly"
    star_section_mode = True
