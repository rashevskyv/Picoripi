"""Zone of the Enders: The 2nd Runner (PlayStation 2, USA): the text of the stage scripts in STAGE.DAT.

The text is the player-visible strings of the 110 stage scripts: tutorials, mission texts, radio lines, menu and memory
card messages (``plugins.zoe2_ps2.scx``). The build writes a new disc image (``plugins.zoe2_ps2.build``): the changed
scripts are packed again into their stage in STAGE.DAT. The film and polygon-demo subtitles (MOVIE.DAT, DEMO.DAT) are not
in the project yet; see ``docs/wiki/Game_Notes.md``.
"""
from typing import Any, Dict, List, Optional, Set, Tuple

import utils.utils as width_utils
from plugins.base_game_rules import BaseGameRules
from core.i18n import tr
from utils.logging_utils import log_warning
from utils.utils import clean_spaces

from . import build, scx, unpack
from .config import PLUGIN_PREFIX, PROBLEM_DEFINITIONS
from .tag_manager import TagManager

TARGET_ID = "ps2_disc_image"


class GameRules(BaseGameRules):
    """Zone of the Enders: The 2nd Runner (PlayStation 2, USA): the text of the stage scripts."""

    problem_prefix = PLUGIN_PREFIX
    problem_definitions = PROBLEM_DEFINITIONS
    tag_manager_class = TagManager
    tag_style = "curly"
    analyze_whole_string_first = True
    show_spaces_as_dots_default = True

    def __init__(self, main_window_ref=None):
        super().__init__(main_window_ref)
        self._last_loaded: Optional[bytes] = None

    def get_display_name(self) -> str:
        return "Zone of the Enders: The 2nd Runner (PlayStation 2)"

    def get_capabilities(self) -> Set[str]:
        return set()

    def get_source_roles(self) -> List[Dict[str, str]]:
        return [{"id": "base", "label": tr("Base game")}]

    def identify_source(self, path: str) -> Optional[Dict[str, Any]]:
        return unpack.identify(path)

    def unpack_sources(self, sources: Dict[str, str], target_dir: str, progress, is_cancelled) -> Optional[str]:
        return unpack.unpack(sources, target_dir, progress, is_cancelled)

    def get_build_targets(self) -> List[Dict[str, Any]]:
        return [{"id": TARGET_ID, "label": tr("PlayStation 2: disc image (ISO)"),
                 "platforms": ["ps2"], "kind": "patch"}]

    def build_target(self, target_id: str, source_dir: str, translation_dir: str, output_dir: str,
                     progress, is_cancelled) -> str:
        if target_id != TARGET_ID:
            return super().build_target(target_id, source_dir, translation_dir, output_dir, progress, is_cancelled)
        return build.build_ps2(source_dir, translation_dir, output_dir, progress, is_cancelled)

    def get_file_formats(self) -> list:
        from core.formats import DEFAULT_FORMATS, FileFormat
        return [FileFormat((unpack.SCRIPT_SUFFIX,), "bytes", "Zone of the Enders stage scripts"), *DEFAULT_FORMATS]

    def load_data_from_json_obj(self, json_obj: Any) -> Tuple[List[List[str]], Dict[str, str]]:
        if not isinstance(json_obj, (bytes, bytearray)):
            return super().load_data_from_json_obj(json_obj)
        data = bytes(json_obj)
        self._last_loaded = data
        return [scx.read_texts(data)], {"0": "script"}

    def save_data_to_json_obj(self, data: list, block_names: dict) -> Any:
        if self._last_loaded is None:
            return super().save_data_to_json_obj(data, block_names)
        lines = list((data[0] if data else []) or [])
        new_bytes, problems = scx.write_texts(self._last_loaded, lines)
        for problem in problems:
            log_warning(f"zoe2_ps2: {problem}")
        return new_bytes

    def calculate_string_width_override(self, text: str, font_map: dict, default_char_width: int = 8) -> Optional[int]:
        icon_sequences = getattr(self.mw, "icon_sequences", []) if self.mw else []
        mappings = getattr(self.mw, "default_tag_mappings", None) if self.mw else None
        return width_utils.calculate_string_width(
            text,
            font_map or {},
            default_char_width=default_char_width,
            icon_sequences=icon_sequences,
            default_tag_mappings=mappings,
        )

    def analyze_subline(
        self,
        text: str,
        next_text: Optional[str],
        subline_number_in_data_string: int,
        qtextblock_number_in_editor: int,
        is_last_subline_in_data_string: bool,
        editor_font_map: Optional[Dict] = None,
        editor_line_width_threshold: Optional[int] = None,
        full_data_string_text_for_logical_check: Optional[str] = None,
        is_target_for_debug: bool = False,
        logical_hard_limit: Optional[int] = None,
    ) -> Set[str]:
        """The base analysis, with defaults for a caller that gives no font map, width or full text."""
        threshold = editor_line_width_threshold or getattr(self.mw, "line_width_warning_threshold_pixels", 240)
        full_text = full_data_string_text_for_logical_check if full_data_string_text_for_logical_check is not None else text
        return super().analyze_subline(
            text, next_text, subline_number_in_data_string, qtextblock_number_in_editor,
            is_last_subline_in_data_string, editor_font_map or {}, threshold, full_text,
            is_target_for_debug, logical_hard_limit=logical_hard_limit,
        )

    def process_pasted_segment(
        self,
        segment_to_insert: str,
        original_text_for_tags: str,
        editor_player_tag_const: str,
    ) -> Tuple[str, str, str]:
        return clean_spaces(segment_to_insert), "OK", ""

    def get_editor_page_size(self) -> int:
        return 4

    def get_default_script_name(self) -> Optional[str]:
        return "zoe2_ps2_script.md"
