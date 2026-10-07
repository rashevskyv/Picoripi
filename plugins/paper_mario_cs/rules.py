"""Paper Mario: Color Splash (Wii U) plugin: the game's big-endian MSBT text.

``1_unpack.bat`` decompresses the game's ``X.lz`` files into ``source\\content`` (the project's Source):
``messages/EU_English/*.msbt`` (48 files: dialogue per chapter, menus, items, enemies, cards, credits),
``fonts/*.bffnt`` (Font Editor, ``font_sources.json``) and the English UI pictures
``Graphics/UI/**/*.EUR_en.bfres`` (Textures window, ``texture_sources.json``). Every MSBT is one block,
every message one string, its control tags readable (``tags.py``, names from the game's ``gojika.msbp``).
Saving writes the whole MSBT with only the edited messages re-encoded; an unedited file is written back
byte for byte. ``2_build.bat`` compresses the changed files again into a Cemu graphic pack.
"""
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple

import utils.utils as width_utils
from plugins.base_game_rules import BaseGameRules
from plugins.common.msbt import Msbt
from utils.logging_utils import log_debug, log_warning
from utils.utils import clean_spaces

from .config import PLUGIN_PREFIX, PROBLEM_DEFINITIONS
from .tag_manager import TagManager
from .tags import describe, from_editor, to_editor


class GameRules(BaseGameRules):
    """Paper Mario: Color Splash (Wii U, Europe)."""

    problem_prefix = PLUGIN_PREFIX
    problem_definitions = PROBLEM_DEFINITIONS
    tag_manager_class = TagManager
    tag_style = "curly"
    analyze_whole_string_first = True
    show_spaces_as_dots_default = True

    def __init__(self, main_window_ref=None):
        super().__init__(main_window_ref)
        self._msbt: Optional[Msbt] = None          # the file loaded or about to be saved
        self._members: Dict[int, Tuple[Optional[str], Optional[Msbt]]] = {}

    def get_display_name(self) -> str:
        return "Paper Mario: Color Splash"

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
        """An MSBT is rebuilt from the existing file (labels, styles): load the newest that parses."""
        if not str(getattr(context, "relative_path", "")).lower().endswith(".msbt"):
            self._msbt = None
            return
        for raw in context.existing_versions():
            try:
                self._msbt = Msbt(raw)
                return
            except (ValueError, IndexError) as error:
                log_warning(f"paper_mario_cs: cannot read {context.relative_path}: {error}; trying the next version")

    def reset_runtime_state(self) -> None:
        self._msbt = None
        self._members.clear()

    # -- where a string comes from -----------------------------------------------

    def _member(self, block_idx: int) -> Tuple[Optional[str], Optional[Msbt]]:
        """``(file name, parsed MSBT)`` of a block; cached until the next project load."""
        if block_idx in self._members:
            return self._members[block_idx]
        found: Tuple[Optional[str], Optional[Msbt]] = (None, None)
        try:
            pm = self.mw.project_manager
            project_idx = (getattr(self.mw, "block_to_project_file_map", None) or {}).get(block_idx, block_idx)
            source = str(pm.project.blocks[project_idx].source_file)
            if source.lower().endswith(".msbt"):
                found = (Path(source).name, Msbt(Path(pm.get_absolute_path(source)).read_bytes()))
        except (AttributeError, IndexError, KeyError, OSError, TypeError, ValueError) as error:
            log_debug(f"paper_mario_cs: no MSBT behind block {block_idx}: {error}")
        self._members[block_idx] = found
        return found

    def get_translation_context_for_string(self, block_idx: int, string_idx: int) -> Dict[str, Any]:
        """The file and the message label (``Global.msbt``, ``bero_to_stagemap``) for AI prompts."""
        name, msbt = self._member(block_idx)
        try:
            index = int(string_idx)
        except (TypeError, ValueError):
            return {}
        if msbt is None or not 0 <= index < len(msbt.messages):
            return {}
        return {"content_role": f"Message {msbt.labels.get(index, index)} in {name}"}

    # -- editor ----------------------------------------------------------------

    def get_tag_tooltip(self, tag: str) -> str:
        return describe(str(tag))

    def get_capabilities(self) -> Set[str]:
        return set()

    def calculate_string_width_override(self, text: str, font_map: dict, default_char_width: int = 8) -> Optional[int]:
        icon_sequences = getattr(self.mw, "icon_sequences", []) if self.mw else []
        return width_utils.calculate_string_width(text, font_map or {}, default_char_width=default_char_width,
                                                  icon_sequences=icon_sequences)

    def process_pasted_segment(self, segment_to_insert: str, original_text_for_tags: str,
                               editor_player_tag_const: str) -> Tuple[str, str, str]:
        return clean_spaces(segment_to_insert), "OK", ""

    def get_editor_page_size(self) -> int:
        return 1
