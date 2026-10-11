"""Metal Gear Solid Master Collection Bonus Content (Vol.1 and Vol.2, Switch) plugin.

``1_unpack.bat`` (``_shared/scripts/zt/mgbonus.py``) writes each app's PSB files to ``source/vol1`` and
``source/vol2``. A text file (PSB version 2 or 3) shows its English strings, one line each; saving writes the
file back with the same bytes wherever nothing changed (``plugins.metal_gear_solid_mc.psb_text``). Font and
picture pages (PSB version 4) open in the font and texture editors and show no text here.
"""
from __future__ import annotations

from typing import Any, List, Optional, Tuple

from core import m2_psb
from plugins.base_game_rules import BaseGameRules
from plugins.metal_gear_solid_mc import psb_text
from utils.logging_utils import log_debug


def _version(data: bytes) -> int:
    return m2_psb.load(bytes(data))[1].version


class GameRules(BaseGameRules):
    """Metal Gear Solid Master Collection Bonus Content: the M2 text files of the two bonus apps."""

    def __init__(self, main_window_ref=None):
        super().__init__(main_window_ref)
        self._last_loaded: Optional[bytes] = None

    def get_display_name(self) -> str:
        return "Metal Gear Solid Master Collection Bonus Content"

    def get_file_formats(self) -> list:
        from core.formats import DEFAULT_FORMATS, FileFormat
        return [FileFormat((".psb",), "bytes", "M2 PSB data"), *DEFAULT_FORMATS]

    def load_data_from_json_obj(self, json_obj: Any) -> Tuple[List[List[str]], dict]:
        if isinstance(json_obj, (bytes, bytearray)) and psb_text.is_psb(json_obj):
            data = bytes(json_obj)
            self._last_loaded = data
            try:
                if _version(data) not in (2, 3):
                    return [[]], {}              # a font or picture page: no text here
                lines = psb_text.lines(data, words=True)
            except (ValueError, IndexError, KeyError, UnicodeDecodeError) as error:
                log_debug(f"metal_gear_mc_bonus: not an M2 text file ({error})")
                return [[]], {}
            return [[text for _path, text in lines]], {"0": "M2 text"}
        return super().load_data_from_json_obj(json_obj)

    def save_data_to_json_obj(self, data: list, block_names: dict) -> Any:
        source = self._last_loaded
        if source is not None and psb_text.is_psb(source) and _version(source) in (2, 3):
            return psb_text.build(source, (data or [[]])[0] if data else [], words=True)
        return super().save_data_to_json_obj(data, block_names)
