from typing import Any, Dict, List, Optional, Tuple

from plugins.base_game_rules import BaseGameRules
from plugins.common.config_factory import problem_ids

from .config import COLOR_MARKER_DEFINITIONS, PROBLEM_DEFINITIONS
from .tag_checker_handler import TagCheckerHandler
from .tag_logic import process_segment_tags_aggressively_zmc
from .tag_manager import TagManager

ProblemIDs = problem_ids(PROBLEM_DEFINITIONS, "ZMC", without=("BROKEN_ICON_HYPHEN",))


class GameRules(BaseGameRules):
    """The Legend of Zelda: The Minish Cap."""

    problem_prefix = "ZMC"
    problem_definitions = PROBLEM_DEFINITIONS
    problem_ids = ProblemIDs
    tag_manager_class = TagManager
    color_marker_definitions = COLOR_MARKER_DEFINITIONS
    # In this game the "empty odd subline" check means an empty first line of a page.
    short_problem_names = {"EMPTY_ODD_SUBLINE_DISPLAY": "EmptyPage"}

    def save_data_to_json_obj(self, data: list, block_names: dict) -> Any:
        """Several blocks are stored as JSON; a single block as Kruptar text."""
        if data and isinstance(data[0], list) and len(data) > 1:
            return data
        return super().save_data_to_json_obj(data, block_names)

    def get_display_name(self) -> str:
        """Get the display name."""
        return "The Legend of Zelda: The Minish Cap"

    def get_default_tag_mappings(self) -> Dict[str, str]:
        """Get the default tag mappings."""
        if self.mw and hasattr(self.mw, 'default_tag_mappings'):
            mappings = dict(self.mw.default_tag_mappings)
            if hasattr(self.mw, 'EDITOR_PLAYER_TAG') and hasattr(self.mw, 'ORIGINAL_PLAYER_TAG'):
                mappings[self.mw.EDITOR_PLAYER_TAG] = self.mw.ORIGINAL_PLAYER_TAG
            return mappings
        return {}

    def get_tag_checker_handler(self) -> Optional[TagCheckerHandler]:
        """Get the tag checker handler."""
        return TagCheckerHandler(self.mw)

    def get_plugin_actions(self) -> List[Dict[str, Any]]:
        """Get the plugin actions."""
        if not self.mw or not hasattr(self.mw, 'plugin_handler'):
            return []
        return [
            {
                'name': 'check_tags_mismatch',
                'text': 'Check Tags Mismatch',
                'tooltip': 'Check for tags mismatch between original and translation',
                'shortcut': None,
                'handler': self.mw.plugin_handler.trigger_check_tags_action,
                'menu': 'Tools'
            }
        ]

    def process_pasted_segment(self,
                               segment_to_insert: str,
                               original_text_for_tags: str,
                               editor_player_tag_const: str) -> Tuple[str, str, str]:
        """Process pasted segment."""
        from utils.utils import clean_spaces
        cleaned_segment = clean_spaces(segment_to_insert)
        return process_segment_tags_aggressively_zmc(
            cleaned_segment,
            original_text_for_tags,
            editor_player_tag_const
        )

    def get_external_reference_url(self, term: str) -> Optional[str]:
        """Return a Zelda Wiki search or reference URL for ``term``."""
        if not term or not term.strip():
            return None
        import urllib.parse
        return f"https://zeldawiki.wiki/wiki/Special:Search?search={urllib.parse.quote(term.strip())}"
