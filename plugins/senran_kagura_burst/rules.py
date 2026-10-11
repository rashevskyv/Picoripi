"""Senran Kagura Burst plugin (3DS, European English): the story and conversation texts, the text compiled into the
executable, the game's fonts and its pictures.

A project's source folder is the workspace's ``source`` tree (``1_unpack.bat`` fills it); the game's files are loose
in the RomFS, so a mod replaces whole files:

- ``romfs/scenario/{hanzo,hebijo}/*.bin`` -- 432 ``TAMS`` message files (3,759 messages): the two schools' story
  chapters (``text_novel_*``, ``kaeruB_*``) and the conversations in the hub and in missions (``text_int_*``).
  The texts may be of any length (``tams``). ``{v02001}`` is a voice line, ``{cff0000ff}`` ... ``{r}`` a colour,
  ``{b008}`` and ``{s022}`` are the engine's background and sound cues; keep them.
- ``exefs/code.bin`` -- the menu, mission, item and battle texts compiled into the executable (2,629 strings, 200
  to a block; ``pool``). They are written in place and may not be longer than the original.
- ``romfs/font/*.bcfna`` (``font_sources.json``, format ``cfna``) -- the game's archived fonts.
- ``romfs/ui/lyt_*.bin`` (``texture_sources.json``, ``binpack``: a pack of ``darc`` layout archives, often
  compressed) -- 788 distinct BCLIM pictures with the English menu, HUD and tutorial text; ``romfs/gm`` and
  ``romfs/logo`` hold CTPK pictures. A changed pack is compressed again when it was.
"""
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple

from core.containers import ContainerManager
from core.containers.darc import DarcContainer
from plugins.base_game_rules import BaseGameRules
from utils.logging_utils import log_debug
from utils.utils import clean_spaces

from . import binpack, pool, tams
from .config import DEFAULT_LINES_PER_PAGE, PLUGIN_PREFIX, PROBLEM_DEFINITIONS
from .tag_manager import TagManager

# What a scenario file holds, by its name.
_ROLES = (("text_novel_", "Story chapter (narration and dialogue)"),
          ("kaeruB_", "Story chapter (narration and dialogue)"),
          ("text_int_npc", "Conversation with a non-player character"),
          ("text_int_pl", "Conversation between the girls"))


def _role(name: str) -> Optional[str]:
    for prefix, role in _ROLES:
        if name.startswith(prefix):
            return role
    return None


