r"""Policenauts (PlayStation, SLPS-00215/00216 with the English fan patch; PSP EBOOT release) plugin.

The project's source folder is the ``source`` folder the workspace's unpack step fills
(``E:\Emulators\RomHacking\Policenauts``): ``PN_VOX1.PNV`` and ``PN_VOX2.PNV`` (the dialogue of discs
1 and 2: the subtitle text the English patch keeps in each voice chunk), ``FONT/*`` and
``SHOTPAC/KANJIFNT.*`` (fonts, Tools -> Font Editor) and ``PAK/*`` (pictures, Tools -> Textures).
Saving writes the same files into the translation folder; the build step puts them back into the
EBOOT.PBP of each disc.
"""
from typing import Any, Dict, List, Optional, Set, Tuple

from plugins.base_game_rules import BaseGameRules
from utils.logging_utils import log_debug, log_warning
from utils.utils import clean_spaces

from . import doc, voice
from .config import DEFAULT_LINES_PER_PAGE, PLUGIN_PREFIX, PROBLEM_DEFINITIONS
from .tag_manager import TagManager

TAG_TIPS = {
    "{dash}": "A long dash (the two-byte glyph D0 06).",
    "{x80}": "Byte 0x80: in \"CO{x80}#2\" it draws the small 2 of CO2.",
}


class GameRules(BaseGameRules):
    """Policenauts (PlayStation, English fan patch)."""

    problem_prefix = PLUGIN_PREFIX
    problem_definitions = PROBLEM_DEFINITIONS
    tag_manager_class = TagManager
    tag_style = "curly"
    show_spaces_as_dots_default = True

    def __init__(self, main_window_ref=None):
        super().__init__(main_window_ref)
        self._last_loaded: Optional[bytes] = None
        self._save_source: Optional[bytes] = None
        self._save_name = ""

    def get_display_name(self) -> str:
        return "Policenauts"

    def get_file_formats(self) -> list:
        from core.formats import DEFAULT_FORMATS, FileFormat
        return [FileFormat((".pnv",), "bytes", "Policenauts dialogue"), *DEFAULT_FORMATS]

    # -- load and save ---------------------------------------------------------

    def load_data_from_json_obj(self, json_obj: Any) -> Tuple[List[List[str]], Dict[str, str]]:
        if not isinstance(json_obj, (bytes, bytearray)):
            return super().load_data_from_json_obj(json_obj)
        data = bytes(json_obj)
        self._last_loaded = data
        try:
            blocks, names = doc.read(data)
        except (voice.VoiceError, ValueError, IndexError) as error:
            log_debug(f"policenauts: not a Policenauts dialogue file ({error})")
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
        out = doc.write(source, data or [], missing)
        if missing:
            log_warning(f"policenauts: {self._save_name or 'file'}: characters the game cannot write were saved "
                        f"as '?': {''.join(sorted(missing))}")
        return out

    # -- editor ----------------------------------------------------------------

    def get_editor_page_size(self) -> int:
        return DEFAULT_LINES_PER_PAGE

    def get_tag_tooltip(self, tag: str) -> str:
        return TAG_TIPS.get(tag, "A byte of the game's text kept as it is.")

    def process_pasted_segment(self, segment_to_insert: str, original_text_for_tags: str,
                               editor_player_tag_const: str) -> Tuple[str, str, str]:
        return clean_spaces(segment_to_insert), "OK", ""
