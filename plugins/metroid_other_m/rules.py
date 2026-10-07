"""Metroid: Other M (Wii, USA R3OE01) plugin: ``message/message_all.dat`` and the Wii HOME Menu messages.

``message_all.dat`` holds every message of the game in eight languages (``msgdat``): menus, chapter summaries,
system messages, area names, tutorials, item and personnel files, and the subtitles of every in-game voice and
cutscene. The project shows the US English table, in groups by message number; saving writes it back and keeps
the other seven tables. The workspace's ``1_unpack.bat`` fills the project's source folder (text, the BRFNT fonts
and the layout textures, each archive as a folder); ``2_build.bat`` packs the translation back into the disc.
"""
from typing import Any, Dict, List, Optional, Set, Tuple

from plugins.base_game_rules import BaseGameRules
from plugins.common.tag_manager import GenericTagManager
from plugins.common.wii_home_menu import HomeCsv, is_home_csv

from . import msgdat
from .config import DEFAULT_LINES_PER_PAGE, PLUGIN_PREFIX, PROBLEM_DEFINITIONS

# first message number -> group name (the English table, 1899 messages)
GROUPS = (
    (0, "Title, save and menu messages"), (30, "Story so far (chapter summaries)"),
    (164, "Prompts and system messages"), (209, "Items found and area names"),
    (259, "Tutorials and item help"), (405, "Item names and personnel files"),
    (506, "Voice and cutscene subtitles"),
)


class TagManager(GenericTagManager):
    """The game's control codes, shown as ``{COLOR_GREEN}``."""

    def get_legitimate_tags(self) -> Set[str]:
        return {msgdat.TAG_RE.pattern}

    def is_tag_legitimate(self, tag_to_check: str) -> bool:
        return isinstance(tag_to_check, str) and msgdat.TAG_RE.fullmatch(tag_to_check) is not None


class GameRules(BaseGameRules):
    """Metroid: Other M (Wii, USA)."""

    problem_prefix = PLUGIN_PREFIX
    problem_definitions = PROBLEM_DEFINITIONS
    tag_manager_class = TagManager
    tag_style = "curly"

    def __init__(self, main_window_ref=None):
        super().__init__(main_window_ref)
        self._home: Optional[HomeCsv] = None
        self._loaded: Optional[bytes] = None        # the last message_all.dat loaded
        self._base: Optional[bytes] = None          # the message_all.dat a save writes over

    def get_display_name(self) -> str:
        return "Metroid: Other M"

    def get_file_formats(self) -> list:
        from core.formats import FileFormat
        return [FileFormat((".dat",), "bytes", "Metroid: Other M messages"),
                FileFormat((".csv",), "bytes", "Wii HOME Menu messages")]

    def load_data_from_json_obj(self, json_obj: Any) -> Tuple[List[List[str]], Dict[str, str]]:
        self._home = None
        if not isinstance(json_obj, (bytes, bytearray)):
            return super().load_data_from_json_obj(json_obj)
        raw = bytes(json_obj)
        if is_home_csv(raw):
            self._home = HomeCsv(raw)
            return [self._home.messages], {"0": "HOME Menu"}
        if not msgdat.is_msgdat(raw):
            return [[]], {}
        self._loaded = raw
        texts = [msgdat.to_editor(t) for t in msgdat.messages(msgdat.tables(raw)[msgdat.ENGLISH])]
        bounds = [first for first, _name in GROUPS] + [len(texts)]
        blocks = [texts[a:b] for a, b in zip(bounds, bounds[1:])]
        return blocks, {str(i): name for i, (_first, name) in enumerate(GROUPS)}

    def prepare_save_context(self, context) -> None:
        """The file is written over its newest existing version (the translation, else the source)."""
        self._home, self._base = None, None
        for raw in context.existing_versions():
            if is_home_csv(raw):
                self._home = HomeCsv(raw)
                return
            if msgdat.is_msgdat(raw):
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
        tables = msgdat.tables(base)
        old = msgdat.messages(tables[msgdat.ENGLISH])
        new = [msgdat.from_editor(str(text)) for block in data for text in block]
        if len(new) != len(old):
            raise ValueError(f"message_all.dat has {len(old)} English messages, the project {len(new)}")
        tables[msgdat.ENGLISH] = msgdat.table(new)
        return msgdat.build(base, tables)

    def reset_runtime_state(self) -> None:
        self._home, self._loaded, self._base = None, None, None

    def get_editor_page_size(self) -> int:
        return DEFAULT_LINES_PER_PAGE