class GameRules(BaseGameRules):
    """Senran Kagura Burst (Nintendo 3DS, European English)."""

    problem_prefix = PLUGIN_PREFIX
    problem_definitions = PROBLEM_DEFINITIONS
    tag_manager_class = TagManager
    tag_style = "curly"
    analyze_whole_string_first = True
    show_spaces_as_dots_default = True

    def __init__(self, main_window_ref=None):
        super().__init__(main_window_ref)
        ContainerManager.register(binpack.PackContainer)   # ui/lyt_*.bin: the layouts' pictures (Tools -> Textures)
        ContainerManager.register(DarcContainer)
        self._save_source: Optional[bytes] = None
        self._last_loaded: Optional[bytes] = None
        self._located_cache: Dict[int, Tuple[Optional[str], Optional[bytes]]] = {}
        self._rooms: Dict[str, List[List[int]]] = {}

    def get_display_name(self) -> str:
        return "Senran Kagura Burst"

    def get_file_formats(self) -> list:
        from core.formats import DEFAULT_FORMATS, FileFormat
        return [FileFormat((".bin",), "bytes", "Senran Kagura Burst message file or executable"),
                *DEFAULT_FORMATS]

    def get_capabilities(self) -> Set[str]:
        return set()

    # -- load and save ---------------------------------------------------------

    def load_data_from_json_obj(self, json_obj: Any) -> Tuple[List[List[str]], Dict[str, str]]:
        if not isinstance(json_obj, (bytes, bytearray)):
            return super().load_data_from_json_obj(json_obj)
        raw = bytes(json_obj)
        self._last_loaded = raw
        try:
            if tams.is_tams(raw):
                return [[tams.to_editor(t) for t in tams.Tams(raw).messages]], {}
            blocks = pool.Pool(raw).texts()
        except (tams.FormatError, pool.PoolError) as error:
            log_debug(f"senran_kagura_burst: unknown file ({error})")
            return [[]], {}
        return blocks, {str(i): f"Text {i + 1}" for i in range(len(blocks))}

    def prepare_save_context(self, context) -> None:
        versions = list(context.existing_versions())
        self._save_source = versions[-1] if versions else None

    def save_data_to_json_obj(self, data: list, block_names: dict) -> Any:
        source = self._save_source if self._save_source is not None else self._last_loaded
        if source is None:
            return super().save_data_to_json_obj(data, block_names)
        if tams.is_tams(source):
            texts = [tams.from_editor(str(s)) for s in (data[0] if data else [])]
            return tams.Tams(source).build(texts)
        return pool.Pool(source).rebuild([[str(s) for s in block] for block in data])

    def reset_runtime_state(self) -> None:
        self._save_source = self._last_loaded = None
        self._located_cache.clear()
        self._rooms.clear()

    # -- where a string comes from -----------------------------------------------

    def _located(self, block_idx: int) -> Tuple[Optional[str], Optional[bytes]]:
        if block_idx in self._located_cache:
            return self._located_cache[block_idx]
        found: Tuple[Optional[str], Optional[bytes]] = (None, None)
        try:
            pm = self.mw.project_manager
            block_map = getattr(self.mw, "block_to_project_file_map", None) or {}
            block = pm.project.blocks[block_map.get(block_idx, block_idx)]
            found = (str(block.source_file).replace("\\", "/"), None)
        except (AttributeError, IndexError, KeyError, OSError, TypeError, ValueError) as error:
            log_debug(f"senran_kagura_burst: no file behind block {block_idx}: {error}")
        self._located_cache[block_idx] = found
        return found

    def get_translation_context_for_string(self, block_idx: int, string_idx: int) -> Dict[str, Any]:
        path, _raw = self._located(block_idx)
        if not path:
            return {}
        if path.endswith("code.bin"):
            return {"content_role": "Menu, mission, item and battle text", "has_speaker": False}
        role = _role(Path(path).name)
        return {"content_role": role, "has_speaker": False} if role else {}

    def _capacities(self, path: str) -> List[List[int]]:
        if path not in self._rooms:
            rooms: List[List[int]] = []
            try:
                source = Path(self.mw.project_manager.get_absolute_path(path)).read_bytes()
                rooms = pool.Pool(source).capacities()
            except (AttributeError, OSError, TypeError, ValueError) as error:
                log_debug(f"senran_kagura_burst: no string rooms for {path}: {error}")
            self._rooms[path] = rooms
        return self._rooms[path]

    def get_message_attributes(self, block_idx: int, string_idx: int) -> Optional[Dict[str, Any]]:
        path, _raw = self._located(block_idx)
        if not path or not path.endswith("code.bin"):
            return None
        try:
            room = self._capacities(path)[_position_in_file(self, block_idx)][int(string_idx)]
        except (IndexError, TypeError, ValueError):
            return None
        return {"file": path, "max_characters": room}

    # -- editor ----------------------------------------------------------------

    def process_pasted_segment(self, segment_to_insert: str, original_text_for_tags: str,
                               editor_player_tag_const: str) -> Tuple[str, str, str]:
        return clean_spaces(segment_to_insert), "OK", ""

    def get_editor_page_size(self) -> int:
        return DEFAULT_LINES_PER_PAGE


def _position_in_file(rules: "GameRules", block_idx: int) -> int:
    """The position of a block among the blocks of its file (the executable's blocks follow each other)."""
    try:
        pm = rules.mw.project_manager
        block_map = getattr(rules.mw, "block_to_project_file_map", None) or {}
        index = block_map.get(block_idx, block_idx)
        source = pm.project.blocks[index].source_file
        position = 0
        while index - position - 1 >= 0 and pm.project.blocks[index - position - 1].source_file == source:
            position += 1
        return position
    except (AttributeError, IndexError, KeyError, TypeError):
        return 0
