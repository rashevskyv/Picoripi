"""Hades (Switch): the English SJSON text and subtitles, one block per file; a translation builds a LayeredFS mod.

A block is one file: an SJSON file (its ``DisplayName`` and ``Description`` strings are the rows) or a subtitle CSV (the
``Line`` column is the row). Saving writes only the rows that changed, into the file's own bytes (``text``). The
English text that the game keeps in Lua scripts (NPC, enemy, room and codex data) is not a block: it is not in
``Content/Game/Text/en``. The Ukrainian reference files (``pl``) stay in the source folder for a reference column.

Not done yet: the reference column, the English Lua text, and the fonts' Cyrillic glyphs (a person draws them).
"""
from typing import Any, Dict, List, Optional, Tuple

from core.i18n import tr
from plugins.base_game_rules import BaseGameRules
from plugins.hades import build, text, unpack
from utils.logging_utils import log_warning

_PLUGIN = "hades"
EN_SJSON = "Content/Game/Text/en/"
EN_CSV = "Content/Subtitles/en/"
LANGUAGES = "Content/Game/Text/Languages.sjson"


class GameRules(BaseGameRules):
    """Hades, Switch base game (English text and subtitles)."""

    def __init__(self, main_window_ref=None):
        super().__init__(main_window_ref)
        self._role = "source"
        self._last_loaded: Optional[bytes] = None
        self._last_kind = ""

    def get_display_name(self) -> str:
        return "Hades (Switch)"

    def get_source_roles(self) -> List[Dict[str, str]]:
        return [{"id": "base", "label": tr("Base game")}, {"id": "update", "label": tr("Update")}]

    def identify_source(self, path: str) -> Optional[Dict[str, Any]]:
        """The Hades Switch base game (0100535012974000) or its update (0100535012974800)."""
        return unpack.identify(path)

    def unpack_sources(self, sources: Dict[str, str], target_dir: str, progress, is_cancelled) -> Optional[str]:
        """The English text, subtitles and fonts (``unpack.py``)."""
        return unpack.unpack(sources, target_dir, progress, is_cancelled)

    def unpack_key_consoles(self) -> List[str]:
        return ["switch"]

    def get_platforms(self) -> List[Dict[str, str]]:
        return [{"id": "switch", "label": tr("Nintendo Switch")}]

    def get_build_targets(self) -> List[Dict[str, Any]]:
        return [{"id": "switch_layeredfs", "label": tr("Switch: Atmosphere LayeredFS mod"),
                 "platforms": ["switch"], "kind": "layeredfs"}]

    def build_target(self, target_id: str, source_dir: str, translation_dir: str, output_dir: str,
                     progress, is_cancelled) -> str:
        if target_id != "switch_layeredfs":
            return super().build_target(target_id, source_dir, translation_dir, output_dir, progress, is_cancelled)
        return build.build_switch(source_dir, translation_dir, output_dir, progress, is_cancelled)

    def includes_source_file(self, rel_path: str) -> bool:
        """The English SJSON files, the language list and the English subtitles are translation blocks."""
        return (rel_path.startswith(EN_SJSON) and rel_path.endswith(".sjson")) \
            or rel_path == LANGUAGES or (rel_path.startswith(EN_CSV) and rel_path.endswith(".csv"))

    def get_file_formats(self) -> list:
        from core.formats import DEFAULT_FORMATS, FileFormat
        return [FileFormat((".sjson", ".csv"), "bytes", "Hades text and subtitles"), *DEFAULT_FORMATS]

    def set_load_role(self, role: str) -> None:
        self._role = role

    def load_data_from_json_obj(self, json_obj: Any) -> Tuple[List[List[str]], Dict[str, str]]:
        if not isinstance(json_obj, (bytes, bytearray)):
            return super().load_data_from_json_obj(json_obj)
        data = bytes(json_obj)
        self._last_loaded = data
        self._last_kind = "sjson" if data.lstrip(b"\xef\xbb\xbf \t\r\n")[:1] == b"{" else "csv"
        rows = text.read_csv(data) if self._last_kind == "csv" else text.read_sjson(data)
        return [rows], {"0": "text"}

    def save_data_to_json_obj(self, data: list, block_names: dict) -> Any:
        if self._last_loaded is None:
            return super().save_data_to_json_obj(data, block_names)
        rows = list((data[0] if data else []) or [])
        writer = text.write_csv if self._last_kind == "csv" else text.write_sjson
        new_bytes, warnings = writer(self._last_loaded, rows)
        for warning in warnings:
            log_warning(f"{_PLUGIN}: {warning}")
        return new_bytes
