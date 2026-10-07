"""Metroid Prime Trilogy plugin: the STRG string tables of Prime 1, 2, 3 and the Trilogy menu.

A project's source folder is the workspace's ``source\\`` (made by ``1_unpack.bat``, ``zt\\mpt.py``):
``<game>\\text\\<package>\\<name>.<id>.strg`` (game: MP1, MP2, MP3, Menu; each table once per game, in the first
package that has it), ``<game>\\font\\<name>.<id>.font`` (FONT + its texture, Font Editor format
``retro_font_gx``) and ``<game>\\texture\\<package>\\<name>.<id>.txtr`` (Textures window format ``txtr_gx``).

Each table is one block, its English strings the strings; ``&tags;`` show as ``{tags}``. Saving writes the
table with the edited text as every language (``strg.Strg.build``); an unedited table keeps its bytes.
``2_build.bat`` puts the files back into every package of that game that holds them.

Prime 1 text here is the Trilogy version of Metroid Prime; a Metroid Prime Remastered plugin can take its
translation over by the English strings (the same text in most tables).
"""
from typing import Any, Dict, List, Optional, Tuple

from plugins.base_game_rules import BaseGameRules
from utils.logging_utils import log_warning
from utils.utils import clean_spaces

from .config import DEFAULT_LINES_PER_PAGE, PLUGIN_PREFIX, PROBLEM_DEFINITIONS
from .strg import Strg
from .tag_manager import TagManager
from .tags import describe, from_editor, to_editor


class GameRules(BaseGameRules):
    """Metroid Prime Trilogy (Wii, USA R3ME01)."""

    problem_prefix = PLUGIN_PREFIX
    problem_definitions = PROBLEM_DEFINITIONS
    tag_manager_class = TagManager
    tag_style = "curly"
    analyze_whole_string_first = True
    show_spaces_as_dots_default = True

    def __init__(self, main_window_ref=None):
        super().__init__(main_window_ref)
        self._strg: Optional[Strg] = None      # the table loaded or about to be saved

    def get_display_name(self) -> str:
        return "Metroid Prime Trilogy"

    def get_file_formats(self) -> list:
        from core.formats import DEFAULT_FORMATS, FileFormat
        return [FileFormat((".strg",), "bytes", "STRG"), *DEFAULT_FORMATS]

    # -- load and save ---------------------------------------------------------

    def load_data_from_json_obj(self, json_obj: Any) -> Tuple[List[List[str]], Dict[str, str]]:
        if not isinstance(json_obj, (bytes, bytearray)):
            return super().load_data_from_json_obj(json_obj)
        self._strg = Strg(json_obj)
        return [[to_editor(text) for text in self._strg.english]], {}

    def save_data_to_json_obj(self, data: list, block_names: dict) -> Any:
        if self._strg is None:
            return super().save_data_to_json_obj(data, block_names)
        strg = self._strg
        texts = data[0] if data and isinstance(data[0], list) else []
        english = strg.english
        out = [from_editor(str(texts[i])) if i < len(texts) and texts[i] is not None else english[i]
               for i in range(strg.count)]
        return strg.build(out)

    def prepare_save_context(self, context) -> None:
        """A table is rebuilt from the existing file (languages, names): load the newest that parses."""
        for raw in context.existing_versions():
            try:
                self._strg = Strg(raw)
                return
            except (ValueError, IndexError) as error:
                log_warning(f"metroid_prime_trilogy: cannot read {context.relative_path}: {error}; trying the next version")

    def reset_runtime_state(self) -> None:
        self._strg = None

    # -- editor ----------------------------------------------------------------

    def get_tag_tooltip(self, tag: str) -> str:
        return describe(self.replace_aliases_with_tags(str(tag)))

    def process_pasted_segment(self, segment_to_insert: str, original_text_for_tags: str,
                               editor_player_tag_const: str) -> Tuple[str, str, str]:
        return clean_spaces(segment_to_insert), "OK", ""

    def get_editor_page_size(self) -> int:
        return DEFAULT_LINES_PER_PAGE
