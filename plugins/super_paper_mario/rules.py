"""Super Paper Mario (Wii, PAL R8PP01) plugin: the English (UK) message files ``msg/UK/*.txt`` and the Wii HOME
Menu messages.

The message files have the Thousand-Year Door format (``paper_mario_gc.msgfile``, one more zero byte at the
end), so the rules are the Thousand-Year Door ones with this game's areas and ``global.txt`` groups. The project's
source folder is the workspace's ``source`` (``1_unpack.bat``: text, fonts and text textures, each archive as a
folder); ``2_build.bat`` packs the translation back into the disc. Ukrainian letters are written as the font slots
of ``translation_map.json`` (the Thousand-Year Door rule: look-alike letters share the Latin glyph, the others take
Latin-1 slots no English message uses).
"""
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple

from plugins.common.wii_home_menu import HomeCsv, is_home_csv
from plugins.paper_mario_gc.rules import GameRules as ThousandYearDoorRules

from .config import DEFAULT_LINES_PER_PAGE, PLUGIN_PREFIX, PROBLEM_DEFINITIONS

# file name -> (place, chapter); the names are the game's own (global.txt place_*)
AREAS = {
    "global": ("Menus, items, enemies", "Global"), "machi": ("Flipside and Flopside", "Town"),
    "stg1": ("Lineland", "Chapter 1"), "stg2": ("Gloam Valley", "Chapter 2"), "stg3": ("The Bitlands", "Chapter 3"),
    "stg4": ("Outer Space", "Chapter 4"), "stg5": ("Land of the Cragnons", "Chapter 5"),
    "stg6": ("Sammer's Kingdom", "Chapter 6"), "stg7": ("The Underwhere", "Chapter 7"),
    "stg8": ("Castle Bleck", "Chapter 8"),
}
# global.txt: key prefix -> (block name, window kind of paper_mario_gc.rules.LAYOUTS); the first match wins
GLOBAL_GROUPS = (
    ("place_", "Places", "name"), ("sub_title_", "Chapter titles", "name"),
    ("in_", "Item names", "item_name"), ("ename_", "Enemy names", "enemy_name"),
    ("ehelp_", "Catch Cards", "description"), ("anna_", "Tippi's tattles", "talk"),
    ("msg_", "Descriptions", "description"), ("menu_", "Menus", "menu"),
    ("", "Other", "global_other"),
)


class GameRules(ThousandYearDoorRules):
    """Super Paper Mario (Wii, PAL R8PP01, English UK)."""

    problem_prefix = PLUGIN_PREFIX
    problem_definitions = PROBLEM_DEFINITIONS
    plugin_dir = Path(__file__).resolve().parent
    areas = AREAS
    global_groups = GLOBAL_GROUPS
    global_markers = ("ename_", "ehelp_")

    def __init__(self, main_window_ref=None):
        super().__init__(main_window_ref)
        self._home: Optional[HomeCsv] = None        # the file loaded or about to be saved, when it is home.csv

    def get_display_name(self) -> str:
        return "Super Paper Mario"

    def get_file_formats(self) -> list:
        from core.formats import FileFormat
        return [FileFormat((".txt",), "bytes", "Super Paper Mario messages"),
                FileFormat((".csv",), "bytes", "Wii HOME Menu messages")]

    def load_data_from_json_obj(self, json_obj: Any) -> Tuple[List[List[str]], Dict[str, str]]:
        self._home = None
        if isinstance(json_obj, (bytes, bytearray)) and is_home_csv(json_obj):
            self._home = HomeCsv(bytes(json_obj))
            return [self._home.messages], {}
        return super().load_data_from_json_obj(json_obj)

    def prepare_save_context(self, context) -> None:
        """home.csv keeps every language but English from the file it is saved over."""
        self._home = None
        if str(getattr(context, "relative_path", "")).lower().endswith(".csv"):
            self._home = next((HomeCsv(raw) for raw in context.existing_versions() if is_home_csv(raw)), None)
            return
        super().prepare_save_context(context)

    def save_data_to_json_obj(self, data: list, block_names: dict) -> Any:
        if self._home is None:
            return super().save_data_to_json_obj(data, block_names)
        texts = data[0] if data and isinstance(data[0], list) else []
        old = self._home.messages
        return self._home.build([str(texts[i]) if i < len(texts) and texts[i] is not None else old[i]
                                 for i in range(len(old))])

    def reset_runtime_state(self) -> None:
        super().reset_runtime_state()
        self._home = None

    def get_speaker_for_string(self, block_idx: int, string_idx: int) -> Optional[str]:
        return None             # no speaker data yet (the Thousand-Year Door one names its own cast)

    def get_capabilities(self) -> Set[str]:
        return set()

    def get_editor_page_size(self) -> int:
        return DEFAULT_LINES_PER_PAGE
