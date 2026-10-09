"""Fragile Dreams: Farewell Ruins of the Moon (Wii, Europe R2GP99) plugin.

The project's source folder is ``source`` of the workspace, which its ``1_unpack.bat`` fills from the disc's
compressed ``FILE_<id>`` files: ``text/60001061.msg`` (every dialogue, subtitle, item description and memory),
``text/40003100/1/*.msg`` (title and boot messages), ``text/60001083/0.msg`` (Wii system messages, save file
title), ``text/600010AF/0.msg`` (end credits) -- message blocks (``fdtext``), one project block per message
block --, ``sys/main.dol`` (its own English blocks: the save check at start, Wii Remote and disc messages,
written in place) and ``hbm/10000081.csv`` (Wii HOME Menu). Fonts are the game's FONT files (format ``fragile_dreams``),
textures the TPL files under ``ui``. ``2_build.bat`` packs, compresses and writes everything back into the disc.
"""
from typing import Any, Dict, List, Optional, Set, Tuple

from plugins.base_game_rules import BaseGameRules
from plugins.common.tag_manager import GenericTagManager
from plugins.common.wii_home_menu import HomeCsv, is_home_csv
from utils.logging_utils import log_warning

from . import fdtext
from .config import DEFAULT_LINES_PER_PAGE, PLUGIN_PREFIX, PROBLEM_DEFINITIONS

_TAG_HELP = {"w": "wait (for a button, or milliseconds)", "v": "voice", "p": "new page", "c": "colour",
             "s": "speed", "k": "key prompt", "e": "emphasis", "[": "filled in by the game"}


class TagManager(GenericTagManager):
    """The game's control codes (``<w>``, ``<v1>``, ``<c#404040ff>``) and placeholders (``[Value]``)."""

    def get_legitimate_tags(self) -> Set[str]:
        return {fdtext.TAG_RE.pattern}

    def is_tag_legitimate(self, tag_to_check: str) -> bool:
        return isinstance(tag_to_check, str) and fdtext.TAG_RE.fullmatch(tag_to_check) is not None


class GameRules(BaseGameRules):
    """Fragile Dreams: Farewell Ruins of the Moon (Wii, Europe)."""

    problem_prefix = PLUGIN_PREFIX
    problem_definitions = PROBLEM_DEFINITIONS
    tag_manager_class = TagManager

    def __init__(self, main_window_ref=None):
        super().__init__(main_window_ref)
        self._home: Optional[HomeCsv] = None
        self._loaded: Optional[bytes] = None
        self._base: Optional[bytes] = None

    def get_display_name(self) -> str:
        return "Fragile Dreams: Farewell Ruins of the Moon"

    def get_file_formats(self) -> list:
        from core.formats import FileFormat
        return [FileFormat((".msg", ".dol"), "bytes", "Fragile Dreams messages"),
                FileFormat((".csv",), "bytes", "Wii HOME Menu messages")]

    # -- load and save ---------------------------------------------------------

    def load_data_from_json_obj(self, json_obj: Any) -> Tuple[List[List[str]], Dict[str, str]]:
        self._home = None
        if not isinstance(json_obj, (bytes, bytearray)):
            return super().load_data_from_json_obj(json_obj)
        raw = bytes(json_obj)
        if is_home_csv(raw):
            self._home = HomeCsv(raw)
            return [self._home.messages], {"0": "HOME Menu"}
        if fdtext.is_dol(raw):
            self._loaded = raw
            found = [block for _at, _room, block in fdtext.dol_blocks(raw)]
            names = dict(zip(("0", "1", "2"), ("Save and Wii Remote messages (main.dol)", "Copyright line (main.dol)",
                                               "Disc errors (main.dol)")))
            return ([[fdtext.to_editor(t) for t in block.texts] for block in found] or [[]],
                    {str(i): names.get(str(i), f"main.dol block {i + 1}") for i in range(len(found))})
        if not fdtext.is_msg(raw):
            return [[]], {}
        self._loaded = raw
        msg = fdtext.parse(raw)
        blocks = [[fdtext.to_editor(t) for t in block.texts] for block in msg.blocks]
        names = {str(i): f"Block {i + 1} ({len(b.texts)})" for i, b in enumerate(msg.blocks)}
        return blocks or [[]], names

    def prepare_save_context(self, context) -> None:
        """The file is written over its newest existing version (the translation, else the source)."""
        self._home, self._base = None, None
        for raw in context.existing_versions():
            if is_home_csv(raw):
                self._home = HomeCsv(raw)
            elif fdtext.is_msg(raw) or fdtext.is_dol(raw):
                self._base = raw
            return

    def save_data_to_json_obj(self, data: list, block_names: dict) -> Any:
        if self._home is not None:
            texts = data[0] if data and isinstance(data[0], list) else []
            old = self._home.messages
            return self._home.build([str(texts[i]) if i < len(texts) and texts[i] is not None else old[i]
                                     for i in range(len(old))])
        base = self._base if self._base is not None else self._loaded
        if base is None:
            return super().save_data_to_json_obj(data, block_names)
        dol = fdtext.is_dol(base)
        msg = fdtext.MsgFile([b for _at, _room, b in fdtext.dol_blocks(base)]) if dol else fdtext.parse(base)
        missing: Set[str] = set()
        new: Dict[int, List[bytes]] = {}
        for index, (block, texts) in enumerate(zip(msg.blocks, data or [])):
            row = [fdtext.from_editor(str(texts[i]), missing) if i < len(texts) and texts[i] is not None else old
                   for i, old in enumerate(block.texts)]
            if row != block.texts:
                new[index] = row
        if missing:
            log_warning("fragile_dreams: characters cp1251 has no byte for were written as '?': "
                        + "".join(sorted(missing)))
        return fdtext.build_dol(base, new) if dol else fdtext.build(msg, new)

    def reset_runtime_state(self) -> None:
        self._home, self._loaded, self._base = None, None, None

    # -- editor ----------------------------------------------------------------

    def get_spellcheck_ignore_pattern(self) -> str:
        return fdtext.TAG_RE.pattern

    def get_tag_tooltip(self, tag: str) -> str:
        if not fdtext.TAG_RE.fullmatch(str(tag)):
            return ""
        key = "[" if str(tag).startswith("[") else str(tag)[1:2]
        return f"Game control code: {_TAG_HELP.get(key, 'code')}"

    def get_editor_page_size(self) -> int:
        return DEFAULT_LINES_PER_PAGE
