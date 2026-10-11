"""Dragon Ball Fusions plugin (3DS, EUR; Arc System Works engine): the message file, the bitmap fonts and the
pictures.

A project's source folder is the workspace's ``source`` tree (``1_unpack.bat`` fills it); the game keeps its files
in the CRI archive ``romfs/DOF.cpk`` and in ``.jarc`` archives inside it, which the unpack writes as folders:

- ``romfs/DOF.cpk/message/msg_en.jmsg`` -- all the English text: 18,683 UTF-16 strings keyed by hash (``jmsg``);
  the French, German, Spanish and Italian files are not opened.
- ``romfs/DOF.cpk/pac/system.jarc/ui/common/en/*.jfnt`` (and ``ui/photo`` in ``photofusion.jarc``) -- the bitmap
  fonts (``font_sources.json``, format ``jfnt``); ``default01.jfnt``, the main font, is a packed outline font that is
  not opened.
- every ``.jtex`` (``jimg``, ``texture_sources.json``): loose in the CPK and inside the ``.jarc`` archives.
"""
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple

from plugins.base_game_rules import BaseGameRules
from utils.logging_utils import log_debug
from utils.utils import clean_spaces

from . import jmsg
from .config import DEFAULT_LINES_PER_PAGE, PLUGIN_PREFIX, PROBLEM_DEFINITIONS
from .tag_manager import TagManager


class GameRules(BaseGameRules):
    """Dragon Ball Fusions (Nintendo 3DS, European English)."""

    problem_prefix = PLUGIN_PREFIX
    problem_definitions = PROBLEM_DEFINITIONS
    tag_manager_class = TagManager
    analyze_whole_string_first = True
    show_spaces_as_dots_default = True

    def __init__(self, main_window_ref=None):
        super().__init__(main_window_ref)
        self._save_source: Optional[bytes] = None
        self._last_loaded: Optional[bytes] = None
        self._keys: Dict[int, Tuple[Optional[str], List[int]]] = {}

    def get_display_name(self) -> str:
        return "Dragon Ball Fusions"

    def get_file_formats(self) -> list:
        from core.formats import DEFAULT_FORMATS, FileFormat
        return [FileFormat((".jmsg",), "bytes", "Arc System Works message file"), *DEFAULT_FORMATS]

    def get_capabilities(self) -> Set[str]:
        return set()

    # -- load and save ---------------------------------------------------------

    def load_data_from_json_obj(self, json_obj: Any) -> Tuple[List[List[str]], Dict[str, str]]:
        if not isinstance(json_obj, (bytes, bytearray)):
            return super().load_data_from_json_obj(json_obj)
        self._last_loaded = bytes(json_obj)
        try:
            return [list(jmsg.Jmsg(self._last_loaded).texts)], {}
        except jmsg.FormatError as error:
            log_debug(f"dragon_ball_fusions: not a message file ({error})")
            return [[]], {}

    def prepare_save_context(self, context) -> None:
        versions = list(context.existing_versions())
        self._save_source = versions[-1] if versions else None

    def save_data_to_json_obj(self, data: list, block_names: dict) -> Any:
        source = self._save_source if self._save_source is not None else self._last_loaded
        if source is None:
            return super().save_data_to_json_obj(data, block_names)
        return jmsg.Jmsg(source).build([str(s) for s in (data[0] if data else [])])

    def reset_runtime_state(self) -> None:
        self._keys.clear()
        self._save_source = self._last_loaded = None

    # -- where a string comes from -----------------------------------------------

    def _located(self, block_idx: int) -> Tuple[Optional[str], List[int]]:
        if block_idx in self._keys:
            return self._keys[block_idx]
        found: Tuple[Optional[str], List[int]] = (None, [])
        try:
            pm = self.mw.project_manager
            block_map = getattr(self.mw, "block_to_project_file_map", None) or {}
            block = pm.project.blocks[block_map.get(block_idx, block_idx)]
            raw = Path(pm.get_absolute_path(block.source_file)).read_bytes()
            found = (str(block.source_file).replace("\\", "/"), jmsg.Jmsg(raw).keys)
        except (AttributeError, IndexError, KeyError, OSError, TypeError, ValueError) as error:
            log_debug(f"dragon_ball_fusions: no message file behind block {block_idx}: {error}")
        self._keys[block_idx] = found
        return found

    def get_message_attributes(self, block_idx: int, string_idx: int) -> Optional[Dict[str, Any]]:
        path, keys = self._located(block_idx)
        try:
            return {"file": path, "key": f"{keys[int(string_idx)]:08X}"}
        except (IndexError, ValueError, TypeError):
            return None

    # -- editor ----------------------------------------------------------------

    def process_pasted_segment(self, segment_to_insert: str, original_text_for_tags: str,
                               editor_player_tag_const: str) -> Tuple[str, str, str]:
        return clean_spaces(segment_to_insert), "OK", ""

    def get_editor_page_size(self) -> int:
        return DEFAULT_LINES_PER_PAGE
