"""Metroid Prime 4: Beyond plugin: the English MSBT tables unpacked from the game's Retro packages.

A project's source folder is the workspace's ``source\\`` (made by ``1_unpack.bat``, ``zt\\mp4.py``):
``text\\<table>.msbt`` (the USEN messages of one MSBT asset), ``font\\FONT_*.rfont`` and
``texture\\<package>\\<name>.txtr``. Each table is one block, each message one string; saving writes the
table back with every other section unchanged. ``2_build.bat`` puts it into the packages (USEN and EUEN).
"""
from typing import Any, Dict, List, Optional, Tuple

import utils.utils as width_utils
from plugins.base_game_rules import BaseGameRules
from plugins.common.msbt import Msbt
from utils.logging_utils import log_warning
from utils.utils import clean_spaces

from .config import DEFAULT_LINES_PER_PAGE, PLUGIN_PREFIX, PROBLEM_DEFINITIONS
from .tag_manager import TagManager
from .tags import describe, from_editor, to_editor


class GameRules(BaseGameRules):
    """Metroid Prime 4: Beyond (Switch, update 1.1.0)."""

    problem_prefix = PLUGIN_PREFIX
    problem_definitions = PROBLEM_DEFINITIONS
    tag_manager_class = TagManager
    tag_style = "curly"
    analyze_whole_string_first = True
    show_spaces_as_dots_default = True

    def __init__(self, main_window_ref=None):
        super().__init__(main_window_ref)
        self._msbt: Optional[Msbt] = None      # the file loaded or about to be saved

    def get_display_name(self) -> str:
        return "Metroid Prime 4: Beyond"

    def get_file_formats(self) -> list:
        from core.formats import DEFAULT_FORMATS, FileFormat
        return [FileFormat((".msbt",), "bytes", "MSBT"), *DEFAULT_FORMATS]

    # -- load and save ---------------------------------------------------------

    def load_data_from_json_obj(self, json_obj: Any) -> Tuple[List[List[str]], Dict[str, str]]:
        if not isinstance(json_obj, (bytes, bytearray)):
            return super().load_data_from_json_obj(json_obj)
        msbt = Msbt(json_obj)
        self._msbt = msbt
        return [[to_editor(tokens, msbt.little) for tokens in msbt.messages]], {}

    def save_data_to_json_obj(self, data: list, block_names: dict) -> Any:
        if self._msbt is None:
            return super().save_data_to_json_obj(data, block_names)
        msbt = self._msbt
        texts = data[0] if data and isinstance(data[0], list) else []
        messages = []
        for index, original in enumerate(msbt.messages):
            text = texts[index] if index < len(texts) else None
            # An untouched message keeps its exact tokens, whatever the editor form would re-encode to.
            if text is None or text == to_editor(original, msbt.little):
                messages.append(original)
            else:
                messages.append(from_editor(str(text), msbt.little))
        return msbt.build(messages)

    def prepare_save_context(self, context) -> None:
        """An MSBT is rebuilt from the existing file (labels, attributes): load the newest that parses."""
        for raw in context.existing_versions():
            try:
                self._msbt = Msbt(raw)
                return
            except (ValueError, IndexError) as error:
                log_warning(f"metroid_prime4: cannot read {context.relative_path}: {error}; trying the next version")

    def reset_runtime_state(self) -> None:
        self._msbt = None

    # -- editor ----------------------------------------------------------------

    def get_tag_tooltip(self, tag: str) -> str:
        return describe(self.replace_aliases_with_tags(str(tag)))

    def calculate_string_width_override(self, text: str, font_map: dict, default_char_width: int = 8) -> Optional[int]:
        icon_sequences = getattr(self.mw, "icon_sequences", []) if self.mw else []
        mappings = getattr(self.mw, "default_tag_mappings", None) if self.mw else None
        return width_utils.calculate_string_width(text, font_map or {}, default_char_width=default_char_width,
                                                  icon_sequences=icon_sequences, default_tag_mappings=mappings)

    def process_pasted_segment(self, segment_to_insert: str, original_text_for_tags: str,
                               editor_player_tag_const: str) -> Tuple[str, str, str]:
        return clean_spaces(segment_to_insert), "OK", ""

    def get_editor_page_size(self) -> int:
        return DEFAULT_LINES_PER_PAGE
