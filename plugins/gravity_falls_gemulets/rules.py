"""Gravity Falls: Legend of the Gnome Gemulets plugin (3DS, EUR; UbiArt Framework): the localisation file, the
bitmap fonts and the pictures.

A project's source folder is the workspace's ``source`` tree (``1_unpack.bat`` fills it):

- ``romfs/enginedata/localisation/localisation.loc8`` -- all the game's text: one section per language
  (English, French, Japanese, German, Spanish, Italian), each 373 menu and system strings and 1,169 dialogue,
  quest and animation-name records. Each language is one block (``loc8``); the English section is the one the
  English game shows. Colours and sizes are ``[C:RRGGBB]...[C:]`` and ``[s:1.5]...[s:]`` tags.
- ``romfs/<bundle>.ipk/.../fonts/mylifecoach6x.tfn.ckd`` (glyph table) with the ``.tga.ckd`` atlas next to it
  (``font_sources.json``, format ``ubiart_tfn``) and ``tahoma.bcfnt``; the pictures (``.tga.ckd`` / ``.png.ckd``,
  format ``ubiart_tex``, ``texture_sources.json``) of the ``.ipk`` bundles, written as folders of members.
"""
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple

from plugins.base_game_rules import BaseGameRules
from utils.logging_utils import log_debug
from utils.utils import clean_spaces

from . import loc8
from .config import DEFAULT_LINES_PER_PAGE, PLUGIN_PREFIX, PROBLEM_DEFINITIONS
from .tag_manager import TAG_RE, TagManager


class GameRules(BaseGameRules):
    """Gravity Falls: Legend of the Gnome Gemulets (Nintendo 3DS, European English)."""

    problem_prefix = PLUGIN_PREFIX
    problem_definitions = PROBLEM_DEFINITIONS
    tag_manager_class = TagManager
    tag_style = "square"
    analyze_whole_string_first = True
    show_spaces_as_dots_default = True

    def __init__(self, main_window_ref=None):
        super().__init__(main_window_ref)
        self._save_source: Optional[bytes] = None
        self._last_loaded: Optional[bytes] = None
        self._parsed: Dict[int, Tuple[Optional[str], Optional[loc8.Loc8], int]] = {}

    def get_display_name(self) -> str:
        return "Gravity Falls: Legend of the Gnome Gemulets"

    def get_file_formats(self) -> list:
        from core.formats import DEFAULT_FORMATS, FileFormat
        return [FileFormat((".loc8",), "bytes", "UbiArt localisation file"), *DEFAULT_FORMATS]

    def get_capabilities(self) -> Set[str]:
        return set()

    # -- load and save ---------------------------------------------------------

    def load_data_from_json_obj(self, json_obj: Any) -> Tuple[List[List[str]], Dict[str, str]]:
        if not isinstance(json_obj, (bytes, bytearray)):
            return super().load_data_from_json_obj(json_obj)
        self._last_loaded = bytes(json_obj)
        try:
            file = loc8.Loc8(self._last_loaded)
        except loc8.FormatError as error:
            log_debug(f"gravity_falls_gemulets: not a localisation file ({error})")
            return [[]], {}
        blocks = file.texts()
        return blocks, {str(i): section.name for i, section in enumerate(file.sections)}

    def prepare_save_context(self, context) -> None:
        versions = list(context.existing_versions())
        self._save_source = versions[-1] if versions else None

    def save_data_to_json_obj(self, data: list, block_names: dict) -> Any:
        source = self._save_source if self._save_source is not None else self._last_loaded
        if source is None:
            return super().save_data_to_json_obj(data, block_names)
        file = loc8.Loc8(source)
        return file.build([[str(s) for s in block] for block in data])

    def reset_runtime_state(self) -> None:
        self._parsed.clear()
        self._save_source = self._last_loaded = None

    # -- where a string comes from -----------------------------------------------

    def _file(self, block_idx: int) -> Tuple[Optional[str], Optional[loc8.Loc8], int]:
        """``(relative path, parsed file, language section number)`` behind a data block."""
        if block_idx in self._parsed:
            return self._parsed[block_idx]
        found: Tuple[Optional[str], Optional[loc8.Loc8], int] = (None, None, 0)
        try:
            pm = self.mw.project_manager
            block_map = getattr(self.mw, "block_to_project_file_map", None) or {}
            project_idx = block_map.get(block_idx, block_idx)
            first = min((k for k, v in block_map.items() if v == project_idx), default=block_idx)
            block = pm.project.blocks[project_idx]
            found = (str(block.source_file).replace("\\", "/"),
                     loc8.Loc8(Path(pm.get_absolute_path(block.source_file)).read_bytes()), int(block_idx) - first)
        except (AttributeError, IndexError, KeyError, OSError, TypeError, ValueError) as error:
            log_debug(f"gravity_falls_gemulets: no localisation file behind block {block_idx}: {error}")
        self._parsed[block_idx] = found
        return found

    def get_message_attributes(self, block_idx: int, string_idx: int) -> Optional[Dict[str, Any]]:
        path, file, section_no = self._file(block_idx)
        if file is None:
            return None
        try:
            section = file.sections[section_no]
            ident = section.ids()[int(string_idx)]
        except (IndexError, ValueError, TypeError):
            return None
        return {"file": path, "language": section.name, "id": ident}

    def get_ai_flow_group_for_string(self, block_idx: int, string_idx: int) -> Optional[str]:
        return "localisation"

    # -- editor ----------------------------------------------------------------

    def get_spellcheck_ignore_pattern(self) -> str:
        return TAG_RE.pattern

    def process_pasted_segment(self, segment_to_insert: str, original_text_for_tags: str,
                               editor_player_tag_const: str) -> Tuple[str, str, str]:
        return clean_spaces(segment_to_insert), "OK", ""

    def get_editor_page_size(self) -> int:
        return DEFAULT_LINES_PER_PAGE
