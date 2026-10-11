"""Final Fantasy Explorers plugin (3DS, EUR English): the game's text tables, its fonts and its pictures.

A project's source folder is the workspace's ``source`` tree (``1_unpack.bat`` fills it; the game's own files are
named by a hash and packed with BLZ, the unpack writes them plain):

- ``romfs/message/message_en.textres`` (6,891 messages: quests, battle, items, dialogue) and
  ``romfs/message/message_home_en.textres`` (5,285 messages: the Guild and home). One block per file, one string per
  message; control characters show as ``{cNN}`` (``textres.py``). An unedited file is written back byte for byte.
- ``romfs/font/font.bcfnt`` (Japanese) and ``font_localize.bcfnt`` (Latin) -- the CFNT fonts (``font_sources.json``).
- ``romfs/ui/<hash>.darc`` (347 layout archives with BCLIM pictures), ``romfs/gfx/<hash>.cgfx`` (545 CGFX files),
  ``romfs/message/messageIcon.tpl`` (CTPK icons) -- the pictures (``texture_sources.json``).
"""
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple

from core.containers import ContainerManager
from core.containers.darc import DarcContainer
from plugins.base_game_rules import BaseGameRules
from utils.logging_utils import log_debug, log_warning
from utils.utils import clean_spaces

from . import textres
from .config import DEFAULT_LINES_PER_PAGE, PLUGIN_PREFIX, PROBLEM_DEFINITIONS
from .tag_manager import TagManager

ROLES = {"message_en": "Game text (quests, battle, items, dialogue)", "message_home_en": "Guild and home text"}


class GameRules(BaseGameRules):
    """Final Fantasy Explorers (Nintendo 3DS, European English)."""

    problem_prefix = PLUGIN_PREFIX
    problem_definitions = PROBLEM_DEFINITIONS
    tag_manager_class = TagManager
    tag_style = "curly"
    analyze_whole_string_first = True
    show_spaces_as_dots_default = True

    def __init__(self, main_window_ref=None):
        super().__init__(main_window_ref)
        ContainerManager.register(DarcContainer)        # ui/*.darc: the layout pictures (Textures window)
        self._file: Optional[textres.TextRes] = None
        self._members: Dict[int, Tuple[Optional[str], Optional[textres.TextRes]]] = {}

    def get_display_name(self) -> str:
        return "Final Fantasy Explorers"

    def get_file_formats(self) -> list:
        from core.formats import DEFAULT_FORMATS, FileFormat
        return [FileFormat((".textres",), "bytes", "Explorers text table"), *DEFAULT_FORMATS]

    def get_capabilities(self) -> Set[str]:
        return set()

    # -- load and save ---------------------------------------------------------

    def load_data_from_json_obj(self, json_obj: Any) -> Tuple[List[List[str]], Dict[str, str]]:
        if not isinstance(json_obj, (bytes, bytearray)):
            self._file = None
            return super().load_data_from_json_obj(json_obj)
        self._file = textres.TextRes(json_obj)
        return [[textres.to_editor(text) for text in self._file.texts]], {}

    def prepare_save_context(self, context) -> None:
        """A file is rebuilt from the newest version that parses (ids and the tail stay as they were)."""
        self._file = None
        if not str(getattr(context, "relative_path", "")).lower().endswith(".textres"):
            return
        for raw in context.existing_versions():
            try:
                self._file = textres.TextRes(raw)
                return
            except (ValueError, IndexError) as error:
                log_warning(f"final_fantasy_explorers: cannot read {context.relative_path}: {error}; trying the next version")

    def save_data_to_json_obj(self, data: list, block_names: dict) -> Any:
        if self._file is None:
            return super().save_data_to_json_obj(data, block_names)
        shown = data[0] if data and isinstance(data[0], list) else []
        texts = []
        for index, original in enumerate(self._file.texts):
            text = shown[index] if index < len(shown) else None
            if text is None or str(text) == textres.to_editor(original):
                texts.append(original)
            else:
                texts.append(textres.from_editor(str(text)))
        return self._file.build(texts)

    def reset_runtime_state(self) -> None:
        self._file = None
        self._members.clear()

    # -- where a string comes from -----------------------------------------------

    def _member(self, block_idx: int) -> Tuple[Optional[str], Optional[textres.TextRes]]:
        if block_idx in self._members:
            return self._members[block_idx]
        found: Tuple[Optional[str], Optional[textres.TextRes]] = (None, None)
        try:
            pm = self.mw.project_manager
            project_idx = (getattr(self.mw, "block_to_project_file_map", None) or {}).get(block_idx, block_idx)
            source = str(pm.project.blocks[project_idx].source_file)
            if source.lower().endswith(".textres"):
                found = (Path(source).as_posix(), textres.TextRes(Path(pm.get_absolute_path(source)).read_bytes()))
        except (AttributeError, IndexError, KeyError, OSError, TypeError, ValueError) as error:
            log_debug(f"final_fantasy_explorers: no text table behind block {block_idx}: {error}")
        self._members[block_idx] = found
        return found

    def _message(self, block_idx: int, string_idx: int) -> Optional[Dict[str, Any]]:
        rel_path, parsed = self._member(block_idx)
        try:
            index = int(string_idx)
        except (TypeError, ValueError):
            return None
        if parsed is None or not 0 <= index < len(parsed.ids):
            return None
        stem = Path(rel_path).stem
        return {"path": rel_path, "file": Path(rel_path).name, "id": f"{parsed.ids[index]:08X}",
                "role": ROLES.get(stem, "Game text")}

    def get_translation_context_for_string(self, block_idx: int, string_idx: int) -> Dict[str, Any]:
        found = self._message(block_idx, string_idx)
        if not found:
            return {}
        return {"content_role": f"{found['role']} ({found['file']})", "has_speaker": False}

    def get_scene_context_for_string(self, block_idx: int, string_idx: int) -> Dict[str, Any]:
        found = self._message(block_idx, string_idx)
        if not found:
            return {}
        return {"resource": found["path"], "label": found["id"]}

    def get_ai_flow_context_for_string(self, block_idx: int, string_idx: int) -> Optional[str]:
        found = self._message(block_idx, string_idx)
        return f"Message {found['id']} in {found['file']}" if found else None

    # -- editor ----------------------------------------------------------------

    def get_tag_tooltip(self, tag: str) -> str:
        code = str(tag).strip("{}")[1:]
        meaning = {"01": "colour or style on", "05": "colour or style off", "07": "name supplied by the game",
                   "0B": "number supplied by the game", "0C": "number supplied by the game", "10": "wait for a button"}
        return f"Control character 0x{code}: {meaning.get(code, 'a game command')}"

    def process_pasted_segment(self, segment_to_insert: str, original_text_for_tags: str,
                               editor_player_tag_const: str) -> Tuple[str, str, str]:
        return clean_spaces(segment_to_insert), "OK", ""

    def get_editor_page_size(self) -> int:
        return DEFAULT_LINES_PER_PAGE
