from typing import Optional, Tuple

from plugins.base_game_rules import BaseGameRules
from plugins.common.config_factory import problem_ids
import utils.utils as uu

from .config import PROBLEM_DEFINITIONS
from .tag_logic import process_segment_tags_aggressively_zww
from .tag_manager import TagManager

ProblemIDs = problem_ids(PROBLEM_DEFINITIONS, "ZWW", without=("BROKEN_ICON_HYPHEN",))


class GameRules(BaseGameRules):
    """Zelda: The Wind Waker."""

    problem_prefix = "ZWW"
    problem_definitions = PROBLEM_DEFINITIONS
    problem_ids = ProblemIDs
    tag_manager_class = TagManager
    tag_style = "square"
    analyze_whole_string_first = True
    short_problem_names = {"EMPTY_ODD_SUBLINE_DISPLAY": "EmptyOddD"}

    def get_display_name(self) -> str:
        """Get the display name."""
        return "Zelda: The Wind Waker"

    def process_pasted_segment(self, segment_to_insert: str, original_text_for_tags: str, editor_player_tag_const: str) -> Tuple[str, str, str]:
        """Process pasted segment."""
        from utils.utils import clean_spaces
        cleaned_segment = clean_spaces(segment_to_insert)
        return process_segment_tags_aggressively_zww(
            segment_to_insert=cleaned_segment,
            original_text_for_tags=original_text_for_tags,
            editor_player_tag_const=editor_player_tag_const
        )

    def calculate_string_width_override(self, text: str, font_map: dict, default_char_width: int = 6) -> Optional[int]:
        """Calculate string width override."""
        icon_sequences = getattr(self.mw, 'icon_sequences', [])
        return uu.calculate_string_width(text, font_map, default_char_width, icon_sequences=icon_sequences)

    def get_editor_page_size(self) -> int:
        """Get the editor page size."""
        return 1

    def get_external_reference_url(self, term: str) -> Optional[str]:
        """Return a Zelda Wiki search or reference URL for ``term``."""
        if not term or not term.strip():
            return None
        import urllib.parse
        return f"https://zeldawiki.wiki/wiki/Special:Search?search={urllib.parse.quote(term.strip())}"
