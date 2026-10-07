"""Lunar: Silver Star Story Complete (PlayStation, USA) plugin: event scripts, name and menu tables, font.

The project's source folder is the ``source`` folder the workspace's unpack step fills
(``E:\\Emulators\\RomHacking\\Lunar\\Silver Star Story``): ``LUNADATA/TEXTnnn.DAT`` (event scripts),
``LUNADATA/SYSTEM.DAT/00_0001.bin`` (items, spells, monsters, places, menus), the unpacked program
``SLUS_006.28`` (the font, Tools -> Font Editor) and the TIM pictures (Tools -> Textures). Saving
writes the same files into the translation folder; the build step puts them back on both discs.
"""
from typing import Any, Dict, List, Optional, Set, Tuple

from plugins.base_game_rules import BaseGameRules
from utils.logging_utils import log_debug, log_warning
from utils.utils import clean_spaces

from . import doc
from .config import DEFAULT_LINES_PER_PAGE, PLUGIN_PREFIX, PROBLEM_DEFINITIONS
from .tag_manager import TagManager

TAG_TIPS = {
    "{wait}": "Wait for a button, then go on on the same page.",
    "{page}": "Wait for a button, then start a new page.",
    "{clear}": "Start a new page without waiting.",
    "{close}": "Close the window.",
    "{end}": "The message ends without waiting for a button.",
}
FAMILY_TIPS = {
    "FA": "Speaker portrait and name (the number picks the character; 00 removes it).",
    "FB": "Second speaker (the right side of the window).",
    "FC": "Text colour (00 = normal).",
    "F8": "Pause, in frames.",
    "F9": "Move the pen right by this many pixels.",
}


class GameRules(BaseGameRules):
    """Lunar: Silver Star Story Complete (PlayStation, USA, SLUS-00628 / SLUS-00899)."""

    problem_prefix = PLUGIN_PREFIX
    problem_definitions = PROBLEM_DEFINITIONS
    tag_manager_class = TagManager
    tag_style = "curly"
    show_spaces_as_dots_default = True
    display_name = "Lunar: Silver Star Story Complete"
    text_doc = doc                  # read/write of one text file; lunar_ebc (Lunar 2) swaps in its own

    def __init__(self, main_window_ref=None):
        super().__init__(main_window_ref)
        self._last_loaded: Optional[bytes] = None
        self._save_source: Optional[bytes] = None
        self._save_name = ""

    def get_display_name(self) -> str:
        return self.display_name

    def get_file_formats(self) -> list:
        from core.formats import DEFAULT_FORMATS, FileFormat
        return [FileFormat((".dat", ".bin"), "bytes", "Lunar text data"), *DEFAULT_FORMATS]

    # -- load and save ---------------------------------------------------------

    def load_data_from_json_obj(self, json_obj: Any) -> Tuple[List[List[str]], Dict[str, str]]:
        if not isinstance(json_obj, (bytes, bytearray)):
            return super().load_data_from_json_obj(json_obj)
        data = bytes(json_obj)
        self._last_loaded = data
        try:
            blocks, names = self.text_doc.read(data)
        except (ValueError, IndexError) as error:       # the script errors are ValueErrors
            log_debug(f"{self.problem_prefix}: not a Lunar text file ({error})")
            return [[]], {}
        return (blocks or [[]]), names

    def prepare_save_context(self, context) -> None:
        """Every save is built from the source file (the last version offered)."""
        versions = list(context.existing_versions())
        self._save_source = versions[-1] if versions else None
        self._save_name = str(getattr(context, "relative_path", "") or "")

    def save_data_to_json_obj(self, data: list, block_names: dict) -> Any:
        source = self._save_source if self._save_source is not None else self._last_loaded
        if source is None:
            return super().save_data_to_json_obj(data, block_names)
        missing: Set[str] = set()
        out = self.text_doc.write(source, data or [], missing)
        if missing:
            log_warning(f"{self.problem_prefix}: {self._save_name or 'file'}: characters the game cannot write were saved "
                        f"as '?': {''.join(sorted(missing))}")
        return out

    # -- editor ----------------------------------------------------------------

    def get_editor_page_size(self) -> int:
        return DEFAULT_LINES_PER_PAGE

    def get_tag_tooltip(self, tag: str) -> str:
        if tag in TAG_TIPS:
            return TAG_TIPS[tag]
        if tag.startswith("{raw:"):
            return "A one-byte glyph of the game's table (kept as it is)."
        return FAMILY_TIPS.get(tag[1:3], "A two-byte control code of the game (kept as it is).")

    def process_pasted_segment(self, segment_to_insert: str, original_text_for_tags: str,
                               editor_player_tag_const: str) -> Tuple[str, str, str]:
        return clean_spaces(segment_to_insert), "OK", ""
