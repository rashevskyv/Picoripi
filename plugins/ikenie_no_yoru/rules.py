"""Ikenie no Yoru (Wii, Japan SEKJ99) with the English fan translation "Night of the Sacrifice".

The workspace's ``1_unpack.bat`` writes the English patch into the Japanese disc and fills the project's source
folder: every message table of the game (``package/<package>/<id>.mes``, ``mes``), the 2D layouts with their
text boxes (``*.brlyt``, ``brlyt``), the strings of ``sys/main.dol`` (``dol``) and the Wii HOME Menu messages
(``hbm/HomeButton*/*.csv``; the Japanese game shows their Japanese column, which the patch left as it was).
Lines the patch left Japanese are shown too: the project marks them with the category "Japanese source".
Fonts (BRFNT) and layout textures (TPL) open in the Font Editor and the Textures window; ``2_build.bat`` packs
the translation back into the disc.
"""
import re
from typing import Any, Dict, List, Optional, Set, Tuple

from plugins.base_game_rules import BaseGameRules
from plugins.common.tag_manager import GenericTagManager
from plugins.common.wii_home_menu import JAPANESE, HomeCsv, is_home_csv

from . import brlyt, dol, mes
from .config import DEFAULT_LINES_PER_PAGE, PLUGIN_PREFIX, PROBLEM_DEFINITIONS

TAG_RE = re.compile(rf"{mes.TAG_RE.pattern}|\{{CR\}}")


class TagManager(GenericTagManager):
    """The game's control codes: ``{PAGE}``, ``{NAME:1}``, ``{SIZE:3F800000}``, ``{COLOR:FF0000FF}``, ``{U0008}``."""

    def get_legitimate_tags(self) -> Set[str]:
        return {TAG_RE.pattern}

    def is_tag_legitimate(self, tag_to_check: str) -> bool:
        return isinstance(tag_to_check, str) and TAG_RE.fullmatch(tag_to_check) is not None


def kind_of(raw: bytes) -> Optional[str]:
    if is_home_csv(raw):
        return "csv"
    if mes.is_mes(raw):
        return "mes"
    if brlyt.is_brlyt(raw):
        return "brlyt"
    if dol.is_main_dol(raw):
        return "dol"
    return None


def texts_of(raw: bytes) -> List[str]:
    """The editor lines of a game file (empty when the plugin does not know the file)."""
    kind = kind_of(raw)
    if kind == "csv":
        return HomeCsv(raw, JAPANESE).messages
    if kind == "mes":
        return [mes.to_editor(m) for m in mes.units(raw)]
    if kind == "brlyt":
        return [text for _pane, text in brlyt.boxes(raw)]
    if kind == "dol":
        return dol.strings(raw)
    return []


def build(base: bytes, texts: List[str]) -> bytes:
    """``base`` with the editor lines ``texts``; unchanged lines give ``base`` back."""
    old = texts_of(base)
    texts = [old[i] if i >= len(texts) or texts[i] is None else str(texts[i]) for i in range(len(old))]
    if texts == old:
        return base
    kind = kind_of(base)
    if kind == "csv":
        return HomeCsv(base, JAPANESE).build(texts)
    if kind == "mes":
        return mes.build([mes.from_editor(t) for t in texts], mes.first_number(base))
    if kind == "brlyt":
        return brlyt.build(base, texts)
    return dol.build(base, texts)


class GameRules(BaseGameRules):
    """Ikenie no Yoru (Wii, Japan) + English patch."""

    problem_prefix = PLUGIN_PREFIX
    problem_definitions = PROBLEM_DEFINITIONS
    tag_manager_class = TagManager
    tag_style = "curly"

    def __init__(self, main_window_ref=None):
        super().__init__(main_window_ref)
        self._loaded: Optional[bytes] = None        # the last game file loaded
        self._base: Optional[bytes] = None          # the game file a save writes over

    def get_display_name(self) -> str:
        return "Ikenie no Yoru"

    def get_file_formats(self) -> list:
        from core.formats import FileFormat
        return [FileFormat((".mes",), "bytes", "Ikenie no Yoru message tables"),
                FileFormat((".brlyt",), "bytes", "Wii layout text boxes"),
                FileFormat((".dol",), "bytes", "Ikenie no Yoru main.dol strings"),
                FileFormat((".csv",), "bytes", "Wii HOME Menu messages")]

    def load_data_from_json_obj(self, json_obj: Any) -> Tuple[List[List[str]], Dict[str, str]]:
        if not isinstance(json_obj, (bytes, bytearray)):
            return super().load_data_from_json_obj(json_obj)
        raw = bytes(json_obj)
        if kind_of(raw) is None:
            return [[]], {}
        self._loaded = raw
        return [texts_of(raw)], {}

    def prepare_save_context(self, context) -> None:
        """The file is written over its newest existing version (the translation, else the source)."""
        self._base = next((raw for raw in context.existing_versions() if kind_of(raw)), None)

    def save_data_to_json_obj(self, data: list, block_names: dict) -> Any:
        base = self._base if self._base is not None else self._loaded
        if base is None:
            return super().save_data_to_json_obj(data, block_names)
        return build(base, [text for block in data for text in block])

    def reset_runtime_state(self) -> None:
        self._loaded, self._base = None, None

    def get_editor_page_size(self) -> int:
        return DEFAULT_LINES_PER_PAGE
