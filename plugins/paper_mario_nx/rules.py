"""Paper Mario: The Thousand-Year Door (Switch, 2024) plugin: the game's MSBT text, fonts and UI textures.

``1_unpack.bat`` of the workspace (``_shared/scripts/zt/ttydnx.py``) fills the source folder:
``msg/EU_English/*.msbt`` (all text: 46 files, ~14,900 messages, little-endian UTF-16 MSBT v3), the fonts
without their zstd wrapper (``font/*.bffnt``, ``font/YoshiFont_*.bfotf``) and the BNTX textures of the UI
(``ui/<folder>/<name>.bfres.bntx`` taken out of each ``.bfres.zst``, ``ui/<folder>/<name>.bntx``). A project
opens every MSBT as one block; saving re-encodes only the edited messages, so an unedited file is written back
byte for byte. ``2_build.bat`` compresses fonts and textures again and puts them back into the LayeredFS mod.

Tags are named from the game's own ``msg.msbp`` (``tags.py``).
"""
from typing import Any, Dict, List, Optional, Tuple

from plugins.base_game_rules import BaseGameRules
from plugins.common.msbt import Msbt
from utils.logging_utils import log_warning
from utils.utils import clean_spaces

from .config import DEFAULT_LINES_PER_PAGE, PLUGIN_PREFIX, PROBLEM_DEFINITIONS
from .tag_manager import TagManager
from .tags import describe, from_editor, to_editor


class GameRules(BaseGameRules):
    """Paper Mario: The Thousand-Year Door (Nintendo Switch)."""

    problem_prefix = PLUGIN_PREFIX
    problem_definitions = PROBLEM_DEFINITIONS
    tag_manager_class = TagManager
    tag_style = "curly"
    analyze_whole_string_first = True
    show_spaces_as_dots_default = True

    def __init__(self, main_window_ref=None):
        super().__init__(main_window_ref)
        self._msbt: Optional[Msbt] = None          # the file loaded or about to be saved

    def get_display_name(self) -> str:
        return "Paper Mario: The Thousand-Year Door (Switch)"

    def get_file_formats(self) -> list:
        from core.formats import DEFAULT_FORMATS, FileFormat
        return [FileFormat((".msbt",), "bytes", "MSBT"), *DEFAULT_FORMATS]

    # -- load and save ---------------------------------------------------------

    def load_data_from_json_obj(self, json_obj: Any) -> Tuple[List[List[str]], Dict[str, str]]:
        if not isinstance(json_obj, (bytes, bytearray)):
            self._msbt = None
            return super().load_data_from_json_obj(json_obj)
        msbt = Msbt(json_obj)
        self._msbt = msbt
        return [[to_editor(tokens, msbt.little) for tokens in msbt.messages]], {}

    def save_data_to_json_obj(self, data: list, block_names: dict) -> Any:
        if self._msbt is None:
            return super().save_data_to_json_obj(data, block_names)
        msbt = self._msbt
        texts = data[0] if data and isinstance(data[0], list) else []
        rebuilt = []
        for index, original in enumerate(msbt.messages):
            text = texts[index] if index < len(texts) else None
            # An untouched message keeps its exact tokens, whatever the editor form would re-encode to.
            if text is None or text == to_editor(original, msbt.little):
                rebuilt.append(original)
            else:
                rebuilt.append(from_editor(str(text), msbt.little))
        return msbt.build(rebuilt)

    def prepare_save_context(self, context) -> None:
        """An MSBT is rebuilt from the existing file (labels, attributes): load the newest that parses."""
        if not str(getattr(context, "relative_path", "")).lower().endswith(".msbt"):
            self._msbt = None
            return
        for raw in context.existing_versions():
            try:
                self._msbt = Msbt(raw)
                return
            except (ValueError, IndexError) as error:
                log_warning(f"paper_mario_nx: cannot read {context.relative_path}: {error}; trying the next version")

    def reset_runtime_state(self) -> None:
        self._msbt = None

    # -- editor ----------------------------------------------------------------

    def get_tag_tooltip(self, tag: str) -> str:
        return describe(self.replace_aliases_with_tags(str(tag)))

    def process_pasted_segment(self, segment_to_insert: str, original_text_for_tags: str,
                               editor_player_tag_const: str) -> Tuple[str, str, str]:
        return clean_spaces(segment_to_insert), "OK", ""

    def get_editor_page_size(self) -> int:
        return DEFAULT_LINES_PER_PAGE
