"""Shin Megami Tensei IV and IV: Apocalypse (3DS, EUR) plugin: MSG2 text tables, executable strings, BCFNT, STEX.

The project's source folder is the workspace's ``source`` folder (``1_unpack.bat``): every ``romfs/**/*.mbm``
(story events, quests, battle and demon talk, menus, names, descriptions; ``dlc/content_NN/romfs/**/*.mbm`` the
DLC text), ``exefs/code.bin`` (skill, place and menu names inside the executable; edits must fit in place),
the Shift-JIS keyed ``romfs/font/*.bcfnt`` fonts (``font_sources.json``) and the UI textures
(``texture_sources.json``). Saving writes the same files into the translation folder; ``2_build.bat`` packs them.
The text keeps the game's control codes as ``{F8xx ...}`` tags (``mbm``); Ukrainian letters take the free
Shift-JIS codes of ``core.font_formats.sjis``, which the fonts map once the letters are drawn.
"""
from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple

from plugins.base_game_rules import BaseGameRules
from utils.logging_utils import log_debug
from utils.utils import clean_spaces

from . import codebin, mbm
from .config import DEFAULT_LINES_PER_PAGE, PLUGIN_PREFIX, PROBLEM_DEFINITIONS
from .tag_manager import TAG_RE, TagManager


class GameRules(BaseGameRules):
    """Shin Megami Tensei IV / IV: Apocalypse (3DS, European English)."""

    problem_prefix = PLUGIN_PREFIX
    problem_definitions = PROBLEM_DEFINITIONS
    tag_manager_class = TagManager
    tag_style = "curly"
    analyze_whole_string_first = True
    show_spaces_as_dots_default = True

    def __init__(self, main_window_ref=None):
        super().__init__(main_window_ref)
        self._save_source: Optional[bytes] = None
        self._last_loaded: Optional[bytes] = None
        self._located: Dict[int, Optional[Tuple[str, List[int]]]] = {}

    def get_display_name(self) -> str:
        return "Shin Megami Tensei IV"

    def get_file_formats(self) -> list:
        from core.formats import DEFAULT_FORMATS, FileFormat
        return [FileFormat((".mbm",), "bytes", "MSG2 text table"),
                FileFormat((".bin",), "bytes", "3DS code.bin (strings inside the executable)"), *DEFAULT_FORMATS]

    def get_capabilities(self) -> Set[str]:
        return set()

    # -- load and save ---------------------------------------------------------

    @staticmethod
    def _parse(raw: bytes) -> List[str]:
        if raw[4:8] == b"MSG2":
            return mbm.Table(raw).texts()
        if raw[:4] == b"\x02\x00\x00\xea" or raw[:2] == b"\x00\x00" and len(raw) > 0x100000:   # ARM code
            return codebin.texts(raw)
        raise mbm.FormatError("neither an MSG2 table nor code.bin")

    @staticmethod
    def _build(raw: bytes, texts: List[str]) -> bytes:
        if raw[4:8] == b"MSG2":
            return mbm.Table(raw).build(texts)
        return codebin.build(raw, texts)

    def load_data_from_json_obj(self, json_obj: Any) -> Tuple[List[List[str]], Dict[str, str]]:
        if not isinstance(json_obj, (bytes, bytearray)):
            return super().load_data_from_json_obj(json_obj)
        self._last_loaded = bytes(json_obj)
        try:
            return [self._parse(self._last_loaded)], {}
        except (mbm.FormatError, ValueError) as error:
            log_debug(f"smt_iv: not a text file ({error})")
            return [[]], {}

    def prepare_save_context(self, context) -> None:
        versions = list(context.existing_versions())
        self._save_source = versions[-1] if versions else None

    def save_data_to_json_obj(self, data: list, block_names: dict) -> Any:
        source = self._save_source if self._save_source is not None else self._last_loaded
        if source is None:
            return super().save_data_to_json_obj(data, block_names)
        return self._build(source, [str(s) for s in (data[0] if data else [])])

    def reset_runtime_state(self) -> None:
        self._located.clear()
        self._save_source = self._last_loaded = None

    # -- context ---------------------------------------------------------------

    def _locate(self, block_idx: int) -> Optional[Tuple[str, List[int]]]:
        """``(relative path, entry ids)`` of a block."""
        if block_idx in self._located:
            return self._located[block_idx]
        found = None
        try:
            pm = getattr(self.mw, "project_manager", None) if self.mw else None
            block_map = getattr(self.mw, "block_to_project_file_map", None) or {}
            block = pm.project.blocks[block_map.get(block_idx, block_idx)]
            raw = Path(pm.get_absolute_path(block.source_file)).read_bytes()
            ids = mbm.Table(raw).ids if raw[4:8] == b"MSG2" else [at for at, _size in codebin.strings(raw)]
            found = (str(block.source_file).replace("\\", "/"), ids)
        except (AttributeError, IndexError, KeyError, OSError, TypeError, ValueError) as error:
            log_debug(f"smt_iv: no text file behind block {block_idx}: {error}")
        self._located[block_idx] = found
        return found

    def get_message_attributes(self, block_idx: int, string_idx: int) -> Optional[Dict[str, Any]]:
        found = self._locate(block_idx)
        if not found or int(string_idx) >= len(found[1]):
            return None
        return {"file": found[0], "id": found[1][int(string_idx)]}

    def get_translation_context_for_string(self, block_idx: int, string_idx: int) -> Dict[str, Any]:
        found = self._locate(block_idx)
        return mbm.roles(found[0]) if found else {}

    def get_ai_flow_group_for_string(self, block_idx: int, string_idx: int) -> Optional[str]:
        found = self._locate(block_idx)
        return found[0] if found else None

    # -- fonts -----------------------------------------------------------------

    def get_font_sources(self) -> List[Dict[str, Any]]:
        """``font_sources.json`` lists both games' fonts; only the ones the project's source folder has."""
        sources = self._plugin_json_list("font_sources.json")
        pm = getattr(self.mw, "project_manager", None) if self.mw else None
        root = (getattr(getattr(pm, "project", None), "metadata", None) or {}).get("source_path")
        if not root or not Path(root).is_dir():
            return sources
        return [s for s in sources if (Path(root) / s["path"]).is_file()] or sources

    # -- editor ----------------------------------------------------------------

    def get_spellcheck_ignore_pattern(self) -> str:
        return TAG_RE.pattern

    def process_pasted_segment(self, segment_to_insert: str, original_text_for_tags: str,
                               editor_player_tag_const: str) -> Tuple[str, str, str]:
        return clean_spaces(segment_to_insert), "OK", ""

    def get_editor_page_size(self) -> int:
        return DEFAULT_LINES_PER_PAGE

    def get_default_script_name(self) -> Optional[str]:
        return "smt_iv_script.md"
