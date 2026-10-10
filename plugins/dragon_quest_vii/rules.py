"""Dragon Quest VII: Fragments of the Forgotten Past (3DS, EUR) plugin: FPT0 text packs, menu lists, BCFNT, DMP.

The project's source folder is the workspace's ``source`` folder (``1_unpack.bat``): ``romfs/MESS/EN/*.fpt``
(every dialogue and event message of the English slot, one pack per area: a block = a pack, a string = a message
with its ``#window,speaker`` header kept aside), ``romfs/MENULIST/EN/*.txt`` (menus, item, spell, monster, class and
place names as CSV lines: a string = a line), the BCFNT fonts (loose and inside the ``LAYOUT/*.arc`` darc archives,
``font_sources.json``) and the UI pictures (``DMP`` textures in FPT0 packs, ``texture_sources.json``). Saving writes
the same files into the translation folder; ``2_build.bat`` compresses them again (LZ11 / LH) into the Luma mod.
"""
from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple

from core.containers import ContainerManager
from core.containers.darc import DarcContainer
from plugins.base_game_rules import BaseGameRules
from utils.logging_utils import log_debug
from utils.utils import clean_spaces

from . import fpt
from .config import DEFAULT_LINES_PER_PAGE, PLUGIN_PREFIX, PROBLEM_DEFINITIONS
from .tag_manager import TAG_RE, TagManager

CRLF = "\r\n"


def menu_lines(raw: bytes) -> Tuple[List[str], bool]:
    """``(lines, file ends with a line break)`` of a MENULIST csv."""
    text = raw.decode("utf-8")
    trailing = text.endswith(CRLF)
    lines = text[:-2].split(CRLF) if trailing else text.split(CRLF)
    return lines, trailing


def menu_build(raw: bytes, lines: List[str]) -> bytes:
    _old, trailing = menu_lines(raw)
    return (CRLF.join(lines) + (CRLF if trailing else "")).encode("utf-8")


class GameRules(BaseGameRules):
    """Dragon Quest VII: Fragments of the Forgotten Past (3DS, European English)."""

    problem_prefix = PLUGIN_PREFIX
    problem_definitions = PROBLEM_DEFINITIONS
    tag_manager_class = TagManager
    tag_style = "curly"
    analyze_whole_string_first = True
    show_spaces_as_dots_default = True

    def __init__(self, main_window_ref=None):
        super().__init__(main_window_ref)
        ContainerManager.register(DarcContainer)        # LAYOUT/*.arc: the game fonts (Font Editor)
        ContainerManager.register(fpt.FptContainer)     # texture packs (Tools -> Textures)
        self._save_source: Optional[bytes] = None
        self._last_loaded: Optional[bytes] = None
        self._located: Dict[int, Optional[List[fpt.Message]]] = {}

    def get_display_name(self) -> str:
        return "Dragon Quest VII (3DS)"

    def get_file_formats(self) -> list:
        from core.formats import DEFAULT_FORMATS, FileFormat
        return [FileFormat((".fpt",), "bytes", "FPT0 message pack"),
                FileFormat((".txt",), "bytes", "menu list (CSV)"), *DEFAULT_FORMATS]

    def get_capabilities(self) -> Set[str]:
        return {"speaker_attribution"}

    # -- load and save ---------------------------------------------------------

    @staticmethod
    def _parse(raw: bytes) -> List[str]:
        if raw[:4] == fpt.MAGIC:
            return fpt.texts(fpt.Pack(raw))
        return menu_lines(raw)[0]

    @staticmethod
    def _build(raw: bytes, texts: List[str]) -> bytes:
        if raw[:4] == fpt.MAGIC:
            return fpt.rebuild(fpt.Pack(raw), texts)
        return menu_build(raw, texts)

    def load_data_from_json_obj(self, json_obj: Any) -> Tuple[List[List[str]], Dict[str, str]]:
        if not isinstance(json_obj, (bytes, bytearray)):
            return super().load_data_from_json_obj(json_obj)
        self._last_loaded = bytes(json_obj)
        try:
            return [self._parse(self._last_loaded)], {}
        except (fpt.FormatError, ValueError) as error:
            log_debug(f"dragon_quest_vii: not a text file ({error})")
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

    def _messages(self, block_idx: int) -> Optional[List[fpt.Message]]:
        if block_idx in self._located:
            return self._located[block_idx]
        found = None
        try:
            pm = getattr(self.mw, "project_manager", None) if self.mw else None
            block_map = getattr(self.mw, "block_to_project_file_map", None) or {}
            block = pm.project.blocks[block_map.get(block_idx, block_idx)]
            raw = Path(pm.get_absolute_path(block.source_file)).read_bytes()
            if raw[:4] == fpt.MAGIC:
                found = fpt.messages(fpt.Pack(raw))
        except (AttributeError, IndexError, KeyError, OSError, TypeError, ValueError) as error:
            log_debug(f"dragon_quest_vii: no message pack behind block {block_idx}: {error}")
        self._located[block_idx] = found
        return found

    def _message(self, block_idx: int, string_idx: int) -> Optional[fpt.Message]:
        found = self._messages(block_idx)
        if not found or int(string_idx) >= len(found):
            return None
        return found[int(string_idx)]

    def get_message_attributes(self, block_idx: int, string_idx: int) -> Optional[Dict[str, Any]]:
        message = self._message(block_idx, string_idx)
        if message is None:
            return None
        name, header, _body, _nl = message
        window, _comma, speaker = header[1:].partition(",")
        return {"file": name, "window": window, "speaker": speaker}

    def get_speaker_for_string(self, block_idx: int, string_idx: int) -> Optional[str]:
        message = self._message(block_idx, string_idx)
        if message is None:
            return None
        speaker = message[1].partition(",")[2].strip()
        return speaker or None

    def get_ai_flow_group_for_string(self, block_idx: int, string_idx: int) -> Optional[str]:
        message = self._message(block_idx, string_idx)
        return message[0] if message else None

    # -- editor ----------------------------------------------------------------

    def get_spellcheck_ignore_pattern(self) -> str:
        return TAG_RE.pattern

    def process_pasted_segment(self, segment_to_insert: str, original_text_for_tags: str,
                               editor_player_tag_const: str) -> Tuple[str, str, str]:
        return clean_spaces(segment_to_insert), "OK", ""

    def get_editor_page_size(self) -> int:
        return DEFAULT_LINES_PER_PAGE

    def get_default_script_name(self) -> Optional[str]:
        return "dragon_quest_vii_script.md"
